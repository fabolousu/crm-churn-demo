# Migration spec — onboarding a new session

**Purpose.** Everything a fresh agent session needs to continue this project without the
conversation that produced it. Read this file end to end before touching anything. It is
self-contained; the other docs it links are the detail behind each section.

**Repo:** `C:\Users\pilad\OneDrive\Documenti\deepseek-harness\default-workspace\crm-churn-demo`
**Remote:** `fabolousu/crm-churn-demo` (public, protected `main`)
**Showcase (live):** <https://fabolousu.github.io/crm-churn-demo/>
**Written at:** `924953f`, 2026-11-19.

---

## 1. What this product is

A B2B CRM for an Italian chamber-of-commerce agency that promotes **initiatives** (trade
missions, events, courses, services) to companies. The differentiator is a machine-learning
layer: a LightGBM model that predicts whether an initiative will be **won**, explains itself
with SHAP drivers, and ranks the pipeline by **where effort actually pays off**.

Two things coexist:

1. **The CRM** — designed in `crm design/`, specified in
   `crm design/design refs/CRM_Sales_Module_Rebuild_Spec.md` (509 lines), visualised in three Stitch
   screens. This is the product shell.
2. **The ML module** — five screens (queue, lead 360, lever, act, portfolio) that already
   work end to end. They become `/previsioni` inside the CRM shell.

## 2. What is built and working (do not rebuild)

| Asset | Evidence |
|---|---|
| Synthetic world generator | 20k companies, 60k leads, prevalence 28.664%, latent AUC 0.782, 13 tests |
| Feature pipeline | 60,000 rows, 0 point-in-time violations, 25 tests |
| Model | LightGBM, AUC **0.773** vs ceiling **0.789**, ECE **0.0104**, lift@10 **2.26**, 24 tests |
| API | 7 endpoints, 63 tests, every response validated against `api/openapi.yaml` |
| ML UI | 5 screens, leverage sort, stability panel, fixtures generated from the API |
| Gates | CI, CodeRabbit CLI exit-code gate, reviewer agent, latent-ceiling guard |
| Ops | Runbook, model policy, plan v2, feature inventory, decisions log |
| Hosting | Static showcase on GitHub Pages, deploying on merge |

**A lane that proposes rewriting any of these must justify why a patch is not enough.**

## 3. Decisions already made (do not re-ask)

| # | Decision |
|---|---|
| Q1 | The CRM becomes the shell; the ML screens move under `/previsioni` |
| Q2 | Slim committed DB (`demo.slim.db`, ~15 MB, top ~2,000 leads) for serving; the 240 MB `data/demo.db` stays local for training |
| Q3 | GitHub Pages for the free public showcase (done). Vercel Hobby is the target for preview URLs + serverless API once a token exists; until then D3–D9 are **blocked with a named input**, never faked |
| Q4 | Both stories in the pitch: CRM is the product, `Previsioni` is the differentiator |

## 4. Review architecture — CodeRabbit is the primary reviewer

This is the rule that must not drift. Three layers, in this order of authority:

### 4.1 CodeRabbit — **primary, blocking**

| Where | What it does |
|---|---|
| **CLI** (`tools/review.ps1`) | The enforcing gate. Runs on the exact commit, returns blocking exit codes |
| **GitHub App** | Comment thread on the PR for humans |

```
pwsh -File tools/review.ps1 -Base main          # full gate
pwsh -File tools/review.ps1 -SkipCodeRabbit     # deterministic layer only (offline)
```

Exit codes and the required response:

| Exit | Meaning | Action |
|---|---|---|
| `0` | No findings at or above `major` | Proceed |
| `1` | Deterministic layer failed | Fix; CodeRabbit was not run |
| `2` | Findings at `major`+ | Fix, or record a justified exception in `docs/DECISIONS.md` |
| `3` | CLI unavailable / auth / quota | **Block.** Do not treat as a pass |

Rules:
- Run it on **the commit that will be merged**, not an earlier push. CodeRabbit is
  stochastic: it passed one commit and blocked the next on the same branch, twice.
