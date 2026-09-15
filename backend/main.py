"""Entry point of the SismoLab AVL backend."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="SismoLab AVL backend", version="0.1.0")

# The GUI runs on a different port in development, so the browser treats it
# as a different origin and blocks the responses unless we allow it here.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    """Liveness probe for the GUI."""
    return {"status": "ok"}
