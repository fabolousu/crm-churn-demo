"""Train the lead-win model, write its artifacts, and score every open lead.

``tools/run_pipeline.py`` calls this after ``ml/features.py``: the world exists, ``lead_features``
is materialised, and this module is the last stage. Everything here is downstream of the
contract in ``docs/LABEL.md`` and ``docs/DECISIONS.md``; nothing here invents a feature.

The label
    ``won`` from ``lead_outcomes``, read here and only here. The training population is the
    inner join of ``lead_features`` and ``lead_outcomes``: a lead that is still open at ``t0``
    is censored and has no label, so it is scored but never trained on. ``latent_p`` is the
    world's *generating* probability; it is loaded by a separate reader and used only to
    record ``latent_auc``, the ceiling the gate compares against. It is never a column of the
    feature frame, so it cannot enter training even by accident -- ``FEATURES`` is an explicit
    allow-list and the frame handed to LightGBM is ``frame[list(FEATURES)]``.

The split
    Temporal, never random. Leads are ordered by ``closed_at`` and the split point is the 80th
    percentile of that column: train on leads closed **before** the cutoff, validate on leads
    closed **at or after** it. The two sides are asserted disjoint against the timestamps
    themselves (train max <= validation min), not against row indices.

The model
    LightGBM binary classifier on the raw contract features. Missing values are *not*
    imputed: the signal columns are legitimately NULL ("not measured", contract convention 5)
    and LightGBM handles NaN natively, choosing a missing-value branch per split. Substituting
    a zero would both fabricate a measurement and shift the distribution of a column the
    business reads as "hours to first response".

    Monotone constraints are set from the signs documented in the generating hazard in
    ``docs/LABEL.md`` (slower response, bigger deal, more discount, more tickets and longer
    gaps all lower win probability; meetings, prior wins, rep win rate and NPS raise it).
    This is domain knowledge recorded in the contract, not per-row information, and it stops a
    tree from fitting a reversal that the world does not contain. The same monotone shape is
    what makes the counterfactual levers in the pitch behave sensibly.

    Hyperparameters and the round count were chosen once, by a small sweep scored on the
    temporal validation split during development; the final fit uses a fixed round count and
    no early stopping, so a run does not silently re-select its own stopping point and the
    reported metrics stay comparable between runs.

Artifacts (committed -- the demo runs offline)
    ``ml/artifacts/model.joblib``       model + feature contract + categorical levels
    ``ml/artifacts/metrics.json``       auc, calibration_error, lift_at_10, latent_auc
    ``ml/artifacts/shap_sample.parquet``  tidy SHAP contributions for a few thousand leads

    and ``lead_scores``, one row per open lead (``new``/``contacted``/``qualified``/
    ``proposal``), with ``probability``, ``band``, ``drivers_json``, ``amount_arr`` and
    ``expected_value = probability * amount_arr``.

Run it with ``python ml/train.py`` or as the last stage of ``python tools/run_pipeline.py``.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import sqlite3
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

ML_DIR = pathlib.Path(__file__).resolve().parent
REPO_ROOT = ML_DIR.parent
if str(REPO_ROOT) not in sys.path:  # so ``python ml/train.py`` and pytest both work
    sys.path.insert(0, str(REPO_ROOT))

from ml.explain import (  # noqa: E402  (after the sys.path bootstrap above)
    CATEGORICAL_FEATURES,
    FEATURES,
    NUMERIC_FEATURES,
    Explainer,
    business_label,
    describe_value,
    prepare_frame,
)

__all__ = [
    "BAND_THRESHOLDS",
    "band_for",
    "expected_calibration_error",
    "fit_model",
    "lift_at_fraction",
    "load_labeled_leads",
    "load_latent_probabilities",
    "run",
    "score_open_leads",
    "temporal_split",
    "write_scores",
]

# --------------------------------------------------------------------------------------
# configuration
# --------------------------------------------------------------------------------------

DEFAULT_DB_PATH = REPO_ROOT / "data" / "demo.db"
DEFAULT_ARTIFACT_DIR = ML_DIR / "artifacts"

# Bump when the feature contract, the label definition or the model shape changes. It is the
# value written to ``lead_scores.model_version`` and ``model_runs.model_version``.
MODEL_VERSION = "lead-win-lgbm-v1"

# A lead is "open" until it reaches a terminal status. ``data/schema.sql`` has no other
# notion of open, and these are the stages the pipeline screen scores.
OPEN_STATUSES: tuple[str, ...] = ("new", "contacted", "qualified", "proposal")

# Temporal split: the 80th percentile of ``closed_at`` splits the labelled population.
SPLIT_QUANTILE = 0.80

# Band cut-offs, stated once. low < 0.20 <= medium < 0.40 <= high < 0.60 <= critical.
BAND_THRESHOLDS: dict[str, float] = {"medium": 0.20, "high": 0.40, "critical": 0.60}
BANDS: tuple[str, ...] = ("low", "medium", "high", "critical")

CALIBRATION_BINS = 10
LIFT_FRACTION = 0.10
DRIVER_LIMIT = 3

# Small enough to commit, wide enough for the demo's global-drivers panel.
SHAP_SAMPLE_LEADS = 2000

# Monotone direction per contract feature, taken from the hazard in docs/LABEL.md:
# +1 higher value raises win probability, -1 lowers it, 0 unconstrained.
MONOTONE_DIRECTIONS: dict[str, int] = {
    "first_response_hours": -1,
    "meetings_before_scoring": +1,
    "prior_won_initiatives": +1,
    "prior_lost_initiatives": -1,
    "owner_win_rate_180d": +1,
    "days_since_last_initiative": -1,
    "amount_arr": -1,
    "discount_pct": -1,
    "tickets_90d": -1,
    "nps_last": +1,
    "usage_trend_slope": +1,
    "payment_delay_days_avg_180d": -1,
}

# Fixed shape, deterministic given the seed. No early stopping: see the module docstring.
NUM_BOOST_ROUND = 500
LGBM_PARAMS: dict[str, Any] = {
    "objective": "binary",
    "metric": "auc",
    "learning_rate": 0.02,
    "num_leaves": 63,
    "min_child_samples": 100,
    "feature_fraction": 0.7,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "lambda_l2": 1.0,
    "verbose": -1,
    "seed": 42,
    "deterministic": True,
    "force_row_wise": True,
    "num_threads": 0,
}


# --------------------------------------------------------------------------------------
# loading
# --------------------------------------------------------------------------------------


def connect(db_path: str | pathlib.Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    return connection


def read_features(connection: sqlite3.Connection) -> pd.DataFrame:
    """Every materialised feature row, keyed by ``lead_id``."""
    frame = pd.read_sql_query("SELECT * FROM lead_features", connection)
    if frame.empty:
        raise RuntimeError(
            "lead_features is empty; run ml/features.py (or tools/run_pipeline.py) first"
        )
    return frame


def load_labeled_leads(connection: sqlite3.Connection) -> pd.DataFrame:
    """Feature rows that carry a label, plus ``won`` and ``closed_at``.

    An inner join, because a lead with no ``lead_outcomes`` row is censored (still open at
    ``t0``) and training on it would teach the model that open means lost. ``latent_p`` is
    deliberately not selected: it belongs to the audit reader below.
    """
    labeled = pd.read_sql_query(
        "SELECT f.*, o.won, o.closed_at "
        "FROM lead_features AS f "
        "JOIN lead_outcomes AS o ON o.lead_id = f.lead_id",
        connection,
    )
    if labeled.empty:
        raise RuntimeError("no labelled leads: lead_outcomes is empty or does not join")
    labeled["closed_at"] = pd.to_datetime(labeled["closed_at"])
    labeled["won"] = labeled["won"].astype("int64")
    return labeled


def load_latent_probabilities(connection: sqlite3.Connection) -> pd.Series:
    """The generator's own probability per labelled lead, for the ceiling audit only.

    Kept out of the feature frame on purpose: ``latent_auc`` measures what the world allows,
    and a model that could read ``latent_p`` would trivially win and tell us nothing.
    """
    latent = pd.read_sql_query(
        "SELECT lead_id, latent_p FROM lead_outcomes", connection
    ).set_index("lead_id")["latent_p"]
    return latent.astype("float64")


def category_levels(features: pd.DataFrame) -> dict[str, list[str]]:
    """Sorted categorical levels for every categorical feature.

    Taken from the whole feature table (not just the training slice) and sorted, so a level
    that first appears in the validation window or in an open lead still maps to a stable
    code, and the mapping is reproducible from the data rather than from row order.
    """
    return {
        column: sorted(str(value) for value in features[column].dropna().unique())
        for column in CATEGORICAL_FEATURES
    }


# --------------------------------------------------------------------------------------
# split and metrics
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Split:
    train: pd.DataFrame
    validation: pd.DataFrame
    quantile: float
    cutoff: pd.Timestamp

    @property
    def train_max_closed_at(self) -> pd.Timestamp:
        return self.train["closed_at"].max()

    @property
    def validation_min_closed_at(self) -> pd.Timestamp:
        return self.validation["closed_at"].min()


def temporal_split(labeled: pd.DataFrame, quantile: float = SPLIT_QUANTILE) -> Split:
    """Split by close date: train before the cutoff, validate at or after it.

    A random split would leak the future into the past on a dataset whose features are
    snapshot-relative; the temporal shape is also how the model will actually be used. The
    disjointness of the two sides is asserted on the timestamps, and both sides must carry
    both classes or the metrics below are undefined.
    """
    if not 0.0 < quantile < 1.0:
        raise ValueError(f"split quantile must be in (0, 1), got {quantile}")

    cutoff = labeled["closed_at"].quantile(quantile)
    train = labeled[labeled["closed_at"] < cutoff]
    validation = labeled[labeled["closed_at"] >= cutoff]

    if train.empty or validation.empty:
        raise RuntimeError(
            f"temporal split at the {quantile:.0%} percentile produced an empty side "
            f"(train={len(train)}, validation={len(validation)})"
        )
    if train["closed_at"].max() > validation["closed_at"].min():
        raise AssertionError(
            "temporal split overlaps: train closes at "
            f"{train['closed_at'].max()} but validation starts at "
            f"{validation['closed_at'].min()}"
        )
    for name, side in (("train", train), ("validation", validation)):
        if side["won"].nunique() < 2:
            raise RuntimeError(f"{name} side holds a single class, so AUC is undefined")

    return Split(
        train=train.reset_index(drop=True),
        validation=validation.reset_index(drop=True),
        quantile=quantile,
        cutoff=cutoff,
    )


def expected_calibration_error(
    labels: Sequence[int] | np.ndarray,
    probabilities: Sequence[float] | np.ndarray,
    bins: int = CALIBRATION_BINS,
) -> float:
    """Expected calibration error with equal-width bins over ``[0, 1]``.

    ``ECE = sum_b (n_b / n) * |mean(predicted in b) - mean(observed in b)|``. Empty bins
    contribute nothing, and a probability of exactly 1.0 lands in the last bin.
    """
    labels = np.asarray(labels, dtype="float64")
    probabilities = np.asarray(probabilities, dtype="float64")
    if labels.shape != probabilities.shape:
        raise ValueError("labels and probabilities must have the same length")
    if labels.size == 0:
        raise ValueError("cannot compute calibration error on an empty set")

    edges = np.linspace(0.0, 1.0, bins + 1)
    # digitize on the interior edges: bin 0 holds [0, 1/bins), the last holds [1-1/bins, 1]
    indices = np.clip(np.digitize(probabilities, edges[1:-1]), 0, bins - 1)
    total = 0.0
    for index in range(bins):
        mask = indices == index
        count = int(mask.sum())
        if count == 0:
            continue
        total += (count / labels.size) * abs(
            float(probabilities[mask].mean()) - float(labels[mask].mean())
        )
    return float(total)


def lift_at_fraction(
    labels: Sequence[int] | np.ndarray,
    probabilities: Sequence[float] | np.ndarray,
    fraction: float = LIFT_FRACTION,
) -> float:
    """Win rate in the top ``fraction`` of the ranked queue, over the base rate.

    ``1.0`` means the model adds nothing over calling every lead equally likely; the gate
    wants ``>= 2.0``. The ranking is by descending probability with a stable sort, so ties do
    not depend on the underlying row order.
    """
    labels = np.asarray(labels, dtype="float64")
    probabilities = np.asarray(probabilities, dtype="float64")
    if labels.size == 0:
        raise ValueError("cannot compute lift on an empty set")
    base_rate = float(labels.mean())
    if base_rate <= 0.0:
        raise ValueError("cannot compute lift when no lead in the set was won")
    take = max(1, int(round(labels.size * fraction)))
    top = np.argsort(-probabilities, kind="stable")[:take]
    return float(labels[top].mean() / base_rate)


def band_for(probability: float) -> str:
    """Band for a probability. Cut-offs: low < 0.20, medium < 0.40, high < 0.60, critical."""
    if probability >= BAND_THRESHOLDS["critical"]:
        return "critical"
    if probability >= BAND_THRESHOLDS["high"]:
        return "high"
    if probability >= BAND_THRESHOLDS["medium"]:
        return "medium"
    return "low"


# --------------------------------------------------------------------------------------
# model
# --------------------------------------------------------------------------------------


def fit_model(
    train: pd.DataFrame,
    categories: Mapping[str, Sequence[str]],
    rounds: int = NUM_BOOST_ROUND,
    params: Mapping[str, Any] | None = None,
) -> lgb.Booster:
    """Fit the LightGBM classifier on the training side of the temporal split."""
    bundle = {
        "features": list(FEATURES),
        "numeric_features": list(NUMERIC_FEATURES),
        "categories": {column: list(levels) for column, levels in categories.items()},
    }
    frame = prepare_frame(bundle, train)
    dataset = lgb.Dataset(
        frame,
        label=train["won"].to_numpy(),
        categorical_feature=list(CATEGORICAL_FEATURES),
        free_raw_data=True,
    )
    fit_params = dict(LGBM_PARAMS)
    if params:
        fit_params.update(params)
    fit_params["monotone_constraints"] = [MONOTONE_DIRECTIONS.get(name, 0) for name in FEATURES]
    fit_params["monotone_constraints_method"] = "advanced"
    return lgb.train(fit_params, dataset, num_boost_round=rounds)


def predict(bundle: Mapping[str, Any], rows: Any) -> np.ndarray:
    """Probability of winning for the given feature rows, in ``[0, 1]``, never NaN."""
    return _predict_prepared(bundle, prepare_frame(bundle, rows))


def _predict_prepared(bundle: Mapping[str, Any], prepared: pd.DataFrame) -> np.ndarray:
    """Score an already-prepared frame; ``prepare_frame`` is the only place dtypes are set."""
    model: lgb.Booster = bundle["model"]
    probabilities = np.asarray(model.predict(prepared), dtype="float64")
    if probabilities.ndim != 1:
        raise ValueError(f"expected one probability per row, got shape {probabilities.shape}")
    if not np.all(np.isfinite(probabilities)):
        raise ValueError("model produced a non-finite probability")
    return np.clip(probabilities, 0.0, 1.0)


# --------------------------------------------------------------------------------------
# scoring
# --------------------------------------------------------------------------------------


def score_open_leads(
    features: pd.DataFrame,
    open_ids: Sequence[str],
    bundle: Mapping[str, Any],
) -> pd.DataFrame:
    """Score every open lead and attach its drivers, band and expected value."""
    if not open_ids:
        return pd.DataFrame(
            columns=[
                "lead_id",
                "model_version",
                "probability",
                "band",
                "drivers_json",
                "amount_arr",
                "expected_value",
            ]
        )

    open_frame = features.loc[features["lead_id"].isin(set(open_ids))].copy()
    if len(open_frame) != len(set(open_ids)):
        missing = sorted(set(open_ids) - set(open_frame["lead_id"]))
        raise RuntimeError(f"open leads without a feature row: {missing[:5]}")

    open_frame = open_frame.sort_values("lead_id", kind="stable").reset_index(drop=True)
    prepared = prepare_frame(bundle, open_frame)
    probabilities = _predict_prepared(bundle, prepared)
    drivers = Explainer(bundle).drivers(prepared, limit=DRIVER_LIMIT)

    amounts = open_frame["amount_arr"].astype("float64").to_numpy()
    scores = pd.DataFrame(
        {
            "lead_id": open_frame["lead_id"].to_numpy(),
            "model_version": bundle["model_version"],
            "probability": probabilities,
            "band": [band_for(float(p)) for p in probabilities],
            "drivers_json": [json.dumps(row, ensure_ascii=False) for row in drivers],
            "amount_arr": amounts,
            "expected_value": probabilities * amounts,
        }
    )
    return scores


def write_scores(
    connection: sqlite3.Connection,
    scores: pd.DataFrame,
    scored_at: str,
) -> int:
    """Replace ``lead_scores`` with this batch, in one transaction.

    Training is the only writer of this table, and a batch that half-applied would leave the
    pipeline screen mixing two model versions, so the delete and the insert share a
    transaction: both land or neither does.
    """
    rows = [
        (
            record.lead_id,
            scored_at,
            record.model_version,
            float(record.probability),
            record.band,
            record.drivers_json,
            float(record.amount_arr),
            float(record.expected_value),
        )
        for record in scores.itertuples(index=False)
    ]

    owned = not connection.in_transaction
    if owned:
        connection.execute("BEGIN IMMEDIATE")
    try:
        connection.execute("DELETE FROM lead_scores")
        connection.executemany(
            "INSERT INTO lead_scores (lead_id, scored_at, model_version, probability, band, "
            "drivers_json, amount_arr, expected_value) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        if owned:
            connection.commit()
    except BaseException:
        if owned:
            connection.rollback()
        raise
    return len(rows)


def record_model_run(
    connection: sqlite3.Connection,
    model_version: str,
    trained_at: str,
    metrics: Mapping[str, Any],
    artifact_path: str,
) -> None:
    """Upsert one ``model_runs`` row so the demo can show which model scored the pipeline."""
    owned = not connection.in_transaction
    connection.execute("DELETE FROM model_runs WHERE model_version = ?", (model_version,))
    connection.execute(
        "INSERT INTO model_runs (model_version, trained_at, metrics_json, artifact_path) "
        "VALUES (?, ?, ?, ?)",
        (model_version, trained_at, json.dumps(dict(metrics), ensure_ascii=False), artifact_path),
    )
    if owned:
        connection.commit()


# --------------------------------------------------------------------------------------
# artifacts
# --------------------------------------------------------------------------------------


def build_shap_sample(
    bundle: Mapping[str, Any],
    validation: pd.DataFrame,
    limit: int = SHAP_SAMPLE_LEADS,
) -> pd.DataFrame:
    """Tidy SHAP contributions for a deterministic sample of the validation population.

    Long format (one row per lead x feature) because every downstream use -- global
    importance, a dependence plot, a tooltip -- is a group-by away, and it keeps the column
    set identical to ``Driver``. The sample is evenly spaced over the validation leads sorted
    by ``lead_id``: reproducible, and not biased toward early or late close dates.
    """
    if validation.empty:
        return pd.DataFrame(
            columns=["lead_id", "feature", "label", "value", "contribution", "direction"]
        )

    ordered = validation.sort_values("lead_id", kind="stable").reset_index(drop=True)
    step = max(1, len(ordered) // max(1, limit))
    sample = ordered.iloc[::step].head(limit)

    explainer = Explainer(bundle)
    prepared = prepare_frame(bundle, sample)
    matrix = explainer.shap_matrix(prepared)

    records: list[dict[str, Any]] = []
    values = prepared.to_dict("records")
    for row_index, (lead_id, feature_values) in enumerate(
        zip(sample["lead_id"].astype(str), values)
    ):
        for feature_index, feature in enumerate(FEATURES):
            contribution = float(matrix[row_index, feature_index])
            records.append(
                {
                    "lead_id": lead_id,
                    "feature": feature,
                    "label": business_label(feature),
                    "value": describe_value(feature, feature_values[feature]),
                    "contribution": contribution,
                    "direction": "increases" if contribution >= 0.0 else "decreases",
                }
            )

    frame = pd.DataFrame.from_records(records)
    frame["contribution"] = frame["contribution"].astype("float32")
    return frame


def bundle_from_model(
    model: lgb.Booster,
    categories: Mapping[str, Sequence[str]],
) -> dict[str, Any]:
    """The artifact dictionary: model plus everything needed to score the same way again."""
    return {
        "model": model,
        "model_version": MODEL_VERSION,
        "features": list(FEATURES),
        "numeric_features": list(NUMERIC_FEATURES),
        "categorical_features": list(CATEGORICAL_FEATURES),
        "categories": {column: list(levels) for column, levels in categories.items()},
        "band_thresholds": dict(BAND_THRESHOLDS),
        "num_boost_round": NUM_BOOST_ROUND,
    }


# --------------------------------------------------------------------------------------
# the whole stage
# --------------------------------------------------------------------------------------


def _display_path(path: pathlib.Path) -> str:
    """Repo-relative POSIX path when the file lives in the repo, else the absolute path."""
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def run(
    db_path: str | pathlib.Path = DEFAULT_DB_PATH,
    artifact_dir: str | pathlib.Path = DEFAULT_ARTIFACT_DIR,
    rounds: int = NUM_BOOST_ROUND,
    shap_leads: int = SHAP_SAMPLE_LEADS,
    params: Mapping[str, Any] | None = None,
    verbose: bool = True,
) -> dict[str, Any]:
    """Train, write the three artifacts, score every open lead, return the metrics.

    ``rounds``/``params`` are exposed so a test can fit a small world quickly; the CLI and the
    pipeline use the module defaults, which are the configuration the committed artifacts were
    produced with.
    """
    artifact_dir = pathlib.Path(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    model_path = artifact_dir / "model.joblib"
    metrics_path = artifact_dir / "metrics.json"
    shap_path = artifact_dir / "shap_sample.parquet"

    staging = tempfile.TemporaryDirectory(prefix=".training-", dir=artifact_dir)
    staged_dir = pathlib.Path(staging.name)
    published: list[pathlib.Path] = []
    connection = connect(db_path)
    try:
        features = read_features(connection)
        labeled = load_labeled_leads(connection)
        latent = load_latent_probabilities(connection)
        open_ids = [
            str(row[0])
            for row in connection.execute(
                "SELECT id FROM leads WHERE status IN ({}) ORDER BY id".format(
                    ", ".join("?" for _ in OPEN_STATUSES)
                ),
                OPEN_STATUSES,
            )
        ]
        known_ids = set(features["lead_id"])
        open_ids = [lead_id for lead_id in open_ids if lead_id in known_ids]

        categories = category_levels(features)
        split = temporal_split(labeled)
        if verbose:
            print(
                f"split        : {len(split.train):,} train (< {split.cutoff}) | "
                f"{len(split.validation):,} validation (>= {split.cutoff})",
                flush=True,
            )

        model = fit_model(split.train, categories, rounds=rounds, params=params)
        bundle = bundle_from_model(model, categories)
        joblib.dump(bundle, staged_dir / model_path.name)

        validation_probabilities = predict(bundle, split.validation)
        validation_labels = split.validation["won"].to_numpy()
        validation_latent = (
            split.validation["lead_id"].map(latent).astype("float64").to_numpy()
        )
        if not np.all(np.isfinite(validation_latent)):
            raise RuntimeError("some validation leads have no latent_p; the audit is unusable")

        auc = float(roc_auc_score(validation_labels, validation_probabilities))
        calibration_error = expected_calibration_error(
            validation_labels, validation_probabilities
        )
        lift = lift_at_fraction(validation_labels, validation_probabilities)
        latent_auc = float(roc_auc_score(validation_labels, validation_latent))

        if not np.all(np.isfinite([auc, calibration_error, lift, latent_auc])):
            raise RuntimeError(
                f"non-finite metric: auc={auc} calibration_error={calibration_error} "
                f"lift_at_10={lift} latent_auc={latent_auc}"
            )

        scores = score_open_leads(features, open_ids, bundle)
        scored_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        connection.execute("BEGIN IMMEDIATE")
        scored_rows = write_scores(connection, scores, scored_at)

        shap_sample = build_shap_sample(bundle, split.validation, limit=shap_leads)
        shap_sample.to_parquet(staged_dir / shap_path.name, index=False, compression="zstd")

        metrics: dict[str, Any] = {
            # the four the gate and the pitch read -- all on the temporal validation split
            "auc": round(auc, 6),
            "calibration_error": round(calibration_error, 6),
            "lift_at_10": round(lift, 6),
            "latent_auc": round(latent_auc, 6),
            "model_version": MODEL_VERSION,
            "split": {
                "strategy": "temporal by closed_at",
                "quantile": SPLIT_QUANTILE,
                "cutoff": split.cutoff.isoformat(),
                "train_rows": int(len(split.train)),
                "validation_rows": int(len(split.validation)),
                "train_max_closed_at": split.train_max_closed_at.isoformat(),
                "validation_min_closed_at": split.validation_min_closed_at.isoformat(),
                "train_win_rate": round(float(split.train["won"].mean()), 6),
                "validation_win_rate": round(float(split.validation["won"].mean()), 6),
            },
            "bands": dict(BAND_THRESHOLDS),
            "scored_leads": int(scored_rows),
            "scored_leads_by_stage": {
                str(row[0]): int(row[1])
                for row in connection.execute(
                    "SELECT f.stage_at_scoring, COUNT(*) FROM lead_scores AS s "
                    "JOIN lead_features AS f ON f.lead_id = s.lead_id "
                    "GROUP BY f.stage_at_scoring ORDER BY f.stage_at_scoring"
                )
            },
            "shap_sample_rows": int(len(shap_sample)),
            "features": list(FEATURES),
            "num_boost_round": int(rounds),
        }
        # newline="\n" so the committed artifact is byte-identical whether it is regenerated on
        # Windows or Linux: the demo's "same seed, same bytes" claim should not depend on the OS.
        with (staged_dir / metrics_path.name).open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n")
        record_model_run(
            connection,
            model_version=MODEL_VERSION,
            trained_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            metrics=metrics,
            artifact_path=_display_path(model_path),
        )
        # All outputs are ready. Keep the previous generation until the database commit
        # succeeds, so publication or commit errors can restore the complete old batch.
        for path in (model_path, shap_path, metrics_path):
            if path.exists():
                shutil.copy2(path, staged_dir / (path.name + ".previous"))
        for path in (model_path, shap_path, metrics_path):
            (staged_dir / path.name).replace(path)
            published.append(path)
        connection.commit()
    except BaseException:
        connection.rollback()
        for path in reversed(published):
            previous = staged_dir / (path.name + ".previous")
            if previous.exists():
                previous.replace(path)
            else:
                path.unlink()
        raise
    finally:
        connection.close()
        staging.cleanup()

    if verbose:
        print(
            f"validation   : auc={auc:.4f} (ceiling {latent_auc:.4f}) "
            f"calibration={calibration_error:.4f} lift@10={lift:.2f}",
            flush=True,
        )
        print(f"artifacts    : {model_path.parent}", flush=True)
        print(f"scored       : {scored_rows:,} open leads", flush=True)

    return metrics


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="train the lead-win model and score the pipeline")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--artifacts", default=str(DEFAULT_ARTIFACT_DIR))
    parser.add_argument("--rounds", type=int, default=NUM_BOOST_ROUND)
    parser.add_argument("--shap-leads", type=int, default=SHAP_SAMPLE_LEADS)
    args = parser.parse_args(argv)

    metrics = run(
        db_path=args.db,
        artifact_dir=args.artifacts,
        rounds=args.rounds,
        shap_leads=args.shap_leads,
    )
    print(json.dumps(metrics, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
