# 🏔️ SismoLab AVL

Simulated seismic observatory management application.
Core data structure: **AVL Tree** of active seismic events ordered by key **K = (Priority, Magnitude, ID)**.

## Architecture

- **Backend**: Python 3.11+ / FastAPI (business logic, REST API)
- **Frontend**: React 18 / Vite (UI, D3.js tree visualization)
- **Pattern**: MVC with strict GUI/business separation

## Project Structure

```
SismoLab-AVL/
├── backend/           # Python backend (FastAPI)
│   ├── models/        # Domain entities
│   ├── structures/    # AVL, BST, Stack, Queue (own implementation)
│   ├── services/      # Business logic orchestration
│   ├── api/           # REST controllers (routers)
│   ├── schemas/       # Pydantic DTOs
│   └── tests/         # Automated tests
├── frontend/          # React frontend (Vite)
├── data/              # JSON test data files
└── docs/              # Documentation
```

## Quick Start

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Team

- Integrante A — Data Structures (AVL, BST, recovery)
- Integrante B — Backend (services, persistence, API)
- Integrante C — Frontend (React, D3.js, UI)

## License

Academic project — Universidad
