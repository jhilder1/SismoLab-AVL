"""
domain.scenario — the Scenario facade and its feature modules.

`from domain.scenario import Scenario, ACTION_LOG_SIZE` keeps working exactly
as when this was a single file.
"""

from domain.scenario.history import ACTION_LOG_SIZE
from domain.scenario.scenario import Scenario

__all__ = ["Scenario", "ACTION_LOG_SIZE"]
