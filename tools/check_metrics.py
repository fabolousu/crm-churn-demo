#!/usr/bin/env python3
"""Model quality gate — single source of truth for the thresholds.

Used by CI and by tools/review.ps1. Two rules, and the second is the interesting one:

1. **Absolute band.** AUC must land in [AUC_MIN, AUC_MAX], calibration below CAL_MAX, lift
   above LIFT_MIN. A demo below the floor is not worth showing; a model above the ceiling is
   suspicious.

2. **Latent ceiling.** The synthetic world is generated from a known hazard, so the
   achievable skill is measurable: `latent_auc` bytes the AUC of the generating probability
   against the realised outcome. A model cannot legitimately beat it. If the reported AUC
   exceeds `latent_auc + LATENT_SLACK`, the model has seen something the generator did not
   intend it to see — leakage, not brilliance. This check is only meaningful because the
   data is synthetic, and it is the single strongest guard in the build.

`latent_auc` is optional so the gate still works before the training lane records it, but a
missing value is reported as a warning rather than silently skipped.

Exit codes: 0 pass, 1 fail (band, calibration, lift, or leakage ceiling), 2 unusable artifact.
"""

from __future__ import annotations

import json
import pathlib
import sys

AUC_MIN = 0.75
AUC_MAX = 0.90
CAL_MAX = 0.05
LIFT_MIN = 2.0
LATENT_SLACK = 0.02

REQUIRED = ("auc", "calibration_error", "lift_at_10")


def main(path: str = "ml/artifacts/metrics.json") -> int:
    artifact = pathlib.Path(path)
    if not artifact.exists():
        print(f"FAIL metrics: {artifact} missing")
        return 2

    try:
        metrics = json.loads(artifact.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"FAIL metrics: {artifact} is not valid JSON ({exc})")
        return 2

    missing = [key for key in REQUIRED if key not in metrics]
    if missing:
        print(f"FAIL metrics: missing {missing}")
        return 2

    auc = float(metrics["auc"])
    calibration = float(metrics["calibration_error"])
    lift = float(metrics["lift_at_10"])
    latent = metrics.get("latent_auc")

    failures: list[str] = []

    if not AUC_MIN <= auc <= AUC_MAX:
        side = "below bar" if auc < AUC_MIN else "above bar"
        failures.append(f"auc={auc:.3f} outside [{AUC_MIN}, {AUC_MAX}] ({side})")
    if calibration >= CAL_MAX:
        failures.append(f"calibration_error={calibration:.3f} >= {CAL_MAX}")
    if lift < LIFT_MIN:
        failures.append(f"lift_at_10={lift:.2f} < {LIFT_MIN}")

    if latent is None:
        print("warn metrics: latent_auc absent — the leakage ceiling cannot be checked")
    else:
        ceiling = float(latent) + LATENT_SLACK
        if auc > ceiling:
            failures.append(
                f"auc={auc:.3f} exceeds the latent ceiling {float(latent):.3f} "
                f"(+{LATENT_SLACK}) — this is leakage, not skill"
            )

    if failures:
        for failure in failures:
            print(f"FAIL metrics: {failure}")
        return 1

    ceiling_note = "" if latent is None else f" (ceiling {float(latent):.3f})"
    print(
        f"ok metrics: auc={auc:.3f} calibration={calibration:.3f} "
        f"lift@10={lift:.2f}{ceiling_note}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
