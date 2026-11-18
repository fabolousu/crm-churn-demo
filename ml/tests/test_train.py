"""Tests for ``ml/train.py`` and the model it produces.

Two fixtures, deliberately different in kind:

* The **committed artifacts** (``ml/artifacts/``) are the thing the demo actually ships, so the
  first group asserts on them directly: the four metrics exist and are finite, the split is
  temporal and disjoint, and the model at rest can be reloaded and re-scored. This group is
  what fails when someone retrains badly and commits the result.

* A **tiny planted world** built from ``data/schema.sql`` in a temporary directory, put through
  the real ``ml/features.py`` and then through ``run()``. Structural properties -- one score
  per open lead, bands monotone in probability, three drivers, no NaN predictions -- can only
  be tested end to end, and testing them on a small world keeps the suite fast and independent
  of ``data/demo.db`` (which is regenerable and never committed).

The last test is behavioural rather than textual: it scrambles ``lead_outcomes.latent_p`` and
re-trains, then asserts every prediction is unchanged. ``latent_auc`` is the world's ceiling,
recorded so the gate can detect leakage; if it ever reached the feature frame, this test
fails even though ``latent_auc`` in ``metrics.json`` would look magnificent.
"""

from __future__ import annotations

import json
import math
import random
import shutil
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "tools"))

import check_metrics  # noqa: E402  (the gate's own thresholds, not a copy of them)
from ml import explain, train  # noqa: E402
from ml.features import build_features  # noqa: E402

SCHEMA_PATH = REPO_ROOT / "data" / "schema.sql"
ARTIFACT_DIR = REPO_ROOT / "ml" / "artifacts"
METRICS_PATH = ARTIFACT_DIR / "metrics.json"
MODEL_PATH = ARTIFACT_DIR / "model.joblib"
SHAP_SAMPLE_PATH = ARTIFACT_DIR / "shap_sample.parquet"

REQUIRED_METRICS = ("auc", "calibration_error", "lift_at_10", "latent_auc")
DRIVER_KEYS = {"feature", "label", "contribution", "value", "direction"}

# Small enough that the fixture trains in a second, still regularised.
TINY_PARAMS = {"num_leaves": 7, "min_child_samples": 8, "learning_rate": 0.1}
TINY_ROUNDS = 40


# --------------------------------------------------------------------------------------
# the committed artifacts: what ships
# --------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def committed_metrics() -> dict:
    assert METRICS_PATH.exists(), (
        f"{METRICS_PATH} is missing; ml/train.py must be run and its artifacts committed"
    )
    return json.loads(METRICS_PATH.read_text(encoding="utf-8"))


def test_metrics_json_has_the_four_finite_keys(committed_metrics: dict) -> None:
    missing = [key for key in REQUIRED_METRICS if key not in committed_metrics]
    assert not missing, f"metrics.json is missing {missing}"
    for key in REQUIRED_METRICS:
        value = committed_metrics[key]
        assert isinstance(value, (int, float)) and not isinstance(value, bool), (
            f"{key} is not a number: {value!r}"
        )
        assert math.isfinite(float(value)), f"{key} is not finite: {value!r}"


def test_committed_metrics_pass_the_model_gate() -> None:
    # Uses tools/check_metrics.py itself, so the thresholds live in exactly one place.
    assert check_metrics.main(str(METRICS_PATH)) == 0


def test_committed_auc_sits_inside_the_gate_band_and_below_the_ceiling(
    committed_metrics: dict,
) -> None:
    auc = float(committed_metrics["auc"])
    latent = float(committed_metrics["latent_auc"])
    assert check_metrics.AUC_MIN <= auc <= check_metrics.AUC_MAX
    assert auc <= latent + check_metrics.LATENT_SLACK, (
        f"auc={auc:.4f} beats the world's latent ceiling {latent:.4f} by more than "
        f"{check_metrics.LATENT_SLACK}: that is leakage, not skill"
    )
    assert float(committed_metrics["calibration_error"]) < check_metrics.CAL_MAX
    assert float(committed_metrics["lift_at_10"]) >= check_metrics.LIFT_MIN


