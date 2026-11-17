#!/usr/bin/env python3
"""Model quality gate — single source of truth for the thresholds.

Used by CI and by tools/review.ps1. An AUC above AUC_MAX on synthetic data is treated as
leakage, not brilliance: the generating process in docs/LABEL.md caps achievable skill, so
a suspiciously high score means the label leaked into the features.

Exit codes: 0 pass, 1 fail (below bar, above bar, or unreadable artifact).
"""

from __future__ import annotations

import json
import pathlib
import sys

AUC_MIN = 0.75
AUC_MAX = 0.90
CAL_MAX = 0.05
LIFT_MIN = 2.0

REQUIRED = ("auc", "calibration_error", "lift_at_10")


def main(path: str = "ml/artifacts/metrics.json") -> int:
    artifact = pathlib.Path(path)
    if not artifact.exists():
        print(f"FAIL metrics: {artifact} missing")
        return 1

    try:
        metrics = json.loads(artifact.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"FAIL metrics: {artifact} is not valid JSON ({exc})")
        return 1

    missing = [key for key in REQUIRED if key not in metrics]
    if missing:
        print(f"FAIL metrics: missing {missing}")
        return 1

    auc = float(metrics["auc"])
    calibration = float(metrics["calibration_error"])
    lift = float(metrics["lift_at_10"])

    failures: list[str] = []
    if not AUC_MIN <= auc <= AUC_MAX:
        side = "below bar" if auc < AUC_MIN else "above bar — suspect leakage"
        failures.append(f"auc={auc:.3f} outside [{AUC_MIN}, {AUC_MAX}] ({side})")
    if calibration >= CAL_MAX:
        failures.append(f"calibration_error={calibration:.3f} >= {CAL_MAX}")
    if lift < LIFT_MIN:
        failures.append(f"lift_at_10={lift:.2f} < {LIFT_MIN}")

    if failures:
        for failure in failures:
            print(f"FAIL metrics: {failure}")
        return 1

    print(
        f"ok metrics: auc={auc:.3f} calibration={calibration:.3f} lift@10={lift:.2f}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
