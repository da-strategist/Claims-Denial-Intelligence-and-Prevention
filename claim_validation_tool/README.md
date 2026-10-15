# ClaustraRCM — AI-Powered Claim Validation Tool

A modular claim validation and denial prevention system for healthcare revenue cycle management. Built with a Python (FastAPI) backend and React frontend.

## Project Structure

```
claim_validation_tool/
├── README.md                  # This file
├── PROJECT_GUIDE.md           # Architecture, conventions, and development workflow
├── PHASES.md                  # Build phases and progress tracker
├── backend/
│   └── app/
│       ├── __init__.py
│       ├── main.py            # FastAPI application entry point
│       ├── routers/           # API route modules (claims, rules, dashboard, etc.)
│       ├── models/            # Pydantic request/response schemas
│       ├── services/          # Business logic (validation engine, AI fix, risk scoring)
│       ├── data/              # Data layer (synthetic data, database connectors)
│       └── tests/             # Backend tests
└── frontend/
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── main.jsx           # React entry point
        ├── App.jsx            # Root component and routing
        ├── components/        # Reusable UI components
        ├── pages/             # View components (Dashboard, Claims, Rules, JAB Audit)
        ├── services/          # API client functions
        └── hooks/             # Custom React hooks
```

## Prerequisites

- Python 3.12+ (managed via `uv`)
- Node.js 18+
- uv package manager

## Setup

### Backend

```bash
# From the project root (Healthcare_RCM_Project/)
uv sync

# Start the API server
cd claim_validation_tool/backend
uvicorn app.main:app --reload --port 8000
```

API docs available at: http://localhost:8000/docs

### Frontend

```bash
cd claim_validation_tool/frontend
npm install
npm run dev
```

App available at: http://localhost:5173

## Development Workflow

1. Backend and frontend run simultaneously in separate terminals
2. Backend serves JSON API on port 8000
3. Frontend dev server on port 5173 proxies API calls (CORS configured)
4. Changes auto-reload in both (uvicorn --reload, Vite HMR)
