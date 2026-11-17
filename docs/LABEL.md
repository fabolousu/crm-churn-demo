# Churn label and the synthetic world

Spec for `data/generator.py` and the definition every lane must use.
If the label changes, everything downstream is invalid — so it lives in one place.

## Pilot scope

**Italy only**, split into five macro-regions: `nord-ovest`, `nord-est`, `centro`,
`sud`, `isole`. Currency EUR, synthetic VAT numbers, Italian company names.

Region changes the *base rate*, not the model. One pooled model with region as a feature
and per-region calibration — five separate models would have too little labelled data
each. A single-country pilot is also the better pitch: it is a rollout story, not a
fantasy.

## The entity model

```
COMPANY ──< LEAD ──won──> ACCOUNT (customer relationship, ARR, renewal)
```

- The **company** is the master record.
- **Leads** are the CRM's activity records against a company, with a success status:
  `new → contacted → qualified → proposal → won | lost`.
- A **won lead** creates an **account** — the relationship that can churn.

## Definition

> **Churned** = at the 180-day horizon after snapshot date `t0`, the account has no
> renewal, no new won lead, and its status is `inactive` or `cancelled`.

| Parameter | Value |
|---|---|
| Horizon | 180 days |
| Snapshot `t0` | Fixed at `2026-01-01` per generated world |
| Eligible accounts | `tenure_days >= 180` and `status = active` at `t0` |
| Excluded | Accounts younger than 180 days, accounts already churned |
| Target prevalence | ~18–22% (asserted by a generator test) |

**Open question, deliberately flagged:** churn on accounts is the target, with lead status
as a *predictor*. The alternative is predicting **lead-win propensity** instead — a
different target on a different population. If the pitch is "predict churning customers",
churn stays the target; lead success becomes the feature family below. Switching later
means a second model, not a relabel.

## Point-in-time discipline

Features come only from rows with `*_at <= t0`. Labels come only from `(t0, t0 + 180d]`.
Labels live in `account_outcomes`, which feature code may not read. A test enforces it.

## The generating process

Region standardisation first, then:

```
logit(p) = -1.55
         -- commercial state
         + 0.60 * is_renewal_within_60d
         + 0.35 * z(discount_pct)
         - 0.45 * z(seats_active_ratio)
         -- product and service
         + 0.45 * z(-usage_trend_slope)
         + 0.55 * z(tickets_90d)
         + 0.40 * z(last_login_days_ago)
         -- relationship
         - 0.30 * z(nps_last)
         + 0.30 * z(payment_delay_days_avg_180d)
         + 0.25 * z(-meetings_90d)
         -- lead pipeline health (the CRM's own success signals)
         + 0.40 * z(days_since_last_lead)     -- silence is the strongest signal
         + 0.35 * z(leads_lost_90d)
         - 0.30 * z(leads_won_90d)
         + 0.30 * z(median_first_response_hours_90d)
         + region_effect                      -- nord-ovest 0.00, nord-est -0.10,
                                              -- centro +0.10, sud +0.25, isole +0.30
         + noise ~ N(0, 0.35)
p = sigmoid(logit(p)); churned ~ Bernoulli(p)
```

The lead terms are the point of this revision: **a customer whose pipeline went quiet is
churning**, and the CRM already records that. It also gives the demo a distinctive line —
"no new opportunity in 94 days" is more persuasive to a sales director than a usage metric.

Expected results on a correct pipeline: **AUC 0.80–0.86**, calibration error < 0.05,
lift@10% ≥ 3×. Above 0.90 means leakage, not brilliance.

## Feature list (contract)

| Feature | Definition at `t0` | Type |
|---|---|---|
| `tenure_days` | Days since `accounts.started_at` | int |
| `arr` | Annual recurring revenue, EUR | float |
| `seats` | Licensed seats | int |
| `seats_active_ratio` | Active / licensed seats | float |
| `discount_pct` | Contract discount | float |
| `renewal_days_left` | Days until `accounts.renewal_date` | int |
| `is_renewal_within_60d` | Derived from `renewal_days_left` | 0/1 |
| `region` | Company macro-region | text |
| `usage_events_90d` | Product events, last 90 days | int |
| `usage_trend_slope` | OLS slope of weekly events, 90 days | float |
| `last_login_days_ago` | Days since most recent login | int |
| `tickets_90d` | Support tickets opened, last 90 days | int |
| `tickets_sev_high_90d` | Of those, high or critical | int |
| `nps_last` | Most recent NPS (−100…100) | int |
| `meetings_90d` | Meetings, last 90 days | int |
| `emails_90d` | Answered outbound emails, last 90 days | int |
| `payment_delay_days_avg_180d` | Mean days late on invoices | float |
| `leads_created_90d` | Leads created for the company, last 90 days | int |
| `leads_won_90d` | Leads won, last 90 days | int |
| `leads_lost_90d` | Leads lost, last 90 days | int |
| `days_since_last_lead` | Days since the company's most recent lead | int |
| `median_first_response_hours_90d` | Median first-response time on those leads | float |
| `open_pipeline_arr` | ARR of open leads at `t0` | float |
| `win_rate_180d` | Won / (won + lost) over 180 days | float |

## Counterfactual levers

Only these, because only these are believable to an executive — and all re-score the same
model:

| Lever | Effect on features |
|---|---|
| `tickets_resolved: n` | `tickets_90d -= n` (floor 0) |
| `usage_recovery_pct: p` | `usage_trend_slope` moves `p%` toward the regional median |
| `discount_reduction_pct: p` | `discount_pct` scaled down by `p%` |
| `executive_meeting: true` | `meetings_90d += 1`, `nps_last += 5` (capped 100) |
| `new_lead_logged: true` | `leads_created_90d += 1`, `days_since_last_lead = 0` |

That last lever is new and is the demo's best moment: "logging one qualified lead today
moves this account from 71% to 58%" is a claim a sales director immediately understands,
and it makes the CRM's own record-keeping the hero of the story.
