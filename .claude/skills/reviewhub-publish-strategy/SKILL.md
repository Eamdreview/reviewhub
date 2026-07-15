---
name: reviewhub-publish-strategy
description: >-
  Build a cross-platform publishing and promotion plan for a finished ReviewHub
  review. Use when asked how/when/where to publish or promote a review — the
  publishing calendar, best date/time, LinkedIn/Medium/X/Pinterest plans, email
  campaign, and internal linking. Grounds timing in the report's freshness/window
  data; flags anything unknown as Verification Required rather than guessing.
---

# reviewhub-publish-strategy — publishing & promotion plan

## Responsibility (one, only)
Plan **distribution** of a completed review. It OWNS publishing/promotion
strategy. It does not verify products, do SEO research, generate the review, or
audit quality — those are the other skills.

## Trigger conditions
- "how/when/where should I publish this?", "promotion plan", "publishing
  calendar", "social plan for the <product> review", "email campaign for it".
- Handoff after `reviewhub-review-generator` (and ideally after
  `reviewhub-quality-audit` passes).

## Inputs
- The product + review package (`reviewhub-review-generator`) and, where
  available, the report's `best_publish_date`, `window_days`, and freshness
  status (via `reviewhub-weekly-report/scripts/extract_products.py`).
- Optional: the user's platforms/audience/list size.

## Outputs — the publishing package (all parts)
`linkedin_article_plan · medium_strategy · twitter_x_thread · pinterest_strategy
· publishing_calendar · best_publishing_date · best_publishing_time ·
cross_platform_promotion_plan · email_campaign_suggestion ·
internal_linking_strategy`

## Dependencies
- `reviewhub-review-generator` package (what's being published).
- `reviewhub-weekly-report/scripts/extract_products.py` (optional) for
  `best_publish_date`/`window_days`/freshness to time the launch.
- No project code is modified.

## Workflow
1. Anchor timing: for a verified upcoming launch, publish ~1–2 days before and
   promote through the opportunity `window_days`; for evergreen, publish ASAP if
   the SERP gap is open. 2. Draft per-platform plans (LinkedIn article angle,
   Medium canonical/tags, X thread beats, Pinterest pins). 3. Build a dated
   calendar (publish → social waves → email → refresh). 4. Suggest best day/time
   from audience norms (state assumption). 5. Internal links to/from related
   ReviewHub reviews. 6. Email campaign outline.

## Verification rules (never guess)
- If `best_publish_date`/launch date is `Verification Required`, do not fabricate
  a launch-timed schedule — provide an evergreen schedule and flag the blocker.
- Best day/time are labelled assumptions unless the user provides real analytics;
  never present them as measured.
- Canonical/cross-post guidance must avoid duplicate-content harm (canonical to
  the primary URL).

## Error handling
- Missing review package → return the calendar skeleton and request the review
  package first (name `reviewhub-review-generator`).
- No launch/window data → default to an evergreen plan, clearly marked.

## Examples
- "Publishing plan for the GetResponse review." → calendar + per-platform plans +
  email + internal links, timed to the opportunity window.
- "When and where should the Faceswap review go?" → date/time (assumption-tagged)
  + platform sequence.

## Limitations
- Strategy only — it schedules and structures promotion; it does not post or
  send anything.

## Handoff
Terminal stage of the pipeline. Loops back to `reviewhub-weekly-report` next week
for the next batch.
