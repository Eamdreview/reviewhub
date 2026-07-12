# SETUP.md — Weekly Affiliate Intelligence Report

This guide walks you through creating every account and API key the system
needs, and storing each one in GitHub Secrets so the weekly automation can use
them securely.

**You do not need to touch any code.** The system reads every key from GitHub
Secrets at runtime. Create the keys below, paste them into GitHub, and the
weekly run (**Fridays 07:00 Cairo**) will pick them up automatically.

---

## Table of contents

1. [How GitHub Secrets work (read this first)](#0-how-github-secrets-work)
2. [OpenRouter — the AI brain](#1-openrouter)
3. [Product Hunt — new-launch discovery](#2-product-hunt)
4. [Reddit — user interest & sentiment](#3-reddit)
5. [YouTube Data API — review demand & competition](#4-youtube-data-api-v3)
6. [Google Custom Search — SEO competition](#5-google-custom-search-json-api)
7. [Gmail App Password — email delivery](#6-gmail-app-password)
8. [Google Trends & scrapers — no keys needed](#7-google-trends--marketplace-scrapers)
9. [Full secrets checklist](#8-full-secrets-checklist)
10. [Verify everything at once](#9-verify-everything-at-once)

---

## 0. How GitHub Secrets work

Every key below is stored as a **repository secret** — an encrypted value only
the GitHub Actions run can read. They are never printed in logs and never
committed to the repo.

**To add a secret (you'll do this many times):**

1. Go to your repo on GitHub: `https://github.com/eamdreview/reviewhub`
2. Click **Settings** (top menu).
3. In the left sidebar: **Secrets and variables → Actions**.
4. Click **New repository secret**.
5. Enter the **Name** exactly as written in this guide (names are
   case-sensitive, e.g. `OPENROUTER_API_KEY`).
6. Paste the **Secret** value.
7. Click **Add secret**.

> ⚠️ **Common mistake:** typos in the secret *name*. The code looks for the
> exact name. `OPENROUTER_KEY` will not work if the code expects
> `OPENROUTER_API_KEY`. Copy names directly from this guide.

> 💡 You can update a secret later, but you **cannot view** its value again
> after saving. Keep your keys in a private password manager too.

---

## 1. OpenRouter

**Why it's needed:** OpenRouter is the AI engine. It routes requests to
high-quality models (for writing the reviews and strategy) and cheap models
(for fast filtering). This is what turns raw data into readable analysis.

**Free or paid:** Pay-as-you-go. Expected cost is **a few cents per day**
(roughly $1–3/month) because the expensive model only processes ~10–15
pre-filtered products. You add a small prepaid balance (e.g. $5) to start.

**Create the account:**
1. Go to <https://openrouter.ai> and click **Sign In** (Google/GitHub login works).
2. Click your avatar → **Credits** → **Add Credits**. Add ~$5 to begin.

**Generate the API key:**
1. Click your avatar → **Keys** (or go to <https://openrouter.ai/keys>).
2. Click **Create Key**, give it a name like `reviewhub`, and **Create**.
3. Copy the key immediately (starts with `sk-or-...`). You won't see it again.

**Store in GitHub Secrets:**
| Secret name | Value |
|---|---|
| `OPENROUTER_API_KEY` | the `sk-or-...` key |

**Common mistakes:**
- Adding a key but **no credits** — requests fail with "insufficient credits."
- Copying the key with a trailing space.

**Verify it works:**
Run this in a terminal (replace `YOUR_KEY`):
```bash
curl https://openrouter.ai/api/v1/models -H "Authorization: Bearer YOUR_KEY" | head
```
A JSON list of models = working. `401 Unauthorized` = bad key.

---

## 2. Product Hunt

**Why it's needed:** Product Hunt is where new AI/SaaS tools launch first. Its
API is the assistant's #1 discovery source and the core of your "be an early
reviewer" edge.

**Free or paid:** **Free.**

**Create the account:**
1. Sign up at <https://www.producthunt.com> (a normal user account).

**Generate the API token:**
1. Go to <https://www.producthunt.com/v2/oauth/applications>.
2. Click **Add an application**.
3. Name it `reviewhub`. For **Redirect URI**, enter `https://localhost`
   (we don't use OAuth redirect, but the field is required).
4. Click **Create Application**.
5. On the app page, find **Developer Token** and click to generate it.
6. Copy the token.

**Store in GitHub Secrets:**
| Secret name | Value |
|---|---|
| `PRODUCTHUNT_TOKEN` | the developer token |

**Common mistakes:**
- Using the **API Key / API Secret** instead of the **Developer Token**. We use
  the ready-made developer token (no OAuth dance needed).

**Verify it works:**
```bash
curl -s https://api.producthunt.com/v2/api/graphql \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"{ posts(first:1){ edges{ node{ name } } } }"}'
```
JSON with a product name = working.

---

## 3. Reddit

**Why it's needed:** Reddit reveals genuine user interest and sentiment —
whether real people are asking about, praising, or complaining about a product.
This feeds the User Sentiment and Vendor Trust signals.

**Free or paid:** **Free** for this low-volume, non-commercial use.

**Create the app (gives you ID + secret):**
1. Log in to Reddit, then go to <https://www.reddit.com/prefs/apps>.
2. Click **create another app...** at the bottom.
3. Fill in:
   - **name:** `reviewhub`
   - **type:** select **script** (important — not "web app").
   - **redirect uri:** `http://localhost:8080`
4. Click **create app**.
5. You'll now see:
   - The **client ID** — the string just **under the app name** (top-left of
     the app box).
   - The **secret** — labeled `secret`.

**Store in GitHub Secrets:**
| Secret name | Value |
|---|---|
| `REDDIT_CLIENT_ID` | the client ID (under the app name) |
| `REDDIT_SECRET` | the secret |

**Common mistakes:**
- Choosing **web app** instead of **script** type.
- Confusing the client ID with the secret — the **ID is the short string under
  the app title**, not the field labeled "secret."

**Verify it works:**
```bash
curl -s -X POST -A "reviewhub/1.0" \
  -d grant_type=client_credentials \
  --user "CLIENT_ID:SECRET" \
  https://www.reddit.com/api/v1/access_token
```
A JSON `access_token` = working. `401` = wrong ID/secret or wrong app type.

---

## 4. YouTube Data API v3

**Why it's needed:** Counting existing review videos and their view counts tells
us two things at once — how much **demand** a product has, and how **saturated**
the review competition already is.

**Free or paid:** **Free** (10,000 quota units/day — far more than we need).

**Create the project + key:**
1. Go to <https://console.cloud.google.com>.
2. Top bar → project dropdown → **New Project** → name it `reviewhub` → **Create**.
3. Make sure your new project is selected.
4. Go to **APIs & Services → Library**, search **YouTube Data API v3**, open it,
   click **Enable**.
5. Go to **APIs & Services → Credentials → Create Credentials → API key**.
6. Copy the key. (Optional but recommended: click **Edit API key → Restrict key
   → API restrictions → YouTube Data API v3** so the key only works for YouTube.)

**Store in GitHub Secrets:**
| Secret name | Value |
|---|---|
| `YOUTUBE_API_KEY` | the API key |

**Common mistakes:**
- Forgetting to **Enable** the API (creating a key isn't enough — the API must
  be enabled on the project).
- Restricting the key by **HTTP referrer** — for a server/Action, leave it
  unrestricted or restrict by **API**, not referrer, or requests will be blocked.

**Verify it works:**
```bash
curl -s "https://www.googleapis.com/youtube/v3/search?part=snippet&q=notion+ai+review&maxResults=1&type=video&key=YOUR_KEY"
```
JSON with a video = working. An `error` about the API not enabled = go back to step 4.

---

## 5. Google Custom Search (JSON API)

**Why it's needed:** This fetches the top 10 Google results for a product's
review keyword, so we can judge **SEO competition** — whether the front page is
locked up by big authority sites or still has room for you to rank.

**Free or paid:** **Free** tier = 100 search queries/day (we use ~10). Paid only
if you exceed 100/day.

**Part A — create the Search Engine (gives the CSE ID):**
1. Go to <https://programmablesearchengine.google.com/controlpanel/all>.
2. Click **Add**.
3. Under "What to search?", choose **Search the entire web**.
4. Name it `reviewhub`, click **Create**.
5. Open the engine → **Setup / Basics** → copy the **Search engine ID**
   (looks like `a1b2c3d4e5f6g7h8i`).

**Part B — enable the API + get the key:**
1. Go to <https://console.cloud.google.com> (reuse the `reviewhub` project).
2. **APIs & Services → Library** → search **Custom Search API** → **Enable**.
3. **APIs & Services → Credentials → Create Credentials → API key** → copy it.
   (You can reuse the same Google project as YouTube; just make a separate key
   or reuse one and enable both APIs on it.)

**Store in GitHub Secrets:**
| Secret name | Value |
|---|---|
| `GOOGLE_CSE_ID` | the Search engine ID (from Part A) |
| `GOOGLE_CSE_KEY` | the API key (from Part B) |

**Common mistakes:**
- Mixing up the two values: **`GOOGLE_CSE_ID`** is the search-engine ID from the
  Programmable Search control panel; **`GOOGLE_CSE_KEY`** is the API key from
  Cloud Console. They are different things.
- Not selecting **"Search the entire web"** — a site-restricted engine returns
  almost nothing.

**Verify it works:**
```bash
curl -s "https://www.googleapis.com/customsearch/v1?key=YOUR_KEY&cx=YOUR_CSE_ID&q=best+ai+writing+tool"
```
JSON with `items` = working.

---

## 6. Gmail App Password

**Why it's needed:** This lets the automation send your weekly report to your
inbox via Gmail's SMTP server. An **App Password** is a special 16-character
password for programs — safer than using your real password, and it's the only
way that works with 2-Step Verification on.

**Free or paid:** **Free.**

**Requirement — turn on 2-Step Verification first:**
1. Go to <https://myaccount.google.com/security>.
2. Under "How you sign in to Google", enable **2-Step Verification** if it isn't
   already. (App Passwords are **not available** without it.)

**Create the App Password:**
1. Go to <https://myaccount.google.com/apppasswords>.
2. If asked, sign in again.
3. Under **App name**, type `reviewhub` and click **Create**.
4. Google shows a **16-character password** (like `abcd efgh ijkl mnop`).
5. Copy it and **remove the spaces** → `abcdefghijklmnop`.

**Store in GitHub Secrets:**
| Secret name | Value |
|---|---|
| `GMAIL_ADDRESS` | your full Gmail address, e.g. `emadselimone@gmail.com` |
| `GMAIL_APP_PASSWORD` | the 16-char app password, **no spaces** |

**Common mistakes:**
- Trying to create an App Password **before** enabling 2-Step Verification (the
  option won't appear).
- Leaving the **spaces** in the password.
- Using your **normal Gmail password** — it won't work for SMTP and is unsafe.

**Verify it works:** The Phase 6 delivery step includes a `--test-email` command
that sends a one-line test to yourself. If it lands, SMTP is configured.

---

## 7. Google Trends & marketplace scrapers

**No keys required.**

- **Google Trends** is read through the free `pytrends` library — no account or
  key. (It's unofficial and occasionally rate-limits; the pipeline treats a
  Trends failure as a soft miss, not a crash.)
- **JVZoo, WarriorPlus, Digistore24, AppSumo, DealMirror, Trustpilot** are read
  from their public pages — no keys. These are the most fragile sources; if one
  changes its layout, that source returns empty and the report notes it in the
  run-notes footer.

Nothing to set up here.

---

## 8. Full secrets checklist

Add all of these under **Settings → Secrets and variables → Actions**. The build
uses exactly these names.

| # | Secret name | From service | Required |
|---|---|---|---|
| 1 | `OPENROUTER_API_KEY` | OpenRouter | ✅ yes |
| 2 | `PRODUCTHUNT_TOKEN` | Product Hunt | ✅ yes |
| 3 | `REDDIT_CLIENT_ID` | Reddit | ✅ yes |
| 4 | `REDDIT_SECRET` | Reddit | ✅ yes |
| 5 | `YOUTUBE_API_KEY` | YouTube Data API | ✅ yes |
| 6 | `GOOGLE_CSE_KEY` | Google Custom Search | ✅ yes |
| 7 | `GOOGLE_CSE_ID` | Google Custom Search | ✅ yes |
| 8 | `GMAIL_ADDRESS` | Gmail | ✅ yes |
| 9 | `GMAIL_APP_PASSWORD` | Gmail | ✅ yes |

> The system is **fail-soft**: if an optional data source's key is missing, that
> signal is skipped and noted in the report rather than crashing the run. But
> the 9 above are all recommended for a complete weekly report.

---

## 9. Verify everything at once

Once every secret is added, you don't have to wait for 7 AM. You can trigger a
run manually to confirm the whole chain works:

1. Go to your repo → **Actions** tab.
2. Select the **Weekly Affiliate Intelligence** workflow.
3. Click **Run workflow → Run workflow**.
4. Watch the run. On success:
   - A new file appears in `reports/` (e.g. `reports/2026-07-08.md`).
   - The report arrives in your Gmail inbox.
   - The run log's final summary lists which sources succeeded and which were
     skipped.

If a step fails, the log names the exact service and secret involved so you know
which one to fix.

---

*Next: with keys being created in parallel, the build proceeds Phase 1 →
Phase 6. You can start adding secrets now; the code is written to wait for them.*
