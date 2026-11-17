## What and why

<!-- One paragraph. Link the task id from workflow/routing.yaml, e.g. T5-api. -->

Task: `T?-????`
Scope touched: <!-- must match the task's scope in workflow/routing.yaml -->

## Evidence

Paste real command output, not a claim.

```
$ python -m pytest -q
$ python tools/check_metrics.py
```

## Self-review checklist

- [ ] Every file in the diff is inside this task's `scope`
- [ ] Tests assert values or boundaries, not just that code runs
- [ ] No test skipped, xfailed, or loosened to pass
- [ ] No feature reads a row dated after the snapshot, and nothing in `ml/` reads `account_outcomes`
- [ ] Response shapes match `api/openapi.yaml`; columns match `data/schema.sql`
- [ ] If a screen changed, it still matches the flow in `docs/PITCH.md`
- [ ] No fabricated metric: every number quoted comes from `ml/artifacts/metrics.json`

## Reviewers

Three gates run on this PR, and all three must be green:

| Gate | Owner | Blocks on |
|---|---|---|
| Deterministic | CI (`ci.yml`) | failing tests or metrics outside [0.75, 0.90] |
| Line-level | CodeRabbit (GitHub app) | findings at `major` or above |
| Judgement | `pr-reviewer` agent + human (you) | contract, test substance, demo impact |
