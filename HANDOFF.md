# HANDOFF — crm-churn-demo

Written 2026-11-20 by the session that built T16 and the D7–D9 hardening. This file
supersedes `docs/MIGRATION_SPEC.md` as the *current* state; read both, in this order:
this file first, then `MIGRATION_SPEC.md` for product/history. It is specific on purpose:
a fresh agent should not have to rediscover any of it.

---

## 0. First five minutes

```powershell
cd C:\Users\pilad\OneDrive\Documenti\deepseek-harness\default-workspace\crm-churn-demo
git status --short --branch          # currently lane/t16-cleanup; main == 792884d
gh pr list --state open              # #9 #10 #11 #12, all MERGEABLE
python -m pytest -q                  # 175 on this branch (counts differ per branch, see §7)
Invoke-RestMethod https://crm-churn-demo.vercel.app/api/health
```

Production is live and healthy. Four PRs are green and waiting for the human to merge.
Nothing is mid-edit. The one thing to do next is merge in the order in §4.

**Do not rewrite T16, the ML stack, the five ML screens, or the review gates.** The
project's own rule: a lane proposing a rewrite must justify why a patch is not enough.

---

## 1. Goal

A B2B CRM for an Italian chamber-of-commerce agency (Promos Italia) that promotes
*initiatives* to companies, with a LightGBM layer that predicts whether a lead will be
won, explains itself with SHAP, and ranks the pipeline by where effort pays off.

Decisions already made (do not re-ask):

| # | Decision |
|---|---|
| Q1 | **The CRM becomes the shell; the five ML screens move under `/previsioni`** |
| Q2 | **Slim committed DB** (`data/demo.slim.db`, ~2.4 MB) for serving; the 240 MB `data/demo.db` stays local for training |
| Q3 | GitHub Pages for the free showcase (live); **Vercel** for previews + serverless API (token now exists) |
| Q4 | **Both stories in the pitch**: CRM is the product, `Previsioni` is the differentiator |

Review hierarchy: **CodeRabbit is the primary, blocking reviewer**. The `pr-reviewer`
agent triages and never approves. **The human is the only approval**; merge is theirs.

---

## 2. Current state (2026-11-20, ~00:20 Europe/Rome)

### Git

| Ref | Tip | Meaning |
|---|---|---|
| `main` | `792884d` | Merge of PR #8 (T16 serverless API). Local main is synced. |
| `lane/T12-crm-schema` | `9184197` | T12 schema + merge of main; PR **#9** |
| `lane/D1-ui-checks` | `cce1114` | D1 axe/link gate + merge of main; PR **#10** |
| `lane/t16-cleanup` | `6d3e0be` | T16 cleanup + D7; PR **#11** |
| `lane/d8-d9-ops` | `02a8329` | D8/D9; PR **#12**; lives in worktree `..\wt-d8-d9` |

The main checkout is on `lane/t16-cleanup` and clean. `lane/d8-d9-ops` is checked out in
the worktree `C:\Users\pilad\OneDrive\Documenti\deepseek-harness\default-workspace\wt-d8-d9`.
Older worktrees `wt-b2-training`, `wt-c-api`, `wt-d-ui` exist from previous sessions.

`HANDOFF.md` is currently **untracked**. Commit it on a docs branch
(`[skip ci]` is appropriate for a docs-only commit) — do not fold it into #11 or #12.

### Open PRs — all MERGEABLE

| PR | Branch | Checks | Tests |
|---|---|---|---|
| **#9** https://github.com/fabolousu/crm-churn-demo/pull/9 | T12 CRM schema | CI + Vercel + CodeRabbit App pass; CLI gate exit 0 (1 minor: `NOT NULL` on TEXT PKs) | **184** |
| **#10** https://github.com/fabolousu/crm-churn-demo/pull/10 | D1 UI gate | CI + Vercel + CodeRabbit App pass; CLI gate exit 0 (4 minor) | **168** + `check:ui` |
| **#11** https://github.com/fabolousu/crm-churn-demo/pull/11 | T16 cleanup + D7 | CI + Vercel + App pass; CLI gate **exit 0, 0 findings** | **175** |
| **#12** https://github.com/fabolousu/crm-churn-demo/pull/12 | D8 + D9 | CI + Vercel + App pass; CLI gate **exit 0**, 2 minor | **168** |

