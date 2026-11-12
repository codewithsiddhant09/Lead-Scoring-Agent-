# Lead Scoring Agent

A sophisticated lead scoring tool that uses AI (Claude) to automatically evaluate and tier leads based on various criteria. Built with FastAPI, SQLAlchemy, and modern async Python.

## Features

- 🤖 **AI-Powered Scoring**: Uses Anthropic's Claude API for intelligent lead evaluation
- 📊 **Multi-Tier Classification**: Automatically categorizes leads into tiers (Hot, Warm, Cold, etc.)
- 📈 **Analytics Dashboard**: Real-time visualization of lead distribution and trends
- 🔄 **Automated Processing**: Background scheduler for batch processing
- 📁 **Excel Import/Export**: Easy data import from Excel files
- 🎯 **Outcome Tracking**: Track and analyze lead conversion outcomes
- 🔍 **Pre-filtering**: Intelligent pre-filtering rules to optimize scoring
- 🌐 **REST API**: Full-featured API with FastAPI

## Tech Stack

- **Backend**: FastAPI, Python 3.11+
- **Database**: PostgreSQL (production) / SQLite (development)
- **AI**: Anthropic Claude API
- **ORM**: SQLAlchemy with Alembic migrations
- **Async**: asyncio, asyncpg
- **Scheduling**: APScheduler
- **Frontend**: Vanilla JavaScript, HTML, CSS

## Quick Start

### Prerequisites

- Python 3.11 or higher
- PostgreSQL (for production) or SQLite (for development)
- Anthropic API key

### Installation

1. Clone the repository:
```bash
git clone https://github.com/codewithsiddhant09/Lead-Scoring-Agent-.git
cd Lead-Scoring-Agent-
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. Run database migrations:
```bash
alembic upgrade head
```

5. Start the server:
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

6. Open your browser:
```
http://127.0.0.1:8000
```

## Configuration

Edit `.env` file with your settings:

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/lead_scoring

# Anthropic API
ANTHROPIC_API_KEY=your-api-key-here
ANTHROPIC_MODEL=claude-sonnet-4-6

# App Settings
APP_ENV=development
LOG_LEVEL=INFO
BATCH_SIZE_THRESHOLD=20
AUTO_OUTREACH_TIERS=Hot,Hot-leaning Warm
```

## API Endpoints

### Leads
- `GET /api/leads` - List all leads
- `POST /api/leads` - Create/import leads
- `GET /api/leads/{id}` - Get lead details
- `POST /api/leads/score` - Trigger manual scoring

### Analytics
- `GET /api/analytics/tiers` - Get tier distribution
- `GET /api/analytics/trends` - Get scoring trends

### Outcomes
- `POST /api/outcomes` - Record lead outcome
- `GET /api/analytics/outcomes` - Get outcome statistics

### Configuration
- `GET /api/config` - Get scoring configuration
- `PUT /api/config` - Update scoring configuration

## Project Structure

```
.
├── app/
│   ├── lead_scoring/      # Core scoring logic
│   │   ├── claude_client.py
│   │   ├── prefilter.py
│   │   ├── tiering.py
│   │   └── models.py
│   ├── routes/            # API endpoints
│   │   ├── leads.py
│   │   ├── analytics.py
│   │   ├── outcomes.py
│   │   └── config_api.py
│   ├── main.py           # FastAPI app
│   ├── models.py         # Database models
│   ├── persistence.py    # Data access layer
│   ├── scheduler.py      # Background jobs
│   └── settings.py       # Configuration
├── alembic/              # Database migrations
├── frontend/             # Web dashboard
│   ├── index.html
│   ├── app.js
│   └── styles.css
├── inbox/                # Incoming lead data
├── requirements.txt      # Python dependencies
└── README.md
```

## Development

### Running Tests
```bash
pytest
```

### Code Formatting
```bash
ruff check .
ruff format .
```

### Database Migrations

Create a new migration:
```bash
alembic revision --autogenerate -m "description"
```

Apply migrations:
```bash
alembic upgrade head
```

## Background Scheduler

The application includes an automated scheduler that:
- Runs every 60 minutes
- Processes unscored leads in batches
- Uses Claude API for intelligent scoring
- Updates lead tiers automatically

## License

MIT License

## Author

Siddhant - [GitHub](https://github.com/codewithsiddhant09)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
