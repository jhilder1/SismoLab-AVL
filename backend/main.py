"""
Entry point of the SismoLab AVL backend.

The GUI never touches the domain objects directly: it talks to this HTTP
layer, which delegates to the services. This keeps the separation between
interface and business logic required by Section 2 of the specification.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.services.scenario import scenario

app = FastAPI(
    title="SismoLab AVL backend",
    description="Backend for the SismoLab AVL tree project",
    version="0.1.0",
)

# it as a different origin and blocks the requests unless we allow them here.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite
        "http://127.0.0.1:5173",
        "http://localhost:3000",   # Create React App
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health() -> dict:
    """Health check endpoint for the GUI to verify the backend is running."""
    return {"status": "ok"}

@app.get("/state")
def get_state() -> dict:
    """
    Snapshot del escenario. La sección 14 exige mantener estos indicadores
    visibles o accesibles.
    """
    return scenario.summary()