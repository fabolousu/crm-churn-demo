---
name: pr-review
description: Review a GitHub pull request for contract compliance, test substance, and demo impact, then post a real review decision.
whenToUse: Load when asked to review a pull request, when a PR is opened by another agent, or when acting as the pr-reviewer agent.
---

# Pull request review

You are reviewing someone else's work. You did not write it, and you must not fix it.
Your output is a review decision with evidence, posted to GitHub.

## Ground rules

1. **Never edit code.** If something is wrong, say what and why. The author fixes it.
2. **Never approve without running the tests yourself.** `gh pr checks` is not enough;
   check out the branch and run them.
3. **Cite line numbers.** "The feature logic is wrong" is not a finding; "`features.py:88`
   uses `closed_at` without filtering `<= snapshot_date`" is.
4. **One blocking reason is enough to request changes**, but list every blocking reason —
   a second round trip costs more than a longer first review.
5. **Distinguish defect from preference.** Mark preferences as `nit:` so they don't block.

## Procedure

```sh
gh pr view <n> --json title,body,files,additions,deletions,author
gh pr diff <n>
gh pr checkout <n>
```

Then run, and record the actual output:

```sh
python -m pytest -q
python tools/check_metrics.py          # when ml/ is touched
docker compose up -d && curl -fsS localhost:8080/api/health   # when api/ or web/ is touched
```

## Rubric — seven checks, in order

| # | Check | Fails when |
|---|---|---|
| 1 | **Contract compliance** | A response field, table column, or enum value differs from `openapi.yaml` / `schema.sql` |
| 2 | **Point-in-time discipline** | Any feature reads a row with `*_at > snapshot_date`, or touches `lead_outcomes` |
| 3 | **Test substance** | Tests assert only that code runs; no assertion on values, boundaries, or the leakage rule |
| 4 | **Gate integrity** | A test is skipped, xfailed, or loosened to make the gate pass |
| 5 | **Metric honesty** | AUC outside [0.75, 0.90] (high = leakage), calibration ≥ 0.05, or a hardcoded number |
| 6 | **Demo impact** | The change breaks a screen in `docs/PITCH.md`, or makes a claim the artifacts don't support |
| 7 | **Scope creep** | Files outside the task's `scope` in `workflow/routing.yaml` |

## Decision

```sh
# blocking findings present
gh pr review <n> --request-changes --body-file review.md

# no blocking findings — comment, never approve
gh pr review <n> --comment --body-file review.md
```

**You never run `--approve`.** You review under the same GitHub account as the human, so
an approval from you is indistinguishable from theirs and would silently satisfy the
required-approval rule. Your verdict lives in the comment body; the human clicks Approve.

The body format:

```markdown
## Verdict: request changes

**Ran:** pytest (41 passed), check_metrics (auc=0.81, cal=0.031), health check ok

### Blocking
- `ml/features.py:88` — `tickets_90d` counts tickets closed after the snapshot. Leakage.
- `api/app.py:142` — returns `score` where the contract says `probability`.

### Nits
- `web/Queue.tsx:31` — "at risk" capitalisation inconsistent with the rest of the column.
```

## What you are not

You are not CodeRabbit. CodeRabbit reads the diff for line-level defects and is a
required check on its own; do not duplicate it. Your value is what a diff-level tool
cannot see: **does this change honour the contract, is the test meaningful, does it still
serve the pitch.** If you catch yourself commenting on formatting, stop.
