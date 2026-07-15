---
name: reviewhub-weekly-report
description: >-
  Turn a ReviewHub Weekly Affiliate Intelligence report (reports/*.md) into a
  vetted review plan. Use when asked to read/curate/triage the weekly report,
  decide which products are worth reviewing, verify affiliate programs and
  launch dates, analyze freshness, or recommend the top opportunities. Works
  only from what the report states — it never guesses missing data, always
  explains ranking, and always verifies launch dates before recommending.
---

# ReviewHub Weekly Report — selection & review-planning skill

You read a Weekly Affiliate Intelligence report and decide **what is actually
worth reviewing this week**, with reasons. The report already scores every
product (Opportunity Score, Freshness, Confidence, ROI); your job is to apply
judgment on top of it: verify, filter, rank, and plan.

## Three non-negotiable rules

1. **Do not guess data.** If a field is `Unknown` / `null`, say so and turn it
   into a verification action. Never invent a launch date, commission, or
   affiliate program. The extractor emits `null` for every unknown on purpose.
2. **Always explain ranking.** Every product you keep, drop, or recommend must
   cite the concrete numbers behind the decision (score breakdown, freshness
   status + confidence, competition grade, ROI = revenue ÷ hours).
3. **Always verify launch dates.** A product may only be *recommended* once its
   launch date is either present in the report or verified from the listing.
   `Launch date: Unknown` is a blocker to resolve, not a fact to skip.

## Step 1 — Locate and extract the report (deterministic, no guessing)

Default to the newest report unless the user names a date:

```bash
ls -t reports/*.md | head -1
python3 .claude/skills/reviewhub-weekly-report/scripts/extract_products.py <report.md> --table
python3 .claude/skills/reviewhub-weekly-report/scripts/extract_products.py <report.md>          # full JSON
```

The extractor parses the exact markers in `src/report.py` and returns, per
product: `opportunity_score`, `buying_intent_0_100`, `score_breakdown`,
`freshness{score,status,confidence_pct,why}`, `launch_date`,
`launch_date_source`, `product_age`, `competition_level`,
`competition_revenue_mult`, `affiliate_program`, `commission`, `recurring`,
`price`, `existing_reviews`, `google_trends`, `roi_per_hour`, `revenue_range`,
`prediction_confidence_pct`, `hours`, `window_days`, `best_publish_date`.
`null` means the report did not state it — treat as **unknown / verify**, never
as zero or as an assumption.

Also read the report's **⚙️ Data Sources** footer: it tells you which
affiliate networks were reachable (e.g. `JVZoo: ok`), which contextualises the
per-product affiliate fields.

## Step 2 — Analyze freshness (the core signal)

Freshness answers "is this worth reviewing **today**?" — it is not age. Use the
`freshness.status` + `confidence_pct` + `why`:

| Status | Meaning | Action |
|---|---|---|
| `fresh` | Live demand/recency signals present | Strong candidate |
| `moderate` | Some signals, mixed | Candidate; note what's weak |
| `stale` | Evidence of **declining** demand/attention | **Reject as outdated** |
| `unknown` | Only liveness signals; no demand/recency evidence (often 0% launch data) | **Do not accept or reject on this alone — verify first** |

Quote the `why` string when you explain a freshness call. Low `confidence_pct`
(e.g. 15–20%) means the freshness picture is thin — say so.

## Step 3 — Verify launch dates (required before any recommendation)

- If `launch_date` is present: compute/confirm `product_age`. An old date is
  **fine** if freshness is `fresh`/`moderate` — do not reject for age.
- If `launch_date` is `Unknown`: you must verify before recommending. Try, in
  order, and record which one you used:
  1. Open the product `url` (listing/sales page) and look for a launch/updated
     date, copyright/© year, "since YYYY", or a changelog.
  2. If the source is JVZoo/Muncheye, check the launch calendar / product page.
  3. WebSearch `"<product name>" launch date OR review 20xx` for corroboration.
- If it still cannot be determined, state **`Launch date: Unknown (verified: no
  public date found)`** — never fall back to calling it "live" or "new".

## Step 4 — Verify affiliate programs (never assume)

For each kept product, resolve the affiliate program from evidence:
- If `affiliate_program`/`commission`/`affiliate_network` are present, use them.
- If `null`, mark **"affiliate: unverified"** and verify: open the product's
  `/affiliate`, `/affiliates`, or `/partners` page, or the marketplace listing,
  and confirm the program is (a) still active and (b) open to new affiliates.
- A product with an **unconfirmed or discontinued** affiliate program cannot be
  a top recommendation — downgrade it to "verify first".

## Step 5 — Select what's worth reviewing / reject the rest

Keep a product only if **all** hold (cite the numbers for each):

- `buying_intent_0_100` ≥ 60 (the platform's hard floor).
- `freshness.status` is `fresh` or `moderate`; **or** `unknown` **and** you
  verified a real, current demand signal in Steps 3–4.
- `competition_level` is `low` or `medium` (not `high` = saturated). `unknown`
  is allowed only after you verify competition yourself.
- Affiliate program verified active (Step 4).

**Reject as outdated only on evidence, never on age:**
- `freshness.status == stale`, or `google_trends` clearly negative/declining, or
- the listing shows the product is no longer sold / affiliate program closed.

**Never reject a product solely because its launch date is old.** SEMrush,
ClickFunnels, Jasper, GetResponse are years old and still excellent review
targets — if freshness is `fresh`/`moderate`, keep them.

Put everything you drop into a short **Rejected** list with the one-line reason
and the number behind it (e.g. "stale — Trends −0.20", "buying intent 41 < 60",
"affiliate program could not be verified").

## Step 6 — Rank and explain

Rank the kept set by **Expected ROI** (`roi_per_hour` = `revenue_range` ÷
`hours`), and for each recommended product write **"Why this ranked here"**:

- the top 2–3 `score_breakdown` contributors (points/weight),
- freshness status + confidence, competition grade, and the two revenue
  multipliers (`competition_revenue_mult`, `freshness_revenue_mult`),
- the ROI math: `est. $lo–$hi ÷ Nh = $X/hr`.

Flag honestly when ROI is **price-driven** (high commission per sale) rather
than demand-driven (freshness `unknown`, low confidence) — a high $/hr with
`unknown` freshness is a high-price bet, not a validated winner.

## Step 7 — Produce the review plan

Output these sections:

1. **Top Opportunities (recommended)** — ranked, each with: ROI, hours, best
   publish date, opportunity window, launch date (verified), freshness+
   confidence, affiliate status, and the "Why this ranked here" explanation.
2. **Verify-first** — promising but blocked on an unverified launch date,
   affiliate program, or `unknown` freshness/competition. List the exact checks.
3. **Rejected (with reasons)** — outdated/stale/low-intent/unverifiable, each
   with the number behind the call.
4. **This week's plan** — a checklist ordered by best-publish-date, sized by
   `hours`, so the user knows what to write first and by when.

Close with a one-line honest confidence note (how much rested on measured data
vs. fields you had to verify or that remain unknown).
