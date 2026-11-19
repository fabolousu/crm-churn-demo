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

## Known limitations (accepted, not fixed)

These were found by the gates and deliberately not fixed. Recording them is the point: an
accepted limitation is engineering, an unrecorded one is a surprise.

| Limitation | Why accepted |
|---|---|
| Derived response instants truncate fractional seconds (`ml/features.py`, fallback path only) | The generator writes integral seconds and `leads.first_response_at` is the preferred source, so the fallback only runs on legacy data; the discrepancy is sub-second |
| The PR reviewer cannot formally "request changes" from GitHub | It authenticates as the repository owner, who is also the PR author, so GitHub rejects it; it posts `--comment` instead, and the human's approval remains the only approval |
| The CodeRabbit GitHub App check reports `skipping` on PR #1 | The app is installed but is not gating this PR, so the **CLI** gate (`tools/review.ps1`) is the enforcing one. Worth fixing before a live demo so the PR page shows an explicit review status |
| Generator: `write_database` replaces the target in place, with a TOCTOU race between the existence check and the unlink | `--db` is deleted before the new file is written, and a concurrent run can unlink a completed output. One fix closes both: temp file + `os.replace`. Deferred because the cost of a failed run is one rerun of a deterministic script |
| Generator: three test-substance gaps — determinism compares only row counts for `company_usage_weekly`/`tickets`/`invoices`/`nps_surveys`/`interactions`; the response-duration tolerance is looser than the stored precision; the overwrite-refusal test asserts the message but not that the database survived | Cheap to close, deferred to keep the lane closed after four review rounds. The determinism hash gap is the most valuable follow-up: the "reproducible from seed 42" claim currently rests on hashing only companies, leads and outcomes |
| Model: `stage_at_scoring` is constant in training — all 40,158 labelled rows are `qualified` — so the proposal-stage effect is unlearnable | Closed leads are labelled at `qualified_at` by contract, which makes the scoring stage degenerate. The `accelerate_to_proposal` counterfactual was removed from `api/openapi.yaml` rather than shown as a number the model cannot produce. **Fix path if the demo needs stage-aware levers:** change the label's scoring point to a fixed offset after creation (e.g. +7 days) so stage varies, which changes `LABEL.md`, the generator and the feature pipeline together — a contract revision, not a tuning change |
| Model: hyperparameters were chosen once on the same validation split and frozen (500 rounds, no early stopping) | Metrics are mildly optimistic; the model sits 0.016 AUC below the latent ceiling, inside the gate's slack. Acceptable for a demo, and the leakage guard still holds |
| **Governance: the CodeRabbit GitHub App pushed a commit authored `coderabbitai[bot]` into a PR branch** (`4f74d7d` on `lane/c-api`) | The changes are sound and tested — transaction ownership in `record_model_run`, staged artifact writes, model-bundle validation on startup, a `pydantic` pin — so they were kept. But a reviewer that can write is no longer an independent reviewer: it authored code in `ml/train.py` and `api/app.py`, which the `pr-reviewer` agent never reviewed, and it could do so again on any branch. For this demo the risk is low and the code was read; for anything real, autofix must be **off** and the app limited to read-only review. Decision recorded rather than silently accepted |
| Generator tests: two `sqlite3.connect` calls relied on the context manager, which commits but never closes — later unlinks failed on Windows only | Fixed rather than accepted: a test that passes on Linux CI and fails on the demo laptop is exactly the wrong kind of green |

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

### One writer per table

`lead_features` is materialised **only** by `ml/features.py`. The generator produces raw
tables plus `lead_outcomes` and leaves `lead_features` empty — asserted by a generator
test. Two producers of one table diverge silently, and a generator that pre-computes
features would let the demo show a table that nothing in the pipeline computed.

## Plan v2 decisions (recorded 2026-11-19)

Q1 CRM becomes the shell; ML screens move under `/previsioni`. Q2 slim committed DB for serving, full DB local for training. Q3 GitHub Pages for the free showcase (done); Vercel Hobby still preferred for previews + serverless once a token exists. Q4 both stories in the pitch. Handover: `docs/NEXT_SESSION.md`.

## T12 — CRM schema (recorded 2026-11-19)

