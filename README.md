# 🎯 Lead Scoring Agent

> **AI-Powered Lead Qualification System for B2B Sales Teams**

An intelligent lead scoring and qualification system that uses Anthropic's Claude AI to automatically evaluate, tier, and prioritize sales leads based on Authority, Fit, Intent, and Reachability. Built for scalability and customization with a modern Python stack.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Configuration Guide](#configuration-guide)
- [Scoring System Explained](#scoring-system-explained)
- [API Documentation](#api-documentation)
- [Database Schema](#database-schema)
- [Project Structure](#project-structure)
- [Development Guide](#development-guide)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)
- [Handover Notes](#handover-notes)

---

## 🔍 Overview

The Lead Scoring Agent is a production-ready system designed to automate the qualification process for B2B leads. It evaluates leads across four dimensions and assigns them to actionable tiers (Hot, Hot-leaning Warm, Warm, Cold), enabling sales teams to prioritize outreach effectively.

### Problem It Solves
- **Manual lead qualification is time-consuming** → Automated AI-powered scoring
- **Inconsistent evaluation criteria** → Standardized, configurable scoring framework
- **Difficulty prioritizing outreach** → Clear tier-based recommendations
- **No visibility into lead quality** → Real-time analytics dashboard

### Target Use Case
Organizations receiving leads from multiple sources (LinkedIn scrapers, form submissions, enrichment APIs) who need to:
1. Score leads automatically based on custom criteria
2. Route high-quality leads to sales teams
3. Track outcomes and refine scoring over time

---

## ✨ Key Features

### 🤖 AI-Powered Intelligence
- **Claude Sonnet 4 Integration**: Uses Anthropic's latest model for nuanced lead evaluation
- **Multi-Axis Scoring**: Evaluates Authority, Fit, Intent, and Reachability (0-100 scale)
- **Batch Processing**: Efficiently scores up to 10,000 leads/batch using Claude's Batch API
- **Competitor Detection**: Automatically flags and deprioritizes competitor profiles

### 📊 Flexible Scoring Framework
- **Configurable Weights**: Adjust importance of each scoring axis via `scoring_config.yaml`
- **Authority Multipliers**: Different multipliers for founders, CTOs, directors, etc.
- **Custom Tier Thresholds**: Define your own Hot/Warm/Cold boundaries
- **Pre-filtering Rules**: Skip AI scoring for job seekers and obvious disqualifications

### 🎯 Outreach Automation
- **Tier-Based Routing**: Auto-dispatch Hot leads, manual review for Warm, skip Cold
- **Outcome Tracking**: Record conversions, meetings, rejections to refine scoring
- **Review Queue**: Flags borderline or competitor leads for human review

### 📈 Analytics & Monitoring
- **Real-time Dashboard**: Visualize tier distribution, trends, and conversion rates
- **Outcome Analytics**: Track which tiers convert best
- **Scoring History**: Full audit trail of scoring decisions with versioning

### 🔄 Production-Ready Architecture
- **Async/Await**: High-performance async Python with FastAPI
- **Background Scheduler**: Hourly batch processing with APScheduler
- **Database Migrations**: Alembic-managed schema evolution
- **Excel Import/Export**: Bulk lead upload and result download
- **RESTful API**: Full CRUD operations with OpenAPI documentation

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Lead Ingestion Layer                     │
│  (Excel Upload, JSON API, Inbox Directory, LinkedIn Scraper) │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                   Pre-filtering Engine                       │
│      (Rule-based: Job seekers, Competitors, Missing data)    │
└───────────────────┬─────────────────────────────────────────┘
                    │
        ┌───────────┴───────────┐
        │ < 20 leads            │ >= 20 leads
        ▼                       ▼
┌──────────────┐        ┌──────────────────┐
│  Sync API    │        │  Batch API       │
│  (Real-time) │        │  (Async, 24hr)   │
└──────┬───────┘        └─────────┬────────┘
       │                          │
       └──────────┬───────────────┘
                  ▼
         ┌────────────────┐
         │  Claude Sonnet │
         │   AI Scoring   │
         └────────┬───────┘
                  │
                  ▼
         ┌────────────────┐
         │ Tiering Engine │
         │  (Weighted avg)│
         └────────┬───────┘
                  │
                  ▼
         ┌────────────────────┐
         │   PostgreSQL DB    │
         │  (Leads + Scores)  │
         └────────┬───────────┘
                  │
      ┌───────────┴───────────┐
      ▼                       ▼
┌──────────┐          ┌──────────────┐
│ Frontend │          │  API Clients │
│Dashboard │          │  (CRM, etc.) │
└──────────┘          └──────────────┘
```

### Data Flow
1. **Ingestion**: Leads arrive via Excel upload, JSON API, or inbox directory
2. **Pre-filter**: Rule-based checks skip LLM for obvious disqualifications
3. **Scoring**: Claude evaluates across 4 axes (Authority, Fit, Intent, Reachability)
4. **Tiering**: Weighted average → Hot (65+) / Hot-lean (55+) / Warm (45+) / Cold (<45)
5. **Persistence**: Score + tier saved to PostgreSQL with version tracking
6. **Review**: Borderline cases flagged for human review
7. **Outreach**: Hot leads auto-routed to sales team

---

## 🛠️ Tech Stack

### Backend
- **Python 3.11+** - Modern async/await syntax
- **FastAPI** - High-performance web framework
- **SQLAlchemy 2.0** - Async ORM with declarative models
- **Pydantic** - Data validation and settings management
- **Alembic** - Database migration management
- **APScheduler** - Background job scheduling

### Database
- **PostgreSQL** (Production) - Primary relational database
- **SQLite** (Development) - Local testing database
- **asyncpg** - Fast async PostgreSQL driver

### AI/ML
- **Anthropic Claude API** - LLM-based lead evaluation
- **Claude Sonnet 4** - Latest model with batch support

### Frontend
- **Vanilla JavaScript** - No framework dependencies
- **HTML5/CSS3** - Responsive dashboard UI
- **Fetch API** - RESTful client

### DevOps
- **pytest** - Testing framework
- **Ruff** - Fast Python linter/formatter
- **python-dotenv** - Environment variable management

---

## 🚀 Getting Started

### Prerequisites

Before you begin, ensure you have:
- **Python 3.11 or higher** ([Download](https://www.python.org/downloads/))
- **PostgreSQL 14+** (Production) or SQLite (Development)
- **Anthropic API Key** ([Get one here](https://console.anthropic.com/))
- **Git** for version control

### Installation Steps

#### 1. Clone the Repository
```bash
git clone https://github.com/codewithsiddhant09/Lead-Scoring-Agent-.git
cd Lead-Scoring-Agent-
```

#### 2. Set Up Python Environment
```bash
# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### 3. Configure Environment Variables
```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your settings (see Configuration Guide below)
# Required: ANTHROPIC_API_KEY, DATABASE_URL
```

**Minimal `.env` for Development:**
```env
DATABASE_URL=sqlite+aiosqlite:///./local.db
ANTHROPIC_API_KEY=sk-ant-your-key-here
ANTHROPIC_MODEL=claude-sonnet-4-6
APP_ENV=development
LOG_LEVEL=INFO
```

#### 4. Initialize Database
```bash
# Run migrations to create tables
alembic upgrade head

# (Optional) Seed with demo data
python _seed_demo.py
```

#### 5. Start the Application
```bash
# Development server with auto-reload
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Production server (use Gunicorn or similar)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

#### 6. Access the Dashboard
- **Frontend**: http://127.0.0.1:8000/
- **API Docs**: http://127.0.0.1:8000/docs
- **Health Check**: http://127.0.0.1:8000/health

---

## ⚙️ Configuration Guide

### Environment Variables (`.env`)

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DATABASE_URL` | PostgreSQL/SQLite connection string | `sqlite+aiosqlite:///./local.db` | ✅ |
| `ANTHROPIC_API_KEY` | Your Anthropic API key | - | ✅ |
| `ANTHROPIC_MODEL` | Claude model name | `claude-sonnet-4-6` | ❌ |
| `APP_ENV` | Environment (development/production) | `development` | ❌ |
| `LOG_LEVEL` | Logging verbosity (DEBUG/INFO/WARNING) | `INFO` | ❌ |
| `BATCH_SIZE_THRESHOLD` | Min leads for batch API | `20` | ❌ |
| `AUTO_OUTREACH_TIERS` | Tiers for auto-dispatch | `Hot,Hot-leaning Warm` | ❌ |
| `SCORING_CONFIG_PATH` | Path to scoring config YAML | `scoring_config.yaml` | ❌ |

#### Database Connection Strings

**SQLite (Development)**:
```env
DATABASE_URL=sqlite+aiosqlite:///./local.db
```

**PostgreSQL (Production)**:
```env
DATABASE_URL=postgresql+asyncpg://username:password@localhost:5432/lead_scoring
```

**PostgreSQL (Cloud - Render/Heroku)**:
```env
DATABASE_URL=postgresql+asyncpg://user:pass@host.render.com:5432/dbname
```

### Scoring Configuration (`scoring_config.yaml`)

This file controls the scoring algorithm. **Key sections:**

#### 1. Weights (must sum to 1.0)
```yaml
weights:
  authority: 0.30    # Decision-maker seniority/role
  fit: 0.30          # Company-product alignment
  intent: 0.25       # Buying signals/urgency
  reachability: 0.15 # Contact info quality
```

#### 2. Tier Thresholds
```yaml
tiers:
  hot_min: 65              # blended_score >= 65 → Hot
  hot_lean_min: 55         # blended_score >= 55 → Hot-leaning Warm
  warm_min: 45             # blended_score >= 45 → Warm
  # Below 45 → Cold
```

#### 3. Authority Multipliers
Adjusts authority score based on role type:
```yaml
authority_multipliers:
  general_management: 1.00       # Founder, CEO, President
  technical_leadership: 0.85     # CTO, VP Eng, Head of Product
  ops_director: 0.80             # COO, Director of Ops
  revenue_leadership: 0.50       # CMO, CRO, VP Sales
  individual_contributor: 0.20   # IC, Analyst, Junior roles
```

#### 4. Outreach Policy
```yaml
outreach:
  auto_dispatch_tiers: ["Hot", "Hot-leaning Warm"]
  manual_review_tiers: ["Warm"]
  never_outreach_tiers: ["Cold"]
  never_outreach_competitor: true
```

#### 5. Hard Rules
```yaml
fit_floor: 30  # If fit < 30 → forced to Cold tier regardless of other scores
disqualified_tier: "Cold"
```

**💡 Pro Tip**: Increment the `version` field whenever you change scoring parameters. This tracks which config version produced each score in the database.

---

## 🧮 Scoring System Explained

### Four-Axis Evaluation

Each lead receives **four scores (0-100)** from Claude:

#### 1. 👤 Authority (30% weight)
**What it measures**: Decision-making power and seniority

**Indicators**:
- C-suite titles (CEO, CTO, CFO)
- Founder/Co-founder status
- VP/Director-level roles
- Technical vs. non-technical leadership
- Reporting structure

**Multipliers Applied**:
- Founders get 1.0x (full score)
- CTOs get 0.85x
- CMOs get 0.50x
- ICs get 0.20x

**Example**:
```
Raw authority: 80
Role: CTO (technical_leadership)
Final authority: 80 × 0.85 = 68
```

#### 2. 🎯 Fit (30% weight)
**What it measures**: How well the company aligns with your ICP

**Indicators**:
- Industry match (e.g., B2B SaaS, FinTech)
- Company size (startups, growth-stage, enterprise)
- Tech stack alignment
- Use case relevance
- Budget indicators

**Hard Rule**: If fit < 30 → lead is forced to "Cold" tier

**Example**:
```
Company: B2B SaaS startup building CRM
Your ICP: Custom software for SaaS companies
Fit score: 85 ✅
```

#### 3. 🔥 Intent (25% weight)
**What it measures**: Buying signals and urgency

**Indicators**:
- Actively hiring developers
- Recent funding announcements
- "Open to work" posts
- Tech stack migration signals
- Conference attendance
- LinkedIn activity about pain points

**Example**:
```
Lead posted: "Looking for a dev agency to rebuild our platform"
Intent score: 90 🚀
```

#### 4. 📞 Reachability (15% weight)
**What it measures**: Likelihood of successful contact

**Indicators**:
- Email address available
- Phone number present
- LinkedIn InMail open
- Social media presence
- Engagement history
- Response rate patterns

**Example**:
```
Email: ✅ present
LinkedIn: ✅ public
Phone: ❌ missing
Reachability: 70
```

### Blended Score Calculation

```
blended_score = (authority_adjusted × 0.30) + 
                (fit × 0.30) + 
                (intent × 0.25) + 
                (reachability × 0.15)
```

**Example**:
```
Authority: 68 (CTO, after 0.85x multiplier)
Fit: 85
Intent: 60
Reachability: 70

blended_score = (68×0.30) + (85×0.30) + (60×0.25) + (70×0.15)
              = 20.4 + 25.5 + 15 + 10.5
              = 71.4 → "Hot" tier ✅
```

### Tier Assignment Logic

```python
if disqualified or fit < fit_floor:
    tier = "Cold"
elif blended_score >= 65:
    tier = "Hot"
elif blended_score >= 55:
    tier = "Hot-leaning Warm"
elif blended_score >= 45:
    tier = "Warm"
else:
    tier = "Cold"
```

### Competitor Flagging

Claude automatically detects if a lead works for a competitor. Flagged leads:
- Still receive scores
- Marked with `is_competitor=True`
- Routed to manual review queue
- Never auto-dispatched for outreach

---

## 📡 API Documentation

### Base URL
```
http://127.0.0.1:8000
```

### Interactive Docs
- **Swagger UI**: http://127.0.0.1:8000/docs
- **ReDoc**: http://127.0.0.1:8000/redoc

---

### 🔹 Leads Endpoints

#### `GET /api/leads`
List all leads with pagination and filtering.

**Query Parameters**:
- `skip` (int): Offset for pagination (default: 0)
- `limit` (int): Max results (default: 100)
- `tier` (str): Filter by tier (Hot, Warm, Cold)
- `needs_review` (bool): Only flagged leads

**Response**:
```json
{
  "leads": [
    {
      "id": "uuid",
      "full_name": "Jane Doe",
      "current_company": "Acme Corp",
      "current_position": "CTO",
      "linkedin_url": "https://linkedin.com/in/janedoe",
      "latest_score": {
        "authority_score": 85,
        "fit_score": 75,
        "intent_score": 60,
        "reachability_score": 80,
        "blended_score": 75.5,
        "tier": "Hot",
        "scored_at": "2026-11-11T10:30:00Z"
      }
    }
  ],
  "total": 1523
}
```

#### `POST /api/leads`
Create or import leads.

**Request Body**:
```json
{
  "leads": [
    {
      "full_name": "John Smith",
      "current_company": "TechCorp",
      "current_position": "Founder & CEO",
      "linkedin_url": "https://linkedin.com/in/johnsmith",
      "email": "john@techcorp.com",
      "country": "United States"
    }
  ]
}
```

**Response**:
```json
{
  "created": 1,
  "updated": 0,
  "lead_ids": ["uuid"]
}
```

#### `POST /api/leads/score`
Trigger immediate scoring for unscored or specific leads.

**Request Body**:
```json
{
  "lead_ids": ["uuid1", "uuid2"],  // Optional: specific leads
  "force_rescore": false           // Re-score even if scored
}
```

**Response**:
```json
{
  "scored": 2,
  "needs_review": 1,
  "results": [...]
}
```

#### `POST /api/leads/upload`
Bulk upload leads from Excel file.

**Form Data**:
- `file`: Excel file (.xlsx, .xls)

**Excel Format**:
| full_name | current_company | current_position | linkedin_url | email |
|-----------|----------------|------------------|--------------|-------|
| Jane Doe | Acme Corp | CTO | linkedin.com/in/jane | jane@acme.com |

**Response**:
```json
{
  "imported": 150,
  "skipped": 5,
  "errors": []
}
```

---

### 🔹 Analytics Endpoints

#### `GET /api/analytics/tiers`
Get tier distribution statistics.

**Response**:
```json
{
  "tiers": {
    "Hot": 45,
    "Hot-leaning Warm": 120,
    "Warm": 340,
    "Cold": 495
  },
  "total_scored": 1000,
  "needs_review": 23
}
```

#### `GET /api/analytics/trends`
Get scoring trends over time.

**Query Parameters**:
- `days` (int): Lookback period (default: 30)

**Response**:
```json
{
  "trend": [
    {"date": "2026-11-01", "hot": 5, "warm": 15, "cold": 10},
    {"date": "2026-11-02", "hot": 8, "warm": 20, "cold": 12}
  ]
}
```

#### `GET /api/analytics/outcomes`
Get outcome conversion statistics.

**Response**:
```json
{
  "by_tier": {
    "Hot": {"meetings": 15, "conversions": 8, "rate": 0.53},
    "Warm": {"meetings": 20, "conversions": 5, "rate": 0.25}
  }
}
```

---

### 🔹 Outcomes Endpoints

#### `POST /api/outcomes`
Record a lead outcome (meeting, conversion, rejection).

**Request Body**:
```json
{
  "lead_id": "uuid",
  "outcome_type": "meeting_booked",  // meeting_booked, converted, rejected, no_response
  "notes": "Great call, moving to next stage",
  "occurred_at": "2026-11-11T15:00:00Z"
}
```

---

### 🔹 Configuration Endpoints

#### `GET /api/config`
Get current scoring configuration.

**Response**:
```json
{
  "version": "1.1.0",
  "weights": {"authority": 0.30, "fit": 0.30, ...},
  "tiers": {"hot_min": 65, ...}
}
```

#### `PUT /api/config`
Update scoring configuration (hot-reload without restart).

**Request Body**: Same structure as `scoring_config.yaml`

---

## 🗄️ Database Schema

### `leads` Table
Primary lead information.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `full_name` | VARCHAR | Lead's full name |
| `headline` | TEXT | LinkedIn headline |
| `current_position` | VARCHAR | Job title |
| `current_company` | VARCHAR | Company name |
| `country` | VARCHAR | Geographic location |
| `about` | TEXT | Profile bio/summary |
| `linkedin_url` | VARCHAR | LinkedIn profile URL |
| `email` | VARCHAR | Email address |
| `open_to_work` | BOOLEAN | Job seeker flag |
| `raw_payload` | JSON | Original ingestion data |
| `source_key` | VARCHAR | Unique identifier from source |
| `created_at` | TIMESTAMP | Record creation time |

**Indexes**:
- `source_key` (unique) - Deduplication
- `full_name`, `current_company` - Search

### `lead_scores` Table
Scoring results and history.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `lead_id` | UUID | Foreign key to `leads` |
| `authority_score` | FLOAT | Authority score (0-100) |
| `fit_score` | FLOAT | Fit score (0-100) |
| `intent_score` | FLOAT | Intent score (0-100) |
| `reachability_score` | FLOAT | Reachability score (0-100) |
| `blended_score` | FLOAT | Weighted average |
| `tier` | VARCHAR | Hot/Warm/Cold classification |
| `is_competitor` | BOOLEAN | Competitor flag |
| `disqualify_reason` | TEXT | Why lead was disqualified |
| `technical_founder` | BOOLEAN | Founder with tech background |
| `company_stage` | VARCHAR | Startup/Growth/Enterprise |
| `industry_match` | TEXT | Industry classification |
| `notes` | TEXT | Claude's reasoning |
| `scoring_model` | VARCHAR | Model version used |
| `scoring_config_version` | VARCHAR | Config version used |
| `scored_at` | TIMESTAMP | When scored |

**Indexes**:
- `lead_id`, `scored_at` (desc) - Latest score lookup
- `tier` - Filtering by tier

### `lead_outcomes` Table
Tracks what happened with each lead.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `lead_id` | UUID | Foreign key to `leads` |
| `outcome_type` | VARCHAR | meeting_booked, converted, rejected, no_response |
| `notes` | TEXT | Outcome details |
| `occurred_at` | TIMESTAMP | When outcome occurred |
| `recorded_at` | TIMESTAMP | When recorded in system |

### `needs_review` Table
Queue for manual review.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `lead_id` | UUID | Foreign key to `leads` |
| `score_id` | UUID | Foreign key to `lead_scores` |
| `reason` | VARCHAR | Why flagged (borderline, competitor, etc.) |
| `reviewed` | BOOLEAN | Has been reviewed |
| `created_at` | TIMESTAMP | When flagged |

---

## 📁 Project Structure

```
Lead-Scoring-Agent-/
│
├── app/                          # Main application code
│   ├── __init__.py
│   ├── main.py                   # FastAPI app entry point
│   ├── settings.py               # Environment-based config
│   ├── db.py                     # Database session management
│   ├── models.py                 # SQLAlchemy models (leads, scores, outcomes)
│   ├── persistence.py            # Data access layer (CRUD operations)
│   ├── scheduler.py              # APScheduler job definitions
│   ├── lead_loader.py            # Lead ingestion adapters
│   ├── excel_import.py           # Excel upload handler
│   ├── export.py                 # Data export utilities
│   │
│   ├── lead_scoring/             # Core scoring engine
│   │   ├── __init__.py
│   │   ├── models.py             # Pydantic models for scoring
│   │   ├── config.py             # YAML config loader
│   │   ├── claude_client.py      # Anthropic API integration
│   │   ├── prefilter.py          # Rule-based pre-filtering
│   │   └── tiering.py            # Tier assignment logic
│   │
│   └── routes/                   # API endpoints
│       ├── __init__.py
│       ├── leads.py              # Lead CRUD + scoring
│       ├── analytics.py          # Stats and trends
│       ├── outcomes.py           # Outcome tracking
│       └── config_api.py         # Config management
│
├── alembic/                      # Database migrations
│   ├── versions/                 # Migration scripts
│   │   ├── 0001_initial.py       # Create tables
│   │   ├── 0002_add_lead_source_key.py
│   │   └── 0003_add_lead_linkedin_url.py
│   ├── env.py                    # Alembic environment
│   └── script.py.mako            # Migration template
│
├── frontend/                     # Web dashboard
│   ├── index.html                # Main dashboard UI
│   ├── app.js                    # Client-side logic
│   └── styles.css                # Dashboard styling
│
├── inbox/                        # JSON lead ingestion directory
│   └── *.json                    # Lead files from scrapers
│
├── tests/                        # Test suite
│   ├── conftest.py               # Pytest fixtures
│   ├── test_integration.py       # End-to-end tests
│   ├── test_prefilter.py         # Pre-filtering logic
│   ├── test_tiering.py           # Tier assignment
│   ├── test_authority_multiplier.py
│   └── test_reachability.py
│
├── .env                          # Environment variables (DO NOT COMMIT)
├── .env.example                  # Example environment config
├── .gitignore                    # Git ignore rules
├── alembic.ini                   # Alembic configuration
├── requirements.txt              # Python dependencies
├── pyproject.toml                # Tool configuration (ruff, pytest)
├── scoring_config.yaml           # Scoring algorithm config
├── _seed_demo.py                 # Demo data seeder
└── README.md                     # This file
```

### Key Files Explained

#### `app/main.py`
FastAPI app factory. Wires together:
- CORS middleware
- API routers
- Static file serving (frontend)
- Scheduler lifecycle management

#### `app/settings.py`
Loads environment variables via `pydantic-settings`. Single source of truth for configuration.

#### `app/scheduler.py`
Background job that:
1. Fetches unscored leads every hour
2. Runs pre-filter rules
3. Calls Claude (sync or batch)
4. Persists results

#### `scoring_config.yaml`
External YAML file for scoring parameters. Allows non-developers to adjust weights/thresholds without code changes.

#### `alembic/versions/`
Database schema evolution. Each migration is versioned and reversible.

---

## 🔧 Development Guide

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_tiering.py

# Run with verbose output
pytest -v
```

### Code Quality

```bash
# Lint code
ruff check .

# Format code
ruff format .

# Type checking (if using mypy)
mypy app/
```

### Database Migrations

#### Create a New Migration
```bash
# Auto-generate from model changes
alembic revision --autogenerate -m "add email_verified column"

# Review the generated file in alembic/versions/
# Edit if needed, then apply:
alembic upgrade head
```

#### Rollback Migration
```bash
# Rollback one version
alembic downgrade -1

# Rollback to specific version
alembic downgrade <revision_id>
```

#### View Migration History
```bash
alembic history
alembic current
```

### Adding a New Scoring Axis

If you need to add a 5th scoring dimension (e.g., "Budget"):

1. **Update Pydantic models** (`app/lead_scoring/models.py`):
```python
class LeadScore(BaseModel):
    # ... existing fields
    budget_score: float = Field(..., ge=0, le=100)
```

2. **Update database model** (`app/models.py`):
```python
class LeadScore(Base):
    # ... existing columns
    budget_score = Column(Float, nullable=False)
```

3. **Create migration**:
```bash
alembic revision --autogenerate -m "add budget_score"
alembic upgrade head
```

4. **Update `scoring_config.yaml`**:
```yaml
weights:
  authority: 0.25
  fit: 0.25
  intent: 0.20
  reachability: 0.15
  budget: 0.15  # New axis
```

5. **Update Claude prompt** (`app/lead_scoring/claude_client.py`):
Add budget evaluation instructions to the system prompt.

### Environment Setup for Development

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# 2. Install dev dependencies
pip install -r requirements.txt
pip install pytest pytest-asyncio pytest-cov mypy ruff

# 3. Set up pre-commit hooks (optional)
pip install pre-commit
pre-commit install

# 4. Run in dev mode
uvicorn app.main:app --reload
```

---

## 🚀 Deployment

### Option 1: Docker (Recommended)

**Create `Dockerfile`**:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Create `docker-compose.yml`**:
```yaml
version: '3.8'
services:
  web:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:password@db:5432/lead_scoring
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    depends_on:
      - db
  
  db:
    image: postgres:15
    environment:
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=lead_scoring
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

**Deploy**:
```bash
docker-compose up -d
```

### Option 2: Cloud Platform (Render/Railway/Fly.io)

#### Render.com Example

1. Create `render.yaml`:
```yaml
services:
  - type: web
    name: lead-scoring-api
    env: python
    buildCommand: "pip install -r requirements.txt"
    startCommand: "uvicorn app.main:app --host 0.0.0.0 --port $PORT"
    envVars:
      - key: ANTHROPIC_API_KEY
        sync: false
      - key: DATABASE_URL
        fromDatabase:
          name: lead-scoring-db
          property: connectionString

databases:
  - name: lead-scoring-db
    databaseName: lead_scoring
    user: lead_scoring_user
```

2. Push to GitHub
3. Connect Render to your repo
4. Deploy automatically on push

### Option 3: Traditional VPS

```bash
# SSH into server
ssh user@your-server.com

# Install dependencies
sudo apt update
sudo apt install python3.11 python3-pip postgresql nginx

# Clone repo
git clone https://github.com/codewithsiddhant09/Lead-Scoring-Agent-.git
cd Lead-Scoring-Agent-

# Set up environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
nano .env  # Add your settings

# Run migrations
alembic upgrade head

# Start with systemd
sudo nano /etc/systemd/system/lead-scoring.service
```

**systemd service file**:
```ini
[Unit]
Description=Lead Scoring API
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/Lead-Scoring-Agent-
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl start lead-scoring
sudo systemctl enable lead-scoring
```

### Production Checklist

- [ ] Set `APP_ENV=production` in `.env`
- [ ] Use PostgreSQL (not SQLite)
- [ ] Set strong database password
- [ ] Rotate Anthropic API key regularly
- [ ] Enable HTTPS (use Nginx reverse proxy + Let's Encrypt)
- [ ] Set up monitoring (Sentry, Datadog, etc.)
- [ ] Configure log aggregation
- [ ] Set up database backups
- [ ] Use process manager (systemd, supervisor, PM2)
- [ ] Set resource limits (memory, CPU)
- [ ] Configure CORS appropriately
- [ ] Add rate limiting (use Nginx or FastAPI middleware)

---

## 🐛 Troubleshooting

### Common Issues

#### 1. `ModuleNotFoundError: No module named 'sqlalchemy'`
**Solution**: Install dependencies
```bash
pip install -r requirements.txt
```

#### 2. `AttributeError: 'AsyncMessages' object has no attribute 'batches'`
**Cause**: Anthropic SDK version doesn't support Batch API yet  
**Solution**: Temporarily disable batch processing by setting a high threshold:
```yaml
# scoring_config.yaml
model:
  batch_size_threshold: 999999  # Force sync API
```

#### 3. Database Connection Errors
**PostgreSQL**:
```bash
# Check if PostgreSQL is running
sudo systemctl status postgresql

# Check connection string format
# Correct: postgresql+asyncpg://user:pass@host:5432/dbname
```

**SQLite**:
```bash
# Ensure path is correct and writable
DATABASE_URL=sqlite+aiosqlite:///./local.db
```

#### 4. Alembic Migration Conflicts
```bash
# Reset to clean state (CAUTION: loses data)
alembic downgrade base
alembic upgrade head

# Or stamp current version
alembic stamp head
```

#### 5. Claude API Rate Limits
**Error**: `429 Too Many Requests`  
**Solution**: Adjust retry policy in `scoring_config.yaml`:
```yaml
retry:
  max_attempts: 6
  initial_backoff_seconds: 2.0
  max_backoff_seconds: 60.0
```

#### 6. Scheduler Not Running
**Check logs**:
```bash
# Should see:
# INFO:app.scheduler:Scheduler started — score_unscored_leads_job every 60 min
```

**If missing**:
- Ensure `APP_ENV != test` in `.env`
- Check for startup errors in logs
- Verify APScheduler is installed

#### 7. Frontend Not Loading
**Check**:
1. `frontend/` directory exists
2. Server is serving static files
3. Visit `http://127.0.0.1:8000/` (not `/api/`)

---

## 📝 Handover Notes

### For the Next Developer

#### 🔑 Critical Files to Understand First
1. **`scoring_config.yaml`** - All scoring logic parameters
2. **`app/lead_scoring/claude_client.py`** - How AI scoring works
3. **`app/models.py`** - Database schema
4. **`app/scheduler.py`** - Automated batch processing

#### 🎛️ Configuration Locations
- **Scoring weights/thresholds**: `scoring_config.yaml`
- **Environment settings**: `.env` file
- **Database schema**: `app/models.py` + `alembic/versions/`
- **API routes**: `app/routes/*.py`

#### 🔄 Common Tasks

**Adjust scoring weights**:
```bash
# Edit scoring_config.yaml
nano scoring_config.yaml

# Restart server (or use PUT /api/config for hot-reload)
```

**Add new lead source**:
1. Create adapter in `app/lead_loader.py`
2. Add endpoint in `app/routes/leads.py`
3. Update ingestion logic in `app/persistence.py`

**Change tier thresholds**:
```yaml
# scoring_config.yaml
tiers:
  hot_min: 70      # Was 65
  hot_lean_min: 60  # Was 55
  warm_min: 50     # Was 45
```

**Modify Claude prompt**:
- Edit system message in `app/lead_scoring/claude_client.py` function `_build_system_prompt()`

#### 🚨 Important Gotchas

1. **Weights must sum to 1.0** - App will fail at startup if not
2. **`source_key` uniqueness** - Used for deduplication; format: `source:identifier`
3. **Scoring version tracking** - Always increment `version` in `scoring_config.yaml` when changing algo
4. **Batch API is async** - Results come back later (up to 24hrs)
5. **Pre-filter skips LLM** - Check `app/lead_scoring/prefilter.py` if leads aren't being scored

#### 📊 Monitoring What to Watch

- **Scoring rate**: Should process ~1000 leads/hour
- **API latency**: < 200ms for GET endpoints
- **Claude API costs**: ~$0.003/lead (sync) or ~$0.0015/lead (batch)
- **Database size**: `lead_scores` table grows fastest (5-10 GB/year for 100k leads)

#### 🔐 Secrets Management

**Never commit**:
- `.env` file
- `local.db` (SQLite database)
- Any files with API keys

**Rotate regularly**:
- `ANTHROPIC_API_KEY`
- Database passwords

#### 📞 Support Resources

- **Anthropic API Docs**: https://docs.anthropic.com/
- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **SQLAlchemy Docs**: https://docs.sqlalchemy.org/
- **Project Issues**: https://github.com/codewithsiddhant09/Lead-Scoring-Agent-/issues

---

## 📄 License

MIT License - see LICENSE file for details

---

## 👨‍💻 Author & Contact

**Siddhant**  
- GitHub: [@codewithsiddhant09](https://github.com/codewithsiddhant09)
- Email: sid181010@gmail.com

---

## 🙏 Acknowledgments

- Anthropic for Claude AI
- FastAPI community
- SQLAlchemy maintainers
- Open-source contributors

---

**Last Updated**: November 2026  
**Version**: 1.0.0  
**Status**: ✅ Production Ready