### Production

- **https://crm-churn-demo.vercel.app** — deployment `dpl_Fv2TG1iXNRLqQX6CkC1usyLzsr73`, READY, target production (this is the T16 merge).
- `/api/health` → `{"status":"ok","model_version":"lead-win-lgbm-v1","scored_at":"2026-11-18T16:10:44Z"}`
- `/api/pipeline?limit=3` → 200, `total=2000`, `total_expected_value=77095687.31`, contract-shaped items with drivers + leverage.
- The **UI is still fixture mode**: no `VITE_API_BASE` is set in Vercel, so the deployed screens do not call the API yet.
- Vercel project: `promos6/crm-churn-demo` (`prj_bIOTXnHFIIEMAyejsDV65oJldtrn`, org `team_DNvshZ4I6c9bXczATJmlRgWv`). GitHub integration is connected (`fabolousu/crm-churn-demo`), so merges to `main` deploy production; PRs get previews.
- Preview URLs are **SSO-protected**. Public requests get Vercel's login HTML with HTTP 200. Use `vercel curl <path> --deployment <url>` or the automation bypass header.

### Credentials (names and locations only — never print or commit values)

| Secret | Where |
|---|---|
| Vercel token | `C:\Users\pilad\.vercel-token` (outside repo; read per command into `$env:VERCEL_TOKEN`) |
| Vercel token for CI | GitHub Actions secret `VERCEL_TOKEN` (used to prove preview project ownership) |
| Vercel bypass | GitHub secret `VERCEL_AUTOMATION_BYPASS_SECRET` — **not set yet**, so preview smoke skips |
| Gemini | User env var `GEMINI_API_KEY` (paid tier; the DSH server was restarted at 20:59 to load it) |
| CodeRabbit | CLI currently OAuth as `fabolousu`, with promo credits. The new paid key is *not* configured yet; place it at `C:\Users\pilad\.coderabbit-key` (see §9) |
| GitHub CLI | `gh` authenticated as `fabolousu` with `repo` + `workflow` |

`.env.local` exists (created by Vercel, contains `VERCEL_OIDC_TOKEN`) and is gitignored.
`.vercel/` is gitignored. Nothing secret is tracked; `git log -S VERCEL_TOKEN` is empty.

---

## 3. What is done

Baseline (do not rebuild): synthetic world (20k companies, 60k leads, latent AUC 0.782),
feature pipeline (60k rows, 0 leakage), LightGBM (AUC 0.773 vs ceiling 0.789, ECE 0.0104,
lift@10 2.26), 7 API endpoints, 5 ML screens, CI, CodeRabbit gate, Pages showcase.

Built in this session:

