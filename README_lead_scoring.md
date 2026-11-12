# Multi-Axis AI Lead Scoring — TechGropse

A standalone, testable lead-scoring module that replaces a single blended score with a **4-axis
LLM-driven model** plus hard disqualification rules. Built around `claude-sonnet-4-6` with forced
tool use for structured output reliability.

> **Assumptions flagged:** This codebase is a fresh, standalone build — your real repo may use
> different migration tooling, a non-UUID `leads.id`, or different column names. Treat the
> migrations + ORM models as **a starting template** that needs reconciliation against your
> existing schema before you merge. See "Adapting to your existing codebase" below.

---

## 1. What's in the box

```
app/
├── lead_scoring/            <- the scoring package (importable, isolated)
│   ├── config.py            <- loads scoring_config.yaml, validates weights sum to 1.0
│   ├── models.py            <- pydantic schemas + Claude tool schema (SCORING_TOOL)
│   ├── prefilter.py         <- stage 1 rule-based gate (no LLM call)
│   ├── tiering.py           <- blended score + tier assignment + authority multiplier
│   └── claude_client.py     <- sync + batch (Message Batches API) scoring
├── routes/                  <- FastAPI routers: leads, outcomes, analytics, config_api
├── export.py                <- styled .xlsx export + outreach gating
├── scheduler.py             <- APScheduler job: rule_prefilter -> (batch) Claude -> persist
├── persistence.py           <- append-only DB writes + needs_review flagging
├── lead_loader.py           <- Apify-shaped dict -> LeadInput
├── models.py                <- SQLAlchemy ORM (Lead, LeadScore, LeadOutcome, NeedsReview)
├── db.py                    <- async engine/session
├── settings.py              <- env-driven settings
└── main.py                  <- FastAPI app + lifespan scheduler + static dashboard mount
alembic/
├── env.py
└── versions/0001_initial.py <- creates leads, lead_scores, lead_outcomes, needs_review
scoring_config.yaml          <- weights, thresholds, outreach policy, model name
tests/                       <- pytest suite (see section 5)
frontend/                    <- static dashboard (see section 7)
```

---

## 2. How scoring works — the pipeline

```
LeadInput ──► rule_prefilter ──► [disqualified+skip]  → forced Cold (no LLM)
                          │
                          ├──► [disqualified, send to LLM to confirm] ─┐
                          │                                            │
                          └──► [clean] ────────────────────────────────┤
                                                                       ▼
                                              Claude tool-call (score_lead)
                                                                       │
                                          ┌────────────────────────────┴─┐
                                          │                              │
                                  deterministic reachability        function multiplier
                                  (email + LinkedIn flags)          (CTO 0.85, CMO 0.50, …)
                                          │                              │
                                          └────────────┬─────────────────┘
                                                       ▼
                                              blended_score
                                                       ▼
                                        tier_for() — applies hard rules + bands
                                                       ▼
                                              ScoringResult + DB write
```

