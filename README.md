# crm-churn-demo

A pitch demo — not a production system. A reimagined CRM for a business whose contracts
renew **whenever there is a new initiative**, so the home screen is a ranked pipeline of
initiatives scored by win probability, built on synthetic data with a known generating
process so every number shown is computed, not asserted.

**Status: Phase 0 contract at v0.3. Lanes not started.**

## The thesis

A CRM that stores records is a filing cabinet. A CRM that scores every open initiative,
ranks it by expected value, and shows the action that raises the odds is a pipeline coach.
The demo proves four claims in five minutes:

1. The rep's first screen is the ranked pipeline, not a list.
2. Every probability explains itself in three drivers.
3. The rep can see what would move it before spending the meeting.
4. Acting on the lead moves the probability — the loop closes on screen.

Because there is no renewal date, churn is not an event: a relationship decays when
initiatives stop. That is shown as a dormancy flag on the company page, and it is the
detail that makes the analysis credible to a sales director.

## Architecture

```
data/generator.py ──► data/demo.db ──► ml/train.py ──► ml/artifacts/ ──► api/app.py ──► web/
   (synthetic world)     (SQLite)        (GBM + SHAP)    (model, metrics)   (FastAPI)    (React)
```

The demo owns its own database. Nothing touches Dataverse, no tenant, no cloud.

## Layout

| Path | Contents |
|---|---|
| `docs/LABEL.md` | Lead-win definition and the synthetic process that generates it |
| `docs/DECISIONS.md` | Scope, non-goals, stack, assumptions |
| `docs/PITCH.md` | Executive narrative and the 5-minute demo script |
| `docs/ORCHESTRATION.md` | Sequencing, per-task routing, the CodeRabbit gate |
| `docs/PR_REVIEW.md` | The three review layers and the PR loop |
| `data/schema.sql` | Data contract — every lane codes against this |
| `api/openapi.yaml` | API contract — service and UI lanes code against this |
| `workflow/routing.yaml` | Executable per-task agent selection |
| `profiles/` | The `pr-reviewer` agent preset |
| `tools/` | `check_metrics.py`, `review.ps1` (the layered gate) |

## Run it (once lanes land)

```sh
python data/generator.py --companies 20000 --seed 42
python ml/train.py
uvicorn api.app:app --port 8000
pnpm --dir web dev
```

## Non-goals

Auth, deployment, real Dynamics integration, drift infrastructure, multi-tenancy.
Each is a day of work that does not move the pitch.
