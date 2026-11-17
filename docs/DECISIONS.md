# Decisions and assumptions

Phase 0 record. Every downstream lane codes against this file; change it here first.

## Scope

| In | Out |
|---|---|
| **Italy pilot**, five macro-regions | Any other country |
| Lead-centric CRM model: company → lead → account | Real customer data |
| GBM churn model with SHAP explanations | Deep learning, LLM scoring |
| Batch scoring (nightly-equivalent) | Real-time scoring |
| Reimagined CRM UI, 5 screens | Dynamics-lookalike shell |
| Simulated retention actions that re-score | Email/telephony integrations |
| Portfolio + calibration + drift panel | ML ops infrastructure |

## Non-goals (deliberate)

Auth, deployment to a shared environment, Dataverse integration, multi-tenancy,
real-time inference, model registry. A mock that pretends to be production invites
questions it cannot answer.

## Stack

| Choice | Reason |
|---|---|
| Python 3.12, pandas, LightGBM, SHAP | Best accuracy-per-effort on tabular data; native explainability |
| FastAPI + Pydantic | The OpenAPI file is the contract, so drift checks are cheap |
| SQLite (`data/demo.db`) | Zero ops for a laptop demo; schema stays Postgres-portable |
| React + Vite + Recharts + Tailwind | Fastest path to an executive-grade UI that agents build reliably |
| `docker compose` | One command on the demo laptop |

Ports: API `8000`, web dev `5173`, composed demo `8080`.

## Determinism

- Generator seed `42`, written to `data/demo.db`.
- `ml/artifacts/model.joblib`, `metrics.json`, `shap_sample.parquet` regenerate
  byte-identically from the seed. The demo never depends on a hand-edited artifact.
- A test asserts `metrics.json` matches a checked-in reference within tolerance.

## Assumptions

1. **Churn horizon is 180 days.** Long enough to be actionable, short enough to measure.
   Assumes **annual renewal cycles**; if contracts renew monthly, both the horizon and the
   ~20% prevalence target change. See `LABEL.md`.
2. **ARR is the revenue proxy and the sort key.** Confirmed: the CFO thinks in ARR, so
   `probability × ARR` orders the queue and the portfolio rollup is in EUR.
3. **Italy, five macro-regions** (`nord-ovest`, `nord-est`, `centro`, `sud`, `isole`) with
   different base rates. One pooled model with region as a feature plus per-region
   calibration — not five models, because ~1.3k labelled churns per region is too thin.
4. **Lead status is a predictor, not the target.** The CRM's lead records (pipeline
   silence, lost leads, response time) predict account churn. Predicting *lead-win
   propensity* instead would be a second model on a different population; flagged in
   `LABEL.md` rather than silently assumed.
5. **Revenue units are EUR.** No currency conversion anywhere in the demo.
6. **Ground truth lives separately** (`account_outcomes`) from features, and
   `features.py` may not read it. Enforced by a test, not by convention.
7. **The demo is read-mostly.** The only write is a simulated action that creates an
   action row and returns a revised score.

## Open items

| Item | Owner | Blocks |
|---|---|---|
| CodeRabbit account + API key (`coderabbit auth login --api-key <key>`) | You | P4 gate only |
| CodeRabbit CLI installed; `coderabbit doctor` clean | You | P4 gate only |
| Confirm annual renewal cycles (assumption 1) | You | Nothing — changing it rewrites `LABEL.md` and the generator |
| Demo laptop OS (macOS / Windows) | You | `compose.yaml` details only |

## How the harness builds this

Contract-first: P0 (this file set) is written by the lead alone. Then lanes run
concurrently against `schema.sql` and `openapi.yaml`:

| Lane | Owns | Depends on |
|---|---|---|
| A | `data/generator.py`, `data/seed.py` | `schema.sql` |
| B1 | `ml/features.py` | `schema.sql` |
| B2 | `ml/train.py`, `ml/explain.py` | A's database, B1's features |
| C | `api/app.py` + contract tests | `openapi.yaml` |
| D | `web/` on fixtures | `openapi.yaml` |
| E | Simulated retention actions | `schema.sql` |

P3 wiring and P4 review are serialized — they are the integration points, and that is
where multi-agent builds fail.
