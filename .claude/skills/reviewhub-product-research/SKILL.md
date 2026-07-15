---
name: reviewhub-product-research
description: >-
  Deep, evidence-based verification of a single affiliate product for ReviewHub.
  Use when asked to research/verify/vet a product, confirm its affiliate program
  or launch date, or build a product dossier before writing a review — typically
  on a product surfaced by reviewhub-weekly-report. Verifies from real sources
  only; anything unproven is "Verification Required" (never guessed).
---

# reviewhub-product-research — deep product verification

## Responsibility (one, only)
Turn one product handle into a **verified fact dossier**. This skill OWNS
product verification. It does not select/rank products (that is
`reviewhub-weekly-report`), does not do SEO (`reviewhub-seo-research`), and does
not write reviews (`reviewhub-review-generator`).

## Trigger conditions
- "verify / research / vet this product", "is this affiliate program real?",
  "confirm the launch date / commission / pricing", "build a product dossier".
- Handed a product from `reviewhub-weekly-report`'s "Products requiring
  verification" or "Top Opportunities" list.

## Inputs
A **product handle** (minimum: `name`; ideally `listing_url` and/or
`official_url`, `source`). If given a weekly report instead, seed the handle
with the parser:
```bash
python3 .claude/skills/reviewhub-weekly-report/scripts/extract_products.py <report.md> \
  | python3 -c "import json,sys;[print(p['name'],'|',p['url']) for p in json.load(sys.stdin)]"
```

## Outputs
A **Product Dossier** — one row per field with `value`, `evidence` (URL/source),
and `status` ∈ {`verified`, `conflicts` (report ≠ reality; use reality),
`Verification Required`}:

`official_website · product_status · affiliate_program · affiliate_network ·
commission · cookie_duration · pricing · OTOs · refund_policy · launch_date ·
vendor · existing_reviews · social_presence · product_activity · trust_signals`

Plus: a **Dossier Confidence %** = verified fields ÷ 15, and a one-line verdict.
This dossier is the canonical fact source consumed by `reviewhub-seo-research`
and `reviewhub-review-generator`.

## Dependencies
- `reviewhub-weekly-report/scripts/extract_products.py` (optional, to seed the
  handle from a report).
- Tools: WebFetch, WebSearch. No project code is modified or required.

## Workflow
1. Resolve the **official website** (real product domain, not the marketplace
   listing). 2. For each field, gather evidence: homepage, `/pricing`,
   `/affiliate|/affiliates|/partners`, `/refund|/guarantee`, `/terms`,
   changelog/blog, and WebSearch for reviews + social profiles. 3. Record value +
   evidence + status per the table above. 4. Compute Dossier Confidence and
   verdict.

## Verification rules (never guess)
- A field is `verified` only with a concrete source; otherwise `Verification
  Required`. Never output a plausible value with no evidence.
- **Affiliate program** must be confirmed **active and open to new affiliates**,
  not merely "exists".
- **Launch date**: use ©/"since"/changelog/first-review/press; if none,
  `Verification Required` — never call it "live/new".
- If the report claimed a value your evidence contradicts, mark `conflicts` and
  keep the evidenced value.

## Error handling
- URL unreachable / blocked (403/Cloudflare) → that field `Verification
  Required`, note the block; do not infer.
- No tools available → return the dossier with all un-checkable fields as
  `Verification Required` and a low confidence; state the limitation.
- Product not found anywhere → verdict `Unverifiable — insufficient public data`.

## Examples
- "Research Faceswap (jvzoo) before I review it." → dossier with each field
  verified/flagged, confidence %, verdict.
- "Confirm ClickAgencyAi's affiliate program and cookie duration." → those rows
  verified from the vendor's affiliate page or `Verification Required`.

## Limitations
- Verifies public information only; cannot see gated affiliate dashboards.
- Point-in-time snapshot — programs/prices change; note the check date.

## Handoff
Dossier → `reviewhub-seo-research` (keywords/SERP) and → `reviewhub-review-generator`
(review package). Products still carrying `Verification Required` on core fields
should not proceed to writing until resolved.
