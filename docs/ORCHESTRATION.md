# Orchestration: when agents run, and how the model is chosen

Two separate questions, often conflated:

- **Sequencing** — which agent is live at which moment, and what it waits for.
- **Routing** — which model/agent is *better* for a given task class, decided by policy,
  not by vibes.

## 1. Sequencing

One lead, flat fan-out, serialized gates. `maxDepth` stays at 1: a child cannot spawn its
own children, so the tree is shallow and accountable. Every child gets `cwd` = the repo
root and `delivery: parent`, so results come back as completion notices, not as tool
output that floods the lead's context.

```
t0  ├── A   generator + seed            (writes data/demo.db)
    ├── B1  features.py against schema  (no data needed yet)
    ├── C   api/app.py on openapi.yaml
    ├── D   web/ shell on fixtures
    └── E   retention simulation stub
t1  └── B2  train.py + explain.py       (waits for A green + B1 merged)

t2  ├── P3  integrator: wire API + UI + seed + compose   (serial — one agent)
    └── D   switch fixtures to live API

t3  └── P4  CodeRabbit gate + triage agent   (serial — tool detects, agent triages)

t4  ├── P5  pitch artifacts, demo hardening
    └──     human dry run of the 5-minute script
```

| Moment | Agents live | Gate before the next moment |
|---|---|---|
| t0 | A, B1, C, D, E (5 concurrent) | Each lane's own tests; contract tests for C |
| t1 | B2 | Generator asserts ~20% prevalence and BU base rates |
| t2 | P3 integrator, D | End-to-end click-through on `compose up` |
| t3 | P4 triage agent | Deterministic checks green **and** CodeRabbit exit 0 |
| t4 | P5 | The demo runs unattended, twice, in a row |

Lanes are independent **because of Phase 0**. Without `schema.sql` and `openapi.yaml` as
a frozen seam, five concurrent agents would produce five incompatible repos and the
integrator would spend its whole life reconciling. The contract is what buys parallelism.

The parallelism ceiling is honest: **five at t0, two at t2, one at t3.** Most of the
project's wall-clock is the review loop, not the fan-out.

## 2. Routing

### The idea

You cannot know a priori which model is best at "write a FastAPI endpoint for this
schema". So don't guess per task — **define task classes, assign by policy, then let the
gates decide**. "Best" is not a property of a model; it is a property of a model × task
class × verification method, observed over time.

### Ordered decision procedure

Applied per task class, once, and recorded:

1. **Is the output automatically verifiable?** (contract test, schema check, metric
   threshold, `docker compose up` succeeds)
   → If yes: pick the **cheapest model that reliably passes**, because quality is measured
   rather than trusted.
2. **Is the blast radius large or is it irreversible?** (schema design, training code,
   anything that invalidates the demo)
   → Strongest reasoner, and I review it myself.
3. **Does it need cross-file synthesis or long context?** (integration, wiring, refactors
   spanning lanes) → long-context model, and serialize it.
4. **Is it taste, not correctness?** (UI polish, pitch writing)
   → Model with the best one-sample judgement; your eyes are the gate, because no test
   can check it.
5. **Is it bulk and mechanical?** (stubs, fixtures, repetitive endpoints)
   → cheapest capable model, high volume, low consequence.
6. **Always:** the gate is **external to the model families that wrote the code** — a
   third-party reviewer tool, not a sibling model — and no agent ever certifies its own
   output.

### The routing table for this demo

| Class | Phase | Agent / model | Why this one | Gate | Fallback |
|---|---|---|---|---|---|
| T1 Contract & architecture | P0 | **Lead** (Anthropic, strong reasoning) | Highest-leverage, irreversible; needs judgement across everything | Your eyeball | — |
| T2 Synthetic world | A | **OpenAI** implementer | Statistics correctness + code; self-verifiable via asserts | prevalence test, distribution review | escalate to lead |
| T3 Features | B1 | **OpenAI** implementer | Subtle timing logic; leakage is silent | leakage test | lead writes it |
| T4 Training + SHAP | B2 | **OpenAI** strong | Highest technical risk in the project | AUC 0.80–0.86, calibration < 0.05 | lead + reviewer pairing |
| T5 API service | C | **DeepSeek** | Fully specified by OpenAPI → mechanical | contract tests green | OpenAI |
| T6 UI | D | **OpenAI** strong | Taste + exec polish; hard to verify | your review of one screen | — |
| T7 Retention sim | E | **DeepSeek** | Small, mechanical, low consequence | unit test | OpenAI |
| T8 Integration | P3 | **Lead** | Cross-lane context; where agents diverge | click-through | OpenAI strong |
| T9 Review | P4 | **CodeRabbit CLI** `--gate major` + **triage agent** | Third-party detection; exit codes make it a real gate | exit 0 **and** deterministic checks | blocks release |
| T10 Pitch artifacts | P5 | **Anthropic** | Writing quality is the deliverable | your read | — |

### Escalation, not second-guessing

- **Gate fails once** → same agent retries with the failure output attached (cheap, and
  usually sufficient).
