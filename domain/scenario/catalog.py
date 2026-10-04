"""
Catalog — the active events and their direct operations (Sections 5 and 6).

Owns the three structures that must always hold the same active events:
the AVL, the BST and `event_index`. Every other module adds, removes or
re-keys an active event through the helpers here (`_index_active`,
`_unindex_active`, `_reindex`), so they can never get out of sync.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from domain.models import (
    AttentionState, Epicenter, EventStatus, Priority, SeismicEvent,
)


class CatalogMixin:
    """Create, correct, delete, review and look up events."""

    # ================================================================
    # Lookups
    # ================================================================

    def id_exists_anywhere(self, event_id: int) -> bool:
        return (event_id in self.event_index
                or event_id in self.archived
                or event_id in self.deleted_ids)

    def get_event(self, event_id: int) -> Optional[SeismicEvent]:
        return self.event_index.get(event_id)

    def _find_any(self, event_id: int) -> Optional[SeismicEvent]:
        """Active or archived event with that id (None if neither)."""
        return self.event_index.get(event_id) or self.archived.get(event_id)

    def _all_events(self) -> list[SeismicEvent]:
        """Active events followed by archived ones."""
        return list(self.event_index.values()) + list(self.archived.values())

    def _require_active(self, event_id: int) -> SeismicEvent:
        event = self.get_event(event_id)
        if not event:
            raise ValueError(f"Evento {event_id} no encontrado entre los activos")
        return event

    def lookup_event(self, event_id: int) -> dict:
        """Find an event by id and say whether it is active, archived or
        deleted (Section 6), even if its priority or magnitude changed.

        The id is only the third component of K, so the AVL cannot be searched
        by id alone: the hash indexes (event_index, archived, deleted_ids)
        answer in O(1) and give the current key; then one AVL search by that
        key measures the access cost (depth + 1 nodes visited).
        """
        event = self.event_index.get(event_id)
        if event is not None:
            key = event.build_key()
            node, visited = self.avl.search(key)
            depth = visited - 1 if node else None
            return {
                "event_id": event_id, "status": "active",
                "event": event.to_dict(), "key": str(key),
                "depth": depth,
                "access_cost": visited,
                "height": node.height if node else None,
                "balance_factor": node.balance_factor if node else None,
                "limit_L": self.L_depth,
                "costly": (event.priority == Priority.HIGH
                           and depth is not None and depth > self.L_depth),
                "associations": self._association_info(event),
            }
        if event_id in self.archived:
            event = self.archived[event_id]
            return {"event_id": event_id, "status": "archived",
                    "event": event.to_dict(), "key": str(event.build_key()),
                    "associations": self._association_info(event)}
        if event_id in self.deleted_ids:
            return {"event_id": event_id, "status": "deleted", "event": None}
        return {"event_id": event_id, "status": "unknown", "event": None}

    def _association_info(self, event: SeismicEvent) -> dict:
        """Chosen reference, candidates (in the order of the selection policy)
        and the events that use this one as reference (Section 7)."""
        def describe(other):
            return {"event_id": other.event_id, "magnitude": other.magnitude,
                    "status": "active" if other.event_id in self.event_index else "archived"}

        reference = (self._find_any(event.reference_event_id)
                     if event.reference_event_id is not None else None)
        assoc = self.associations.get(event.event_id)
        candidates = [describe(c) for c in (self._find_any(i) for i in (assoc.candidate_ids if assoc else []))
                      if c is not None]
        replicas = sorted((describe(e) for e in (*self.event_index.values(), *self.archived.values())
                           if e.reference_event_id == event.event_id),
                          key=lambda r: r["event_id"])
        return {"reference": describe(reference) if reference else None,
                "candidates": candidates, "replicas": replicas}

    # ================================================================
    # Keeping AVL, BST and event_index in sync
    # ================================================================

    def _index_active(self, event: SeismicEvent) -> None:
        """Add an event to the active catalogue (AVL + BST + id index)."""
        self.avl.insert(event)
        self.bst.insert(event.build_key())
        self.event_index[event.event_id] = event

    def _unindex_active(self, event: SeismicEvent) -> None:
        """Remove an event from the active catalogue (AVL + BST + id index)."""
        key = event.build_key()
        self.avl.delete(key)
        self.bst.delete(key)
        del self.event_index[event.event_id]

    def _reindex(self, event: SeismicEvent, old_key, new_key) -> None:
        """Move an active event to its new key when a correction changed K."""
        if old_key != new_key:
            self.avl.delete(old_key)
            self.avl.insert(event)
            self.bst.delete(old_key)
            self.bst.insert(new_key)

    def _validate_event_data(self, event_id, magnitude, depth_km, epicenter_x,
                             epicenter_y, occurrence_time) -> None:
        """Raise ValueError with every problem found in the event data."""
        errors = SeismicEvent.validate_data(
            event_id, magnitude, depth_km,
            epicenter_x, epicenter_y,
            occurrence_time, self.clock,
        )
        if errors:
            raise ValueError("; ".join(errors))

    def _require_station(self, station_id: str) -> None:
        if station_id not in self.stations:
            raise ValueError(f"Estación '{station_id}' no existe en el escenario")

    # ================================================================
    # Operations
    # ================================================================

    def create_event(self, event_id: int, magnitude: float, depth_km: float,
                     epicenter_x: float, epicenter_y: float,
                     occurrence_time: datetime, station_id: str) -> SeismicEvent:
        self._validate_event_data(event_id, magnitude, depth_km,
                                  epicenter_x, epicenter_y, occurrence_time)
        if self.id_exists_anywhere(event_id):
            raise ValueError(f"El ID {event_id} ya existe en el sistema")
        self._require_station(station_id)

        before = self.snapshot()

        event = SeismicEvent(
            event_id=event_id, magnitude=magnitude, depth_km=depth_km,
            epicenter=Epicenter(epicenter_x, epicenter_y),
            occurrence_time=occurrence_time, station_id=station_id,
            zones=self.zones,
        )
        self._index_active(event)
        self.total_events_created += 1

        self._record("CREATE", before,
            f"Crear evento {event.format_id()} M={event.magnitude}")

        self.recalculate_all_associations()
        return event

    def correct_event(self, event_id: int, magnitude: Optional[float] = None,
                      depth_km: Optional[float] = None,
                      epicenter_x: Optional[float] = None,
                      epicenter_y: Optional[float] = None,
                      occurrence_time: Optional[datetime] = None) -> SeismicEvent:
        event = self._require_active(event_id)

        def pick(new, current):
            return new if new is not None else current

        self._validate_event_data(
            event_id,
            pick(magnitude, event.magnitude),
            pick(depth_km, event.depth_km),
            pick(epicenter_x, event.epicenter.x),
            pick(epicenter_y, event.epicenter.y),
            pick(occurrence_time, event.occurrence_time),
        )

        before = self.snapshot()
        old_key = event.build_key()

        new_epicenter = None
        if epicenter_x is not None or epicenter_y is not None:
            new_epicenter = Epicenter(pick(epicenter_x, event.epicenter.x),
                                      pick(epicenter_y, event.epicenter.y))

        new_key = event.apply_correction(
            magnitude=magnitude, depth_km=depth_km,
            epicenter=new_epicenter, occurrence_time=occurrence_time,
            zones=self.zones,
        )
        self._reindex(event, old_key, new_key)
        self.total_corrections += 1

        self._record("CORRECT", before,
            f"Corregir evento {event.format_id()} rev={event.revision}")

        self.recalculate_all_associations()
        return event

    def preview_delete(self, event_id: int) -> dict:
        """What deleting an event will do, shown before running it (Section 6).

        Read only. Lists the node's current descendants, which stay active
        (unlike archiving a branch, Section 10), and the events that use it as
        reference, whose association is recalculated after the deletion.
        """
        event = self._require_active(event_id)
        key = event.build_key()
        node, visited = self.avl.search(key)
        descendants = [i for i in self.avl.collect_subtree_ids(node) if i != event_id]
        dependents = sorted(e.event_id for e in self._all_events()
                            if e.reference_event_id == event_id)
        return {
            "event": event.to_dict(),
            "key": str(key),
            "depth": visited - 1,
            "descendants": descendants,
            "dependents": dependents,
        }

    def delete_event(self, event_id: int) -> SeismicEvent:
        event = self._require_active(event_id)

        before = self.snapshot()
        self._unindex_active(event)
        event.status = EventStatus.DELETED
        self.deleted_ids.add(event_id)

        if event_id in self.associations:
            del self.associations[event_id]

        self.recalculate_all_associations()

        self._record("DELETE", before,
            f"Eliminar evento {event.format_id()}")
        return event

    def mark_reviewed(self, event_id: int) -> SeismicEvent:
        event = self._require_active(event_id)
        # Nothing would change, so no action is recorded (an empty undo step).
        if event.attention_state == AttentionState.REVIEWED:
            raise ValueError(f"El evento {event.format_id()} ya está marcado como revisado")
        before = self.snapshot()
        event.attention_state = AttentionState.REVIEWED
        self._record("REVIEW", before,
            f"Marcar revisado {event.format_id()}")
        return event
