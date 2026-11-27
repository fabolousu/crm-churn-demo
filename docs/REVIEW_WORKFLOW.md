# Review workflow (canonical)

CodeRabbit is the mandatory pull-request reviewer for this repository. It is not optional and not replaceable by a model panel.

## Canonical configuration

`.coderabbit.yaml` must contain:

```yaml
reviews:
  auto_review:
    auto_pause_after_reviewed_commits: 0
  finishing_touches:
    autofix:
      enabled: true
```

This is the same semantic configuration in `bookinator` and `crm-churn-demo`. Comments and ordering may differ; the values may not.

## Write and autofix

- CodeRabbit has write access to the repository.
- Autofix is triggered by `@coderabbitai autofix` in a PR comment, or by the Fix comments checkbox. It does not silently rewrite every review.
- A bot commit is a normal code change: it needs independent review and tests before merge.
- Human approval on the PR remains mandatory. CodeRabbit cannot approve or merge on its own.

## Independence

A reviewer that can write is not an independent reviewer. The canonical workflow accepts that tradeoff by keeping a human gate:

1. CodeRabbit reviews and may commit fixes.
2. The human reads the bot commits like any other change.
3. The human approves and merges.

Model panels, supervisor verdicts and play tests are supplementary evidence. They do not replace CodeRabbit and they do not replace human approval.

## Change control

Any change to the canonical block above must change this document and the canonical check in `bookinator` (`workflow/check_coderabbit_canonical.py`) in the same pass. That check compares this repository's semantic config with the Bookinator config and fails on drift.
