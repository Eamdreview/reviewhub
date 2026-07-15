---
name: reviewhub-quality-audit
description: >-
  Audit a finished ReviewHub review draft before publishing. Use when asked to
  review/check/QA/proofread a written review or judge if it is ready to publish.
  Checks fact accuracy against the verified dossier, affiliate links, SEO
  completeness, grammar/readability, structure, and required assets. Returns PASS
  / PASS WITH WARNINGS / FAIL with detailed, evidence-based findings.
---

# reviewhub-quality-audit — pre-publish review audit

## Responsibility (one, only)
Audit a **completed draft** and gate publishing. It OWNS pre-publish QA. It does
not verify the product from scratch (it checks the draft *against* the existing
dossier), do keyword research, generate the review, or plan distribution.

## Trigger conditions
- "audit / QA / proofread / is this ready to publish?" for a written review.
- Handoff after the draft is written (post `reviewhub-review-generator`).

## Inputs
- The **review draft** (file path or pasted text) — required.
- The **verified dossier** (`reviewhub-product-research`) and **SEO package**
  (`reviewhub-seo-research`) to check facts and SEO against. If absent, fact/SEO
  checks return `Verification Required` rather than passing by default.

## Outputs — audit findings (all checks) + verdict
Checks: `fact_accuracy · affiliate_links · seo_completeness · grammar ·
readability · duplicate_sections · missing_images · missing_screenshots ·
broken_references · missing_faqs · missing_cta · confidence_score ·
publishing_readiness`.

Each check → status + specific findings (location + fix). Then a **verdict**:
- **PASS** — no blocking issues; all core checks clear.
- **PASS WITH WARNINGS** — publishable, with listed non-blocking fixes.
- **FAIL** — one or more blockers (wrong/unverified facts, broken/missing
  affiliate links, missing CTA, key SEO elements absent).

Plus a **Confidence Score %** (share of checks that could be fully verified).

## Dependencies
- The draft; ideally the dossier + SEO package for grounded checks.
- Tools: WebFetch (link/reference checking), Read/Grep (draft parsing). No
  project code modified.

## Workflow
1. Parse the draft. 2. Cross-check every factual claim against the dossier →
   flag unsupported/contradicted claims. 3. Verify affiliate links resolve and
   point to the right program; flag missing/broken. 4. SEO completeness: title,
   meta, H1, slug, primary keyword usage, H2s, FAQ present vs the SEO package.
   5. Grammar/readability pass. 6. Structure: duplicate sections, missing images/
   screenshots (per the review package checklist), broken references, missing
   FAQ/CTA. 7. Compute confidence + verdict.

## Verification rules (never guess)
- A fact "passes" only if it matches a verified dossier field; a claim with no
  supporting evidence is a finding, not a pass.
- Do not assume a link works — check it. Unreachable to verify → `Verification
  Required`, not PASS.

## Error handling
- No draft provided → request it; do not audit from memory.
- Missing dossier/SEO package → run the checks you can; mark fact/SEO checks
  `Verification Required` and cap the verdict at `PASS WITH WARNINGS`.
- Link checker blocked → report the link as unverified, not broken.

## Examples
- "Audit drafts/getresponse-review.md before I publish." → per-check findings +
  PASS/WARN/FAIL + fixes.
- "Is my Faceswap review publish-ready?" → verdict + the exact blockers.

## Limitations
- Audits the draft against available evidence; it does not rewrite the article or
  re-verify the product from scratch (use `reviewhub-product-research` for that).

## Handoff
On PASS/PASS WITH WARNINGS → `reviewhub-publish-strategy`. On FAIL → back to the
writer (and `reviewhub-product-research`/`reviewhub-seo-research` for the specific
gaps).
