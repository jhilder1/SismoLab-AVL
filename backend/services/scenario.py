import copy
from datetime import datetime, timedelta
from typing import Optional

from backend.models.event import SeismicEvent
from backend.models.report import Report
from backend.models.association import Association
from backend.models.epicenter import Epicenter
from backend.models.zone import Zone
from backend.models.station import Station
from backend.models.enums import Priority, AttentionState, EventStatus
from backend.structures.avl_tree import AVLTree
from backend.structures.bst_tree import BSTTree
from backend.structures.undo_stack import UndoStack
from backend.structures.report_queue import ReportQueue
from backend.structures.tree_key import TreeKey


class Scenario:
    """Contenedor central del estado del simulador."""

    def __init__(self):
        # Árboles
        self.avl = AVLTree()
        self.bst = BSTTree()

        # Índice rápido: event_id -> SeismicEvent (O(1) por hash map)
        self.event_index: dict[int, SeismicEvent] = {}

        # Eventos archivados y eliminados
        self.archived: dict[int, SeismicEvent] = {}
        self.deleted_ids: set[int] = set()

        # Asociaciones: event_id -> Association
        self.associations: dict[int, Association] = {}

        # Cola de reportes y pila de deshacer
        self.report_queue = ReportQueue()
        self.undo_stack = UndoStack()

        # Configuración del escenario
        self.zones: list[Zone] = []
        self.stations: dict[str, Station] = {}

        # Parámetros ajustables
        self.W_hours: float = 48.0    # ventana temporal para asociaciones
        self.R_km: float = 40.0       # radio de distancia para asociaciones
        self.L_depth: int = 3         # profundidad para acceso costoso
        self.T_archive_hours: float = 72.0  # antigüedad para archivo

        # Reloj de simulación
        self.clock: datetime = datetime(2026, 1, 1, 0, 0, 0)

        # Métricas
        self.total_events_created = 0
        self.total_reports_processed = 0
        self.total_corrections = 0
        self.total_archives = 0

    def id_exists_anywhere(self, event_id: int) -> bool:
        return (event_id in self.event_index
                or event_id in self.archived
                or event_id in self.deleted_ids)

    def get_event(self, event_id: int) -> Optional[SeismicEvent]:
        return self.event_index.get(event_id)

    def snapshot(self) -> dict:
        """Deep copy del estado completo para undo."""
        return copy.deepcopy({
            "event_index": {eid: e.snapshot() for eid, e in self.event_index.items()},
            "archived": {eid: e.snapshot() for eid, e in self.archived.items()},
            "deleted_ids": set(self.deleted_ids),
            "associations": {eid: a.to_dict() for eid, a in self.associations.items()},
            "avl_keys": self.avl.inorder(),
            "clock": self.clock,
            "W_hours": self.W_hours,
            "R_km": self.R_km,
            "L_depth": self.L_depth,
            "T_archive_hours": self.T_archive_hours,
            "total_events_created": self.total_events_created,
            "total_reports_processed": self.total_reports_processed,
            "total_corrections": self.total_corrections,
            "total_archives": self.total_archives,
            "stress_mode": self.avl.stress_mode,
        })

    def summary(self) -> dict:
        """
        Indicadores visibles que exige la sección 14, más los parámetros
        vigentes. Todo endpoint que modifique algo devuelve esta misma forma,
        para que la interfaz repinte la pantalla con una sola respuesta.
        """
        return {
            "counts": {
                "active": self.avl.size,
                "archived": len(self.archived),
                "deleted": len(self.deleted_ids),
                "queued_reports": self.report_queue.size(),
                "undo_depth": self.undo_stack.size(),
            },
            "tree": {
                "height": self.avl.height,
                "leaves": self.avl.count_leaves(),
                "root": str(self.avl.root.key) if self.avl.root else None,
                "balanced": self.avl.is_balanced(),
            },
            "rotations": {
                "ll": self.avl.rotations_ll,
                "rr": self.avl.rotations_rr,
                "lr": self.avl.rotations_lr,
                "rl": self.avl.rotations_rl,
                "simple_left": self.avl.simple_turns_left,
                "simple_right": self.avl.simple_turns_right,
            },
            "metrics": {
                "events_created": self.total_events_created,
                "reports_processed": self.total_reports_processed,
                "corrections": self.total_corrections,
                "archives": self.total_archives,
            },
            "parameters": {
                "W_hours": self.W_hours,
                "R_km": self.R_km,
                "L_depth": self.L_depth,
                "T_archive_hours": self.T_archive_hours,
            },
            "clock": self.clock.isoformat(),
            "stress_mode": self.avl.stress_mode,
        }
# Instancia única compartida por todas las peticiones de este proceso.
# Por eso uvicorn debe correr con un solo worker: dos procesos tendrían
# cada uno su propio árbol.
scenario = Scenario()