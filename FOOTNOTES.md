# Claims Denial Intelligence Platform — Footnotes

> Plain-language explanations of key concepts, metrics, and design decisions referenced throughout the project. Written so that anyone picking up the project can get up to speed quickly.

---

## 1. Expected Recovery Curve (Probability of Collection by Aging Bucket)

**What it means:** The longer a claim sits unpaid, the less likely you are to ever collect on it. The "expected recovery curve" is the historical collection rate at each aging bucket — it tells finance teams how much of their outstanding AR is realistically going to turn into cash.

**How it works in practice:** A hospital's finance team looks at their historical data and asks: "Of all the claims that landed in the 91–120 day bucket, what percentage eventually got paid?" They do this for every bucket and typically see something like:

- 0–30 days: ~98% collected
- 31–60 days: ~90% collected
- 61–90 days: ~75% collected
- 91–120 days: ~55% collected
- 120+ days: ~30% collected

The curve slopes downward as claims age. CFOs don't just look at how old the money is — they mentally multiply each bucket by its expected recovery rate to estimate how much outstanding AR will actually convert to cash. That's the "dollar amount at risk" calculation.

**How we build it with our data:** `fact_claims` has `days_in_ar` and `status` (paid, denied, etc.) for 120,000 claims over 24 months. We group claims into aging buckets, look at the final outcome for each, and calculate the actual recovery percentage per bucket. It's not a pre-built column — it's a metric we derive in the `fct_ar_aging_buckets` mart model.

---

## 2. Cost to Collect

**What it means:** For every dollar the hospital brings in, how many cents did it spend chasing that dollar? If a hospital collects $100M in revenue but spends $4M on billing staff, appeals, rework, clearinghouse fees, and follow-up — their cost to collect is 4 cents per dollar (4%).

**Industry benchmarks:** 3–5% for a well-run revenue cycle. Struggling hospitals can hit 7–10%, mostly because they spend so much time reworking denied claims and filing appeals.

**What it requires in a real hospital:** This metric pulls from the general ledger — actual payroll for billing staff, vendor costs for clearinghouses, software licenses, outsourced collections, etc. Our dataset models the clinical and claims side of the operation, not administrative expenses, so we don't have true cost data.

**What we can do instead:** Build operational burden proxies from the data we have:

- Count of reworked claims and resubmissions
- Number of appeals filed (from `fact_appeals`)
- Average time spent per workflow step (from `fact_workflow_events.duration_minutes`)
- Volume of claims requiring multiple touches (from `fact_claim_status_history`)

These tell a compelling story about operational burden even without a true dollar figure. We can also let users plug in their own cost assumptions (average cost per appeal, cost per rework) and multiply against our volumes — this is actually how consulting engagements typically work.

---

## 3. Pre-Submission Risk Flags — Design Decision

**The gap:** Our dataset is a closed loop — every claim has already been submitted, adjudicated, and resolved. Dashboard 6 (Pre-Submission Risk Flags) is supposed to answer "which claims should we pull back and fix before submitting?" but there's no in-flight queue of pending claims in the data.

**Option A — Retrospective risk model:** Use the full dataset to build the logic: "claims with these workflow failure patterns got denied X% of the time." The dashboard shows historical claims and what *would have been* flagged if the system had existed. Powerful for a product demo or consulting pitch — e.g., "here are the 4,200 claims that went out with known problems, and here's the $12M in denials that could have been caught." Proves the concept without pretending we have a live feed.

**Option B — Holdout simulation (recommended):** Take a slice of the data (e.g., the most recent 2–3 months) and treat those claims as "not yet submitted." Build the risk model on the earlier months, then score the holdout batch as if they were sitting in a submission queue. This gives Dashboard 6 a realistic feel: "here are 8,500 pending claims, 1,200 are flagged as high-risk, estimated $3.2M at stake." It also provides a natural accuracy proof: "we predicted these 1,200 would be denied, and here's how many actually were."

**Recommendation:** Option B. It's not much extra effort (a date-based split in an intermediate model), and it makes the demo far more convincing for a CFO audience. Implementation would live in `int_pre_submission_risk.sql` or similar.

**Decision status:** Pending — to be confirmed before Phase 9/10 modeling begins.

---

*Created: 2026-05-14*
*This file is a living document — add new footnotes as concepts come up during the build.*