1. **T16 — serverless API (merged, #8)**
   - `data/demo.slim.db` (2.41 MB): top 2,000 open leads by EV, 1,811 companies, features,
     scores, `model_runs`, and a precomputed `lead_leverage` table (2,000 rows).
   - `serverless/app.py` + `api/index.py`: FastAPI (fastapi/pydantic/sqlite3 only) serving
     `/api/health` and `/api/pipeline` exactly to `api/openapi.yaml`.
   - `requirements.txt` is runtime-only; `requirements-dev.txt` holds the full stack; CI
     installs the dev file. `vercel.json` has the function config + rewrites.
   - Why: Vercel **always** installs the root `requirements.txt`; the full ML stack is
     559 MB unzipped vs the 250 MB function limit.
   - Verified: 168 tests, slim DB exact top-2,000 match, L021037 leverage matches a fresh
     model score to <1e-9, production health + pipeline live.
2. **D1 — UI gate (#10)**
   - `playwright-core` + `axe-core`, `web/scripts/check-ui.mjs` (`pnpm --dir web check:ui`):
     serves `dist/`, runs axe WCAG 2.0/2.1 A/AA, crawls rendered links/subresources,
     samples 5 records per route template.
   - Fixed the findings: low-contrast small labels in `AppShell`/`QueueRow`/`RegionFilter`/
     `ActPage`/`LeadPage`, and the Recharts calibration scatter (one labelled image,
     decorative internals hidden).
   - Result: 14 routes / 6 templates / 0 violations / 0 broken links / 0 failed assets.
3. **T12 — CRM schema (#9)**
   - `data/crm_schema.sql`: `crm_companies`, `crm_contacts`, `crm_company_contacts`,
     `crm_initiatives`, `crm_leads`, `crm_activities`, `crm_lead_statuses` (14 seeded
     statuses). `api/migrations/apply.py` is idempotent and tracked in
     `crm_schema_migrations`; 16 tests prove ML tables are untouched.
   - `crm_leads` exists beyond B1's five-entity list because B2's status/uniqueness/closing
     rules have no other target; ML `leads` keeps its closed enum.
4. **D7 — demo guardrails (#11, fastest/demo scope)**
   - Public, read-only API; **no token auth** (Auth is a recorded non-goal).
   - Generated docs/OpenAPI disabled in the function; CORS is an explicit allowlist;
     `nosniff`/`no-referrer`; validation tests. Accepted exceptions recorded in
     `DECISIONS.md` (no durable rate limit, synthetic data, no LLM at request time).
5. **D8/D9 — operations (#12)**
   - `uptime.yml`: 10-minute probe of health (`status=ok`) + pipeline, creates/comments on
     a `uptime` issue, closes on recovery, serialized with `concurrency`.
   - `deployment-smoke.yml` + `scripts/smoke_deployment.sh`: smoke on successful
     deployments. Preview smoke proves the host belongs to this project via the Vercel API
     (`projectId`) before sending the bypass secret, runs the script from the **default
     branch** (not PR code), and fails closed if ownership cannot be verified.
   - `scripts/validate_deployment_url.py`: HTTPS only, rejects credentials/query/fragment,
     exact production alias or API-verified preview host. `curl --globoff`.
   - RUNBOOK: pre-merge preview check, production smoke, rollback, last-known-good
     `dpl_Fv2TG1iXNRLqQX6CkC1usyLzsr73`.
6. **T16 cleanups (#11)**
   - `api/serverless.py` moved to `serverless/app.py` so only `api/index.py` is a Vercel
     function; `vercel.json` `includeFiles` is a single brace-glob string (the schema
     rejects arrays).
   - `build_slim_db.py` builds to `demo.slim.db.tmp`, validates, then `os.replace`; a
     failed rebuild preserves the committed artifact. A rebuild reproduced identical bytes.
   - `MIGRATION_SPEC` points at `requirements-dev.txt`.

---

## 4. What is left, in order

### 4.1 Merge the four PRs (human action)

Recommended order: **#10 → #9 → #11 → #12**. #10 changes only `web/`; #9 adds the schema;
#11 and #12 are deployment hardening. Every merge redeploys production automatically.

**Expected conflict:** `docs/DECISIONS.md`. #9, #11 and #12 each append a section after the
T16 vendor-fallback paragraph. Resolution is additive — keep, in order:

1. `## T12 — CRM schema (recorded 2026-11-19)`
2. `## D7 guardrails — demo scope (recorded 2026-11-19)`
3. `## D8/D9 operations (recorded 2026-11-19)`

Remove the `<<<<<<<` / `=======` / `>>>>>>>` markers. No other file conflicts are expected
(#10 is `web/` only; #11 is `api/`, `serverless/`, `scripts/`, `vercel.json`, `docs/`;
#12 is `.github/`, `scripts/`, `docs/`). If #11/#12 show conflicts, merge `main` into them,
resolve only `DECISIONS.md`, re-run `pytest`, and push.

### 4.2 Post-merge verification

- `curl https://crm-churn-demo.vercel.app/api/health` and `/api/pipeline?limit=1`.
- The new production deployment must serve the moved `serverless/app.py` function
  (the preview for #11 already did; verify production after merge).
- Run the uptime workflow once: `gh workflow run uptime.yml`, then check the run.
- D8's forced-failure alert path is **not tested**: there is no `workflow_dispatch` input
  to force a failure. Add one if you need to prove the alert, or stop the API and watch.
- Preview smoke stays skipped until `VERCEL_AUTOMATION_BYPASS_SECRET` is added as a repo
  secret (Vercel → Deployment Protection → Protection Bypass for Automation).
- Confirm the deployed UI now includes D1's contrast fixes (after #10 merges).

### 4.3 CodeRabbit paid key

Add the new key outside the repo, then switch auth:

```powershell
# put the key in C:\Users\pilad\.coderabbit-key first (one line, no quotes)
$k = (Get-Content "$env:USERPROFILE\.coderabbit-key" -Raw).Trim()
coderabbit auth login --api-key $k
coderabbit auth status --agent
```

Current OAuth auth works; the new key is only needed so usage lands on the paid plan.
Never commit it or paste it into chat.

### 4.4 Remaining product lanes

- **T13** CRM domain rules (`api/crm/`, acceptance tests from spec §15.1): status table
  wiring, uniqueness, auto-link, closing-date hook, `POST /api/intake/*`.
- **T14** deterministic Italian seed data (~2k companies, ~3k contacts, ~1.2k initiatives,
  ~6k leads) — depends on T12.
- **T15** CRM UI shell + `Lead personali aperti` + `Scheda Lead`, v2 design, IT locale.
- **T17** independent verification (`docs/VERIFICATION_REPORT.md`) with **Gemini** (must not
  be Anthropic-authored). Gemini paid key is working; run after the merges so it checks the
  merged state.
- **D7 residual**: decide whether a public demo is acceptable long-term; rate limiting has
  no durable store on Hobby.
- **Endpoint coverage / UI wiring**: only health + pipeline are serverless. Lead 360,
  company 360, counterfactual, actions and portfolio are still local-only. The deployed UI
  stays on fixtures until those exist and `VITE_API_BASE` is set. This is a product
  decision, not a bug.
- **`api/app.py` is still a dead Vercel function** (Vercel compiles every `.py` under
  `api/`; `/api/app` would 500 because the ML stack is not installed). Workaround options:
  move the original app outside `api/` (touches `uvicorn api.app:app`, tests, docs), or add
  a rewrite for `/api/app` to the slim app's 404. Not done.
- **Two minor CodeRabbit notes on #12** (non-blocking): RUNBOOK says the uptime issue
  includes URL/status but the body only links the run; the fail-closed check should only
  fail exit-code-2 when the bypass secret is present. Fold into a follow-up if desired.
- **#9 minor**: explicit `NOT NULL` on TEXT primary keys (SQLite allows NULL in a TEXT PK).

---

## 5. Decisions and why

| Decision | Why |
|---|---|
| CRM is the shell, ML under `/previsioni` | Q1; one product, not two apps |
| Slim DB + precomputed leverage | 240 MB DB + 559 MB ML stack cannot ship in 250 MB; scores are batch-produced already |
| `crm_` namespace; separate `crm_leads` | ML tables must stay untouched; B2 rules need a CRM lead target |
| `crm_leads` beyond B1's five entities | Otherwise status/uniqueness/closing rules have nowhere to live |
| Manifestazione/Servizio deferred | P1/P2, spec §16.2 catalogues still open; no invented fields |
| Root `requirements.txt` runtime-only | Vercel installs it unconditionally (verified); full stack in `requirements-dev.txt` |
| Only health + pipeline serverless | T16 gate; full endpoint parity is a later lane |
| Public read-only API, no auth (D7) | Demo/link-first; Auth already a recorded non-goal; exceptions documented |
| GitHub issues as D8 alerts | No new account; Hobby logs are not alerting; token cost N/A (no LLM runtime) |
| Preview smoke verifies project ownership | A hostname pattern is not proof; Vercel API `projectId` is |
| T16 authored on Anthropic Sonnet | The Gemini T16 run failed with HTTP 503; later probes hit the free-tier 20/day cap. Documented fallback. Gemini is now paid and working; do not redo T16 |
| CodeRabbit primary; human only approval | Spec §4; reviewer agent never approves |
| Merge order #10 → #9 → #11 → #12 | #10 is user-visible UI; conflicts only in DECISIONS |

---

## 6. Key files

| File | Purpose |
|---|---|
| `data/schema.sql` | ML data contract (do not edit for CRM work) |
| `data/crm_schema.sql` | CRM DDL + 14 status seeds (`crm_` namespace) |
| `api/migrations/apply.py` | Idempotent CRM migration runner; CLI `--db` |
| `api/app.py` | Original FastAPI app (model-backed, local); **not used by the serverless function** |
| `serverless/app.py` | Slim read-only FastAPI app for Vercel; no numpy/pandas/ml |
| `api/index.py` | Vercel entry; imports `serverless.app` |
| `scripts/build_slim_db.py` | Builds `data/demo.slim.db` atomically, precomputes leverage |
| `data/demo.slim.db` | 2.41 MB committed serving DB (top 2,000 leads) |
| `requirements.txt` / `requirements-dev.txt` | Runtime (fastapi, pydantic) / full local+CI stack |
| `vercel.json` | Static build + functions config + API rewrites |
| `.vercelignore` | Excludes `data/demo.db` (not the slim DB), node_modules, dist, tmp |
| `web/scripts/check-ui.mjs` | D1 axe + rendered link crawl (`pnpm --dir web check:ui`) |
| `scripts/validate_deployment_url.py` | HTTPS + Vercel project-ownership validator for preview smoke (rejects credentials/query/fragment) |
| `.github/workflows/uptime.yml` | D8 monitor |
| `.github/workflows/deployment-smoke.yml` | D9 deployment smoke |
| `scripts/smoke_deployment.sh` | Checks `/`, `/api/health`, `/api/pipeline?limit=1` |
| `tools/review.ps1` | Enforcing review gate (exit 0/1/2/3) |
| `docs/DECISIONS.md` | Every decision/exception; **expect the merge conflict here** |
| `docs/RUNBOOK.md` | Demo run, deploy/smoke/rollback, last-known-good |
| `docs/MIGRATION_SPEC.md` | Original handover; setup/env facts |
| `docs/UI_FEATURE_INVENTORY.md` | P0/P1/P2 rows and gaps |
| `crm design/CRM_Sales_Module_Rebuild_Spec.md` | 509-line functional spec |

---

## 7. Commands that matter

```powershell
# Environment (full stack; requirements.txt alone is runtime-only now)
python -m pip install -r requirements-dev.txt
pnpm --dir web install

# Tests (counts: main 168, T12 184, D1 168, cleanup 175, D8/D9 168)
python -m pytest -q

# Slim DB (needs data/demo.db, ~90 s pipeline if missing)
python tools/run_pipeline.py                 # regenerate 240 MB demo.db if absent
python scripts/build_slim_db.py              # atomic rebuild; prints size/counts

# CRM migration (local DB only; not applied to production slim DB)
python api/migrations/apply.py --db data/demo.db

# Web
$env:TEMP = (Resolve-Path .tmp).Path; $env:TMP = $env:TEMP   # Vite/esbuild quirk
pnpm --dir web build
pnpm --dir web check:ui                      # axe + link crawl (needs Chrome)

# Review gate (run on the commit that will be merged)
pwsh -File tools/review.ps1 -Base main
# exit 0 pass, 1 deterministic fail, 2 findings at/above major, 3 CodeRabbit unavailable

# Vercel
$env:VERCEL_TOKEN = (Get-Content "$env:USERPROFILE\.vercel-token" -Raw).Trim()
vercel whoami
vercel ls crm-churn-demo
vercel inspect <deployment-url-or-id> --logs
vercel deploy --yes                          # preview (no --prod)
vercel deploy --prod                         # production, only from merged main
vercel curl /api/health --deployment <preview-url>   # bypasses SSO
vercel rollback <url>                        # rollback (see RUNBOOK)

# GitHub / PRs
gh pr checks <n>
gh pr checks <n> --watch
gh run watch <run-id> --exit-status
gh workflow run uptime.yml
gh pr create --base main --head <branch> --title "..." --body-file <file>

# Smoke (Windows: use Git Bash; WSL bash is broken here)
& "C:\Program Files\Git\bin\bash.exe" scripts/smoke_deployment.sh https://crm-churn-demo.vercel.app
```

---

## 8. Open problems and risks

1. **DECISIONS.md merge conflict** across #9/#11/#12 — expected, additive, resolve as §4.1.
2. **`api/app.py` is a live-but-dead Vercel function**: `/api/app` is reachable and would
   500 (no ML deps). Either move it out of `api/` or rewrite it to the slim 404. Not a
   data leak, but it is a confusing public surface.
3. **Only two serverless endpoints.** The UI is fixture-only; the production API is a
   proof of D5, not the app's backend. Wiring `/api` requires endpoint parity first.
4. **Preview smoke is currently skipped** because `VERCEL_AUTOMATION_BYPASS_SECRET` is not
   a repo secret. The workflow is safe without it, but it proves less than it claims.
5. **D8 alert path untested**; no force-failure input. Test after merge or add one.
6. **D7 residual risk**: public/unauthenticated, no durable rate limit. Accepted for a
   demo; revisit before public traffic.
7. **D9 rollback is manual.** No automated promotion gate; RUNBOOK documents it.
8. **CodeRabbit CLI is stochastic**; it has lost its WebSocket mid-review (exit 2 as
   incomplete). Re-run rather than treating it as findings. Always run on the merge commit.
9. **CodeRabbit paid key not configured**; current auth is OAuth with promo credits.
10. **Gemini** is paid and working now. The free-tier 20/day cap caused the earlier 429;
    the DSH server must be restarted after changing `GEMINI_API_KEY` (process env is fixed
    at launch, and provider keys are scrubbed from child shells — checking `$env:` in a
    tool shell is inconclusive).
11. **T17 not run.** It must be Gemini (non-Anthropic) and should verify the merged state.
12. **`lead_outcomes` is empty in the slim DB** by design: all 2,000 leads are open.
13. **Two #12 minors** and one #9 minor remain non-blocking.

---

## 9. Gotchas (hard-won)

- **Vercel always installs root `requirements.txt`.** Never put the ML stack back there;
  custom install commands are ignored. This is the reason for the slim serverless app.
- **Vercel compiles every `.py` under `api/` as a function.** Shared code lives in
  `serverless/`; `api/index.py` is the only intended entry. `api/app.py` is the exception.
- **`vercel.json` `includeFiles` must be a string**, not an array. Current value:
  `"{data/demo.slim.db,serverless/**}"`.
- **Preview URLs are SSO-protected.** A public GET returns Vercel's login HTML with 200;
  that is not the app. Use `vercel curl`, and note it may create a bypass secret as a side
  effect (revoke it in the dashboard when done).
- **`bash` on this box resolves to WSL, which fails** (`execvpe(/bin/bash)`). Use
  `C:\Program Files\Git\bin\bash.exe` for shell scripts.
- **Vite build quirk:** esbuild temp files in `%TEMP%` can fail on OneDrive/Defender. Set
  `TEMP`/`TMP` to the repo `.tmp/` before building.
- **pytest under the sandbox:** `tmp_path` creation used to fail with `mkdir(0o700)`
  PermissionError under workspace-write. The session is now full-access; if it recurs,
  the tests themselves are fine — it is confinement, not code.
- **`data/demo.db` is 240 MB and gitignored.** Never commit it; `data/demo.slim.db` is the
  committed artifact (2.41 MB) and must stay under 25 MB.
- **Slim DB rebuild is atomic now.** Build to `.tmp`, validate, `os.replace`. A failed run
  leaves the previous artifact intact.
- **No hand-typed numbers.** Every figure must trace to `metrics.json`, the API, or a
  committed seed. Six drifts are recorded; this is the project's most repeated failure.
- **CodeRabbit autofix stays off**; the app once authored a commit into a branch.
- **The reviewer agent never approves** — it shares the human's GitHub account.
- **Git worktrees:** #12 lives in `..\wt-d8-d9`. Do not edit the same branch in two
  worktrees; switch the main checkout to `main` before working elsewhere.
- **Windows paths and OneDrive:** keep `.tmp/`, `web/dist/`, `node_modules/` out of git;
  they are ignored. The Vercel CLI scans the project directory — `.vercelignore` is what
  keeps the 251 MB DB out of the upload (without it the CLI hung for 10+ minutes).
- **CI Node 20 deprecation warnings** are noise from GitHub Actions, not failures.

---

## 10. Suggested next moves

1. Merge #10 and #9; then ask the agent to rebase/resolve #11 and #12 against the new
   `main` (only `docs/DECISIONS.md` conflicts).
2. Verify production after each merge: `/api/health`, `/api/pipeline?limit=1`, `/`, `/portfolio`.
3. Add `VERCEL_AUTOMATION_BYPASS_SECRET` and test a preview smoke end-to-end; test the
   uptime alert path once.
4. Configure the CodeRabbit paid key and run a final CLI gate on the merged `main`.
5. Start **T13** (CRM rules) against the merged schema, then T14 seed, T15 UI.
6. Run **T17** with Gemini once the merged state is stable.