- **Exit 1 means "failed or did not review every file"** — always block. Treating it as a
  pass is the classic mistake.
- Its findings carry `codegenInstructions`; hand those to the authoring lane verbatim.
- **Autofix is off.** The app once pushed a commit authored `coderabbitai[bot]` into a branch.
  It is a reviewer, not an author. If you see a bot commit, stop and inspect it.
- Quota: included reviews are metered per rolling hour; don't burn them on trivial commits.

### 4.2 Reviewer agent — **triage only, never approval**

`pr-reviewer` preset (`.dsh/skills/pr-review/`, `profiles/preset-pr-reviewer.patch.yml`)
triages CodeRabbit's output: separates real defects from noise, assigns each to a lane,
re-runs the gate, and posts `--comment` or `--request-changes`.

- **Never `--approve`.** It authenticates as the repo owner, who is the PR author; an
  approval would satisfy branch protection while proving nothing.
- Its independence rule still applies: it must run on a different vendor family than the
  author (Anthropic-authored PR → Gemini reviewer; Gemini-authored → Anthropic).
- Its second job is the judgement layer CodeRabbit cannot do: does the change honour the
  contract, is the test meaningful, does it still serve the pitch.

### 4.3 Human — **the only approval**

Approve and merge. The one irreversible step, and the only one that makes the other two
layers mean anything.

## 5. Team, vendors and routing

Model selection for Anthropic and Gemini is enabled, but **recorded per session at creation**:
verify in the new session before starting any lane.

```
subagent(provider: "anthropic", model: "claude-opus-4-7",   prompt: "reply ROUTE OK")
subagent(provider: "google",    model: "gemini-3.8-flash", prompt: "reply ROUTE OK")
```

If either is refused, the session is unauthorized: start another. **Never fall back silently**
— that turns the three-vendor claim into a false statement.

| Lane | Task | Vendor / tier | Reviewer |
|---|---|---|---|
| T12 | CRM schema | Anthropic Opus (reasoning) | Gemini verifier |
| T13 | CRM domain rules | Anthropic Sonnet (workhorse) | Gemini verifier |
| T14 | Seed data | DeepSeek (bulk) | Verifier |
| T15 | CRM UI | Anthropic Sonnet (workhorse) | Gemini verifier |
| T16 | Slim DB + Vercel config | Gemini (workhorse) | CodeRabbit + agent |
| T17 | Independent verification | Gemini (workhorse) | Human |

Tier policy and its falsifier: `docs/AGENT_MODEL_POLICY.md`. Manifest: `workflow/routing.yaml`.

## 6. Work streams and gates

### WS-B — CRM P0 (the design folder)

| Phase | Deliverable | Gate |
|---|---|---|
| **B1 schema** | Migration adding `Azienda`, `Contatto`, `Relazione`, `Iniziativa`, `Attività`, status table | Schema applies; **all pre-existing tests stay green**; ML tables untouched |
| **B2 rules** | Configurable status table, uniqueness `(Contatto, Iniziativa)`, company auto-link, closing-date hook, `POST /api/intake/*` | Spec §15.1 acceptance tests for these rules pass |
| **B3 seed** | ~2k companies, ~3k contacts, ~1.2k initiatives, ~6k leads, Italian, deterministic | Seeded from a fixed seed; row counts asserted; no real PII |
| **B4 UI** | Shell + `Lead personali aperti` + `Scheda Lead`, v2 design, IT locale | Build passes; every P0 row in the inventory has a component |
| **B5 verify** | `docs/VERIFICATION_REPORT.md`: done / partial / missing per inventory row | Every non-done row has an owner and next step |

B2 ∥ B3 can run in parallel after B1. B4 depends on B1+B2+B3.

### WS-C — Independent verification

The verifier re-runs every gate itself and diffs each claim against a commit, a test run or a
response — **never against a lane's summary**. Anything marked done without evidence is
downgraded to partial. Gate: the report lists each item as done/partial/missing with owner.

### WS-D — Pipeline (one gate per phase)