def test_committed_split_is_temporal_and_disjoint(committed_metrics: dict) -> None:
    split = committed_metrics["split"]
    assert split["quantile"] == pytest.approx(train.SPLIT_QUANTILE)
    assert split["train_rows"] > 0 and split["validation_rows"] > 0
    train_max = datetime.fromisoformat(split["train_max_closed_at"])
    validation_min = datetime.fromisoformat(split["validation_min_closed_at"])
    assert train_max <= validation_min, (
        "the temporal split overlaps: a validation lead closed before a training lead"
    )
    # A random split would put the same close date on both sides; 80/20 of the same population
    # is what makes the fractions recognisable.
    total = split["train_rows"] + split["validation_rows"]
    assert split["train_rows"] / total == pytest.approx(split["quantile"], abs=0.01)


def test_committed_metrics_were_scored_on_the_whole_open_pipeline(
    committed_metrics: dict,
) -> None:
    by_stage = committed_metrics["scored_leads_by_stage"]
    assert set(by_stage) <= set(train.OPEN_STATUSES), (
        f"a terminal status was scored: {sorted(set(by_stage) - set(train.OPEN_STATUSES))}"
    )
    assert set(by_stage) == set(train.OPEN_STATUSES), (
        "every open stage must be scored, or the pipeline screen has holes"
    )
    assert committed_metrics["scored_leads"] == sum(by_stage.values())


def test_committed_model_reloads_and_scores_without_nan() -> None:
    bundle = explain.load_bundle(MODEL_PATH)
    assert bundle["model_version"] == json.loads(
        METRICS_PATH.read_text(encoding="utf-8")
    )["model_version"]
    assert list(bundle["features"]) == list(explain.FEATURES)

    # A row built from the model's own categorical levels, so the test does not depend on the
    # particular vocabulary of the generated world.
    row: dict[str, object] = {feature: 0 for feature in explain.NUMERIC_FEATURES}
    for feature in explain.CATEGORICAL_FEATURES:
        row[feature] = bundle["categories"][feature][0]
    probabilities = train.predict(bundle, row)
    assert probabilities.shape == (1,)
    assert np.isfinite(probabilities).all()
    assert 0.0 <= float(probabilities[0]) <= 1.0


def test_committed_shap_sample_is_small_and_tidy() -> None:
    assert SHAP_SAMPLE_PATH.exists(), f"{SHAP_SAMPLE_PATH} is missing"
    sample = pd.read_parquet(SHAP_SAMPLE_PATH)
    assert not sample.empty
    assert set(sample.columns) >= {"lead_id", "feature", "label", "value", "contribution",
                                   "direction"}
    assert sample["contribution"].notna().all()
    assert np.isfinite(sample["contribution"].to_numpy()).all()
    assert set(sample["feature"]) == set(explain.FEATURES)
    assert set(sample["direction"]) <= {"increases", "decreases"}
    leads = sample["lead_id"].nunique()
    assert leads <= train.SHAP_SAMPLE_LEADS, (
        f"shap_sample.parquet holds {leads} leads; it is committed, so it must stay small"
    )
    assert len(sample) == leads * len(explain.FEATURES)
    assert SHAP_SAMPLE_PATH.stat().st_size < 5_000_000, "the committed SHAP sample is too big"


def test_driver_mapping_covers_the_contract_and_renders_the_pitch_wording() -> None:
    for feature in explain.FEATURES:
        assert feature in explain.FEATURE_LABELS, f"no business label for {feature}"
        assert explain.FEATURE_LABELS[feature]
    # The two examples the contract quotes, verbatim in spirit: hours and days, with the unit
    # immediately after the number.
    assert explain.describe_value("first_response_hours", 11.0) == "11 hours to first response"
    assert explain.describe_value("days_since_last_initiative", 94) == (
        "94 days since the last initiative"
    )
    # "Not measured" is never rendered as a zero.
    assert explain.describe_value("first_response_hours", float("nan")) == "no response yet"
    assert explain.describe_value("nps_last", float("nan")) == "never surveyed"
    assert explain.describe_value("owner_win_rate_180d", float("nan")) == (
        "rep has no recent closures"
    )


# --------------------------------------------------------------------------------------
# bands: the cut-offs are the contract
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("probability", "band"),
    [
        (0.0, "low"),
        (0.199, "low"),
        (0.20, "medium"),
        (0.399, "medium"),
        (0.40, "high"),
        (0.599, "high"),
        (0.60, "critical"),
        (1.0, "critical"),
    ],
)
def test_band_cutoffs_are_low_020_medium_040_high_060(probability: float, band: str) -> None:
    assert train.band_for(probability) == band


