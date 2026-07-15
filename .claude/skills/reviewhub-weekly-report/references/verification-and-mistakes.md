# Verification standards & report-mistake catalog

The report is a hypothesis. Verify it. For every field record: the **value**,
the **evidence source**, and a status — `verified`, `conflicts` (report vs
reality disagree → use reality, log a mistake), or `Verification Required`
(could not be checked → do NOT assume the report is right).

## How to verify each field

| Field | How to verify | Counts as evidence |
|---|---|---|
| **Launch date** | Open the product URL; look for ©/"since YYYY", changelog, "founded", first press/launch coverage; WebSearch `"<product>" launch 20xx`, `"<product>" review 20xx` | A dated page, dated review, archive/first-seen date, or vendor statement |
| **Affiliate program** | Open `/affiliate`, `/affiliates`, `/partners`, or the marketplace listing; confirm it exists, is **active**, and open to new affiliates | A live signup page, commission terms, or marketplace listing that still accepts affiliates |
| **Official website** | Resolve the real product domain (not the JVZoo/marketplace listing URL) | A reachable product homepage on its own domain |
| **Network** | Identify JVZoo / WarriorPlus / ShareASale / PartnerStack / Impact / direct | Named on the affiliate page or marketplace |
| **Product status** | Homepage + pricing page load; not "sunset/retired/acquired/closed" | Working buy/pricing flow |
| **Pricing** | Current price/plan on the pricing page | A live price; flag if it differs from the report |
| **Existing reviews** | WebSearch the product + "review"; count YouTube videos + authority sites (G2, Capterra, Trustpilot, Forbes, PCMag, TechRadar) | Actual SERP/YouTube counts |
| **Freshness signals** | Google Trends direction, recent YouTube upload dates, recent Reddit/forum threads, changelog activity | Any dated, current demand/attention signal |

Rules:
- Cross-check the report against Data Sources footer (`--sources`): a per-product
  affiliate claim is only as trustworthy as its source's health (e.g. trust a
  JVZoo product's data only if `JVZoo: ok`).
- If a tool (WebSearch/WebFetch) is unavailable or the page won't load, the field
  is `Verification Required`. Never substitute the report's value as "verified".

## Report-mistake catalog (detection tests)

Run each test; when it fires, record the mistake, the evidence, and the
corrected value. Rank on corrected values.

1. **Old product ranked as new** — Report implies fresh/launch, but the verified
   launch date is > ~12 months old. *Test:* `freshness=fresh` or launch language
   but verified age is old. *Correct:* set true age; re-judge freshness from live
   signals (old + still-in-demand is fine, just not "new").
2. **Wrong / placeholder launch date** — *Test:* `launch_date` is `Unknown`,
   `YYYY-01-01` (approx-year artifact), equals today, or conflicts with a dated
   review/press. *Correct:* replace with the verified date or `Verification
   Required`.
3. **Missing affiliate link / program** — *Test:* `affiliate_program`/
   `commission`/`network` are null, or no signup page found. *Correct:* mark
   affiliate `Verification Required`; a product with an unconfirmed program
   cannot be a top pick.
4. **Wrong competition** — *Test:* `competition_level` disagrees with an actual
   SERP/YouTube count (e.g. graded `low`/`unknown` but many authority reviews
   exist, or graded `high` but SERP is thin). *Correct:* regrade from the real
   count; re-figure ROI hours/window.
5. **Unrealistic ROI** — *Test:* `roi_per_hour` not ≈ `revenue_mid ÷ hours`;
   revenue driven by an **assumed** commission (`commission=null`, "40% assumed")
   or unmeasured price; ROI implausibly high on `unknown` freshness. *Correct:*
   recompute with verified price/commission; label price-driven ROI as a bet.
6. **Missing keywords** — *Test:* no keyword/search-intent data anywhere for the
   product. *Correct:* generate the SEO brief from verified searches (this is
   expected — the report doesn't produce keywords; you do).
7. **Wrong categorization** — *Test:* stated `category` conflicts with what the
   product actually is (verify on the homepage). *Correct:* set the true category;
   it changes benchmark, competitors, and article angle.

Also flag internal contradictions the report itself contains — e.g. competition
graded `low` (a ×1.30 revenue bonus) while the write-up says "page 1 is
saturated". Trust the evidence, not the badge.
