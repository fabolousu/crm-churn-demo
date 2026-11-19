# Agent model policy

Status of the premise, stated first because it changes what this document is for.

## There is no Anthropic call in the product

A search of every `.py`, `.ts`, `.tsx`, `.js`, `.mjs`, `.json`, `.yaml` and `.md` file
(excluding `node_modules`, `.git`, `dist`) returns Anthropic/Haiku/Claude only in
`docs/ORCHESTRATION.md` and `workflow/routing.yaml` — as **model-family labels for the build
agents**, never as runtime code. The product's only model is the LightGBM bundle in
`ml/artifacts/model.joblib` (`lead-win-lgbm-v1`); it makes no network API call.

So "tasks that use Haiku" cannot be enumerated, because no task used Haiku. What *is* true,
and is the real defect this workstream can fix:

1. `workflow/routing.yaml` names a **family** (`anthropic`, `deepseek`) but no **tier**, so
   "use the strong model here" was unenforceable — any Anthropic call would have taken the
   account default, which is Haiku-class.
2. Every lane in this build actually ran on `deepseek-flash`, because no Anthropic route was
   configured in the harness when the lanes ran. That is a documented gap, not a model choice.

The policy below fixes both: every task class has a tier, a reason, and a test for when the
tier is wrong.

## Tiers

| Tier | Models | Use for | Never use for |
|---|---|---|---|
| **Reasoning** | Claude Opus (or Sonnet when the task is bounded) | Decisions whose cost of being wrong exceeds the price difference: contracts, invariants, cross-lane design, adjudicating a disputed review finding | Anything a test can adjudicate |
| **Workhorse** | Claude Sonnet | Code-bearing lanes with subtle logic (point-in-time, leakage, transaction boundaries), review triage, executive-facing copy | Bulk repetition |
| **Bulk** | Claude Haiku | Mechanical, fully specified, cheap to verify: fixtures, test scaffolding, PR bodies, formatting, PR-title assembly | Any task where a silent wrong answer passes a build |
| **Cost lane** | DeepSeek flash | The same mechanical class where cost dominates and a gate catches errors | Reasoning or taste |

Decision rule, applied per task: **if a wrong answer is caught by an automated gate, use the
cheapest tier that passes it. If it is caught only by a human or not at all, use the highest
tier the budget allows.**

## Task-by-task mapping

`prev` is what actually ran; `tier` is the policy. Tasks marked **↑** are the ones this
workstream moves up from a Haiku-class default.

| # | Task | Prev | Tier | Why |
|---|---|---|---|---|
| T1 | Contract & architecture (label, schema, API, invariants) | deepseek-flash | **Reasoning ↑** | Wrong now = every lane wrong later. Not gate-detectable: gates check conformance to the contract, not its correctness |
| T2 | Synthetic world generator | deepseek-flash | **Workhorse ↑** | Statistical correctness; a plausible-looking world can be wrong in ways only a specialist notices |
| T3 | Feature pipeline / point-in-time | deepseek-flash | **Reasoning ↑** | Leakage is silent by construction. This is the single highest-consequence code in the repo |
| T4 | Training, calibration, explanations | deepseek-flash | **Workhorse ↑** | Tuning and split discipline need judgement; the gate catches only the thresholds |
| T5 | API service against a frozen contract | deepseek-flash | **Bulk** (Haiku/flash) | Fully specified by `openapi.yaml`; contract tests adjudicate every field |
| T6 | Executive UI | deepseek-flash | **Workhorse ↑** | Taste is not testable; the screen either reads well to a CFO or it doesn't |
| T7 | Retention simulation / mechanical endpoints | deepseek-flash | **Bulk** | Small, specified, unit-tested |
| T8 | Integration & wiring | deepseek-flash | **Reasoning ↑** | Cross-lane context; failures are emergent, not local |
| T9 | Review triage (findings → fixes) | anthropic (untiered) | **Workhorse** | Must judge whether a finding is real; Haiku would accept the tool's output uncritically |
| T10 | Pitch copy, Q&A, runbook | anthropic (untiered) | **Workhorse** | Every drifts-versus-source failure in this build was a copy failure |
| T11 | Fixture regeneration, PR bodies, doc formatting | n/a | **Bulk** | Purely mechanical, verified by diff |

## Where Haiku is still justified

| Use | Why lower tier is correct |
|---|---|
| Fixture regeneration from the API | The input is an API response and the output is a file; a diff proves correctness |
| PR body assembly from command output | Copy-paste of real output; wrong copy is visible in review |
| Test scaffolding for an already-specified endpoint | The contract test fails if the scaffolding is wrong |
| Commit-message drafting | Human reads it; no run-time consequence |
| Bulk doc formatting / link fixing | Reversible, cheap to check |

The rule that makes these safe: **each Haiku use has a gate that fails on a wrong answer.**
Where that is not true, the task is misclassified.

## Consequence for a re-run

If this build were run again with Anthropic routes configured, the routing manifest would
send T1, T3, T8 to Opus; T2, T4, T6, T9, T10 to Sonnet; T5, T7, T11 to Haiku; and keep the
DeepSeek cost lane for T5/T7 where vendor diversity matters more than tier. The lanes that
produced this build ran on one model family — that is the honest limitation of the artifact,
and it is why this document describes policy rather than a migration.