def test_bands_are_monotone_in_probability() -> None:
    ranks = {name: rank for rank, name in enumerate(train.BANDS)}
    grid = np.linspace(0.0, 1.0, 1001)
    bands = [train.band_for(float(p)) for p in grid]
    for earlier, later in zip(bands, bands[1:]):
        assert ranks[later] >= ranks[earlier], (
            f"band went backwards from {earlier} to {later} on a rising probability"
        )
    assert {"low", "medium", "high", "critical"} <= set(bands)


# --------------------------------------------------------------------------------------
# metric helpers
# --------------------------------------------------------------------------------------


def test_calibration_error_is_zero_for_a_perfect_forecast() -> None:
    # Two bins, perfectly calibrated: 20% of 1s in the 0.2 bin, 80% of 1s in the 0.8 bin.
    labels = np.array([0] * 80 + [1] * 20 + [0] * 20 + [1] * 80)
    probabilities = np.array([0.2] * 100 + [0.8] * 100)
    assert train.expected_calibration_error(labels, probabilities) == pytest.approx(0.0, abs=1e-12)


def test_calibration_error_catches_an_overconfident_model() -> None:
    labels = np.array([0] * 90 + [1] * 10)
    probabilities = np.array([0.9] * 100)
    # predicted 0.9, observed 0.1 -> error 0.8
    assert train.expected_calibration_error(labels, probabilities) == pytest.approx(0.8)


def test_lift_is_one_for_a_useless_ranking_and_above_one_for_a_good_one() -> None:
    balanced = np.array([1, 0] * 50)  # base rate 0.5
    assert train.lift_at_fraction(balanced, np.full(100, 0.5)) == pytest.approx(1.0)

    labels = np.array([1] * 50 + [0] * 50)
    # all positives at the top: the top decile wins every time, so lift = 1 / base rate = 2
    perfect = np.array([1.0] * 50 + [0.0] * 50)
    assert train.lift_at_fraction(labels, perfect) == pytest.approx(2.0)


def test_temporal_split_rejects_an_overlapping_frame() -> None:
    frame = pd.DataFrame(
        {
            "closed_at": pd.to_datetime(
                ["2024-01-01", "2024-02-01", "2024-03-01", "2024-04-01"]
            ),
            "won": [0, 1, 0, 1],
        }
    )
    split = train.temporal_split(frame, quantile=0.5)
    assert split.train["closed_at"].max() < split.validation["closed_at"].min()

    # A quantile outside (0, 1) is a configuration error, not a silent 50/50 fallback.
    with pytest.raises(ValueError):
        train.temporal_split(frame, quantile=1.0)


# --------------------------------------------------------------------------------------
# a tiny planted world, put through features and training end to end
# --------------------------------------------------------------------------------------

_INDUSTRIES = ("manifattura", "servizi", "retail", "tech")
_REGIONS = ("nord-ovest", "nord-est", "centro", "sud", "isole")
_SOURCES = ("inbound", "outbound", "referral", "partner", "event")


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value))


