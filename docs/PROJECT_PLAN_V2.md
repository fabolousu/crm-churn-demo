# Project plan v2 — three-vendor build

Supersedes the plan in `docs/ORCHESTRATION.md` for everything after Phase 0. Written against
the state of `main` at `2cc7cbc`, with Anthropic and Gemini routes now enabled in the harness.

## 0. Baseline: what exists, and is kept

Everything below is verified, committed, and **not rebuilt**.

| Asset | Evidence | Verdict |
|---|---|---|
| Synthetic world generator | 20k companies, 60k leads, 28.664% prevalence, latent AUC 0.782, 13 tests | **Keep** |
| Feature pipeline | 60,000 rows, 0 point-in-time violations, 25 tests | **Keep** |
| Model + artifacts | LightGBM, AUC 0.773 vs ceiling 0.789, ECE 0.0104, lift 2.26, 24 tests | **Keep** |
| API | 7 endpoints, 63 tests, contract-validated via `jsonschema` | **Keep**, extend |
| ML demo UI | 5 screens, leverage sort, stability panel | **Keep** as the `Previsioni` module |
| Gates | CI, CodeRabbit CLI (exit-code gate), `pr-reviewer` agent, latent-ceiling guard | **Keep** |
| Repo & VCS | 78 commits, protected `main`, 7 merged PRs, review trail | **Keep** |
| Docs | label, decisions, pitch, runbook, orchestration, PR review, inventory, model policy | **Keep**, extend |
| Design inputs | `crm design/`: 509-line spec + 3 Stitch screens, now committed | **Input only** |

**Explicitly not rebuilt:** the generator, the feature pipeline, the trained model, the seven
API endpoints, the five ML screens, the review gates, and the CI pipeline. Any lane that
proposes rewriting one of these must justify why a patch is not enough.

## 1. What is new

| # | New work | Why it exists |
|---|---|---|
| N1 | CRM data model: `Azienda`, `Contatto`, `Relazione`, `Iniziativa`, `Attività` | The three designed screens need them; nothing in the current schema provides them |
| N2 | Lead domain logic: configurable status table, uniqueness rule, company auto-link, closing date, owner defaults | Spec §4, §5.3, §3.6 — testable business rules |
| N3 | CRM UI: app shell + `Lead personali aperti` + `Scheda Lead` | The P0 of `docs/UI_FEATURE_INVENTORY.md` |
| N4 | Seeded Italian CRM dataset | The screens are empty without it |
| N5 | Vercel deployment of UI + API | Hosting requirement |
| N6 | Guardrails, monitoring, staged rollout | WS4 phases 7–9 |

## 2. Team roster — who does what, on which vendor

The point of three vendors is **skill-fit plus review independence**: no artifact is reviewed
by the model family that wrote it.

| Agent | Vendor / tier | Owns | Why this vendor |
|---|---|---|---|
| `architect` | **Anthropic Opus** | Plan, contracts, schema decisions, adjudicating disputes | Reasoning tier; the cost of being wrong is highest here |
| `crm-backend` | **Anthropic Sonnet** | N1, N2: entities, migrations, status table, uniqueness, auto-link, intake endpoints | Subtle business rules; tests catch shape, not intent |
| `crm-frontend` | **Anthropic Sonnet** | N3: shell, list, form, status flyout | Taste; the design must be judged, not diffed |
| `vercel-engineer` | **Google Gemini 3.8 Flash** | N5: `vercel.json`, function adapters, build config, env wiring | Infrastructure configuration is verifiable — cheapest tier that passes the deploy check |
| `data-seeder` | **DeepSeek flash** | N4: deterministic Italian seed data | Bulk, mechanical, diffable against the schema |
| `verifier` | **Google Gemini** (never Anthropic) | WS-C: independent check that WS-A/B actually landed | Must not share a family with the authors it audits |
| `reviewer` | **pr-reviewer preset** on **Gemini** for Anthropic-authored PRs, on **Anthropic** for Gemini-authored PRs | Judgement-level review | Structural independence, matching the rule above |
| Line-level gate | **CodeRabbit** (third party) | Diff findings, exit-code gate | Independent of all three vendors |
| Human | **You** | Approve, merge, deploy promotion, final pitch | The only irreversible step |

Routing is declared in `workflow/routing.yaml` (`model` + `tier`) and enforced per call by
passing `provider`/`model` to the subagent. Tier policy: `docs/AGENT_MODEL_POLICY.md`.

## 3. Workstreams and gates

### WS-A — Model policy · **DONE**
Gate: every task class has a tier, every Haiku use has a stated reason, tier≠family recorded
as a gap. → `docs/AGENT_MODEL_POLICY.md`.

### WS-B — CRM UI P0 (the design folder)

| Phase | Owner | Deliverable | Gate |
|---|---|---|---|
| B1 schema | `architect` + `crm-backend` | Migration adding the five entities + reference tables; ML tables untouched | Schema loads; existing 145 tests still green |
| B2 domain rules | `crm-backend` | Status table seeded, uniqueness index, auto-link, closing-date hook, `POST /api/intake/*` | Each acceptance test from spec §15.1 that touches these rules passes |
| B3 seed data | `data-seeder` | ~2,000 companies, ~3,000 contacts, ~1,200 initiatives, ~6,000 leads, Italian | Deterministic from a seed; row counts asserted; no PII-shaped data |
| B4 UI | `crm-frontend` | Shell + list + form, v2 design, i18n IT | Build passes; every P0 row in the inventory has a component; manual screen check |
| B5 verification | `verifier` | Status table: done / partial / missing per inventory row | Every non-done row has an owner and a next step |

