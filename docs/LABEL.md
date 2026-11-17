# Lead-win label and the synthetic world

Spec for `data/generator.py` and the definition every lane must use.
If the label changes, everything downstream is invalid — so it lives in one place.

## The business shape this encodes

Contracts in this business **renew whenever there is a new initiative**. There is no
renewal date, no renewal event, and therefore **no conventional churn**. A customer
relationship is a sequence of initiatives, and it ends when initiatives stop being
proposed — not on a date.

That single fact drives the whole design:

| Conventional CRM | This CRM |
|---|---|
| Customer churns at a renewal date | Initiative is **won or lost**; relationship decays when initiatives stop |
| Target: probability of churn | Target: **probability an initiative is won** |
| Horizon: 180 days of silence | Horizon: none needed — the lead closes |
| "Save this customer" | "Win this initiative" |

**Dormancy** survives as a derived indicator, not a target: a company with no new
initiative for 180+ days is flagged dormant on its company page. It is shown, not modelled.

## Pilot scope

**Italy only**, five macro-regions: `nord-ovest`, `nord-est`, `centro`, `sud`, `isole`.
EUR throughout, synthetic Italian company names and format-plausible VAT numbers.

Region changes the base rate, not the model: one pooled model with region as a feature and
per-region calibration. At 20k companies and ~60k leads, a per-region model would be
thinner than the pooled one.

## Definition

> **Won** = a lead whose `status` is `won` at close. **Lost** = `lost`.
> The model predicts `won` for a lead that has reached at least `qualified`.

| Parameter | Value |
|---|---|
| Population | Leads created before `t0`, reached `qualified`, closed by `t0` |
| Excluded | Leads still open at `t0` (censored — they have no label yet) |
| Scoring point | `qualified_at`; for open leads, their current stage at `t0` |
| Label | `won = 1` if the lead closed `won`, else `0` |
| Target prevalence | ~25–30% (asserted by a generator test) |

Excluding censored leads is not fastidiousness — including them silently teaches the model
that open means lost, and the pipeline screen would rank exactly backwards.

## Point-in-time discipline

Features are computed as of `snapshot_date` (the scoring point). Nothing after it may
appear in `lead_features`: not the outcome, not the final amount, not a late stage change.
Labels live in `lead_outcomes`, which feature code may not read. A test enforces it.

## The generating process

**Standardisation reference (part of the contract).** Continuous features are standardised
over the **generated population at `t0`, globally** — not per region, and not over the scored
subset. The generator's reference scale is therefore observable and fixed, not an
implementation detail: a different reference population rescales the logit and changes the
achievable AUC.

One consequence is written down here on purpose: the world has a **known signal ceiling**.
The lane that built it measured the latent-probability AUC at **~0.79**, so a faithful model
should land around 0.77–0.79, and anything near 0.86 is leakage rather than skill.
`tools/check_metrics.py` enforces exactly that: the reported AUC may not exceed the latent
ceiling by more than 0.02.

```
logit(p) = -0.95
         -- response and engagement (the strongest controllable signal)
         - 0.45 * z(log1p(first_response_hours))
         + 0.25 * z(meetings_before_scoring)
         + 0.30 * is_proposal_stage
         -- evidence from the account's history
         + 0.40 * z(prior_won_initiatives)
         - 0.30 * z(prior_lost_initiatives)
         + 0.35 * z(owner_win_rate_180d)
         + 0.20 * z(-days_since_last_initiative)
         -- deal shape
         - 0.25 * z(amount_arr)               -- bigger initiatives are harder
         - 0.20 * z(discount_pct)
         -- friction
         - 0.25 * z(tickets_90d)
         + 0.20 * z(nps_last)
         + source_effect                      -- referral +0.35, partner +0.15,
                                              -- inbound +0.10, event 0.00, outbound -0.25
         + region_effect                      -- nord-ovest 0.00, nord-est +0.05,
                                              -- centro 0.00, sud -0.10, isole -0.15
         + noise ~ N(0, 0.40)
p = sigmoid(logit(p)); won ~ Bernoulli(p)
```

