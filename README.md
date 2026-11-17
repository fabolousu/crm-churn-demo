# crm-churn-demo

A pitch demo — not a production system. A reimagined CRM where the home screen is a
ranked queue of revenue at risk, built on synthetic data with a known churn process so
every number shown is computed, not asserted.

**Status: Phase 0 (contract) complete. Lanes P1 not started.**

## The thesis

A CRM that stores records is a filing cabinet. A CRM that ranks accounts by
revenue × churn risk and tells the rep what would change the outcome is an operating
system for retention. The demo has to prove four claims in five minutes:

1. The rep's first screen is a queue, not a list.
2. Every risk score explains itself in three drivers.
3. The rep can see what would move the score before spending a call.
4. Acting on the account moves the score — the loop closes on screen.

## Architecture

```
data/generator.py ──► data/demo.db ──► ml/train.py ──► ml/artifacts/ ──► api/app.py ──► web/
   (synthetic world)     (SQLite)        (GBM + SHAP)    (model, metrics)   (FastAPI)    (React)
```

The mock owns its own database. Nothing touches Dataverse, no tenant, no cloud.

## Layout

| Path | Contents |
|---|---|
| `docs/LABEL.md` | Churn definition and the synthetic process that generates it |
| `docs/DECISIONS.md` | Scope, non-goals, stack, and the assumptions I made |
| `docs/PITCH.md` | Executive narrative and the 5-minute demo script |
| `data/schema.sql` | Data contract — every lane codes against this |
| `api/openapi.yaml` | API contract — UI and service lanes code against this |
| `data/generator.py` | Synthetic world generator *(P1)* |
| `ml/` | Features, training, SHAP *(P1–P2)* |
| `api/` | FastAPI service *(P2)* |
| `web/` | Reimagined CRM UI *(P1–P3)* |

## Run it (once lanes land)

```sh
python data/generator.py --accounts 20000 --seed 42
python ml/train.py
uvicorn api.app:app --port 8000
pnpm --dir web dev
```

## Non-goals

Auth, deployment, real Dynamics integration, drift infrastructure, multi-tenancy.
Each is a day of work that does not move the pitch.
