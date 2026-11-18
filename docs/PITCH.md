# The pitch

Audience: business / executives. Five minutes, one laptop. The demo *is* the pitch.

## The argument

> Your contracts don't renew on a date. They renew when someone proposes the next
> initiative. So a CRM that stores records can't tell you the one thing that matters:
> **which initiative you are about to lose.**

Three claims, each proved by a screen:

1. **The first screen is the pipeline, ranked by expected value** — not a list of records.
2. **Every probability explains itself** in three drivers a sales director recognises.
3. **You can see the action that moves it** before spending the meeting.

## Why the "no renewal" detail is the whole story

Most churn models assume a renewal date. This business doesn't have one — a relationship
continues because someone keeps proposing initiatives. That makes the pipeline itself the
retention mechanism, and it makes lead-win prediction the highest-value model in the CRM.

Dormancy still exists, and it is shown: a company with no new initiative in 180+ days is
flagged on its page. It is a *symptom*, not the target — and noticing that is what makes
this analysis credible to a sales director.

## The five minutes

| Time | Screen | Line |
|---|---|---|
| 0:00 | Title, one sentence | "We don't have renewals. We have initiatives. This is a CRM that knows which ones we're losing." |
| 0:30 | **Pipeline queue** | "First screen: open initiatives ranked by expected value. €720M of open pipeline, €282M of it expected — ordered by what's worth a meeting." |
| 1:30 | **Lead 360** | Click the top lead. "Moretti Componenti: 59.9% to win, €142k expected. Three reasons, in business language, and none of them is a dashboard." |
| 2:30 | **The lever** | Switch the sort to leverage. "Rossi Componenti: 47.5% to 67.0% with an executive sponsor — 19.5 points, €23k of ARR moved. The biggest deal on the page is worth 0.9 points. **That** is the rethink: rank by where effort pays off." |
| 3:30 | **Act, then re-score** | Click. "Action logged, probability updated, and the lead moves in the queue. The loop closes." |
| 4:20 | **Portfolio** | "Five Italian regions, one calibrated model — so 34% means 34%, not just 'unlikely'." |
| 4:50 | Close | "The model is the easy part. The rethink is that this screen replaces the record-first CRM everyone else still ships." |

## Three numbers to have ready

- **Expected pipeline value** — what the queue is worth, in EUR.
- **Lift at the top decile** — how much better than random targeting. The honest headline,
  not raw accuracy.
- **Calibration error** — because "34%" must mean 34%; it's the difference between a
  dashboard and a decision tool.

All three come from `ml/artifacts/metrics.json`. If a number isn't in that file, the answer
is "we haven't measured that" — never an estimate.

## Questions to expect

| Question | Answer |
|---|---|
| "Is this real Dynamics?" | "The data model is Dataverse-shaped. The redesign is the point — this is what the next version should be, not a reskin of today's." |
| "How do we know it works?" | "We generated the world from a known win process, so we can prove the model recovers it: AUC 0.81 — and 0.95 would mean leakage, not brilliance." |
| "What's fake here?" | "The companies and leads. The model, the explanations, and the re-scoring loop are the real implementation." |
| "Where's the churn model?" | "You don't have renewals, so churn isn't an event — dormancy is. It's shown on the company page: 214 days without a new initiative." |
| "Why would reps use it?" | "It removes triage: no list to sort, no guessing why a deal is cold, no separate BI tool." |
| "Next step?" | "Same model on your real pipeline. The UI is already the argument." |

## What not to show

- Model code, notebooks, feature lists.
- Drift monitoring beyond the single panel.
- Any empty state or loading spinner. Pre-seed, pre-score, pre-warm.

## Demo hygiene

- Run offline. `docker compose up`, seeded DB, committed artifacts.
- Pre-warm the model so the first click isn't a four-second load.
- Have a second lead picked in case the first one's numbers land badly.
- Never claim a metric the artifact doesn't contain.
