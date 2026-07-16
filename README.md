# ReviewHub — Weekly Affiliate Intelligence Pipeline

An automated 6-stage pipeline that scans 600+ affiliate products weekly across 9 sources, scores them on a 9-criteria weighted model, predicts 30-day revenue/ROI, and emails a prioritized intelligence report every Friday — so you always know **which review to write next**.

```
[1] Collect → [2] Enrich → [3] Triage → [4] Score → [5] Write → [6] Deliver
```

## What it does

- **Collect** — pulls launch/product candidates from MunchEye, WarriorPlus, JVZoo, Digistore24, ProductHunt, HackerNews, GitHub Trending, TheresAnAIForThat, FutureTools.
- **Qualify** — minimum-quality gate; junk never reaches enrichment.
- **Enrich** — Google Trends, Reddit sentiment (VADER), YouTube review counts, Trustpilot, Google CSE competition checks.
- **Triage & Score** — 9 weighted criteria (buying intent 25, SEO 15, profitability 13, freshness 12, momentum 12, demand 10, sentiment 5, evergreen 5, vendor trust 3) with a hard buying-intent floor of 60.
- **Revenue Prediction** — transparent multiplicative model estimating 30-day revenue, hours of effort, and $/hr ROI per product. All figures labeled as estimates with a confidence score.
- **Write** — LLM (OpenRouter) generates an intelligence brief per product: analysis, SEO opportunity, competition, affiliate economics, recommended action.
- **Deliver** — Markdown report saved to `reports/` (committed) and emailed via Gmail SMTP.

Runs automatically every **Friday 05:00 UTC** via GitHub Actions (`weekly-intelligence.yml`).

## Quick start

```bash
pip install -r requirements.txt

python -m src.main --dry-run     # offline run on fake data, no keys needed
python -m src.main --test-email  # verify Gmail SMTP secrets
python -m src.main               # real run (requires secrets below)
```

### Required secrets (GitHub Actions / env)

| Secret | Used by |
| --- | --- |
| `OPENROUTER_API_KEY` | Write stage (intelligence briefs) |
| `GMAIL_ADDRESS` / `GMAIL_APP_PASSWORD` | Deliver stage (email) |
| `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` | Reddit enrichment |
| `GOOGLE_CSE_KEY` / `GOOGLE_CSE_CX` | Competition analysis |
| `YOUTUBE_API_KEY` | YouTube review counts |

Any single source failing degrades the report but never stops the run.

## The Learning Engine (close the loop!)

The pipeline's predictions only calibrate once you feed back **real results** of published reviews. This is the most important habit for making money with this system:

```bash
# Log one published review
python -m src.learning.cli add \
  --product "BrowserAgent" --network jvzoo --category "AI browser agent" \
  --publish-date 2026-07-11 --review-type Review --traffic-source linkedin \
  --affiliate-clicks 42 --sales 3 --commission 18.5 --revenue 55.5 \
  --hours-invested 1

# Bulk import from data/history/reviews.csv
python -m src.learning.cli import

# See what the engine has learned (best category/network/day/source)
python -m src.learning.cli insights
```

**Weekly habit:** after publishing each review, log it immediately (revenue can be blank). Then once a week, update clicks/sales/revenue from your WarriorPlus / JVZoo / Digistore24 dashboards. After ~15–20 reviews with real numbers, `insights` starts telling you which categories, networks, platforms and publish days actually pay you — and future reports get smarter.

## Repo layout

```
src/
  main.py            # orchestrator (6 stages)
  config.py          # ALL tuning: weights, floors, keywords, models
  collect/           # 9 source scrapers + fake data for --dry-run
  enrich/            # trends, reddit, youtube, trustpilot, google_cse
  qualify.py         # minimum-quality gate
  triage.py, classify.py, score.py, freshness.py, competition.py
  revenue.py         # deterministic revenue/ROI prediction
  vendor.py          # vendor reputation profiles
  advisor.py         # "write this one first" pick
  write.py           # LLM intelligence briefs
  report.py          # Markdown report assembly
  deliver.py         # save + Gmail SMTP
  learning/          # Learning Engine (history.db) + CLI
reports/             # weekly Markdown archive (committed)
data/                # stage outputs, history.db, knowledge.db (git-ignored)
.github/workflows/   # weekly-intelligence.yml (Fri 05:00 UTC), discovery-debug.yml
```

## Tuning

Everything lives in `src/config.py`: scoring `WEIGHTS`, `BUYING_INTENT_FLOOR`, keyword lists, enabled sources, OpenRouter model choices, revenue model constants, timezone. Change behaviour without touching pipeline logic.

## Workflow (human-in-the-loop by design)

1. Friday: report lands in your inbox.
2. **You** pick the product(s) you have/can get an affiliate link for.
3. Write the review (v4.1 honest-review system) and publish (LinkedIn/Medium).
4. Log it in the Learning Engine the same day.
5. Update numbers weekly — the system calibrates itself around what actually earns.
