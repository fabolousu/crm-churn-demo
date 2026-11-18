#!/usr/bin/env python3
"""P3 runner: generate or reuse the world, materialise features, then train.

One command for the whole data path, so the demo never depends on remembering the order:

    python tools/run_pipeline.py                 # generate, build features, train
    python tools/run_pipeline.py --skip-generate # reuse data/demo.db
    python tools/run_pipeline.py --companies 2000 --seed 7

The ordering is the contract: the generator writes raw tables and `lead_outcomes` and leaves
`lead_features` empty; `ml/features.py` is the only writer of `lead_features`; `ml/train.py`
reads both and writes `ml/artifacts/` plus `lead_scores`.

Exit codes: 0 success, 1 a stage failed (the failing stage's own output is printed).
"""

from __future__ import annotations

import argparse
import pathlib
import sqlite3
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "demo.db"


def banner(step: str) -> None:
    print(f"\n=== {step} ===", flush=True)


def run(cmd: list[str], cwd: pathlib.Path = ROOT) -> None:
    started = time.time()
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        print(f"\nFAILED ({result.returncode}) after {time.time() - started:.1f}s: {' '.join(cmd)}")
        sys.exit(1)
    print(f"ok in {time.time() - started:.1f}s: {' '.join(cmd)}", flush=True)


def build_features() -> int:
    """Call the feature pipeline in-process; it is the only writer of lead_features."""
    sys.path.insert(0, str(ROOT / "ml"))
    import features  # noqa: PLC0415 — imported after sys.path is set

    if not DB.exists():
        print(f"FAILED: {DB} does not exist; run without --skip-generate")
        sys.exit(1)

    con = sqlite3.connect(DB)
    try:
        rows = features.build_features(con)
        con.commit()
    finally:
        con.close()
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="generate -> features -> train")
    parser.add_argument("--companies", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--skip-generate", action="store_true", help="reuse data/demo.db")
    args = parser.parse_args()

    if args.skip_generate:
        banner("generate (skipped)")
    else:
        banner("generate")
        # --overwrite: the runner's generate step is explicitly a regeneration. The
        # generator refuses to clobber an existing database by default (it guards against a
        # typo'd --db path destroying a tracked file), so the flag belongs here.
        run(
            [
                "python",
                "data/generator.py",
                "--companies",
                str(args.companies),
                "--seed",
                str(args.seed),
                "--overwrite",
            ]
        )

    banner("features")
    started = time.time()
    rows = build_features()
    print(f"ok in {time.time() - started:.1f}s: lead_features <- {rows} rows", flush=True)

    banner("train")
    train = ROOT / "ml" / "train.py"
    if not train.exists():
        print("FAILED: ml/train.py is missing — the training lane has not landed")
        return 1
    run(["python", str(train)])

    banner("done")
    metrics = ROOT / "ml" / "artifacts" / "metrics.json"
    if metrics.exists():
        print(metrics.read_text(encoding="utf-8").strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