def _build_tiny_world(db_path: Path, seed: int = 7) -> Path:
    """Create and populate a small database from ``data/schema.sql``.

    Shaped like the real world but not a copy of it: closed qualified initiatives with a
    planted, learnable win signal, open initiatives at every open stage, and a few closed
    leads that never qualified (so they carry a feature row but no label).
    """
    rng = random.Random(seed)
    companies: list[tuple] = []
    leads: list[tuple] = []
    outcomes: list[tuple] = []
    interactions: list[tuple] = []

    start = datetime(2022, 1, 3)
    for index in range(24):
        company_id = f"C-{index:03d}"
        companies.append(
            (
                company_id,
                f"Azienda {index:03d} Srl",
                f"IT{index:011d}",
                _REGIONS[index % len(_REGIONS)],
                "Milano",
                _INDUSTRIES[index % len(_INDUSTRIES)],
                20 + 13 * index,
                (start + timedelta(days=7 * index)).isoformat(timespec="seconds"),
                f"rep-{index % 5}",
            )
        )

        for round_index in range(7):
            created = datetime(2023, 1, 5) + timedelta(
                days=70 * round_index + 3 * index, hours=6 * round_index
            )
            qualified_at = created + timedelta(days=4)
            proposal_at = created + timedelta(days=9)
            closed_at = qualified_at + timedelta(days=20)
            amount = 10_000.0 + 5_000.0 * rng.randrange(0, 20)
            discount = float(rng.choice((0.0, 5.0, 10.0, 15.0)))
            hours = rng.choice((None, 0.5, 2.0, 5.0, 11.0, 30.0, 72.0))
            meetings = rng.randrange(0, 4)
            latency = 60.0 if hours is None else hours
            logit = (
                1.1
                - 0.35 * math.log1p(latency)
                + 0.45 * meetings
                - 0.02 * discount
                - amount / 400_000.0
                + rng.gauss(0.0, 0.25)
            )
            probability = _sigmoid(logit)
            won = 1 if rng.random() < probability else 0
            lead_id = f"L-{index:03d}-{round_index}"
            leads.append(
                (
                    lead_id,
                    company_id,
                    created.isoformat(timespec="seconds"),
                    "won" if won else "lost",
                    rng.choice(_SOURCES),
                    f"rep-{index % 5}",
                    hours,
                    (created + timedelta(hours=hours)).isoformat(timespec="seconds")
                    if hours is not None
                    else None,
                    qualified_at.isoformat(timespec="seconds"),
                    proposal_at.isoformat(timespec="seconds"),
                    closed_at.isoformat(timespec="seconds"),
                    None if won else "price",
                    amount,
                    discount,
                )
            )
            outcomes.append(
                (
                    lead_id,
                    qualified_at.isoformat(timespec="seconds"),
                    won,
                    closed_at.isoformat(timespec="seconds"),
                    probability,
                )
            )
            for meeting_index in range(meetings):
                interactions.append(
                    (
                        f"X-{lead_id}-{meeting_index}",
                        company_id,
                        lead_id,
                        "meeting",
                        "outbound",
                        (created + timedelta(hours=6 * (meeting_index + 1))).isoformat(
                            timespec="seconds"
                        ),
                        1,
                    )
                )

    # Open initiatives: one per stage, spread across companies.  A `new`/`contacted` lead is
    # scored at creation; `qualified` and `proposal` at their stage timestamp.
    stages = ("new", "contacted", "qualified", "proposal")
    for index in range(20):
        stage = stages[index % len(stages)]
        created = datetime(2025, 9, 1) + timedelta(days=3 * index)
        qualified_at = created + timedelta(days=3) if stage in ("qualified", "proposal") else None
        proposal_at = created + timedelta(days=8) if stage == "proposal" else None
        lead_id = f"L-OPEN-{index:03d}"
        leads.append(
            (
                lead_id,
                f"C-{index % 24:03d}",
                created.isoformat(timespec="seconds"),
                stage,
                _SOURCES[index % len(_SOURCES)],
                f"rep-{index % 5}",
                2.0,
                None,
                qualified_at.isoformat(timespec="seconds") if qualified_at else None,
                proposal_at.isoformat(timespec="seconds") if proposal_at else None,
                None,
                None,
                15_000.0 + 1_000.0 * index,
                0.0,
            )
        )

    # Closed but never qualified: a feature row with no label, exactly the censored shape the
    # trainer must exclude and never score.
    for index in range(3):
        lead_id = f"L-LEGACY-{index}"
        created = datetime(2023, 5, 1) + timedelta(days=11 * index)
        leads.append(
            (
                lead_id,
                f"C-{index:03d}",
                created.isoformat(timespec="seconds"),
                "lost",
                "outbound",
                f"rep-{index % 5}",
                36.0,
                None,
                None,
                None,
                (created + timedelta(days=9)).isoformat(timespec="seconds"),
                "silent",
                5_000.0,
                0.0,
            )
        )

    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    connection = sqlite3.connect(str(db_path))
    try:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        connection.executemany(
            "INSERT INTO companies (id, name, vat_number, region, city, industry, employees, "
            "created_at, owner_rep) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            companies,
        )
        connection.executemany(
            "INSERT INTO leads (id, company_id, created_at, status, source, owner_rep, "
            "first_response_hours, first_response_at, qualified_at, proposal_at, closed_at, "
            "lost_reason, amount_arr, discount_pct) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            leads,
        )
        connection.executemany(
            "INSERT INTO interactions (id, company_id, lead_id, kind, direction, occurred_at, "
            "answered) VALUES (?, ?, ?, ?, ?, ?, ?)",
            interactions,
        )
        connection.executemany(
            "INSERT INTO lead_outcomes (lead_id, snapshot_date, won, closed_at, latent_p) "
            "VALUES (?, ?, ?, ?, ?)",
            outcomes,
        )
        build_features(connection)
        connection.commit()
    finally:
        connection.close()
    return db_path


