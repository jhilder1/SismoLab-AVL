"""
Global configuration for the SismoLab backend.

Default parameter values match the specification:
  W = 48 hours (association time window)
  R = 40 km   (association distance radius)
  L = 3       (costly access depth limit)
  T = 72 hours (archive age threshold)
"""


class Config:
    """
    Application-wide configuration with default values from the spec.
    All values are mutable at runtime via the simulation API.
    """

    # Association parameters (Section 7)
    DEFAULT_W_HOURS: float = 48.0   # time window for association candidates
    DEFAULT_R_KM: float = 40.0      # distance radius for association candidates

    # Access cost (Section 9)
    DEFAULT_L_DEPTH_LIMIT: int = 3  # depth limit for costly access marking

    # Archive threshold (Section 10)
    DEFAULT_T_ARCHIVE_HOURS: float = 72.0  # minimum age for archive eligibility

    # Server
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # CORS — allow React dev server
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
