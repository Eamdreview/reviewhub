---
name: reviewhub-seo-research
description: >-
  Build a complete SEO research package for a ReviewHub product review. Use when
  asked for keywords, search intent, SERP/competitor analysis, PAA questions, or
  on-page SEO (title/meta/H1/slug/outline/FAQ) for a product — usually after
  reviewhub-product-research. Keyword, SERP, competitor and PAA data must come
  from real searches; never fabricated. Unknown search data = Verification Required.
---

# reviewhub-seo-research — SEO research package

## Responsibility (one, only)
Produce the **SEO package** for one product. This skill OWNS keyword/SERP
research and on-page SEO. It does not verify product facts
(`reviewhub-product-research`), rank opportunities (`reviewhub-weekly-report`),
or write the review body (`reviewhub-review-generator`).

## Trigger conditions
- "keyword research / SEO plan / SERP analysis / PAA / title + meta + slug" for a
  product; "build the SEO package for <product>".
- Handoff from `reviewhub-product-research` (uses its verified category + name).

## Inputs
- Product handle + (ideally) the **verified dossier** from
  `reviewhub-product-research` (for the correct name, category, official site).
- If starting from a report, seed name/category/url with
  `reviewhub-weekly-report/scripts/extract_products.py`.

## Outputs — the SEO package (all fields)
`primary_keyword · secondary_keywords · long_tail_keywords · search_intent ·
related_entities · competitor_analysis · serp_opportunities · paa_questions ·
internal_links · external_authority_sources · seo_title · meta_description ·
url_slug · h1 · h2_outline · faq`

Each keyword/competitor/PAA item carries its **evidence source** or is marked
`Verification Required`. Title/meta/H1/slug/H2/FAQ are expert recommendations
grounded in the verified primary keyword + dossier.

## Dependencies
- `reviewhub-product-research` output (preferred) for grounded name/category.
- `reviewhub-weekly-report/scripts/extract_products.py` (optional seed).
- Tools: WebSearch (SERP/PAA/autosuggest), WebFetch. No project code changed.

## Workflow
1. Confirm the product's true name/category from the dossier. 2. WebSearch the
   head terms (`<product> review`, `<product> alternatives`, `<category>
   software`); read the real SERP. 3. Derive primary/secondary/long-tail from
   autosuggest + related + PAA — **from results, not imagination**. 4. Count
   ranking competitors (YouTube + authority sites) → `competitor_analysis` +
   `serp_opportunities` (gaps). 5. Collect PAA/forum questions. 6. Map related
   entities, candidate internal links (other ReviewHub reviews) and external
   authority sources. 7. Write title/meta/H1/slug/H2 outline/FAQ.

## Verification rules (never fabricate keyword data)
- Every keyword, competitor count, and PAA question must trace to a real search;
  if search tools are unavailable, output the structure with those data fields as
  `Verification Required` — do not invent volumes, counts, or questions.
- Do not assert search volume unless a real source provides it; qualify as
  relative demand (High/Med/Low) with the evidence.

## Error handling
- No search tool / blocked → return the package skeleton with data fields
  `Verification Required` and a clear note; still provide grounded
  title/meta/H1/slug from the product name.
- Ambiguous product name (brand collision) → flag and disambiguate before
  producing keywords.

## Examples
- "SEO package for GetResponse review." → primary `getresponse review`,
  secondary/long-tail from SERP, competitor count, PAA, title/meta/slug/outline.
- "Find SERP gaps for a Jasper AI review." → `serp_opportunities` grounded in the
  live SERP.

## Limitations
- Provides relative demand and evidenced counts, not paid-tool exact volumes.
- SERP is time-sensitive; note the search date.

## Handoff
SEO package → `reviewhub-review-generator` (structure + keywords for the review)
and later → `reviewhub-quality-audit` (SEO completeness check).
