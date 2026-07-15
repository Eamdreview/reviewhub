---
name: reviewhub-review-generator
description: >-
  Assemble a complete, evidence-grounded Review Package (structure + briefing) for
  a ReviewHub product, ready for a writer. Use when asked to draft/outline/prepare
  a product review or build a review brief (after reviewhub-product-research and
  reviewhub-seo-research). Every claim traces to the verified dossier; unproven
  points are flagged, not invented. Returns READY TO WRITE / NEEDS VERIFICATION /
  NEEDS ASSETS.
---

# reviewhub-review-generator — review package

## Responsibility (one, only)
Assemble the **review package** (the brief a writer needs) from verified inputs.
It OWNS review structuring. It does not verify facts
(`reviewhub-product-research`), do keyword research (`reviewhub-seo-research`),
plan distribution (`reviewhub-publish-strategy`), or audit a finished draft
(`reviewhub-quality-audit`). It grounds every point in evidence and never
fabricates product claims.

## Trigger conditions
- "prepare / outline / brief a review of <product>", "build the review package",
  "am I ready to write the <product> review?".
- Handoff from `reviewhub-seo-research`.

## Inputs
- The **verified dossier** (`reviewhub-product-research`) — required for facts.
- The **SEO package** (`reviewhub-seo-research`) — required for keywords/outline.
- Optional: an assets list (screenshots the user already has).

## Outputs — the review package (all sections)
`executive_summary · target_audience · why_review_now · review_angle ·
strengths · weaknesses · use_cases · comparison_ideas · pros · cons · pricing ·
bonuses · OTOs · refund · screenshots_checklist · review_outline · faq ·
cta_strategy`

Then a **status** (exactly one):
- **READY TO WRITE** — dossier core fields verified + SEO package present +
  pricing/affiliate confirmed.
- **NEEDS VERIFICATION** — one or more core facts are `Verification Required`
  (list them; point to `reviewhub-product-research`).
- **NEEDS ASSETS** — facts/SEO fine but required screenshots/media are missing
  (list them from `screenshots_checklist`).

Plus a **Package Confidence %** (share of sections backed by verified evidence).

## Dependencies
- `reviewhub-product-research` output (facts) and `reviewhub-seo-research` output
  (keywords/outline). Without both, status cannot be READY TO WRITE.
- No project code is modified.

## Workflow
1. Pull facts from the dossier and keywords/outline from the SEO package.
2. Derive strengths/weaknesses/pros/cons/use-cases **only** from verified facts
   and cited user sentiment. 3. Build the outline around the primary keyword +
   H2 outline + FAQ. 4. Compile the screenshots checklist (pricing page, key
   features, dashboard, results). 5. Evaluate the status gate and confidence.

## Verification rules (never guess)
- Every pro/con/strength/claim cites a dossier field or a sourced review; no
  invented capabilities, numbers, or testimonials.
- Pricing/OTOs/refund/bonuses come from the dossier; if `Verification Required`
  there, they stay flagged here and force `NEEDS VERIFICATION`.
- This skill prepares a brief; it does not fabricate marketing copy or fake
  hands-on experience.

## Error handling
- Missing dossier or SEO package → return `NEEDS VERIFICATION` /
  `NEEDS ASSETS` with exactly what to run first (name the upstream skill).
- Conflicting facts between inputs → surface the conflict; do not silently pick.

## Examples
- "Prepare the GetResponse review package." → all sections + `READY TO WRITE`
  (if inputs complete) or a precise blocker list.
- "Is the Faceswap review ready?" → status + the missing verifications/assets.

## Limitations
- Produces a writer's package (structure, evidence, angles), not a final
  published article; the human/writer composes the prose.

## Handoff
Package → `reviewhub-quality-audit` (after a draft is written) and →
`reviewhub-publish-strategy` (distribution). Do not proceed while status is
`NEEDS VERIFICATION`/`NEEDS ASSETS`.
