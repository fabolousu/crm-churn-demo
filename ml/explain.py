"""SHAP explanations for the lead-win model, and the business wording for each feature.

Why this module exists separately from ``ml/train.py``: the API lane explains one lead at a
time, while training explains a batch. Both must produce the *same* numbers in the same
shape, and every string a human reads in the demo comes from this file so the wording is
reviewed in one place.

Contract for a driver (``api/openapi.yaml`` -> ``Driver``, and ``lead_scores.drivers_json``
in ``data/schema.sql``)::

    {"feature": "first_response_hours",
     "label": "First response time",
     "contribution": -0.4123,          # SHAP value, in log-odds (positive = helps win)
     "value": "11 hours to first response",
     "direction": "decreases"}         # "increases" | "decreases"

Determinism: TreeSHAP is a closed-form computation over a fixed booster and a fixed row, so
a lead's drivers are reproducible byte-for-byte across runs and machines. The only ordering
judgement is "top N by absolute contribution"; ties are broken by the contract feature order
so that the output never depends on dictionary or hash ordering.

``NULL`` is meaningful here (``docs/LABEL.md`` convention 5): a missing signal is rendered as
"not measured" wording -- "no response yet", "never surveyed" -- rather than as a zero. The
model itself sees the NaN, and LightGBM routes it down its own branch; the SHAP contribution
is therefore the value of the "missing" path, not the value of a zero.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sqlite3
import sys
import warnings
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
import shap
import joblib

__all__ = [
    "CATEGORICAL_FEATURES",
    "NUMERIC_FEATURES",
    "FEATURES",
    "FEATURE_LABELS",
    "business_label",
    "describe_value",
    "prepare_frame",
    "Explainer",
    "load_bundle",
    "explain",
    "top_drivers",
]

ML_DIR = pathlib.Path(__file__).resolve().parent
REPO_ROOT = ML_DIR.parent
DEFAULT_MODEL_PATH = ML_DIR / "artifacts" / "model.joblib"
DEFAULT_DB_PATH = REPO_ROOT / "data" / "demo.db"

# The feature contract, in ``docs/LABEL.md`` order. Categorical columns are declared to
# LightGBM as such; the split between the two lists is part of the stored model bundle, so a
# scoring frame is always cast back to exactly the dtypes the model was trained on.
CATEGORICAL_FEATURES: tuple[str, ...] = ("source", "stage_at_scoring", "region", "industry")
NUMERIC_FEATURES: tuple[str, ...] = (
    "age_days_at_scoring",
    "amount_arr",
    "discount_pct",
    "first_response_hours",
    "employees",
    "company_age_days",
    "prior_won_initiatives",
    "prior_lost_initiatives",
    "days_since_last_initiative",
    "lifetime_won_arr",
    "open_initiatives_count",
    "usage_trend_slope",
    "tickets_90d",
    "nps_last",
    "payment_delay_days_avg_180d",
    "meetings_before_scoring",
    "owner_win_rate_180d",
)
FEATURES: tuple[str, ...] = CATEGORICAL_FEATURES + NUMERIC_FEATURES

# Note what is absent: ``lead_id`` and ``snapshot_date`` identify a row, ``first_response_at``
# is the provenance of ``first_response_hours`` (not a predictor), and ``latent_p`` lives in
# ``lead_outcomes`` and is only ever used to *audit* the ceiling, never as an input.

# Short business names, used as ``Driver.label``. The rendered, value-carrying wording lives
# in ``describe_value`` -- that is ``Driver.value``.
FEATURE_LABELS: dict[str, str] = {
    "source": "Lead source",
    "stage_at_scoring": "Stage at scoring",
    "age_days_at_scoring": "Time in the pipeline",
    "amount_arr": "Proposed ARR",
    "discount_pct": "Discount offered",
    "first_response_hours": "First response time",
    "region": "Region",
    "industry": "Industry",
    "employees": "Company size",
    "company_age_days": "Company tenure",
    "prior_won_initiatives": "Initiatives won before",
    "prior_lost_initiatives": "Initiatives lost before",
    "days_since_last_initiative": "Gap since the last initiative",
    "lifetime_won_arr": "Revenue won to date",
    "open_initiatives_count": "Other open initiatives",
    "usage_trend_slope": "Usage trend",
    "tickets_90d": "Support tickets",
    "nps_last": "Latest NPS",
    "payment_delay_days_avg_180d": "Payment behaviour",
    "meetings_before_scoring": "Meetings held",
    "owner_win_rate_180d": "Rep win rate",
}

_REGION_LABELS = {
    "nord-ovest": "North-west",
    "nord-est": "North-east",
    "centro": "Centre",
    "sud": "South",
    "isole": "Islands",
}

_SOURCE_LABELS = {
    "inbound": "Inbound",
    "outbound": "Outbound",
    "referral": "Referral",
    "partner": "Partner",
    "event": "Event",
}

_STAGE_LABELS = {
    "new": "New, not yet contacted",
    "contacted": "Contacted",
    "qualified": "Qualified",
    "proposal": "Proposal submitted",
}

DIRECTION_UP = "increases"
DIRECTION_DOWN = "decreases"


# --------------------------------------------------------------------------------------
# wording
# --------------------------------------------------------------------------------------


def business_label(feature: str) -> str:
    """Short business name for a feature column, safe to show to an executive."""
    return FEATURE_LABELS.get(feature, feature.replace("_", " ").capitalize())


def _missing(value: Any) -> bool:
    """True for NULL/NaN/None, in one place so "not measured" wording stays consistent."""
    if value is None:
        return True
    if isinstance(value, (float, int, np.floating, np.integer)) and not isinstance(value, bool):
        return bool(np.isnan(value)) if isinstance(value, (float, np.floating)) else False
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):  # e.g. an array; not something this module produces
        return False


def _number(value: Any, decimals: int = 0) -> str:
    return f"{float(value):,.{decimals}f}"


def _compact(value: Any, decimals: int = 1) -> str:
    """Format with fixed decimals, then drop a trailing ``.0`` ("4.0 years" -> "4 years")."""
    text = _number(value, decimals)
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _plural(count: float, singular: str, plural: str | None = None) -> str:
    return singular if abs(float(count) - 1.0) < 1e-9 else (plural or singular + "s")


def _hours(value: Any) -> str:
    hours = float(value)
    if hours < 1.0:
        minutes = max(1, int(round(hours * 60.0)))
        return f"{minutes} {_plural(minutes, 'minute')} to first response"
    if hours < 24.0:
        return f"{_compact(hours)} hours to first response"
    return f"{_compact(hours / 24.0)} days to first response"


def describe_value(feature: str, value: Any) -> str:
    """Render one feature value as the sentence a human reads in the demo.

    ``NULL`` becomes "not measured" phrasing, never a zero: "no response yet", "never
    surveyed", "rep has no recent closures". ``0`` where zero is a real measurement keeps
    its own wording ("no support tickets in 90 days", "no discount").
    """
    missing = _missing(value)

    if feature == "source":
        if missing:
            return "source not recorded"
        return f"{_SOURCE_LABELS.get(str(value), str(value).capitalize())} lead"

    if feature == "stage_at_scoring":
        if missing:
            return "stage not recorded"
        return _STAGE_LABELS.get(str(value), str(value).capitalize())

    if feature == "age_days_at_scoring":
        if missing:
            return "age not recorded"
        days = int(round(float(value)))
        return f"{days} {_plural(days, 'day')} since the initiative started"

    if feature == "amount_arr":
        if missing:
            return "amount not recorded"
        amount = float(value)
        return "no amount proposed" if amount == 0.0 else f"€{_number(amount)} proposed ARR"

    if feature == "discount_pct":
        if missing:
            return "discount not recorded"
        discount = float(value)
        return "no discount" if discount == 0.0 else f"{_compact(discount)}% discount"

    if feature == "first_response_hours":
        return "no response yet" if missing else _hours(value)

    if feature == "region":
        if missing:
            return "region not recorded"
        return _REGION_LABELS.get(str(value), str(value).capitalize())

    if feature == "industry":
        if missing:
            return "industry not recorded"
        return str(value).capitalize()

    if feature == "employees":
        if missing:
            return "headcount not recorded"
        return f"{_number(value)} employees"

    if feature == "company_age_days":
        if missing:
            return "company tenure not recorded"
        years = float(value) / 365.25
        if years < 1.0:
            months = max(1, int(round(float(value) / 30.44)))
            return f"company on file for {months} {_plural(months, 'month')}"
        return f"company on file for {_compact(years)} years"

    if feature == "prior_won_initiatives":
        if missing:
            return "previous wins not recorded"
        count = int(round(float(value)))
        if count == 0:
            return "no previous wins"
        return f"{count} {_plural(count, 'initiative')} won before"

    if feature == "prior_lost_initiatives":
        if missing:
            return "previous losses not recorded"
        count = int(round(float(value)))
        if count == 0:
            return "no previous losses"
        return f"{count} {_plural(count, 'initiative')} lost before"

    if feature == "days_since_last_initiative":
        if missing:
            return "gap not recorded"
        days = int(round(float(value)))
        if days == 0:
            return "an initiative started today"
        return f"{days} days since the last initiative"

    if feature == "lifetime_won_arr":
        if missing:
            return "revenue history not recorded"
        amount = float(value)
        return "no revenue won yet" if amount == 0.0 else f"€{_number(amount)} won to date"

    if feature == "open_initiatives_count":
        if missing:
            return "open initiatives not recorded"
        count = int(round(float(value)))
        if count == 0:
            return "no other open initiatives"
        return f"{count} other open {_plural(count, 'initiative')}"

    if feature == "usage_trend_slope":
        if missing:
            return "usage trend not measurable yet"
        slope = float(value)
        if abs(slope) < 0.5:
            return "usage flat"
        direction = "rising" if slope > 0 else "falling"
        return f"usage {direction} {_compact(abs(slope))} events per week"

    if feature == "tickets_90d":
        if missing:
            return "support tickets not recorded"
        count = int(round(float(value)))
        if count == 0:
            return "no support tickets in 90 days"
        return f"{count} {_plural(count, 'support ticket')} in 90 days"

    if feature == "nps_last":
        return "never surveyed" if missing else f"NPS {int(round(float(value)))}"

    if feature == "payment_delay_days_avg_180d":
        if missing:
            return "no invoices in the last 180 days"
        delay = float(value)
        if abs(delay) < 0.5:
            return "invoices paid on time"
        if delay > 0:
            return f"invoices paid {_compact(delay)} days late"
        return f"invoices paid {_compact(abs(delay))} days early"

    if feature == "meetings_before_scoring":
        if missing:
            return "meetings not recorded"
        count = int(round(float(value)))
        return "no meetings yet" if count == 0 else f"{count} {_plural(count, 'meeting')} so far"

    if feature == "owner_win_rate_180d":
        if missing:
            return "rep has no recent closures"
        rate = float(value)
        return f"rep wins {_number(rate * 100.0, 0)}% of initiatives"

    # Unknown column: still readable, and obviously not a curated label.
    if missing:
        return "not measured"
    return f"{feature.replace('_', ' ')}: {value}"


# --------------------------------------------------------------------------------------
# model bundle, frame preparation and SHAP
# --------------------------------------------------------------------------------------


def load_bundle(path: str | pathlib.Path = DEFAULT_MODEL_PATH) -> dict[str, Any]:
    """Load the artifact dictionary written by ``ml/train.py``."""
    return joblib.load(pathlib.Path(path))


def prepare_frame(bundle: Mapping[str, Any], rows: Any) -> pd.DataFrame:
    """Cast a feature frame (or a single-row mapping) into the model's exact dtypes.

    Categorical columns are cast to the *training* categories, not to a fresh category set:
    LightGBM encodes categories by code, so a differently ordered ``region`` column would
    silently rescore every lead. Rows may be a ``pandas.DataFrame`` (raw database columns are
    fine), a mapping of column -> value, or a single ``pandas.Series``. Missing columns raise,
    because a silently-absent feature is a scoring bug, not a missing value.
    """
    if isinstance(rows, Mapping):
        frame = pd.DataFrame([rows])
    elif isinstance(rows, pd.Series):
        frame = rows.to_frame().T
    else:
        frame = pd.DataFrame(rows)

    missing = [column for column in bundle["features"] if column not in frame.columns]
    if missing:
        raise KeyError(f"feature frame is missing columns: {missing}")

    prepared = frame.loc[:, list(bundle["features"])].copy()
    for column, categories in bundle["categories"].items():
        values = prepared[column].astype("object")
        # A level the model never saw cannot be encoded as a level: mapping it to a new code
        # would silently change what every other level means. It becomes missing (NaN) instead,
        # which is exactly how LightGBM treats an unknown categorical at scoring time.
        known = values.isin(list(categories))
        prepared[column] = pd.Categorical(values.where(known), categories=categories)
    for column in bundle["numeric_features"]:
        prepared[column] = pd.to_numeric(prepared[column], errors="coerce").astype("float64")
    return prepared


def _positive_class_values(values: Any, rows: int, columns: int) -> np.ndarray:
    """Normalise SHAP output across versions: ``(n, f)`` or a ``[negative, positive]`` list.

    Newer shap releases return one array for a binary LightGBM model; older ones return a
    list of two arrays. Taking the positive class keeps the sign convention (log-odds of
    winning) the same either way.
    """
    if isinstance(values, list):
        if len(values) == 0:
            raise ValueError("SHAP returned no values")
        values = values[-1] if len(values) == 2 else values[0]
    if hasattr(values, "values"):  # shap.Explanation
        values = values.values
    matrix = np.asarray(values, dtype="float64")
    if matrix.ndim == 3:  # (rows, columns, classes)
        matrix = matrix[:, :, -1]
    if matrix.shape != (rows, columns):
        raise ValueError(
            f"unexpected SHAP shape {matrix.shape}, expected {(rows, columns)}"
        )
    return matrix


class Explainer:
    """TreeSHAP over one loaded model, with cached categories and feature order."""

    def __init__(self, bundle: Mapping[str, Any]) -> None:
        self.bundle = bundle
        self.features = tuple(bundle["features"])
        with warnings.catch_warnings():
            # See shap_matrix: the version-specific output-shape warning is not actionable.
            warnings.filterwarnings(
                "ignore", message=".*LightGBM binary classifier with TreeExplainer.*"
            )
            self._explainer = shap.TreeExplainer(bundle["model"])

    def prepare(self, rows: Any) -> pd.DataFrame:
        return prepare_frame(self.bundle, rows)

    def shap_matrix(self, prepared: pd.DataFrame) -> np.ndarray:
        """SHAP values in log-odds, shape ``(rows, features)``, in contract feature order."""
        with warnings.catch_warnings():
            # shap 0.54 warns that the binary-LightGBM output "changed to a list of ndarray";
            # ``_positive_class_values`` accepts either shape, so the warning is noise on every
            # explanation -- including one per API request.
            warnings.filterwarnings(
                "ignore", message=".*LightGBM binary classifier with TreeExplainer.*"
            )
            raw = self._explainer.shap_values(prepared)
        return _positive_class_values(raw, len(prepared), len(self.features))

    def drivers(
        self,
        prepared: pd.DataFrame,
        limit: int = 3,
    ) -> list[list[dict[str, Any]]]:
        """Top-``limit`` contributions per row, as ``Driver`` dictionaries.

        Ranked by absolute contribution (a strong negative driver explains a lead as much as
        a strong positive one), ties broken by contract feature order so output is stable.
        """
        matrix = self.shap_matrix(prepared)
        values = prepared.to_dict("records")
        rows: list[list[dict[str, Any]]] = []
        for index, record in enumerate(values):
            contributions = matrix[index]
            order = sorted(
                range(len(self.features)),
                key=lambda position: (-abs(contributions[position]), position),
            )
            drivers: list[dict[str, Any]] = []
            for position in order[:limit]:
                feature = self.features[position]
                contribution = float(contributions[position])
                drivers.append(
                    {
                        "feature": feature,
                        "label": business_label(feature),
                        "contribution": round(contribution, 6),
                        "value": describe_value(feature, record[feature]),
                        "direction": DIRECTION_UP if contribution >= 0.0 else DIRECTION_DOWN,
                    }
                )
            rows.append(drivers)
        return rows

    def explain_one(self, row: Any, limit: int = 3) -> list[dict[str, Any]]:
        return self.drivers(self.prepare(row), limit=limit)[0]


def explain(bundle: Mapping[str, Any], rows: Any, limit: int = 3) -> list[list[dict[str, Any]]]:
    """Convenience wrapper: explain one or more rows with a bundle in a single call."""
    explainer = Explainer(bundle)
    return explainer.drivers(explainer.prepare(rows), limit=limit)


def top_drivers(
    bundle: Mapping[str, Any],
    row: Mapping[str, Any] | pd.Series,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Explain a single lead from a mapping of feature -> value.

    Convenience for a one-off call (the CLI, a test). A service that explains many leads should
    build one :class:`Explainer` and reuse it: constructing a TreeSHAP explainer costs more than
    explaining a row.
    """
    return Explainer(bundle).explain_one(row, limit=limit)


# --------------------------------------------------------------------------------------
# CLI: one lead, straight from the demo database
# --------------------------------------------------------------------------------------


def _cli(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="explain one lead's score")
    parser.add_argument("--lead-id", required=True)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--model", default=str(DEFAULT_MODEL_PATH))
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args(argv)

    bundle = load_bundle(args.model)
    connection = sqlite3.connect(args.db)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            "SELECT * FROM lead_features WHERE lead_id = ?", (args.lead_id,)
        ).fetchone()
        score = connection.execute(
            "SELECT probability, band, expected_value FROM lead_scores WHERE lead_id = ? "
            "ORDER BY scored_at DESC LIMIT 1",
            (args.lead_id,),
        ).fetchone()
    finally:
        connection.close()

    if row is None:
        print(f"FAIL explain: lead {args.lead_id} has no lead_features row", file=sys.stderr)
        return 2

    drivers = top_drivers(bundle, dict(row), limit=args.limit)
    payload = {
        "lead_id": args.lead_id,
        "model_version": bundle.get("model_version"),
        "probability": None if score is None else float(score["probability"]),
        "band": None if score is None else str(score["band"]),
        "expected_value": None if score is None else float(score["expected_value"]),
        "drivers": drivers,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
