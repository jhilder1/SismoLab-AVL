"""
History — snapshots, undo/redo and the action log (Sections 13 and 14).

Every undoable operation calls `_record(type, before, description)` with the
snapshot it took before changing anything. Undo/redo restore whole
snapshots, so they never need to know how each operation works.
"""

from __future__ import annotations

from domain.indicators import indicator_changes, indicators_from_state, indicators_of
from domain.models import format_time
from domain.storage import apply_state, scenario_to_dict
from core.linear import UndoStack

# Entries kept in the action log (Section 14). Older ones are dropped first.
ACTION_LOG_SIZE = 200


class HistoryMixin:
    """Snapshots, undo/redo stacks and the action log of a Scenario."""

    def snapshot(self) -> dict:
        """Full independent copy of the state, including the exact tree topology.

        Same format as a saved scenario file (domain/storage.py), so later
        changes to the scenario never alter a snapshot already taken.
        """
        return scenario_to_dict(self)

    def _record(self, action_type: str, before: dict, description: str) -> None:
        """Push one undoable action with the state it must return to."""
        self.undo_stack.push({
            "type": action_type, "before": before, "description": description,
        })
        self.redo_stack = UndoStack()
        self._log_action(action_type, description, before)

    def _replace_state(self, state: dict, action_type: str, description: str) -> None:
        """A load or a version restore is one undoable action (Section 13)."""
        before = self.snapshot()
        apply_state(self, state)
        self._record(action_type, before, description)

    # --- Action log (Section 14) ---

    def _log_action(self, action_type: str, description: str, before: dict) -> None:
        """Add an action to the log with every indicator it changed (Section 14:
        "El registro de una acción debe permitir explicar cómo se obtuvieron
        sus métricas"). `before` is the snapshot taken when the action started."""
        self.actions_logged += 1
        self.action_log.append({
            "seq": self.actions_logged,
            "type": action_type,
            "description": description,
            "clock": format_time(self.clock),
            "changes": indicator_changes(indicators_from_state(before), indicators_of(self)),
        })

    def get_action_log(self, limit: int = ACTION_LOG_SIZE) -> list[dict]:
        """Most recent actions first."""
        return list(reversed(self.action_log))[:max(0, limit)]

    # --- Undo / redo ---

    def undo(self) -> dict:
        if self.undo_stack.is_empty():
            return {"result": "EMPTY", "message": "No hay acciones para deshacer"}

        action = self.undo_stack.pop()
        current_state = self.snapshot()

        if not hasattr(self, "redo_stack"):
            self.redo_stack = UndoStack()

        self.redo_stack.push({
            "type": action["type"],
            "before": current_state,
            "description": action["description"],
        })

        # The snapshot already holds the queue in its original order, so undoing
        # a queue step puts the report back even when that step discarded it.
        apply_state(self, action["before"])
        self._log_action("UNDO", f"Deshacer: {action['description']}", current_state)

        return {
            "result": "UNDONE",
            "action_type": action["type"],
            "description": action["description"],
        }

    def redo(self) -> dict:
        if not hasattr(self, "redo_stack") or self.redo_stack.is_empty():
            return {"result": "EMPTY", "message": "No hay acciones para rehacer"}

        action = self.redo_stack.pop()
        current_state = self.snapshot()

        self.undo_stack.push({
            "type": action["type"],
            "before": current_state,
            "description": action["description"],
        })

        apply_state(self, action["before"])
        self._log_action("REDO", f"Rehacer: {action['description']}", current_state)

        return {
            "result": "REDONE",
            "action_type": action["type"],
            "description": action["description"],
        }

    def can_undo(self) -> bool:
        return not self.undo_stack.is_empty()