- The CRM entities live in a `crm_` namespace in `data/crm_schema.sql`: `crm_companies`, `crm_contacts`, `crm_company_contacts`, `crm_initiatives`, `crm_leads`, `crm_activities`, `crm_lead_statuses`. `api/migrations/apply.py` applies them once per database and records the version in `crm_schema_migrations`; `api/tests/test_crm_schema.py` snapshots every non-CRM table before and after to prove the ML schema is untouched.
- `crm_leads` is in T12 even though B1's name list stops at five entities: B2's rules — configurable status table, `UNIQUE(Contatto, Iniziativa)`, closing date, owner default — have no target otherwise, and the ML `leads` table has a closed enum and must stay untouched. The two lead tables are deliberately separate, not synced.
- `Manifestazione di Interesse` (spec §3.5), `Servizio` (spec §3.7) and the reference catalogues (province, macro sectors, sectors, tipologie, fonti, posizioni) are not in B1. Their columns are TEXT so no catalogue is invented while spec §16.2 is open; the lanes that need them add them.
- Owner/team columns are TEXT: there is no users/teams table yet, so the spec's owner defaults and RBAC (§10) remain a documented gap rather than stub tables.

## T16 vendor fallback (recorded 2026-11-19)

T16 (Vercel serverless API lane) was initially assigned to the Gemini 3.8 Flash model. That run died with no files and no message; a probe of the session returned only session-init output with zero authored content. Per the documented "Gemini lanes re-runnable on Anthropic" limitation in `docs/ORCHESTRATION.md`, the lane was re-run on Anthropic Claude Sonnet (claude-sonnet-4-6). This is recorded here rather than silently accepted: the authoring model changed mid-lane, and CodeRabbit remains the independent primary reviewer for all code introduced in this lane (it did not participate in authorship). The deliverables — `api/serverless.py`, `api/index.py`, `scripts/build_slim_db.py`, `api/tests/test_serverless.py`, and the dependency split — were written entirely in the Anthropic fallback run.

## D7 guardrails — demo scope (recorded 2026-11-19)

Decision: the demo API stays **public and read-only**; token auth is not added. `DECISIONS.md` already lists Auth as a non-goal, and a link that requires a key defeats the pitch. D7 is recorded as **passed with documented exceptions**, not as a full auth implementation:

- **Auth** — not implemented; justified exception (demo non-goal). The API is read-only and serves synthetic data.
- **Rate limiting** — not implemented in-function: Vercel functions are stateless and this Hobby project has no durable counter. Mitigation is the read-only surface plus bounded responses; revisit before any traffic beyond the demo.
- **Input/output validation** — FastAPI bounds every query (`limit` 1–200, `min_probability` 0–1, region/sort enums) and Pydantic models enforce the contract; tests cover the 422 and 200 cases.
- **PII** — the dataset is synthetic (generator seed 42); no real personal data is served.
- **Prompt injection** — N/A: no LLM runs at request time; the model is used only in the offline build.
- Generated docs/schema are disabled in the function (`docs_url=None`, `openapi_url=None`); CORS is an explicit allowlist, and responses carry `nosniff`/`no-referrer`.

## D8/D9 operations (recorded 2026-11-19)

- **D8 alerting**: GitHub Actions `uptime.yml` checks `/api/health` (`status=ok`) and `/api/pipeline?limit=1` every 10 minutes; failures create or comment on an issue labelled `uptime`, and recovery closes it. Hobby logs are not an alert channel. Token cost is N/A (no LLM runs at request time). GitHub disables scheduled workflows after 60 days of repository inactivity — re-enable if the demo goes quiet.
- **D9 rollout**: `deployment-smoke.yml` runs `scripts/smoke_deployment.sh` on successful Vercel deployments. Preview smoke requires `VERCEL_AUTOMATION_BYPASS_SECRET` and `VERCEL_TOKEN` (which must have access to this Vercel project, and is used to prove the deployment's project ownership before the bypass header is sent). Without the bypass secret the preview is skipped with a notice; if ownership cannot be verified the job fails rather than claiming success. Production is public and needs neither secret. Rollback is manual via the Vercel dashboard or `vercel rollback`; `docs/RUNBOOK.md` records the procedure and the last-known-good deployment.