@pytest.fixture(scope="module")
def trained(tmp_path_factory: pytest.TempPathFactory) -> dict:
    """One end-to-end training run on the tiny world, shared by the structural tests."""
    directory = tmp_path_factory.mktemp("tiny-world")
    db_path = _build_tiny_world(directory / "demo.db")
    artifact_dir = directory / "artifacts"
    metrics = train.run(
        db_path=db_path,
        artifact_dir=artifact_dir,
        rounds=TINY_ROUNDS,
        shap_leads=40,
        params=TINY_PARAMS,
        verbose=False,
    )
    return {
        "db_path": db_path,
        "artifact_dir": artifact_dir,
        "metrics": metrics,
        "metrics_path": artifact_dir / "metrics.json",
        "model_path": artifact_dir / "model.joblib",
        "shap_path": artifact_dir / "shap_sample.parquet",
    }


def _scores(db_path: Path) -> list[sqlite3.Row]:
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    try:
        return list(connection.execute("SELECT * FROM lead_scores"))
    finally:
        connection.close()


def _open_lead_ids(db_path: Path) -> set[str]:
    placeholders = ", ".join("?" for _ in train.OPEN_STATUSES)
    connection = sqlite3.connect(str(db_path))
    try:
        return {
            row[0]
            for row in connection.execute(
                f"SELECT id FROM leads WHERE status IN ({placeholders})", train.OPEN_STATUSES
            )
        }
    finally:
        connection.close()


def test_tiny_world_training_produces_finite_metrics(trained: dict) -> None:
    metrics = trained["metrics"]
    on_disk = json.loads(trained["metrics_path"].read_text(encoding="utf-8"))
    assert on_disk == metrics, "the returned metrics and metrics.json disagree"
    for key in REQUIRED_METRICS:
        assert key in metrics
        assert math.isfinite(float(metrics[key]))
    assert 0.0 <= float(metrics["auc"]) <= 1.0
    assert 0.0 <= float(metrics["calibration_error"]) <= 1.0
    assert float(metrics["lift_at_10"]) >= 0.0


def test_tiny_world_split_is_temporal_and_disjoint(trained: dict) -> None:
    split = trained["metrics"]["split"]
    assert split["train_rows"] > 0 and split["validation_rows"] > 0
    train_max = datetime.fromisoformat(split["train_max_closed_at"])
    validation_min = datetime.fromisoformat(split["validation_min_closed_at"])
    assert train_max <= validation_min
    # 24 companies x 7 closed initiatives are labelled; the three legacy losses are not.
    assert split["train_rows"] + split["validation_rows"] == 24 * 7


def test_tiny_world_predictions_are_never_nan(trained: dict) -> None:
    bundle = explain.load_bundle(trained["model_path"])
    connection = sqlite3.connect(str(trained["db_path"]))
    try:
        labelled = pd.read_sql_query(
            "SELECT f.*, o.closed_at FROM lead_features AS f "
            "JOIN lead_outcomes AS o ON o.lead_id = f.lead_id",
            connection,
        )
    finally:
        connection.close()
    probabilities = train.predict(bundle, labelled)
    assert probabilities.shape == (len(labelled),)
    assert np.isfinite(probabilities).all()
    assert (probabilities >= 0.0).all() and (probabilities <= 1.0).all()


