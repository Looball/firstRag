# FirstRAG

FirstRAG is a full-stack RAG application organized as a monorepo.

## Project Structure

```text
FirstRAG/
├── frontend/      # Next.js / React frontend
├── backend/       # FastAPI backend
├── docs/          # Project documentation
├── deploy/        # Deployment assets
├── scripts/       # Automation and maintenance scripts
└── .env.example   # Environment variable template
```

## Backend

The backend lives in `backend/` and keeps the original FastAPI service
layout. Runtime configuration is loaded from the monorepo root `.env` file.

```bash
cd backend
python -m uvicorn app.main:app --reload
```

## Frontend

The frontend lives in `frontend/` after the repository merge.

```bash
cd frontend
npm install
npm run dev
```

## Documentation

Project documentation lives in `docs/`. Start with:

- `docs/ARCHITECTURE.md`
- `docs/API.md`
- `docs/RAG_WORKFLOW.md`
- `docs/AGENT_GUIDE.md`
