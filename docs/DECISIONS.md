# Decisions and assumptions

Phase 0 record. Every downstream lane codes against this file; change it here first.

## Scope

| In | Out |
|---|---|
| Synthetic 20k-account world, 3 business units | Any real customer data |
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
| FastAPI + Pydantic | The OpenAPI file is the contract, so code generation and drift checks are cheap |
| SQLite (`data/demo.db`) | Zero ops for a laptop demo; schema stays Postgres-portable |
| React + Vite + Recharts + Tailwind | Fastest path to an executive-grade UI that agents build reliably |
| `docker compose` | One command for the demo laptop |

Ports: API `8000`, web dev `5173`, composed demo `8080`.

## Determinism

- Generator seed `42`, written to `data/demo.db` and committed only as `seed=42` instructions.
- `ml/artifacts/model.joblib`, `metrics.json`, `shap_sample.parquet` regenerate byte-identically
  from the seed. The demo never depends on a hand-edited artifact.
- A test asserts `metrics.json` matches a checked-in reference within tolerance.

## Assumptions

1. **Churn horizon is 180 days.** Long enough to be actionable, short enough to measure.
   See `LABEL.md`.
2. **Revenue proxy is ARR.** Risk × ARR is the queue's sort key.
3. **Ground truth is stored separately** (`account_outcomes`) from features, and
   `features.py` may not read it. Enforced by a test, not by convention.
4. **Three business units** (`north`, `south`, `emea`) with different base churn rates,
   to make the segment view meaningful and to prove the model isn't BU-blind.
5. **The demo is read-mostly.** The only write is a simulated action that creates a task
   row and returns a revised score.

## Open items

| Item | Owner | Blocks |
|---|---|---|
| CodeRabbit account + API key (`coderabbit auth login --api-key <key>`) | You | P4 gate only |
| CodeRabbit CLI installed; `coderabbit doctor` clean on the demo laptop | You | P4 gate only |
| Confirm 180-day horizon matches the pitch's story | You | Nothing — changing it rewrites `LABEL.md` and the generator |
| Demo laptop OS (macOS / Windows) | You | `compose.yaml` details only |

## How the harness builds this

Contract-first: P0 (this file set) is written by the lead agent alone. Then four lanes run
concurrently against `schema.sql` and `openapi.yaml`:

| Lane | Owns | Depends on |
|---|---|---|
| A | `data/generator.py`, `data/seed.py` | `schema.sql` |
| B | `ml/features.py`, `ml/train.py`, `ml/explain.py` | A's output |
| C | `api/app.py` + service tests | `openapi.yaml` |
| D | `web/` on fixtures | `openapi.yaml` |
| E | Simulated retention actions | `schema.sql` |

P3 wiring and P4 review are serialized — they are the integration points, and that is
where multi-agent builds actually fail.
