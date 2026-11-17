# Decisions and assumptions

Contract **v0.3** — supersedes v0.2. Every downstream lane codes against this file; change
it here first.

## Scope

| In | Out |
|---|---|
| **Italy pilot**, five macro-regions | Any other country |
| Lead-centric model: company → lead (initiative) → won | Real customer data |
| **Lead-win probability** as the model target | Contract-churn modelling (see below) |
| GBM with SHAP explanations | Deep learning, LLM scoring |
| Batch scoring (nightly-equivalent) | Real-time scoring |
| Reimagined CRM UI, 5 screens | Dynamics-lookalike shell |
| Simulated actions that re-score | Email/telephony integrations |
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
| SQLite (`data/demo.db`) | Zero ops on a demo laptop; schema stays Postgres-portable |
| React + Vite + Recharts + Tailwind | Fastest path to an executive-grade UI that agents build reliably |
| `docker compose` | One command on the demo laptop |

Ports: API `8000`, web dev `5173`, composed demo `8080`.

## Determinism

- Generator seed `42` → `data/demo.db`.
- `ml/artifacts/model.joblib`, `metrics.json`, `shap_sample.parquet` regenerate
  identically from the seed. The demo never depends on a hand-edited artifact.
- A test asserts `metrics.json` matches a checked-in reference within tolerance.

## Assumptions

1. **The target is lead win, not churn.** Contracts renew *whenever there is a new
   initiative*, so there is no renewal date and therefore no conventional churn event.
   The relationship decays when initiatives stop — that is shown as a **dormancy flag**
   on the company page, not modelled.
2. **Scoring point is qualification** (`qualified_at`), or the lead's current stage for
   still-open leads. Earlier scoring has too little signal; later scoring leaves no time to act.
3. **Censored leads are excluded from training** — leads still open at `t0` have no label.
   Including them teaches the model that open means lost and inverts the queue.
4. **Expected value is the sort key**: `probability × amount_arr`. Confirmed: the CFO
   thinks in ARR, and EUR is the only currency in the demo.
5. **Italy, five macro-regions** with different base rates; one pooled model with region
   as a feature plus per-region calibration. Not five models — each region would be thinner
   than the pooled set.
6. **Lead status is the target, not a predictor.** Predicting account churn instead would
   be a different model on a different population; the version history is in `LABEL.md`.
7. **Ground truth lives separately** (`lead_outcomes`) from features, and `features.py`
   may not read it. Enforced by a test and by CI, not by convention.
8. **The demo is read-mostly.** The only write is a simulated action that creates an
   action row and returns a revised probability.

## Open items

| Item | Owner | Blocks |
|---|---|---|
| CodeRabbit account + API key (`coderabbit auth login --api-key <key>`) | You | P4 gate only |
| CodeRabbit CLI installed; `coderabbit doctor` clean | You | P4 gate only |
| Demo laptop OS (macOS / Windows) | You | `compose.yaml` details only |

## How the harness builds this

Contract-first: P0 is written by the lead alone. Then lanes run concurrently against
`data/schema.sql` and `api/openapi.yaml`:

| Lane | Owns | Depends on |
|---|---|---|
| A | `data/generator.py`, `data/seed.py` | `schema.sql` |
| B1 | `ml/features.py` | `schema.sql` |
| B2 | `ml/train.py`, `ml/explain.py` | A's database, B1's features |
| C | `api/app.py` + contract tests | `openapi.yaml` |
| D | `web/` on fixtures | `openapi.yaml` |
| E | Simulated actions | `schema.sql` |

P3 wiring and P4 review are serialized — they are the integration points, and that is
where multi-agent builds fail.
