"""Build ``data/demo.slim.db`` from ``data/demo.db`` for Vercel serverless serving.

Keeps the top 2,000 open leads by ``expected_value``, their companies,
``lead_features``/``lead_scores``/``lead_outcomes``, all ``model_runs``, and builds
a ``lead_leverage`` table with precomputed leverage deltas so the serverless function
does NOT import numpy/pandas/lightgbm at all.

Run this locally (full dev environment required) before committing the slim DB:

    python scripts/build_slim_db.py

Target size: < 25 MB.
"""

from __future__ import annotations

import os
import pathlib
import sqlite3
import sys
from contextlib import closing

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

SRC_DB = REPO_ROOT / "data" / "demo.db"
DST_DB = REPO_ROOT / "data" / "demo.slim.db"
# Build into a sibling first: a failed rebuild must never destroy the committed
# serving artifact that the deployed function is reading.
TMP_DB = DST_DB.with_name(DST_DB.name + ".tmp")
SCHEMA_SQL = REPO_ROOT / "data" / "schema.sql"
TOP_N = 2_000
OPEN_STATUSES = ("new", "contacted", "qualified", "proposal")


def _open(path: pathlib.Path) -> sqlite3.Connection:
    """Open a SQLite connection in autocommit mode (isolation_level=None)."""
    conn = sqlite3.connect(str(path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    return conn


def build_slim_db() -> None:
    if not SRC_DB.exists():
        raise FileNotFoundError(
            f"{SRC_DB} not found. Run 'python tools/run_pipeline.py' first."
        )

    # Remove a stale temp DB; the published artifact is left untouched until the end.
    if TMP_DB.exists():
        TMP_DB.unlink()

    print(f"Source DB: {SRC_DB} ({SRC_DB.stat().st_size / 1_048_576:.1f} MB)")

    # --- Step 1: create schema in destination ---
    # executescript() commits any pending transaction and runs DDL.
    # We use isolation_level=None (autocommit) so there is no implicit transaction to worry about.
    schema_sql = SCHEMA_SQL.read_text(encoding="utf-8")
    with closing(_open(TMP_DB)) as dst:
        dst.execute("PRAGMA foreign_keys = OFF")
        dst.executescript(schema_sql)

        # Also create the lead_leverage table now
        dst.executescript("""
            CREATE TABLE IF NOT EXISTS lead_leverage (
                lead_id TEXT PRIMARY KEY,
                max_leverage REAL NOT NULL,
                discount_upside REAL NOT NULL
            );
        """)

    print("Schema created.")

    # --- Step 2: load source data ---
    with closing(_open(SRC_DB)) as src:
        open_placeholders = ", ".join("?" * len(OPEN_STATUSES))

        # Top 2000 open leads by expected_value (from lead_scores)
        lead_ids_rows = src.execute(
            f"""
            SELECT s.lead_id
            FROM lead_scores AS s
            JOIN leads AS l ON l.id = s.lead_id
            WHERE l.status IN ({open_placeholders})
            ORDER BY s.expected_value DESC
            LIMIT ?
            """,
            (*OPEN_STATUSES, TOP_N),
        ).fetchall()
        lead_ids = [str(r["lead_id"]) for r in lead_ids_rows]

        assert len(lead_ids) > 0, "No open leads found in source DB"
        assert len(lead_ids) <= TOP_N, f"Expected at most {TOP_N} lead ids"

        # Leads
        lead_placeholders = ", ".join("?" * len(lead_ids))
        leads = src.execute(
            f"SELECT * FROM leads WHERE id IN ({lead_placeholders})",
            lead_ids,
        ).fetchall()

        # Company ids for those leads
        company_ids = list({str(row["company_id"]) for row in leads})
        company_placeholders = ", ".join("?" * len(company_ids))

        companies = src.execute(
            f"SELECT * FROM companies WHERE id IN ({company_placeholders})",
            company_ids,
        ).fetchall()

        # lead_features for top leads
        features = src.execute(
            f"SELECT * FROM lead_features WHERE lead_id IN ({lead_placeholders})",
            lead_ids,
        ).fetchall()

        # lead_scores for top leads
        scores = src.execute(
            f"SELECT * FROM lead_scores WHERE lead_id IN ({lead_placeholders})",
            lead_ids,
        ).fetchall()

        # lead_outcomes for top leads (may be empty for open leads, but keep any that exist)
        outcomes = src.execute(
            f"SELECT * FROM lead_outcomes WHERE lead_id IN ({lead_placeholders})",
            lead_ids,
        ).fetchall()

        # All model_runs
        model_runs = src.execute("SELECT * FROM model_runs").fetchall()

    print(f"Leads selected:    {len(lead_ids)}")
    print(f"Companies:         {len(companies)}")
    print(f"Lead features:     {len(features)}")
    print(f"Lead scores:       {len(scores)}")
    print(f"Lead outcomes:     {len(outcomes)}")
    print(f"Model runs:        {len(model_runs)}")

    # Assertions
    assert len(leads) == len(lead_ids), "Leads count mismatch"
    assert len(companies) >= 1, "No companies found"
    assert len(features) >= 1, "No lead_features found"
    assert len(scores) >= 1, "No lead_scores found"
    assert len(model_runs) >= 1, "No model_runs found"

    # --- Step 3: insert into slim DB (all in one transaction for speed) ---
    with closing(_open(TMP_DB)) as dst:
        dst.execute("PRAGMA foreign_keys = OFF")
        dst.execute("PRAGMA synchronous = OFF")
        dst.execute("BEGIN")

        # companies
        if companies:
            cols = list(companies[0].keys())
            pqs = ", ".join("?" * len(cols))
            dst.executemany(
                f"INSERT INTO companies ({', '.join(cols)}) VALUES ({pqs})",
                [tuple(row) for row in companies],
            )

        # leads
        if leads:
            cols = list(leads[0].keys())
            pqs = ", ".join("?" * len(cols))
            dst.executemany(
                f"INSERT INTO leads ({', '.join(cols)}) VALUES ({pqs})",
                [tuple(row) for row in leads],
            )

        # lead_features
        if features:
            cols = list(features[0].keys())
            pqs = ", ".join("?" * len(cols))
            dst.executemany(
                f"INSERT INTO lead_features ({', '.join(cols)}) VALUES ({pqs})",
                [tuple(row) for row in features],
            )

        # lead_scores
        if scores:
            cols = list(scores[0].keys())
            pqs = ", ".join("?" * len(cols))
            dst.executemany(
                f"INSERT INTO lead_scores ({', '.join(cols)}) VALUES ({pqs})",
                [tuple(row) for row in scores],
            )

        # lead_outcomes
        if outcomes:
            cols = list(outcomes[0].keys())
            pqs = ", ".join("?" * len(cols))
            dst.executemany(
                f"INSERT INTO lead_outcomes ({', '.join(cols)}) VALUES ({pqs})",
                [tuple(row) for row in outcomes],
            )

        # model_runs
        if model_runs:
            cols = list(model_runs[0].keys())
            pqs = ", ".join("?" * len(cols))
            dst.executemany(
                f"INSERT INTO model_runs ({', '.join(cols)}) VALUES ({pqs})",
                [tuple(row) for row in model_runs],
            )

        dst.execute("COMMIT")
        dst.execute("PRAGMA foreign_keys = ON")

    print("Data inserted.")

    # --- Step 4: compute lead_leverage ---
    print("Computing lead_leverage (this uses the full ML stack)...")
    _build_lead_leverage(lead_ids, TMP_DB)

    # --- Step 5: VACUUM, validate, then publish atomically ---
    with closing(_open(TMP_DB)) as dst:
        dst.execute("VACUUM")

    size_mb = TMP_DB.stat().st_size / 1_048_576
    assert size_mb < 25, f"Slim DB too large: {size_mb:.2f} MB (limit 25 MB)"

    # Publish only after the build has validated: the previous artifact stays intact
    # until this replace, which is atomic on the same filesystem.
    os.replace(TMP_DB, DST_DB)

    print(f"\nSlim DB published: {DST_DB}")
    print(f"Size: {size_mb:.2f} MB")
    print("OK — size within 25 MB limit.")

    # Final count verification
    with closing(_open(DST_DB)) as dst:
        for table in ("companies", "leads", "lead_features", "lead_scores", "model_runs", "lead_leverage"):
            count = dst.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  {table}: {count} rows")


def _build_lead_leverage(lead_ids: list[str], db_path: pathlib.Path) -> None:
    """Score committable levers and discount what-if for every lead using the full ML stack.

    ``max_leverage`` = max delta over committable levers (exec_sponsor_meeting,
    discovery_meeting), clipped to [0, 1].
    ``discount_upside`` = delta from setting discount_pct → 0, clipped to [0, 1].
    """
    import numpy as np
    import pandas as pd

    from ml.train import predict
    from ml.explain import load_bundle

    MODEL_PATH = REPO_ROOT / "ml" / "artifacts" / "model.joblib"
    bundle = load_bundle(str(MODEL_PATH))

    with closing(_open(db_path)) as conn:
        lead_placeholders = ", ".join("?" * len(lead_ids))
        feature_rows = conn.execute(
            f"SELECT * FROM lead_features WHERE lead_id IN ({lead_placeholders})",
            lead_ids,
        ).fetchall()

    if not feature_rows:
        print("WARNING: no feature rows found for lead_leverage computation")
        return

    print(f"  Found {len(feature_rows)} feature rows for leverage computation.")

    # Build a DataFrame
    rows_dicts = [dict(r) for r in feature_rows]
    frame = pd.DataFrame(rows_dicts)
    present_ids = [str(r["lead_id"]) for r in feature_rows]

    # Current predictions
    current = predict(bundle, frame)

    # exec_sponsor_meeting: +1 meeting, +5 NPS if measured
    sponsor = frame.copy()
    sponsor["meetings_before_scoring"] = (
        pd.to_numeric(sponsor["meetings_before_scoring"], errors="coerce").fillna(0.0) + 1.0
    )
    nps = pd.to_numeric(sponsor["nps_last"], errors="coerce")
    sponsor["nps_last"] = np.minimum(nps + 5.0, 100.0)
    best = np.maximum(np.zeros(len(frame)), predict(bundle, sponsor) - current)

    # discovery_meeting: +1 meeting
    discovery = frame.copy()
    discovery["meetings_before_scoring"] = (
        pd.to_numeric(discovery["meetings_before_scoring"], errors="coerce").fillna(0.0) + 1.0
    )
    best = np.maximum(best, predict(bundle, discovery) - current)

    # Discount upside: discount_pct → 0
    discount_var = frame.copy()
    discount_var["discount_pct"] = 0.0
    discount_delta = predict(bundle, discount_var) - current

    max_leverage = np.clip(best, 0.0, 1.0)
    discount_upside = np.clip(discount_delta, 0.0, 1.0)

    # Insert into slim DB
    with closing(_open(db_path)) as conn:
        conn.execute("BEGIN")
        conn.executemany(
            "INSERT INTO lead_leverage (lead_id, max_leverage, discount_upside) VALUES (?, ?, ?)",
            [
                (lead_id, float(ml), float(du))
                for lead_id, ml, du in zip(present_ids, max_leverage, discount_upside)
            ],
        )
        conn.execute("COMMIT")

    print(f"lead_leverage populated: {len(present_ids)} rows")


if __name__ == "__main__":
    build_slim_db()
