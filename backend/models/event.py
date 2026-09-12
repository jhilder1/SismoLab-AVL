"""
SeismicEvent — the central domain entity.

Represents a single earthquake in the simulated observatory. Each event has:
- An immutable numeric identifier (1–999999).
- Physical data: magnitude, hypocentral depth, epicenter, occurrence time.
- Derived attributes: priority, AVL key K=(P,M,I), populated zone membership.
- Lifecycle state: active / archived / deleted.
- Attention state: pending / reviewed.
- Revision tracking with set of reporting stations.

The event knows how to calculate its own priority and build its AVL key,
but it does NOT insert itself into the tree — that is the service's job.
"""

from __future__ import annotations

import copy
from datetime import datetime
from typing import Optional

from .enums import Priority, AttentionState, EventStatus
from .epicenter import Epicenter
from .zone import Zone


class SeismicEvent:
    """
    A seismic event (earthquake) in the observatory catalog.

    Attributes:
        event_id:           unique integer identifier [1, 999999], immutable.
        magnitude:          decimal in [-2.0, 10.0], max 1 decimal place.
        depth_km:           hypocentral depth in km [0.0, 700.0], max 1 decimal.
        epicenter:          (x, y) coordinates on the 2D plane.
        occurrence_time:    UTC datetime of the earthquake.
        revision:           current revision number (>= 1, auto-incremented).
        reporting_stations: set of station IDs that have submitted accepted reports.
        priority:           calculated priority level (LOW / MEDIUM / HIGH).
        attention_state:    PENDING or REVIEWED.
        status:             ACTIVE, ARCHIVED, or DELETED.
        in_populated_zone:  whether the epicenter is in a populated zone.
        reference_event_id: ID of the associated reference event (possible mainshock), or None.
    """

    __slots__ = (
        "event_id",
        "magnitude",
        "depth_km",
        "epicenter",
        "occurrence_time",
        "revision",
        "reporting_stations",
        "priority",
        "attention_state",
        "status",
        "in_populated_zone",
        "reference_event_id",
    )

    def __init__(
        self,
        event_id: int,
        magnitude: float,
        depth_km: float,
        epicenter: Epicenter,
        occurrence_time: datetime,
        station_id: str,
        zones: list[Zone],
        revision: int = 1,
    ) -> None:
        # Immutable identity
        self.event_id: int = event_id

        # Physical data — normalized to 1 decimal
        self.magnitude: float = round(magnitude, 1)
        self.depth_km: float = round(depth_km, 1)
        self.epicenter: Epicenter = epicenter
        self.occurrence_time: datetime = occurrence_time

        # Revision tracking
        self.revision: int = revision
        self.reporting_stations: set[str] = {station_id}

        # Derived: zone membership and priority
        self.in_populated_zone: bool = self._check_populated_zone(zones)
        self.priority: Priority = self._calculate_priority()

        # Lifecycle
        self.attention_state: AttentionState = AttentionState.PENDING
        self.status: EventStatus = EventStatus.ACTIVE

        # Association (set later by AssociationService)
        self.reference_event_id: Optional[int] = None

    # ----------------------------------------------------------------
    # Priority calculation (Section 4 — mandatory, fixed rules)
    # ----------------------------------------------------------------

    def _calculate_priority(self) -> Priority:
        """
        Derive priority from magnitude, depth, and zone membership.

        Rules (applied in order, limits inclusive):
          Priority 3 (HIGH):  M >= 6.0
                              OR (M >= 4.5 AND H <= 30.0 AND populated zone)
          Priority 2 (MEDIUM): not HIGH and M >= 4.5
          Priority 1 (LOW):    everything else
        """
        if self.magnitude >= 6.0:
            return Priority.HIGH

        if self.magnitude >= 4.5:
            if self.depth_km <= 30.0 and self.in_populated_zone:
                return Priority.HIGH
            return Priority.MEDIUM

        return Priority.LOW

    def _check_populated_zone(self, zones: list[Zone]) -> bool:
        """
        Determine whether the epicenter is in a populated zone.

        An epicenter on the border of two zones is classified as populated
        if ANY of those zones is populated (Section 3 rule).
        """
        for zone in zones:
            if zone.contains(self.epicenter) and zone.is_populated:
                return True
        return False

    def recalculate_priority(self, zones: list[Zone]) -> Priority:
        """
        Recalculate zone membership and priority from current data.

        Called after a correction changes magnitude, depth, or epicenter.
        Returns the new priority (also updates internal state).
        """
        self.in_populated_zone = self._check_populated_zone(zones)
        self.priority = self._calculate_priority()
        return self.priority

    # ----------------------------------------------------------------
    # AVL key construction
    # ----------------------------------------------------------------

    def build_key(self) -> "TreeKey":  # noqa: F821
        """
        Build the AVL/BST comparison key K = (P, M, I).

        This must be called after priority is (re)calculated.
        Import here to avoid circular dependency.
        """
        from backend.structures.tree_key import TreeKey
        return TreeKey(
            priority=int(self.priority),
            magnitude=self.magnitude,
            event_id=self.event_id,
        )

    # ----------------------------------------------------------------
    # Correction support
    # ----------------------------------------------------------------

    def apply_correction(
        self,
        magnitude: Optional[float] = None,
        depth_km: Optional[float] = None,
        epicenter: Optional[Epicenter] = None,
        occurrence_time: Optional[datetime] = None,
        zones: list[Zone] = None,
    ) -> "TreeKey":  # noqa: F821
        """
        Apply a correction to this event's data.

        Only non-None fields are updated. The identifier is immutable.
        Automatically increments the revision, resets attention to PENDING,
        recalculates zone membership and priority, and returns the new key.

        Args:
            magnitude: new magnitude, or None to keep current.
            depth_km: new hypocentral depth, or None to keep current.
            epicenter: new epicenter, or None to keep current.
            occurrence_time: new occurrence time, or None to keep current.
            zones: list of scenario zones (required for priority recalculation).

        Returns:
            The new TreeKey after the correction.
        """
        if zones is None:
            zones = []

        if magnitude is not None:
            self.magnitude = round(magnitude, 1)
        if depth_km is not None:
            self.depth_km = round(depth_km, 1)
        if epicenter is not None:
            self.epicenter = epicenter
        if occurrence_time is not None:
            self.occurrence_time = occurrence_time

        # Auto-increment revision and reset attention
        self.revision += 1
        self.attention_state = AttentionState.PENDING

        # Recalculate derived fields
        self.recalculate_priority(zones)
        return self.build_key()

    # ----------------------------------------------------------------
    # Display and formatting
    # ----------------------------------------------------------------

    def format_id(self) -> str:
        """Format the event ID as SIS-XXXXXX (e.g. SIS-000010)."""
        return f"SIS-{self.event_id:06d}"

    def __repr__(self) -> str:
        return (
            f"SeismicEvent({self.format_id()}, M={self.magnitude}, "
            f"P={self.priority.name}, {self.attention_state.value}, "
            f"rev={self.revision})"
        )

    # ----------------------------------------------------------------
    # Snapshot for undo (deep copy of mutable state)
    # ----------------------------------------------------------------

    def snapshot(self) -> dict:
        """
        Create a deep copy of all mutable state for undo purposes.

        Returns a plain dict that can be used to restore this event
        to its exact previous state.
        """
        return {
            "event_id": self.event_id,
            "magnitude": self.magnitude,
            "depth_km": self.depth_km,
            "epicenter": Epicenter(self.epicenter.x, self.epicenter.y),
            "occurrence_time": self.occurrence_time,
            "revision": self.revision,
            "reporting_stations": set(self.reporting_stations),
            "priority": self.priority,
            "attention_state": self.attention_state,
            "status": self.status,
            "in_populated_zone": self.in_populated_zone,
            "reference_event_id": self.reference_event_id,
        }

    def restore_from_snapshot(self, snap: dict) -> None:
        """Restore mutable state from a snapshot dict."""
        self.magnitude = snap["magnitude"]
        self.depth_km = snap["depth_km"]
        self.epicenter = snap["epicenter"]
        self.occurrence_time = snap["occurrence_time"]
        self.revision = snap["revision"]
        self.reporting_stations = set(snap["reporting_stations"])
        self.priority = snap["priority"]
        self.attention_state = snap["attention_state"]
        self.status = snap["status"]
        self.in_populated_zone = snap["in_populated_zone"]
        self.reference_event_id = snap["reference_event_id"]

    # ----------------------------------------------------------------
    # Serialization (JSON)
    # ----------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "event_id": self.event_id,
            "magnitude": self.magnitude,
            "depth_km": self.depth_km,
            "epicenter": self.epicenter.to_dict(),
            "occurrence_time": self.occurrence_time.isoformat(),
            "revision": self.revision,
            "reporting_stations": sorted(self.reporting_stations),
            "priority": int(self.priority),
            "attention_state": self.attention_state.value,
            "status": self.status.value,
            "in_populated_zone": self.in_populated_zone,
            "reference_event_id": self.reference_event_id,
        }

    @classmethod
    def from_dict(cls, data: dict, zones: list[Zone]) -> "SeismicEvent":
        """
        Deserialize from a dictionary.

        Note: priority and zone membership are recalculated from data
        to ensure consistency, not taken from the stored values.
        """
        event = cls.__new__(cls)
        event.event_id = data["event_id"]
        event.magnitude = round(data["magnitude"], 1)
        event.depth_km = round(data["depth_km"], 1)
        event.epicenter = Epicenter.from_dict(data["epicenter"])
        event.occurrence_time = datetime.fromisoformat(data["occurrence_time"])
        event.revision = data["revision"]
        event.reporting_stations = set(data.get("reporting_stations", []))
        event.attention_state = AttentionState(data.get("attention_state", "pending"))
        event.status = EventStatus(data.get("status", "active"))
        event.reference_event_id = data.get("reference_event_id")

        # Recalculate derived fields for consistency
        event.in_populated_zone = event._check_populated_zone(zones)
        event.priority = event._calculate_priority()

        return event

    # ----------------------------------------------------------------
    # Validation (static, before creating an event)
    # ----------------------------------------------------------------

    @staticmethod
    def validate_data(
        event_id: int,
        magnitude: float,
        depth_km: float,
        epicenter_x: float,
        epicenter_y: float,
        occurrence_time: datetime,
        simulation_clock: datetime,
    ) -> list[str]:
        """
        Validate all input fields before creating or correcting an event.

        Returns a list of error messages. Empty list means all data is valid.
        """
        errors: list[str] = []

        # ID range
        if not (1 <= event_id <= 999999):
            errors.append(
                f"event_id must be between 1 and 999999, got {event_id}"
            )

        # Magnitude range
        if not (-2.0 <= magnitude <= 10.0):
            errors.append(
                f"magnitude must be between -2.0 and 10.0, got {magnitude}"
            )

        # Depth range
        if not (0.0 <= depth_km <= 700.0):
            errors.append(
                f"depth_km must be between 0.0 and 700.0, got {depth_km}"
            )

        # Epicenter coordinates
        if not (0.0 <= epicenter_x <= 1000.0):
            errors.append(
                f"epicenter.x must be between 0.0 and 1000.0, got {epicenter_x}"
            )
        if not (0.0 <= epicenter_y <= 1000.0):
            errors.append(
                f"epicenter.y must be between 0.0 and 1000.0, got {epicenter_y}"
            )

        # Time cannot be in the future relative to simulation clock
        if occurrence_time > simulation_clock:
            errors.append(
                f"occurrence_time ({occurrence_time.isoformat()}) cannot be "
                f"after simulation clock ({simulation_clock.isoformat()})"
            )

        return errors