- **Gate fails twice** → escalate one tier (DeepSeek → OpenAI → lead). Record it.
- **Gate fails three times** → the *spec* is wrong, not the model. Stop the agent, fix
  `docs/DECISIONS.md` or the contract, restart. This is the rule that saves the most
  money and the most time.

Every outcome goes into a scoreboard (task class, model, attempts, result). After the
demo, the table above stops being a guess and becomes evidence — and re-running the
project with different models becomes a measurement instead of an argument.

### What "best" means here, precisely

| Task type | Metric for "best" | Because |
|---|---|---|
| Verifiable (API, sim, generator) | pass rate per euro | an agent that passes the gate for 1/5 the price is better |
| High-risk (model, features) | first-pass gate success | a retry loop on training code costs more than a stronger model |
| Taste (UI, pitch) | your judgement on one sample | unmeasurable; sample it once, keep it |
| Review | defect catch rate | only worth having if it finds what the authors missed |

### Mechanics in DSH

- **Static routing** (the default here): the workflow script passes
  `agent(prompt, { provider, model })` per call, and the tool's `agentOptions` supplies
  defaults. Deterministic, auditable, reproducible — exactly what a pitch build needs.
- **Dynamic routing** (available, not used): `modelSelection: true` on the `subagent` tool
  plus `list_subagent_models`, letting a lead choose per call. Powerful and
  non-deterministic; wrong choice for a demo that must run the same way twice.
- **Role-bound routing**: an `agentPreset` per role pins model and tools together. Use it
  when a role recurs across projects, not for a one-off demo.
- Requires **Settings → Plugins → Subagent → Model selection** to authorize all three
  routes for new sessions; otherwise every cross-vendor call is clamped.

## 3. The CodeRabbit gate

Correction to an earlier assumption: **this needs no plugin.** CodeRabbit ships a CLI,
and a CLI is a better gate than a plugin would be — it returns deterministic exit codes,
so the gate does not depend on a model choosing to be strict.

### What it gives us

| Command | Purpose |
|---|---|
| `coderabbit review --agent` | NDJSON structured findings for agent consumption |
| `coderabbit review --agent --gate major` | **Exit 2 when any finding is `major` or above** — the blocking gate |
| `coderabbit review --agent --base main` | Review the branch diff rather than the working tree |
| `coderabbit review --uncommitted --include-untracked` | Review work that hasn't been committed yet |
| `coderabbit auth login --api-key <key>` | Non-interactive auth, suitable for a build script |
| `coderabbit doctor` | Verify install and local review readiness |
| `coderabbit usage` | Included reviews and billing-period usage |

### Exit-code semantics (the part that must be handled correctly)

| Exit | Meaning | Gate decision |
|---|---|---|
| `0` | Review complete, nothing at or above the gate severity | pass |
| `1` | Review failed **or did not cover every file** | **block** — an incomplete review is not a pass |
| `2` | Findings at or above `--gate` severity | **block**, hand findings to the authors |
| other | Auth, network, or usage-limit failure | **block** and surface the diagnostics |

Treating exit 1 as success is the classic mistake here: it means *not everything was
reviewed*, which is exactly when a gate should hold.

### Division of labour

- **CodeRabbit detects.** It is the third-party reviewer: independent of OpenAI,
  Anthropic, and DeepSeek, so it satisfies the cross-vendor rule structurally.
- **The triage agent decides.** Its job is not to invent findings — it reads the NDJSON,
  separates real defects from noise, deduplicates, assigns each to the owning lane, and
  re-runs the gate. It cannot pass the gate by disagreeing with it; it can only file a
  fix or escalate with reasoning.
- **The lead adjudicates disputes.** If CodeRabbit flags something the author believes is
  a false positive, the lead decides and records it in `docs/DECISIONS.md`.

### What CodeRabbit cannot gate

It reviews a diff. It has no opinion on whether:

- `ml/artifacts/metrics.json` meets the AUC/calibration thresholds,
- the generator produces a plausible prevalence,
- `docker compose up` actually serves the demo,
- the UI is legible to an executive.

Those stay as deterministic gates (`pytest`, a metrics assertion, a compose smoke test).
**The gate is layered: machine-checkable correctness first, CodeRabbit on top, human on
the pitch.** A single tool that claims to gate everything is a single point of failure.

### Practical constraints

- Needs an account and an API key, and it eats into an included-review quota — so run it
  at **build time and on lane merges**, never on every keystroke.
- Requires network. The **demo run itself must stay offline**; the gate runs before, and
  the artifacts are committed.
- Windows: the CLI has a native install path; `doctor` is the fastest way to confirm the
  binary and `coderabbit` (not the `cr` alias) resolves from PowerShell.
- `tools/review.ps1` implements the full layered gate and maps the exit codes above.

## 4. The honest limitation

Five lanes and three vendors does not mean fifteen meaningful choices. This project has
**six real decision points** (T2, T3/T4, T5, T6, T9, T10). Everything else is either the
lead's work or serialized integration. Over-orchestrating — an agent per file, a
"coordinator agent" between lanes — adds handoff cost and context loss without adding
capability. The contract is what makes five agents safe; the gates are what make them
correct; the routing table is what makes them affordable.
