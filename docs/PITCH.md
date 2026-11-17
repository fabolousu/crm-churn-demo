# The pitch

Audience: business / executives. Five minutes, one laptop, no slides after the first
thirty seconds. The demo *is* the pitch.

## The argument

> A CRM that stores records is a filing cabinet. The record is the byproduct.
> This one starts from what the rep should do today, and shows them why.

Three claims, each proved by a screen, not by a bullet:

1. **The first screen is a queue, not a list.** Ranked by revenue at risk.
2. **Every score explains itself.** Three drivers, in business language.
3. **You can see what would change the outcome** — before spending the call.

## The five minutes

| Time | Screen | Line |
|---|---|---|
| 0:00 | Title, one sentence | "Your CRM knows everything about the past and nothing about next quarter." |
| 0:30 | **Today's queue** | "This is what a rep sees first. Not accounts. €18.4M of revenue at risk, ordered by what's worth saving." |
| 1:30 | **Account 360** | Click the top account. "71% likely to be gone in six months. Three reasons: renewal in 43 days, seven support tickets, usage down 34%." |
| 2:30 | **Why / counterfactual** | Move the lever. "Resolve the two open tickets and get one exec meeting: 71% drops to 34%. Now the call has a purpose." |
| 3:30 | **Act, then re-score** | Click. "Task created, score updated, and it's out of the queue until the task closes. The loop closes." |
| 4:20 | **Portfolio** | "Across three business units — and the model is calibrated, which means the 71% means 71%, not just 'high'." |
| 4:50 | Close | "The model is the easy part. The rethink is that these four screens replace the record-first CRUD that everyone else still ships." |

## Three numbers to have ready

- **Revenue at risk** in the queue — the number the CFO cares about.
- **Lift at the top decile** — how much better than random targeting; this is the honest
  headline, not raw accuracy.
- **Calibration error** — because "71%" must mean 71%; it's the difference between a
  dashboard and a decision tool.

All three are computed from `ml/artifacts/metrics.json`. If a number is asked and it
isn't in that file, the answer is "we didn't measure that yet" — never an estimate.

## Questions to expect

| Question | Answer |
|---|---|
| "Is this real Dynamics?" | "The data model is Dataverse-shaped. The redesign is the point — we're showing what the next version should be, not reskinning today's." |
| "How do we know the model works?" | "We generated the world with a known churn process, so we can prove the model recovers it: AUC 0.81, and it doesn't cheat because 0.99 would mean leakage." |
| "What's fake here?" | "The customers. Everything else — the model, the explanations, the scoring loop — is the real implementation." |
| "Why would reps use it?" | "It removes work: no list to triage, no guessing why an account is at risk, no separate BI tool." |
| "What's the next step?" | "Same model against your tenant with your label. The UI is already the argument." |

## What not to show

- Model code, notebooks, feature lists.
- Drift monitoring beyond the single panel (it invites "who watches this in production").
- Any screen with an empty state or a loading spinner. Pre-seed, pre-score, pre-warm.

## Demo hygiene

- Run offline. `docker compose up`, seeded DB, model artifacts committed.
- Pre-warm the model so the first click isn't a 4-second load.
- Have a second account picked in case the first one's numbers land badly.
- Never claim a metric the artifact doesn't contain.
