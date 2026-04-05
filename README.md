# IARS — Full-Stack Intelligent Recruitment System

End-to-end AI recruitment pipeline: FastAPI backend + MongoDB + interactive dashboard.

## Quick Start

### 1. Install & configure
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Edit .env — add GROQ_API_KEY and MONGO_URI at minimum
```

### 2. Start MongoDB
```bash
# Option A: Docker
docker run -d -p 27017:27017 --name iars_mongo mongo:7

# Option B: Local MongoDB
mongod --dbpath ./data/db
```

### 3. Start API
```bash
cd backend
uvicorn app.main:app --reload --port 8000
# Docs: http://localhost:8000/docs
```

### 4. Open Dashboard
Open `frontend/dashboard.html` in your browser.
> Make sure API is running at http://localhost:8000

### Full Docker Stack
```bash
make docker-up
# API:      http://localhost:8000/docs
# MongoDB:  localhost:27017
# Mongo UI: http://localhost:8081
```

---

## Architecture

```
frontend/dashboard.html  ←→  FastAPI (port 8000)  ←→  MongoDB
                                    │
                          LangGraph 7-node scorer
                          Groq LLM (Llama 3.3 70b)
                          GitHub API / IMAP / SMTP / LinkedIn
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/stats/global` | Dashboard KPIs + chart data |
| GET | `/api/v1/activity/` | Activity feed |
| GET | `/api/v1/activity/stream` | SSE real-time stream |
| POST | `/api/v1/jobs/` | Create job + auto-generate JD |
| GET | `/api/v1/jobs/` | List all jobs |
| POST | `/api/v1/jobs/{id}/post-linkedin` | Post JD to LinkedIn |
| GET | `/api/v1/candidates/` | List candidates (filterable) |
| POST | `/api/v1/candidates/score/file` | Upload CV + score |
| POST | `/api/v1/candidates/score/text` | Score raw text |
| POST | `/api/v1/candidates/{id}/send-email` | Send outreach/rejection email |
| POST | `/api/v1/pipeline/run` | Run full pipeline for a job |
| GET | `/api/v1/pipeline/runs` | Pipeline run history |

## MongoDB Collections

- `jobs` — job postings with AI-generated descriptions
- `candidates` — scored candidates with full evaluation reports
- `pipeline_runs` — pipeline execution history
- `activity_feed` — real-time event log
- `stats` — cached aggregate metrics

## Environment Variables

See `backend/.env.example` for full list. Minimum required:
```
GROQ_API_KEY=...
MONGO_URI=mongodb://localhost:27017
```