### WS-C — Independent verification
Gate: the verifier re-runs the gates itself, diffing claims against commits and test output —
not against the lane's summary. Anything marked done without evidence is downgraded.

### WS-D — Pipeline (ordered, one gate per phase)

| Phase | What | Gate |
|---|---|---|
| D1 Testing | pytest (all suites), `tsc --noEmit`, production build, a11y (axe), link check | All green locally before any merge |
| D2 Version control | Branches + PRs, protected `main` | **Already satisfied** — 7 PRs, no direct pushes since protection |
| D3 CI/CD | PR checks + deploy on merge | A throwaway PR runs the full pipeline; merge to main deploys |
| D4 Frontend hosting | Static `dist/` on Vercel, custom domain, SSL | Site resolves over HTTPS; smoke test passes |
| D5 Backend hosting | API as Vercel function (see §4) | `/api/health` responds in prod; one end-to-end request completes |
| D6 Secrets | Keys in Vercel env vars only | Secret scan clean; runtime reads only from Vercel |
| D7 Guardrails | Auth, rate limit, input/output validation, PII, prompt-injection | Each has a blocked case and a passing case |
| D8 Monitoring | Uptime, error rate, latency, token cost, traces | A forced failure raises an alert |
| D9 Staged rollout | Preview → checks → promote | Preview verified before production |

## 4. Hosting decision — the constraint that shapes D5

`data/demo.db` is **240 MB**. Vercel's function bundle limit is 250 MB unzipped, and the
deployed artifact would be one cold-start away from failure. Shipping LightGBM (≈50 MB of
native wheels) inside the same function makes it worse.

**Architecture: move the model out of the runtime.**

1. **Batch scores at build time.** `lead_scores` already holds probability, band, drivers and
   expected value for all 19,752 open leads. Extend the same batch to precompute the three
   counterfactual deltas per lead into `lead_leverage` (≈59k rows). The API then answers
   `/counterfactual` from a table instead of loading the model.
2. **Shrink the reader database.** Export a demo subset — top 2,000 leads by expected value
   plus their companies/contacts/initiatives — to `demo.slim.db` (~10–20 MB) and commit it.
   The full 240 MB database stays local for training only.
3. **API = Python serverless function** (`api/index.py` + `vercel.json` rewrites), read-only,
   `sqlite3` against the bundled slim DB. Writes (`/actions`) go to a 30-minute ephemeral store
   or are disabled in prod with an explicit "preview only" banner.
4. **Frontend = static `dist/`** on Vercel's CDN, `VITE_API_BASE` set per environment.

**What cannot run on Vercel, and the alternative:** training and full-database serving. If the
demo ever needs live re-training or writes, the API moves to a container (Cloud Run / Fly) with
a volume — documented gap, not a silent omission.

## 5. Risks

| Risk | Mitigation |
|---|---|
| Gemini route authorized but flaky (2 timeouts, 429 quota observed) | Anthropic is the verified path; Gemini lanes get a retry-then-fail policy and their work is re-runnable on Anthropic |
| 240 MB database in a serverless bundle | Slim DB + precomputed leverage (§4); full DB stays local |
| CRM entities disturb the ML schema | Separate migration namespace; ML tables and their 145 tests must stay green |
| Doc drift (6 incidents) | Pitch/runbook numbers generated from `metrics.json` and the API rather than typed |
| CodeRabbit autofix can author code | Autofix off; review-only (recorded in `DECISIONS.md`) |
| Two UIs (CRM + ML) diverge | One shell; ML screens mounted under `/previsioni` as a module |
| Vercel credentials absent | Phases D3–D9 cannot pass; a documented exception is the honest alternative, not a fake "deployed" |

## 6. Sequencing

```
WS-A (done)
   ↓
B1 schema ──┬─► B2 domain rules ──┬─► B4 UI ──► B5 verification ──► WS-C
            └─► B3 seed data ─────┘
Open decision needed: does the CRM replace the shell (§7 Q1)?
   ↓
D1 testing (can start now, on what exists) ──► D2 (done) ──► D3 CI/CD
                                                              ↓
                            D6 secrets ──► D5 backend ──► D4 frontend ──► D7 ──► D8 ──► D9
```

Parallel windows: B2 ∥ B3; D6 ∥ D5; D1 can run immediately. Everything else is serialized at a
gate, and the integration points are where agents diverge.

## 7. Decisions required before execution

| # | Decision | Default if silent |
|---|---|---|
| Q1 | Does the CRM replace the shell, with ML under `/previsioni`? | **Yes** — one product, ML as a module |
| Q2 | Slim DB (committed, ~15 MB) or Postgres for serving? | **Slim DB** — no credentials needed, matches the offline demo |
| Q3 | Vercel token, team/project, and custom domain | Phases D3–D9 documented as blocked, not faked |
| Q4 | Is the CRM demo also in the pitch, or only the ML story? | **Both**: CRM shell is the product, `Previsioni` is the differentiator |

## 8. Definition of done

- Every WS-B inventory P0 row mapped to a component, with gaps listed and owned.
- WS-C status table signed off by a verifier from a different vendor family than the authors.
- D1–D9 each marked passed or blocked with the specific missing input named.
- No secret in the repository (`git log -S` clean for every key).
- The demo runs offline, and every number on screen traces to `metrics.json`, the API, or a
  committed seed — never to a hand-typed figure.