def test_every_open_lead_has_exactly_one_score_row(trained: dict) -> None:
    db_path = trained["db_path"]
    rows = _scores(db_path)
    scored = [row["lead_id"] for row in rows]
    open_ids = _open_lead_ids(db_path)
    assert open_ids, "the fixture has no open leads -- the test would be vacuous"
    assert len(scored) == len(set(scored)), "a lead was scored twice"
    assert set(scored) == open_ids, (
        f"unscored open leads: {sorted(open_ids - set(scored))[:5]}; "
        f"scored non-open leads: {sorted(set(scored) - open_ids)[:5]}"
    )
    # The three legacy losses are closed: they must not appear in the pipeline screen.
    assert not {"L-LEGACY-0", "L-LEGACY-1", "L-LEGACY-2"} & set(scored)
    for row in rows:
        assert 0.0 <= float(row["probability"]) <= 1.0
        assert row["band"] in train.BANDS
        assert float(row["expected_value"]) == pytest.approx(
            float(row["probability"]) * float(row["amount_arr"])
        )


def test_scores_are_populated_in_every_open_stage(trained: dict) -> None:
    placeholders = ", ".join("?" for _ in train.OPEN_STATUSES)
    connection = sqlite3.connect(str(trained["db_path"]))
    try:
        stages = {
            row[0]
            for row in connection.execute(
                "SELECT DISTINCT f.stage_at_scoring FROM lead_scores AS s "
                "JOIN lead_features AS f ON f.lead_id = s.lead_id "
                "JOIN leads AS l ON l.id = s.lead_id "
                f"WHERE l.status IN ({placeholders})",
                train.OPEN_STATUSES,
            )
        }
    finally:
        connection.close()
    assert stages == set(train.OPEN_STATUSES)


def test_scored_bands_are_monotone_in_probability(trained: dict) -> None:
    ranks = {name: rank for rank, name in enumerate(train.BANDS)}
    rows = sorted(_scores(trained["db_path"]), key=lambda row: float(row["probability"]))
    ordered = [ranks[row["band"]] for row in rows]
    for earlier, later in zip(ordered, ordered[1:]):
        assert later >= earlier, (
            "a higher probability got a lower band; the cut-offs are not monotone"
        )
    for row in rows:
        assert row["band"] == train.band_for(float(row["probability"]))


def test_drivers_json_parses_and_holds_at_most_three_drivers(trained: dict) -> None:
    for row in _scores(trained["db_path"]):
        drivers = json.loads(row["drivers_json"])
        assert isinstance(drivers, list)
        assert 0 < len(drivers) <= train.DRIVER_LIMIT
        for driver in drivers:
            assert set(driver) == DRIVER_KEYS
            assert isinstance(driver["feature"], str) and driver["feature"] in explain.FEATURES
            assert isinstance(driver["label"], str) and driver["label"]
            assert isinstance(driver["value"], str) and driver["value"]
            assert driver["direction"] in ("increases", "decreases")
            assert math.isfinite(float(driver["contribution"]))
        # ranked by absolute contribution, biggest first
        magnitudes = [abs(float(driver["contribution"])) for driver in drivers]
        assert magnitudes == sorted(magnitudes, reverse=True)


def test_shap_explanations_are_deterministic(trained: dict) -> None:
    bundle = explain.load_bundle(trained["model_path"])
    connection = sqlite3.connect(str(trained["db_path"]))
    connection.row_factory = sqlite3.Row
    try:
        # open leads, because those are the rows the scorer also explained
        rows = [
            dict(row)
            for row in connection.execute(
                "SELECT f.* FROM lead_features AS f JOIN lead_scores AS s "
                "ON s.lead_id = f.lead_id ORDER BY f.lead_id LIMIT 3"
            )
        ]
    finally:
        connection.close()
    assert rows
    first = [explain.top_drivers(bundle, row) for row in rows]
    second = [explain.top_drivers(bundle, row) for row in rows]
    assert first == second, "SHAP drivers changed between two calls on the same row"
    # and the same drivers the scorer stored, since both go through this module
    stored = {
        row["lead_id"]: json.loads(row["drivers_json"]) for row in _scores(trained["db_path"])
    }
    for row, drivers in zip(rows, first):
        assert stored[row["lead_id"]] == drivers


def test_latent_p_is_not_a_feature(trained: dict) -> None:
    bundle = explain.load_bundle(trained["model_path"])
    assert "latent_p" not in bundle["features"]
    assert "latent_p" not in explain.FEATURES
    assert "latent_p" not in explain.NUMERIC_FEATURES
    assert "latent_p" not in explain.CATEGORICAL_FEATURES
    assert "latent_p" not in bundle["model"].feature_name()
    # Nor is the row identifier, nor the provenance timestamp of the response duration.
    assert "lead_id" not in bundle["features"]
    assert "snapshot_date" not in bundle["features"]
    assert "first_response_at" not in bundle["features"]


