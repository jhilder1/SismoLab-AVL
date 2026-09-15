"""
Entry point of the SismoLab AVL backend.

The GUI never touches the domain objects directly: it talks to this HTTP
layer, which delegates to the services. This keeps the separation between
interface and business logic required by Section 2 of the specification.
"""

from fastapi import FastAPI

app = FastAPI(
    title="SismoLab AVL backend",
    description="Backend for the SismoLab AVL tree project",
    version="0.1.0",
)

@app.get("/health")
def health() -> dict:
    """Health check endpoint for the GUI to verify the backend is running."""
    return {"status": "ok"}