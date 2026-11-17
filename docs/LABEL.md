# Churn label and the synthetic world

This file is the spec for `data/generator.py` and the definition every lane must use.
If the label changes, everything downstream is invalid — so it lives in one place.

## Definition

> **Churned** = at the 180-day horizon after snapshot date `t0`, the account has no
> renewal, no new order, and its status is `inactive` or `cancelled`.

| Parameter | Value |
|---|---|
| Horizon | 180 days |
| Snapshot `t0` | A single fixed date per generated world, `2026-01-01` |
| Eligible accounts | `tenure_days >= 180` and `status = active` at `t0` |
| Excluded | Accounts younger than 180 days (no history), accounts already churned |
| Target prevalence | ~18–22% (asserted by a generator test) |

The horizon is a *pitch* decision, not a statistical one: 180 days is long enough that a
rep can act, short enough that the number can be measured within a year.

## Point-in-time discipline

Features come only from events with `event_at <= t0`. The label is read only from
`(t0, t0 + 180d]`. These live in different tables (`features` vs `account_outcomes`), and
`ml/features.py` is forbidden from reading `account_outcomes`. A test enforces it.

This is the discipline that separates a demo that survives due diligence from one that
scores 0.95 offline and is useless in production.

## The generating process

Churn is generated from an explicit hazard model so the ground truth is known. Every
continuous feature is standardised within its business unit before entering the logit.

```
logit(p) = -1.55
         + 0.55 * z(tickets_90d)
         + 0.45 * z(-usage_trend_slope)          # declining usage raises risk
         + 0.40 * z(last_login_days_ago)
         + 0.60 * is_renewal_within_60d
         + 0.35 * z(discount_pct)                # deep discount = price-sensitivity signal
         - 0.45 * z(seats_active_ratio)
         - 0.30 * z(nps_last)
         + 0.30 * z(payment_delay_days_avg_180d)
         + 0.25 * z(-meetings_90d)               # fewer touchpoints raises risk
         + bu_effect                             # north 0.00, south +0.25, emea -0.15
         + noise ~ N(0, 0.35)                    # unobserved factors
p = sigmoid(logit(p)); churned ~ Bernoulli(p)
```

`noise` is what makes this an honest test: without it, a model would recover the exact
function and report a fake AUC of 0.99.

Expected results on a correctly built pipeline: **AUC 0.80–0.86**, calibration error
below 0.05, lift@10% of 3× or better. A model that scores above 0.90 is a leakage bug,
not a triumph — that is the check the reviewer applies.

## Feature list (contract)

| Feature | Definition at `t0` | Type |
|---|---|---|
| `tenure_days` | Days since `accounts.created_at` | int |
| `arr` | Annual recurring revenue | float |
| `seats` | Licensed seats | int |
| `seats_active_ratio` | Active seats / licensed seats | float |
| `usage_events_90d` | Product events in the last 90 days | int |
| `usage_trend_slope` | OLS slope of weekly events over 90 days | float |
| `tickets_90d` | Support tickets opened in the last 90 days | int |
| `tickets_sev_high_90d` | Of those, severity high or critical | int |
| `last_login_days_ago` | Days since most recent login | int |
| `renewal_days_left` | Days until `accounts.renewal_date` | int |
| `is_renewal_within_60d` | Derived flag from `renewal_days_left` | 0/1 |
| `discount_pct` | Contract discount | float |
| `payment_delay_days_avg_180d` | Mean days late on invoices | float |
| `nps_last` | Most recent NPS score (−100…100) | int |
| `meetings_90d` | Meetings in the last 90 days | int |
| `emails_90d` | Outbound emails answered in the last 90 days | int |
| `bu`, `region`, `industry` | Categoricals | text |

## Counterfactual levers

Only these are permitted, because only these are believable to an executive:

| Lever | Effect on features |
|---|---|
| `tickets_resolved: n` | `tickets_90d -= n` (floor 0) |
| `usage_recovery_pct: p` | `usage_trend_slope` moves `p%` toward the BU median |
| `discount_reduction_pct: p` | `discount_pct` scaled down by `p%` |
| `executive_meeting: true` | `meetings_90d += 1`, `nps_last += 5` (capped 100) |

Each lever returns a new probability from the same model, never a separate formula.
If the UI showed a hand-built estimate, the demo would be lying in the most
convincing possible way.