def test_scrambling_latent_p_does_not_move_a_single_prediction(
    trained: dict, tmp_path: Path
) -> None:
    """The behavioural leakage test: ``latent_p`` may only be audited, never learned from."""
    db_path = tmp_path / "scrambled.db"
    shutil.copyfile(trained["db_path"], db_path)

    connection = sqlite3.connect(str(db_path))
    try:
        connection.execute("UPDATE lead_outcomes SET latent_p = 0.999")
        connection.commit()
    finally:
        connection.close()

    scrambled = train.run(
        db_path=db_path,
        artifact_dir=tmp_path / "artifacts",
        rounds=TINY_ROUNDS,
        shap_leads=20,
        params=TINY_PARAMS,
        verbose=False,
    )

    before = {row["lead_id"]: float(row["probability"]) for row in _scores(trained["db_path"])}
    after = {row["lead_id"]: float(row["probability"]) for row in _scores(db_path)}
    assert before and set(before) == set(after)
    for lead_id, probability in before.items():
        # Bit-for-bit: the features are identical and the fit is deterministic.
        assert after[lead_id] == probability, (
            f"scrambling latent_p moved lead {lead_id} from {probability} to {after[lead_id]}: "
            "the generating probability leaked into the features"
        )

    # The scramble did land, so the equality above is meaningful: the audit metric moved while
    # the model did not.
    assert scrambled["latent_auc"] == pytest.approx(0.5, abs=1e-9)
    assert scrambled["auc"] == pytest.approx(trained["metrics"]["auc"])


@pytest.mark.parametrize("failure", ["model", "shap", "metrics", "scores", "run", "publish", "commit"])
def test_failed_retraining_preserves_generation(trained, tmp_path, monkeypatch, failure):
    db = tmp_path / "demo.db"
    artifacts = tmp_path / "artifacts"
    shutil.copyfile(trained["db_path"], db)
    shutil.copytree(trained["artifact_dir"], artifacts)
    before = {path.name: path.read_bytes() for path in artifacts.iterdir()}
    with sqlite3.connect(db) as connection:
        old_scores = connection.execute("SELECT * FROM lead_scores").fetchall()
        old_runs = connection.execute("SELECT * FROM model_runs").fetchall()

    def fail(*args, **kwargs):
        raise OSError("injected write failure")

    if failure == "model":
        monkeypatch.setattr(train.joblib, "dump", fail)
    elif failure == "shap":
        monkeypatch.setattr(pd.DataFrame, "to_parquet", fail)
    elif failure == "metrics":
        original = Path.open
        def open_path(path, *args, **kwargs):
            if path.name == "metrics.json" and args and args[0] == "w":
                fail()
            return original(path, *args, **kwargs)
        monkeypatch.setattr(Path, "open", open_path)
    elif failure in ("scores", "run"):
        name = "write_scores" if failure == "scores" else "record_model_run"
        original = getattr(train, name)
        def write_then_fail(*args, **kwargs):
            original(*args, **kwargs)
            fail()
        monkeypatch.setattr(train, name, write_then_fail)
    elif failure == "publish":
        original = Path.replace
        def replace(path, target):
            if path.name == "metrics.json":
                fail()
            return original(path, target)
        monkeypatch.setattr(Path, "replace", replace)
    else:
        class FailedCommit(sqlite3.Connection):
            def commit(self):
                fail()
        monkeypatch.setattr(train, "connect", lambda path: sqlite3.connect(path, factory=FailedCommit))

    with pytest.raises(OSError, match="injected"):
        train.run(db, artifacts, rounds=TINY_ROUNDS, shap_leads=10,
                  params=TINY_PARAMS, verbose=False)
    assert {path.name: path.read_bytes() for path in artifacts.iterdir()} == before
    with sqlite3.connect(db) as connection:
        assert connection.execute("SELECT * FROM lead_scores").fetchall() == old_scores
        assert connection.execute("SELECT * FROM model_runs").fetchall() == old_runs
