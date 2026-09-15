"""
ScenarioService — the single in-memory holder of the simulation state.

Section 12 ("Guardado estructural") lists what a scenario is made of:
the active tree topology, the history, retired identifiers, stations,
associations, the queue in its original order, the simulation clock, the
zones, the parameters W, R, L and T, the execution mode and the accumulated
metrics. This class holds exactly that.

Only ONE instance exists per server process. Running uvicorn with more than
one worker would give each process its own tree, so the server must always
run single-process.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from backend.config import Config
from backend.models.event import SeismicEvent
from backend.models.station import Station
from backend.models.zone import Zone
from backend.structures.avl_tree import AVLTree
from backend.structures.bst_tree import BSTTree
from backend.structures.report_queue import ReportQueue
from backend.structures.undo_stack import UndoStack


class Metrics:
    """
    Counters required by Section 14.

    Rotation counters live in the AVL tree itself, since that is where the
    rotations happen. These are the operational ones.

    Section 14: "Los contadores forman parte del estado restaurable: deshacer
    o restaurar una version recupera sus valores anteriores." That is why they
    are a plain object with to_dict/restore instead of loose integers.
    """

    __slots__ = (
        "accepted_corrections",
        "discarded_reports",
        "conflicts",
        "bulk_archives",
        "archived_events",
    )

    def __init__(self) -> None:
        self.accepted_corrections = 0
        self.discarded_reports = 0
        self.conflicts = 0
        self.bulk_archives = 0
        self.archived_events = 0

    def to_dict(self) -> dict:
        return {name: getattr(self, name) for name in self.__slots__}

    def restore(self, data: dict) -> None:
        for name in self.__slots__:
            setattr(self, name, data[name])


class ScenarioService:
    """
    Holds the whole simulation state and hands it to the other services.

    This class stores; it does not decide. Inserting an event, resolving a
    report or choosing a branch to archive belongs to the specific services.
    Keeping storage and policy apart is what Section 2 asks for when it
    requires "una separacion de GUI y negocio".
    """

    def __init__(self) -> None:
        # --- Active catalog (Section 2) ---
        # "El AVL sera la estructura central del catalogo activo."
        self.avl_tree = AVLTree()

        # Section 12 requires the same comparator and insertion order to be
        # applied to an unbalanced BST, so the two can be compared by height,
        # leaves and number of comparisons.
        self.bst_tree = BSTTree()

        # Section 6: the identifier is only the THIRD component of the key, so
        # finding an event by id in the AVL alone would cost O(n). This index
        # makes it O(1) at the price of O(n) extra memory.
        # It maps id -> SeismicEvent, never id -> node: rotations move nodes
        # around, the event object stays the same.
        self.event_index: dict[int, SeismicEvent] = {}

        # --- History (Section 6) ---
        # "Los eventos archivados salen del AVL activo, pero conservan su
        # identidad, sus datos y sus asociaciones en el historico."
        self.archived: dict[int, SeismicEvent] = {}

        # "Un identificador eliminado se conserva como retirado: sus reportes
        # posteriores se rechazan hasta deshacer esa eliminacion."
        self.deleted_ids: set[int] = set()

        # --- Scenario geometry (Section 3) ---
        # Stations and zones are "parametrizadas, pero inmutables durante la
        # ejecucion del sistema". They are only replaced by a scenario load.
        self.stations: dict[str, Station] = {}
        self.zones: list[Zone] = []

        # --- Pending reports (Section 8) ---
        self.report_queue = ReportQueue()

        # --- Undo (Section 13) ---
        self.undo_stack = UndoStack()

        # --- Simulation clock (Section 3) ---
        # "Los tiempos de ocurrencia no pueden ser posteriores a ese reloj."
        self.simulation_clock: datetime = datetime.now(timezone.utc)

        # --- Configurable parameters ---
        self.w_hours: float = Config.DEFAULT_W_HOURS                  # Section 7
        self.r_km: float = Config.DEFAULT_R_KM                        # Section 7
        self.l_depth_limit: int = Config.DEFAULT_L_DEPTH_LIMIT        # Section 9
        self.t_archive_hours: float = Config.DEFAULT_T_ARCHIVE_HOURS  # Section 10

        # --- Metrics (Section 14) ---
        self.metrics = Metrics()

    # ------------------------------------------------------------------
    # Read-only lookups
    # ------------------------------------------------------------------

    def find_active(self, event_id: int) -> Optional[SeismicEvent]:
        """O(1) lookup of an active event by identifier."""
        return self.event_index.get(event_id)

    def find_archived(self, event_id: int) -> Optional[SeismicEvent]:
        """O(1) lookup of an archived event by identifier."""
        return self.archived.get(event_id)

    def is_deleted(self, event_id: int) -> bool:
        return event_id in self.deleted_ids

    def id_is_taken(self, event_id: int) -> bool:
        """
        Section 6: before inserting, the system "comprueba que el identificador
        no pertenezca a un evento activo, archivado o eliminado". All three
        states block reuse, so they are checked together in one place.
        """
        return (
            event_id in self.event_index
            or event_id in self.archived
            or event_id in self.deleted_ids
        )

    @property
    def stress_mode(self) -> bool:
        """
        The execution mode lives in the AVL tree, which is what actually defers
        the rotations. Exposed here so the API reads it from one place only.
        """
        return self.avl_tree.stress_mode

    # ------------------------------------------------------------------
    # State summary for the GUI
    # ------------------------------------------------------------------

    def summary(self) -> dict:
        """
        Snapshot of the indicators Section 14 asks to keep visible, plus the
        current parameters. Every mutating endpoint returns this so the GUI can
        repaint everything from a single response, which is what Section 15
        asks for: "La interfaz debe comunicar que operacion ocurrio y por que
        produjo ese resultado."
        """
        return {
            "counts": {
                "active": self.avl_tree.size,
                "archived": len(self.archived),
                "deleted": len(self.deleted_ids),
                "queued_reports": self.report_queue.size(),
                "undo_depth": self.undo_stack.size(),
            },
            "tree": {
                "height": self.avl_tree.height,
                "root": str(self.avl_tree.root.key) if self.avl_tree.root else None,
            },
            "rotations": {
                "ll": self.avl_tree.rotations_ll,
                "rr": self.avl_tree.rotations_rr,
                "lr": self.avl_tree.rotations_lr,
                "rl": self.avl_tree.rotations_rl,
                "simple_left": self.avl_tree.simple_turns_left,
                "simple_right": self.avl_tree.simple_turns_right,
            },
            "metrics": self.metrics.to_dict(),
            "parameters": {
                "w_hours": self.w_hours,
                "r_km": self.r_km,
                "l_depth_limit": self.l_depth_limit,
                "t_archive_hours": self.t_archive_hours,
            },
            "simulation_clock": self.simulation_clock.isoformat(),
            "stress_mode": self.stress_mode,
        }


# Single instance shared by every request in this process.
scenario = ScenarioService()