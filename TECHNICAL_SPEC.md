# News Notifications — Serverless Web Scraper & Alerting System
## Technical Specification

**Version:** 1.1
**Date:** 2026-03-10
**Target Cost:** < $2 / month

---

## 1. Overview

A serverless, event-driven pipeline on AWS that scrapes a configurable list of websites every 5 minutes, detects new content via hash comparison, and pushes notifications to a personal phone (SMS) and/or email. Each site runs as its own Lambda function, configured entirely through environment variables. Adding a new site means adding a new function block to the SAM template — no code changes.

---

## 2. Goals & Constraints

| Goal | Detail |
|------|--------|
| Cost | < $2 / month all-in |
| Extensibility | New sites added via SAM template only — no code changes |
| Delivery | SMS (SNS) and/or Email (SES) |
| Infra style | Fully serverless, no databases, no running servers |
| Language | Python 3.12 |
| IaC | AWS SAM (YAML) |
| Scrape interval | 5 minutes (stored as `SCRAPE_INTERVAL_MINUTES` env var) |

---

## 3. Architecture

```
┌──────────────────────────────────────────────────────────┐
│              EventBridge Scheduler                        │
│         rate(5 minutes) — one rule per Lambda            │
└───────┬─────────────────────┬────────────────────────────┘
        │                     │
        ▼                     ▼
┌───────────────┐    ┌────────────────┐   (one Lambda per site,
│ Trumpstruth   │    │  SiteB         │    same code, different
│ ScraperFn     │    │  ScraperFn     │    env vars)
│               │    │                │
│ env vars:     │    │ env vars:      │
│  SITE_URL     │    │  SITE_URL      │
│  CSS_SELECTOR │    │  CSS_SELECTOR  │
│  ...          │    │  ...           │
└──────┬────────┘    └───────┬────────┘
       │                     │
       │  read/write last_hash
       ▼                     ▼
┌──────────────────────────────────────┐
│       SSM Parameter Store            │
│  /news-notifier/state/trumpstruth    │  ← one param per site
│  /news-notifier/state/siteb          │    stores last content hash
└──────────────┬───────────────────────┘
               │ new content detected?
               ▼
┌──────────────────────┐
│   SNS Topic          │  PersonalAlerts (shared by all sites)
│   fan-out            │
└──────┬───────┬───────┘
       │       │
       ▼       ▼
  SMS sub   Email sub
 (phone #) (address)
```

**No DynamoDB.** State is a single string (SHA-256 hash) per site, stored in SSM Parameter Store at zero cost.

---

## 4. AWS Infrastructure Components

### 4.1 EventBridge Scheduler
- One schedule rule per Lambda, each firing `rate(5 minutes)`.
- Rule has no payload — all config is in the Lambda's env vars.
- **Cost:** Well under 14M free events/month → **$0.00**

### 4.2 Scraper Lambda (one per site)
- **Runtime:** Python 3.12, ARM64 (Graviton).
- **Memory:** 512 MB.
- **Timeout:** 30 seconds.
- **Code:** All functions share the exact same `handler.py` — behavior is driven entirely by environment variables.
- **Layers:** One shared `ScraperDepsLayer` (requests, beautifulsoup4, lxml, feedparser).
- **IAM role:** GetParameter + PutParameter on its own SSM key, Publish to SNS topic.
- **Cost at 5-min interval, 10 sites:**
  10 × 8,640 invocations = 86,400/month — well under 1M free tier → **$0.00**

### 4.3 Lambda Environment Variables (per function)

| Variable | Example | Purpose |
|----------|---------|---------|
| `SITE_URL` | `https://trumpstruth.org/` | Page to fetch |
| `SITE_NAME` | `Trump Truth Social` | Human label in notifications |
| `SCRAPE_TYPE` | `css` \| `rss` \| `json` | Parser to use |
| `CSS_SELECTOR` | `.truth-post` | CSS selector (if scrape_type=css) |
| `SCRAPE_INTERVAL_MINUTES` | `5` | Documents the schedule; not used in logic |
| `MAX_ITEMS` | `3` | Top N items to extract and hash |
| `SNS_TOPIC_ARN` | `arn:aws:sns:...` | Notification destination |
| `SSM_STATE_KEY` | `/news-notifier/state/trumpstruth` | Where to store last hash |
| `NOTIFICATION_PREFIX` | `New Truth Social post` | Message prefix |

### 4.4 SSM Parameter Store (replaces DynamoDB)
- **Type:** Standard parameter (free tier).
- **Value stored:** `last_content_hash::last_seen_iso_timestamp` (single string, e.g. `a3f9bc12...::2026-03-10T14:32:00Z`)
- **One parameter per site.**
- **Cost:** Standard parameters have no charge for storage or API calls → **$0.00**

### 4.5 SNS Topic — `PersonalAlerts`
- Single shared topic across all site functions.
- Subscriptions: SMS (phone number) and/or Email.
- **Cost:** SMS ~$0.00645/message (US). Email free.

### 4.6 Lambda Layer — `ScraperDepsLayer`
- Packages: `requests`, `beautifulsoup4`, `lxml`, `feedparser`, `jmespath`
- Shared across all site functions — deployed once.

