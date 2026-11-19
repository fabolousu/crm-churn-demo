# Start here — handover for the next session

> **Read [`docs/MIGRATION_SPEC.md`](MIGRATION_SPEC.md) first.** It supersedes this file as the
> entry point: it carries the product context, the review hierarchy (CodeRabbit is the primary
> reviewer), the team roster, every gate, the environment quirks and the first-hour sequence.

Written at `bacfa18`. The next session starts with **no memory of the conversation that
produced this repo**, so everything load-bearing is in files.

## Live now

- **Showcase (free, public):** **<https://fabolousu.github.io/crm-churn-demo/>** — deployed by
  `.github/workflows/pages.yml` on every merge to `main`, **fixture mode**, no backend.
- **Repo:** `fabolousu/crm-churn-demo`, protected `main`, 8 merged PRs, 80 commits.
- **Local demo:** `docs/RUNBOOK.md` (uvicorn + `pnpm preview`, API on `:8000`).

## Decisions already made — do not re-ask

| # | Decision |
|---|---|
| Q1 | **The CRM becomes the shell.** The five ML screens move under `/previsioni` as a module. One product, not two apps |
| Q2 | **Slim committed DB** (`demo.slim.db`, ~15 MB, top ~2,000 leads). The 240 MB `data/demo.db` stays local for training only |
| Q3 | **GitHub Pages for the free showcase** (done). **Vercel Hobby** remains the choice for preview deployments + serverless API, but needs a free account and a token — until then D3–D9 are *blocked with a named input*, never faked |
| Q4 | **Both stories in the pitch**: CRM shell is the product, `Previsioni` is the differentiator |

## The plan

`docs/PROJECT_PLAN_V2.md` — workstreams, phases, gates, team roster, risks.
`docs/UI_FEATURE_INVENTORY.md` — 40+ features mapped to targets with P0/P1/P2 and 7 gaps.
`docs/AGENT_MODEL_POLICY.md` — tier policy and the falsifier for each tier.
`workflow/routing.yaml` — 16 tasks with `model`, `tier`, `reviewer`.

## Team and how to invoke it

Model selection is now enabled for Anthropic and Gemini, but **only for sessions created
after the setting changed**. Verify with one cheap call before starting a lane:

```
subagent(provider: "anthropic", model: "claude-opus-4-7", prompt: "reply ROUTE OK")
subagent(provider: "google",    model: "gemini-3.8-flash", prompt: "reply ROUTE OK")
```

If either is refused, the session is not authorized — start another one; do not fall back
silently, because then the "three-vendor team" claim on the pitch becomes false.

| Lane | Vendor / tier |
|---|---|
| T12 CRM schema | Anthropic Opus (reasoning) |
| T13 CRM rules | Anthropic Sonnet (workhorse) |
| T14 seed data | DeepSeek (bulk) |
| T15 CRM UI | Anthropic Sonnet (workhorse) |
| T16 Vercel / slim DB | Gemini (workhorse) |
| T17 verification | Gemini (must not be Anthropic — the authors are) |

## First three moves

1. **Verify routing** with the two calls above. If it fails, stop and report.
2. **T12 + T13** — CRM schema and domain rules, on Anthropic. Create a new migration
   namespace; **the ML tables and their 145 tests must stay green.** Gate: migration applies,
   all pre-existing tests pass, uniqueness/auto-link/status rules covered by tests from spec
   §15.1.
3. **D1 checks in parallel** (no decision needed): `pytest` (all suites), `tsc --noEmit`,
   `pnpm build`, axe accessibility, broken-link crawl. Gate: all green before any merge.

Then: T14 seed → T15 UI → T17 verification → D3–D9 (blocked on Vercel token).

## Non-negotiables

- **Do not rebuild** the generator, features, model, API endpoints, ML screens, gates or CI.
  Patch them. A rewrite needs a written reason.
- **No secrets in the repo.** Routes reference credentials by name (`apiKeyEnv`); a scan of
  the working tree and `git log -S` must stay clean.
- **No fabricated numbers.** Six incidents are recorded in `docs/DECISIONS.md`; every number
  on screen traces to `metrics.json`, the API, or a committed seed.
- **CodeRabbit autofix stays off** — it authored a commit into a PR branch uninvited.
- **Gates are not advisory.** A blocked phase names its missing input; it does not get a
  green checkmark because the work "looks done".

## Environment quirks on this laptop

- `pnpm install` took 45 minutes once (OneDrive + Defender). `web/node_modules` is present.
- Vite build fails removing an `esbuild-*` file in `%TEMP%`: set `TEMP`/`TMP` to a repo
  `.tmp/` directory first. Documented in `docs/RUNBOOK.md`.
- The GitHub token has `repo` + `workflow` scopes; Pages is enabled with `build_type=workflow`.

## Exact kickoff prompt for the new session

> Read `docs/NEXT_SESSION.md`, `docs/PROJECT_PLAN_V2.md` and
> `docs/UI_FEATURE_INVENTORY.md`. Then verify subagent routing to Anthropic and Gemini with
> the two test calls in the handover. If routing works, start T12 (CRM schema, Anthropic
> Opus) and the D1 checks in parallel, and report each gate as passed or blocked.
