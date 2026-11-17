# Pull request review

Three independent gates run on every PR. They are deliberately different in kind, because
one tool that claims to catch everything is one tool that can be argued with.

| Layer | Who | Sees | Blocks on |
|---|---|---|---|
| **1. Deterministic** | CI (`ci.yml`) | The whole repo | Failing tests, AUC outside [0.75, 0.90], calibration ≥ 0.05, label leakage, contract drift |
| **2. Line-level** | CodeRabbit (GitHub app) | The diff | Findings at `major` or above (`coderabbit review --agent --gate major`) |
| **3. Judgement** | `pr-reviewer` agent, then a human | The diff **and** the contract | Contract violations, hollow tests, demo impact, scope creep |

## Why the third layer is a separate agent

CodeRabbit reads the diff. It cannot know that `tickets_90d` must exclude rows after the
snapshot date, or that a renamed response field breaks `web/`, or that a test asserting
`is not None` is worthless. Those require the contract in context — so the reviewer is a
different agent with a different prompt, mounted separately, holding the whole repo.

It is also a different **agent**, not just a different model: separate persona, separate
tool set, separate preset (`profiles/preset-pr-reviewer.patch.yml`), and it never reviews
its own work. Independence here is structural, not a matter of instructions.

## The loop

```
lane agent ──► branch ──► gh pr create ──► CI + CodeRabbit ──► pr-reviewer
                                                                    │
                     ┌──────────────────────────────────────────────┤
                     │ approve                                      │ request changes
                     ▼                                              ▼
              human merge                              findings → author's lane
                                                       (same agent, failure attached)
```

1. An implementer works on `lane/<task-id>`, pushes, and opens a PR using the template.
2. CI and CodeRabbit run automatically; both are required checks.
3. The lead dispatches `pr-reviewer` with the PR number.
4. Reviewer checks out the branch, runs the tests itself, applies the seven-check rubric,
   and posts `--approve` or `--request-changes`.
5. On `request-changes`: the authoring agent gets the findings verbatim and pushes a fix to
   the same branch. Escalation rules live in `workflow/routing.yaml`.
6. A human merges. No agent merges to `main`.

## Rules

- **No agent merges to `main`.** Merging is the human gate.
- **No agent approves either.** The reviewer posts `--request-changes` or `--comment`,
  never `--approve`: it runs under the human's GitHub token, so its approval would satisfy
  branch protection while proving nothing. Your click is the approval.
- **No self-review.** The reviewer never reviews a branch authored in the same session.
- **Findings must be reproducible.** Every blocking comment names a file:line and the
  command that exposed it.
- **A green PR that weakened a test is a red PR.** Weakening a gate is the one change that
  always requests changes, regardless of severity.
- **CodeRabbit stays enabled on the repo**; its app review and the agent review are
  complementary, not redundant. Turn off neither.

## Repo bootstrap (one-time)

The repository is initialized locally with `main` as the default branch. Pushing needs a
valid GitHub token:

```powershell
gh auth login -h github.com
gh repo create crm-churn-demo --private --source . --remote origin --push
```

Then, in the repository settings:

1. Branch protection on `main`: require the `ci` checks, require one approval, no direct pushes.
2. Install the CodeRabbit GitHub app on the repository.
3. Add `CODERABBIT_API_KEY` as a repository secret if the CLI is used in CI rather than via the app.
