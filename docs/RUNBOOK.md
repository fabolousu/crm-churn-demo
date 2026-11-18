# Demo runbook

For the person driving the laptop. Five minutes of demo, about two minutes of setup.

## Pre-flight (do this before the room, once)

```powershell
# 1. Dependencies (first time only)
python -m pip install -r requirements.txt
pnpm --dir web install

# 2. Data, features, model, scores — deterministic from seed 42
python tools/run_pipeline.py

# 3. Confirm the model gate before you trust any number on screen
python tools/check_metrics.py
```

Expected gate output: `ok metrics: auc=0.773 calibration=0.010 lift@10=2.26 (ceiling 0.789)`.
If it fails, **do not demo**. The numbers on screen come from that artifact.

## Start it (two terminals)

**Terminal 1 — API**

```powershell
python -m uvicorn api.app:app --host 127.0.0.1 --port 8000
```

**Terminal 2 — UI**

`VITE_API_BASE` is a **build-time** variable. Set it, then build, then serve:

```powershell
$env:VITE_API_BASE = "http://127.0.0.1:8000"
pnpm --dir web build
pnpm --dir web preview --port 5173
```

Open `http://127.0.0.1:5173`.

> Fixture mode: if you skip `VITE_API_BASE`, the UI renders committed fixtures with the
> same numbers. That is the fallback if the API misbehaves on stage — the screens still
> work, and you say so if asked.

## Pre-warm (30 seconds before you start)

Click through everything once, in this order — the first hit loads the model bundle:

1. `/api/health` in a browser tab → `{"status":"ok","model_version":"lead-win-lgbm-v1"}`
2. The queue screen
3. Farina Vetri's lead page
4. Toggle the exec-sponsor lever
5. The portfolio screen

Then reload the queue so the demo starts on a warm page.

## The five minutes

Follow `docs/PITCH.md`. The beats and the numbers on each screen match:

| Time | Screen | Anchor number |
|---|---|---|
| 0:30 | Queue | €720.7M open · €282.0M expected · 19,752 leads |
| 1:30 | Top lead (Moretti Componenti) | 59.9% · €142,297 EV |
| 2:30 | Leverage sort (Russo Industrie) | 50.5% → 60.7% · +10.2 pts · rank 170 → 71 |
| 3:30 | Act | probability updates, lead re-ranks |
| 4:20 | Portfolio | calibration 0.0104 · stability Watch 0.171 |

## Offline check

Disconnect Wi-Fi (or turn off the adapter), reload the queue, click into a lead, toggle the
lever. Everything above must still work. If anything breaks, it was reaching the network —
find it before the room does.

## If something fails on stage

| Symptom | Move |
|---|---|
| UI shows stale/blank data | The API is down → restart Terminal 1, reload. Fixtures still work. |
| `data/demo.db` missing | `python tools/run_pipeline.py` (~2 min) — do not run this in the room if you can avoid it |
| A number is questioned that isn't on screen | Open `ml/artifacts/metrics.json`. Never estimate. |
| Queue looks different from rehearsal | Scores are deterministic from seed 42; a difference means the DB was regenerated with another seed |

## Known gaps (state them if asked; don't paper over them)

- No drift **trend** chart: the demo has one snapshot, so the stability panel shows
  holdout-vs-train, not production drift over time.
- No `docker compose`: two terminals instead. `compose.yaml` is not written yet.
- Discount is a **what-if, not an action**: `ActionRequest` carries no discount value, so it
  cannot be committed, and the leverage ranking deliberately excludes it (`max_leverage` counts
  only committable levers). `discount_upside` is shown separately and labelled as not actionable.
  If asked: the model says price-sensitive accounts churn more; it does not say un-discounting a
  signed deal saves it.
- The lever's **committable** median is **+0.43 points** and the p90 is **+3.41**; Russo's
  +10.2 is a tail case, not the norm, and 2,845 of 19,752 leads have no positive committable
  move at all. Say the median out loud — it is the credible number, and it is why the
  leverage sort is the product.
- `discount_upside` (the old Rossi +19.5) is a what-if the model can score but no rep can
  commit. Show it only in the what-if lane, never as a recommendation.
