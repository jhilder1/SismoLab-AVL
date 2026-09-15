import copy
from backend.models.event import SeismicEvent
from backend.models.epicenter import Epicenter
from backend.models.association import Association
from backend.models.enums import AttentionState, EventStatus
from backend.structures.tree_key import TreeKey
from .scenario import Scenario


class UndoService:
    """Deshace la última acción restaurando el snapshot anterior."""

    def __init__(self, scenario: Scenario):
        self.sc = scenario

    def undo(self) -> dict:
        if self.sc.undo_stack.is_empty():
            return {"result": "EMPTY", "message": "No hay acciones para deshacer"}

        action = self.sc.undo_stack.pop()
        before = action["before"]

        # Limpiar árboles y reconstruir desde el snapshot
        self.sc.avl.__init__()
        self.sc.bst.__init__()
        self.sc.event_index.clear()
        self.sc.archived.clear()
        self.sc.deleted_ids = before["deleted_ids"]
        self.sc.clock = before["clock"]
        self.sc.W_hours = before["W_hours"]
        self.sc.R_km = before["R_km"]
        self.sc.L_depth = before["L_depth"]
        self.sc.T_archive_hours = before["T_archive_hours"]
        self.sc.total_events_created = before["total_events_created"]
        self.sc.total_reports_processed = before["total_reports_processed"]
        self.sc.total_corrections = before["total_corrections"]
        self.sc.total_archives = before["total_archives"]
        self.sc.avl.stress_mode = before["stress_mode"]

        # Restaurar eventos activos
        for eid, snap in before["event_index"].items():
            event = SeismicEvent.__new__(SeismicEvent)
            event.event_id = snap["event_id"]
            event.magnitude = snap["magnitude"]
            event.depth_km = snap["depth_km"]
            event.epicenter = snap["epicenter"]
            event.occurrence_time = snap["occurrence_time"]
            event.revision = snap["revision"]
            event.reporting_stations = snap["reporting_stations"]
            event.priority = snap["priority"]
            event.attention_state = snap["attention_state"]
            event.status = snap["status"]
            event.in_populated_zone = snap["in_populated_zone"]
            event.reference_event_id = snap["reference_event_id"]
            self.sc.event_index[eid] = event

            key = event.build_key()
            self.sc.avl.insert(key)
            self.sc.bst.insert(key)

        # Restaurar archivados
        for eid, snap in before["archived"].items():
            event = SeismicEvent.__new__(SeismicEvent)
            event.event_id = snap["event_id"]
            event.magnitude = snap["magnitude"]
            event.depth_km = snap["depth_km"]
            event.epicenter = snap["epicenter"]
            event.occurrence_time = snap["occurrence_time"]
            event.revision = snap["revision"]
            event.reporting_stations = snap["reporting_stations"]
            event.priority = snap["priority"]
            event.attention_state = snap["attention_state"]
            event.status = snap["status"]
            event.in_populated_zone = snap["in_populated_zone"]
            event.reference_event_id = snap["reference_event_id"]
            self.sc.archived[eid] = event

        # Restaurar asociaciones
        self.sc.associations.clear()
        for eid, a_dict in before["associations"].items():
            self.sc.associations[eid] = Association.from_dict(a_dict)

        return {
            "result": "UNDONE",
            "action_type": action["type"],
            "description": action["description"],
        }

    def can_undo(self) -> bool:
        return not self.sc.undo_stack.is_empty()

    def peek_last_action(self) -> dict:
        if self.sc.undo_stack.is_empty():
            return {}
        return self.sc.undo_stack.peek()