Expected results on a correct pipeline: **AUC 0.78–0.86**, calibration error below 0.05,
lift@10% of 2.5× or better. The band in `tools/check_metrics.py` is [0.75, 0.90]; above
0.90 means leakage, because `noise` and the censoring rule cap what is knowable.

A lead-scoring model is naturally weaker than a churn model — less history per record and
more human variance. Anyone who claims 0.95 on this task is measuring their own leak.

## Feature list (contract)

| Feature | Definition at the scoring point | Type |
|---|---|---|
| `source` | Lead source | text |
| `stage_at_scoring` | `new`/`contacted`/`qualified`/`proposal` | text |
| `age_days_at_scoring` | Days from `created_at` to scoring | int |
| `amount_arr` | Proposed initiative value, EUR | float |
| `discount_pct` | Proposed discount | float |
| `first_response_hours` | Hours to first response, but **only when `first_response_at <= snapshot_date`**; otherwise NULL. A `contacted` lead scored at creation has not been answered yet | float |
| `region` | Company macro-region | text |
| `industry`, `employees` | Company firmographics | text, int |
| `company_age_days` | Days since `companies.created_at` | int |
| `prior_won_initiatives` | Won initiatives before this one | int |
| `prior_lost_initiatives` | Lost initiatives before this one | int |
| `days_since_last_initiative` | **Snapshot-relative**: days from the scoring point back to the previous lead's `created_at`. Not creation-to-creation | int |
| `lifetime_won_arr` | Total ARR won from this company | float |
| `open_initiatives_count` | Leads **open at the snapshot**: `created_at <= snapshot AND (closed_at IS NULL OR closed_at > snapshot)`, excluding the scored lead. Not "currently open" | int |
| `usage_trend_slope` | OLS slope of weekly usage, 90 days | float |
| `tickets_90d` | Support tickets, last 90 days | int |
| `nps_last` | Most recent NPS (−100…100) | int |
| `payment_delay_days_avg_180d` | Mean days late on invoices | float |
| `meetings_before_scoring` | Meetings on this lead so far | int |
| `owner_win_rate_180d` | Win rate of the assigned rep over the 180 days before the snapshot, **excluding the scored lead's own closure** | float |

### Conventions that must not drift

1. **Snapshot-relative, not record-relative.** `days_since_last_initiative` measures from the
   scoring point. The generator and the feature pipeline must use the same convention, or the
   model learns a signal the demo cannot explain.
2. **Open at the snapshot is a timestamp test**, never a status test. A lead that was open at
   `S` and closed later still counts at `S`; a lead whose close date changes must not change
   a historical row.
3. **A feature may only use an event that has happened by the snapshot.** `leads.first_response_at`
   is the source of truth for when a response happened; `lead_features.first_response_at` records
   the instant the feature row actually used, and `first_response_hours` is NULL whenever that
   instant is after the snapshot. A duration with no timestamp is unverifiable — this was a real
   defect caught on PR #1.
4. **Never let a record's own outcome enter its features.** `owner_win_rate_180d` excludes the
   scored lead, and company-level history excludes it too. Self-inclusion is leakage that
   looks like a strong model.
5. **`NULL` means "not measured"; `0.0` means "measured zero".** Do not conflate them: these
   columns are z-scored, and a sentinel zero silently shifts the distribution.

## Counterfactual levers

All forward-looking — nothing time-travels a response that already happened — and all
re-score the same model:

| Lever | Effect on features |
|---|---|
| `exec_sponsor_meeting: true` | `meetings_before_scoring += 1`, `nps_last += 5` (cap 100) |
| `discovery_meeting: true` | `meetings_before_scoring += 1` |
| `discount_pct: p` | `discount_pct = p` |
| `accelerate_to_proposal: true` | `stage_at_scoring = 'proposal'` |

The pitch line this produces: **"Book an executive sponsor meeting and this initiative
goes from 34% to 52%."** Actionable, forward-looking, and computed by the model rather than
by a slide.
