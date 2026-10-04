"""
Scenario — central state of the simulator.

Holds the AVL, the BST, the event index, the history, the queue, the undo
stack, zones, stations, parameters and metrics. Every operation goes through
here.

The class itself only declares the state. Each group of operations lives in
its own module of this package and is mixed in below, so a feature can be
read and changed without scrolling through the others:

    catalog.py       create / correct / delete / review / look up events
    reports.py       report queue and its four processing cases (Section 8)
    associations.py  reference event of each event (Section 7)
    archive.py       eligible branches, preview and archive (Section 10)
    balance.py       stress mode and global recovery (Section 8)
    audit.py         global consistency check (Section 14)
    queries.py       queries and performance analysis (Section 11)
    settings.py      clock and parameters W, R, L, T
    persistence.py   files and named versions (Sections 12 and 13)
    history.py       snapshots, undo/redo and action log (Sections 13 and 14)
    summary.py       the state the interface draws
"""

from __future__ import annotations

from collections import deque
from datetime import datetime

from core.avl_tree import AVLTree, BSTTree
from core.linear import ReportQueue, UndoStack
from domain.models import Association, SeismicEvent, Station, Zone
from domain.scenario.archive import ArchiveMixin
from domain.scenario.associations import AssociationsMixin
from domain.scenario.audit import AuditMixin
from domain.scenario.balance import BalanceMixin
from domain.scenario.catalog import CatalogMixin
from domain.scenario.history import ACTION_LOG_SIZE, HistoryMixin
from domain.scenario.persistence import PersistenceMixin
from domain.scenario.queries import QueriesMixin
from domain.scenario.reports import ReportsMixin
from domain.scenario.settings import SettingsMixin
from domain.scenario.summary import SummaryMixin


class Scenario(
    CatalogMixin,
    ReportsMixin,
    AssociationsMixin,
    ArchiveMixin,
    BalanceMixin,
    AuditMixin,
    QueriesMixin,
    SettingsMixin,
    PersistenceMixin,
    HistoryMixin,
    SummaryMixin,
):
    """Central container of the simulator state."""

    def __init__(self):
        self.avl = AVLTree()
        self.bst = BSTTree()
        self.event_index: dict[int, SeismicEvent] = {}
        self.archived: dict[int, SeismicEvent] = {}
        self.deleted_ids: set[int] = set()
        self.associations: dict[int, Association] = {}
        self.report_queue = ReportQueue()
        self.undo_stack = UndoStack()
        self.redo_stack = UndoStack()
        self.zones: list[Zone] = []
        self.stations: dict[str, Station] = {}

        # Adjustable parameters
        self.W_hours: float = 48.0
        self.R_km: float = 40.0
        self.L_depth: int = 3
        self.T_archive_hours: float = 72.0

        # Simulation clock
        self.clock: datetime = datetime(2026, 1, 1, 0, 0, 0)

        # Metrics and indicators (Section 14)
        self.total_events_created = 0
        self.total_reports_processed = 0
        self.total_corrections = 0
        self.total_archives = 0              # events archived, cumulative
        self.total_archive_operations = 0    # mass-archive operations (Section 14)
        self.total_reports_discarded = 0
        self.total_conflicts = 0
        self.total_confirmations = 0

        # Section 8: the queue is paused while a global recovery is running.
        self._recovery_in_progress = False

        # Section 14: one entry per action with the indicators it changed.
        # Session-only and append-only: an undo adds its own entry instead of
        # erasing one, so the log still explains every value shown so far.
        self.action_log: deque = deque(maxlen=ACTION_LOG_SIZE)
        self.actions_logged = 0