### 4.7 SSM Parameters (config, not state)
- `/news-notifier/phone` — personal phone number for SNS SMS subscription
- `/news-notifier/email` — personal email address
- Read once at deploy time by SAM, not at runtime.

### 4.8 CloudWatch Logs
- One log group per Lambda, 7-day retention.
- **Cost:** Negligible → **~$0.01/month**

---

## 5. Project Structure

```
newsNotifications/
├── TECHNICAL_SPEC.md
├── template.yaml               ← SAM template — add new sites here
├── src/
│   └── scraper/
│       ├── handler.py          ← single handler shared by all site Lambdas
│       ├── fetcher.py          ← HTTP fetch (requests + optional Playwright)
│       ├── parser.py           ← css / rss / json parsing, returns list[str]
│       ├── state.py            ← SSM get/put last_hash helpers
│       └── notifier.py         ← SNS publish helper
├── layer/
│   └── requirements.txt        ← requests, bs4, lxml, feedparser, jmespath
└── tests/
    ├── test_parser.py
    ├── test_state.py
    └── test_notifier.py
```

---

## 6. Handler Logic — `handler.py`

```
def lambda_handler(event, context):
    1. Read all config from os.environ
    2. Fetch page (fetcher.fetch(SITE_URL))
    3. Parse content (parser.parse(html, SCRAPE_TYPE, CSS_SELECTOR, MAX_ITEMS))
       → returns list of text strings
    4. Hash the joined content (SHA-256)
    5. Read last_hash from SSM (state.get(SSM_STATE_KEY))
    6. If hash == last_hash → log "no change" → return
    7. If hash != last_hash:
       a. state.put(SSM_STATE_KEY, new_hash)
       b. Build message: f"{NOTIFICATION_PREFIX}:\n\n{content_preview}"
       c. notifier.publish(SNS_TOPIC_ARN, message, subject=SITE_NAME)
    8. Done
```

---

## 7. SAM Template Structure — Adding a New Site

Each site is one `AWS::Serverless::Function` block. To add a new site, copy-paste the block and change the env vars:

```yaml
# template.yaml (abbreviated)

Globals:
  Function:
    Runtime: python3.12
    Architectures: [arm64]
    MemorySize: 512
    Timeout: 30
    Layers:
      - !Ref ScraperDepsLayer
    Environment:
      Variables:
        SNS_TOPIC_ARN: !Ref PersonalAlertsTopic

Resources:

  # ── Site: Trump Truth Social ────────────────────────────
  TrumpstruthScraperFn:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: src/scraper/
      Handler: handler.lambda_handler
      Environment:
        Variables:
          SITE_URL: "https://trumpstruth.org/"
          SITE_NAME: "Trump Truth Social"
          SCRAPE_TYPE: "css"
          CSS_SELECTOR: ".truth-post"   # confirmed after DOM inspection
          SCRAPE_INTERVAL_MINUTES: "5"
          MAX_ITEMS: "3"
          SSM_STATE_KEY: "/news-notifier/state/trumpstruth"
          NOTIFICATION_PREFIX: "New Truth Social post"
      Events:
        Schedule:
          Type: ScheduleV2
          Properties:
            ScheduleExpression: "rate(5 minutes)"

  # ── To add a new site: copy block above, change values ──
  # ExampleSiteFn:
  #   Type: AWS::Serverless::Function
  #   Properties:
  #     ...same structure, new env vars...
  #     Events:
  #       Schedule:
  #         ScheduleExpression: "rate(5 minutes)"

  # ── Shared infrastructure ────────────────────────────────
  PersonalAlertsTopic:
    Type: AWS::SNS::Topic

  ScraperDepsLayer:
    Type: AWS::Serverless::LayerVersion
    Properties:
      ContentUri: layer/
      CompatibleRuntimes: [python3.12]
      CompatibleArchitectures: [arm64]
```

---

## 8. Revised Cost Breakdown (5-Minute Interval)

| Service | 1 site | 5 sites | 10 sites |
|---------|--------|---------|----------|
| Lambda (invocations + GB-sec) | $0.00 | $0.00 | $0.00 |
| SSM Parameter Store | $0.00 | $0.00 | $0.00 |
| EventBridge Scheduler | $0.00 | $0.00 | $0.00 |
| SNS SMS (~20 alerts/month) | ~$0.13 | ~$0.35 | ~$0.65 |
| CloudWatch Logs | ~$0.01 | ~$0.02 | ~$0.03 |
| **Total** | **~$0.14** | **~$0.37** | **~$0.68** |

**SNS SMS is the only real cost.** Infrastructure is effectively free at this scale.

---

## 9. Open Questions / Decisions Needed

| # | Question | Options |
|---|----------|---------|
| 1 | Notification channel? | SMS / Email / Both |
| 2 | trumpstruth.org CSS selector | Needs DOM inspection to confirm |
| 3 | JS rendering needed? | Inspect whether site requires Playwright |
| 4 | Archive raw content to S3? | Yes / No |

---

## 10. Next Steps

- [ ] Confirm notification preferences (SMS/email)
- [ ] Inspect trumpstruth.org DOM to identify correct CSS selector
- [ ] Implement `src/scraper/` modules
- [ ] Build `template.yaml`
- [ ] Deploy and smoke test
- [ ] Add additional sites by extending `template.yaml`