### Hard rules (override the blended score)
1. **`Open To Work == True`** → `tier = Cold`, **no LLM call**, `disqualify_reason = "job seeker"`.
2. **Competitor keyword match** (rule) **or `is_competitor == True`** (LLM) → `tier = Cold`.
3. **`fit_score < 30`** → `tier = Cold` regardless of other axes (catches the "fractional
   consultant with great email + high authority but wrong industry" bug from manual testing).

### Tier bands (apply top-down)
| Band | Condition |
|---|---|
| Hot | blended_score ≥ 65 |
| Hot-leaning Warm | blended_score ≥ 55 |
| Warm | blended_score ≥ 45 |
| Cold | else (and the hard rules above) |

---

## 3. Quick start

```bash
# 1. Install
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# edit DATABASE_URL, ANTHROPIC_API_KEY

# 3. Migrate
alembic upgrade head

# 4. Run
uvicorn app.main:app --reload
```

On boot, the scheduler starts a job that runs **every 60 min** and processes unscored + stale
leads. Disable in tests with `APP_ENV=test`.

### Useful endpoints
- `POST /api/leads/upload` — upload an `.xlsx` workbook from the dashboard; valid rows are upserted and scored
- `POST /api/leads/{lead_id}/score` — score one lead on demand

### Excel upload

Open `http://127.0.0.1:8001/` and click **Upload .xlsx**. The first worksheet is imported. Required column:

- `Full Name`

Supported profile columns include `Headline`, `Position` or `Current Position`, `Company` or `Current Company`, `Country`, `About`, `Top Skills`, `Company Website(s)`, `Open To Work`, `Hiring`, `Connections`, `Followers`, `Email(s)`, `Email Status(es)`, `Email Quality Score(s)`, `Premium`, `Verified`, and `Open Profile`.

Rows are deduplicated using a stable source key: supplied `Lead ID`, first email address, or a normalized name/company fallback. The upload response reports created, updated, scored, review, and row-error counts. Invalid rows do not block other valid rows. Files are limited to `.xlsx`, 10 MB, and 10,000 data rows.
- `POST /api/leads/score-batch` — score a list of Apify payloads (auto-switches to batch API when ≥20)
- `GET  /api/leads/{lead_id}/scores` — full scoring history for one lead
- `POST /api/outcomes` — log contact / reply / conversion
- `GET  /api/analytics/by-tier` — reply + conversion rate per tier (calibration signal)
- `GET  /api/analytics/calibration-summary` — min/avg/max blended score per tier
- `GET  /api/config/scoring` — view current config
- `POST /api/config/scoring/reload` — hot-reload after editing `scoring_config.yaml`
- `GET  /api/config/export.xlsx` — download styled .xlsx
- `GET  /api/config/outreach-queue` — JSON of leads eligible for HeyReach/Smartlead

---

## 4. Recalibrating weights — the calibration loop

The whole point of `scoring_config_version` is to keep attribution. When you tune:

```yaml
version: "1.1.0"   # bump me!
weights:
  authority: 0.30
  fit: 0.35        # try up-weighting fit
  intent: 0.25
  reachability: 0.10
tiers:
  hot_min: 67      # raise the bar to reduce false positives
  hot_lean_min: 57
  warm_min: 46
```

Then `POST /api/config/scoring/reload` and let the scheduler run a cycle. New score rows will
carry `scoring_config_version = "1.1.0"`; old rows still say `"1.0.0"`. Use
`GET /api/analytics/by-tier` to see whether reply/conversion improved.

To attribute outcomes to a specific config version:

```sql
SELECT ls.scoring_config_version,
       COUNT(*) AS leads,
       AVG(CASE WHEN o.converted IS TRUE THEN 1.0 ELSE 0.0 END) AS conv_rate
FROM lead_scores ls
LEFT JOIN lead_outcomes o ON o.lead_id = ls.lead_id
WHERE ls.scored_at > now() - interval '30 days'
GROUP BY ls.scoring_config_version
ORDER BY ls.scoring_config_version;
```

---

## 5. Reading the review queue

`needs_review` rows are written when a re-score's tier disagrees with the previous tier for the
same lead. This protects you from silent tier flips caused by:

- Config changes that moved thresholds.
- LLM non-determinism (small but real).
- Updated Apify profile data.

A row carries `previous_tier`, `new_tier`, `previous_score_id`, `new_score_id`, and a `resolved`
flag. Build a quick dashboard tab over it, or just inspect weekly.

---

## 6. Running the tests

```bash
pytest
```

Coverage:
- `test_prefilter.py` — job seeker, dev agency keyword, clean founder, freelance, outsource, clean enterprise.
- `test_tiering.py` — every tier boundary (65.0, 64.9, 55.0, 54.9, 45.0, 44.9), fit-floor override, disqualify override, blended-score arithmetic.
- `test_authority_multiplier.py` — founder/CEO/CTO/CMO/CRO/COO/junior + headline-promotion edge case.
- `test_reachability.py` — zero/valid/catch-all/invalid/best-email-wins/premium+verified+open.
- `test_integration.py` — mocked Anthropic → tier assignment, competitor forces Cold, persistence writes + needs_review on disagreement, .xlsx color fills, outreach gating, Apify loader string-vs-bool handling.

The integration test uses `sqlite+aiosqlite` for hermetic runs. Production is Postgres — both
work against the same SQLAlchemy declarative models.

---

## 7. Frontend dashboard

`GET /` serves `frontend/index.html` — a self-contained dashboard with:

- KPI tiles (total leads, hot, hot-leaning warm, warm, cold)
- Reply / conversion rate per tier (pulled from `/api/analytics/by-tier`)
- Lead table with live tier color coding
- Filters by tier + industry + search
- Buttons to download the styled .xlsx and pull the outreach queue

No build step; CDN-loaded Chart.js only.

---

## 8. Adapting to your existing codebase — things you MUST reconcile before merging

1. **Migration tool.** I assumed **Alembic**. If you use something else, port `alembic/versions/0001_initial.py` into your tool. The SQL it emits is portable Postgres.
2. **`leads.id` type.** I assumed **UUID**. If yours is `bigint` or `varchar`, change:
   - `app/models.py` (`Lead.id` column type)
   - `app/lead_scoring/models.py` (`LeadInput.lead_id: UUID`)
   - `alembic/versions/0001_initial.py`
3. **Existing `leads` columns.** I added a `raw_payload JSONB` and a few normalized fields. If your `leads` already has equivalent columns, point `lead_from_apify` at them.
4. **OpenAI enrichment contract.** This module is **additive**. It reads from `leads.raw_payload` and never touches whatever OpenAI enrichment writes. No breaking change.
5. **APScheduler.** `app/scheduler.py` defines `score_unscored_leads_job`. Either (a) replace your existing job with a call to this function or (b) call it after your Apify ingestion job writes new rows.
6. **Existing pre-score logic.** If you have prior scoring rows in `lead_scores`, the FK migration expects the table to be empty. If not, append the new columns with `ALTER TABLE` instead of `CREATE TABLE`.
7. **Outreach dispatchers (HeyReach, Smartlead).** Wire them by polling `GET /api/config/outreach-queue` after each scoring cycle, or call it inline from your existing dispatcher.

---

## 9. Cost / latency expectations

- **Sync** single-lead scoring: ~1-3s end-to-end (Claude Sonnet 4.6, 500-600 max tokens).
- **Batch** (>20 leads): 50% cheaper via Message Batches API; expect 5-30 min turnaround depending on Anthropic queue depth. Polling interval is exponential up to 30s.
- **Job seekers** never call the LLM — saves the cost of the most common disqualification.
- **Reachability** is 100% deterministic — no LLM calls for it.

If you want to push past 20 leads/hour, raise `batch_size_threshold` to 50 or simply always use
the batch path.

---

## 10. What I'd build next (out of scope here)

- A/B test two `scoring_config.yaml` versions by routing 50/50 of leads to each.
- A "manual tier override" admin tool that updates `lead_scores` AND `needs_review` together.
- Webhook from HeyReach/Smartlead back into `POST /api/outcomes` to auto-fill reply/conversion data.
- Per-tier threshold recommendations in `/api/analytics/calibration-summary` that surface "if you
  set hot_min to 67, expected lift = +12% precision, -8% coverage" — derived from your outcome data.