| Phase | Gate |
|---|---|
| D1 Testing | `pytest` (all suites), `tsc --noEmit`, production build, axe accessibility, broken-link crawl — all green locally before any merge |
| D2 VCS | **Done**: protected `main`, 8 PRs, no direct pushes |
| D3 CI/CD | A throwaway PR runs the full pipeline; a merge deploys |
| D4 Frontend hosting | Site resolves over HTTPS; smoke test passes. **Pages already does this** |
| D5 Backend hosting | `/api/health` responds in a deployed function; one end-to-end request completes |
| D6 Secrets | Repo scan clean; runtime reads only from the platform's secret store |
| D7 Guardrails | Auth, rate limit, input/output validation, PII, prompt injection — each with a blocked case and a passing case |
| D8 Monitoring | Uptime, error rate, latency, token cost, traces — a forced failure raises an alert |
| D9 Staged rollout | Preview verified before production promotion |

D5–D9 need a Vercel token (or another host). If absent: **blocked**, with the missing input
named in the report.

## 7. Environment (this laptop)

| Fact | Detail |
|---|---|
| Node/pnpm | Installed; `web/node_modules` present. `pnpm install` took **45 min** once — avoid reinstalling |
| Vite build quirk | Fails with `Access is denied` removing an `esbuild-*` file in `%TEMP%`. Set `TEMP`/`TMP` to a repo `.tmp/` first |
| Python | 3.12; `pip install -r requirements-dev.txt` already satisfied |
| GitHub | `gh` authenticated with `repo` + `workflow`; Pages enabled (`build_type=workflow`) |
| CodeRabbit | CLI v0.9.5 at `%LOCALAPPDATA%\Programs\coderabbit`, signed in as `fabolousu` |
| Data | `data/demo.db` is **240 MB** and gitignored; regenerate with `python tools/run_pipeline.py` (~90 s) |

## 8. Conventions

- **Branches:** `lane/<task-id>-<short-name>`; PR title starts with the task id.
- **Commits:** imperative subject, body explains *why*; append `[skip ci]` for docs-only.
- **Docs:** any decision goes in `docs/DECISIONS.md`; any limitation too. Undocumented
  decisions are treated as defects.
- **Numbers:** never hand-type a figure into copy. It must come from `metrics.json`, an API
  response, or a committed seed. Six drifts are recorded in `DECISIONS.md`; this is the
  project's most repeated failure.
- **Secrets:** reference by credential name (`apiKeyEnv`), never inline. `git log -S` must
  stay clean for every key.

## 9. Known limitations (carry these forward, do not rediscover)

| Limitation | Consequence |
|---|---|
| `stage_at_scoring` is degenerate in training | The stage-advance lever was removed; only committable levers rank |
| Discount counterfactual is causally naive | Shown as a what-if only, never as a recommendation |
| CodeRabbit autofix | Must stay off |
| Reviewer shares the author's GitHub account | It can never approve; the human does |
| Gemini availability | Authorized but has timed out / returned 429; every Gemini lane must be re-runnable on Anthropic |
| No drift **trend** | One snapshot; the panel shows holdout-vs-train only |
| `Servizio` entity | Under-specified in the source manual; do not invent fields |

## 10. First hour in the new session

1. Read this file, then `docs/PROJECT_PLAN_V2.md` and `docs/UI_FEATURE_INVENTORY.md`.
2. Run the two routing checks (§5). Report pass/fail **before** any lane starts.
3. Confirm the baseline still passes: `python -m pytest -q` and
   `pwsh -File tools/review.ps1 -Base main -SkipCodeRabbit`.
4. Start **T12** (Anthropic Opus) and **D1** in parallel.
5. Report each gate as `passed` or `blocked — <missing input>`. No green checkmarks for
   work that merely looks finished.

## 11. Definition of done

- Every P0 inventory row maps to a component, with gaps listed and owned.
- CodeRabbit exit 0 on the merged commit of every PR; the human approved each one.
- The CRM shell serves `/previsioni` with the ML screens intact.
- The showcase URL reflects the merged state.
- No secret in the repository; no hand-typed number on screen.
- The pitch runs offline for five minutes using only `docs/PITCH.md` and `docs/RUNBOOK.md`.
