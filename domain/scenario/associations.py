"""
Associations — the reference event of each event (Section 7).

A candidate reference has strictly greater magnitude, occurred strictly
before, within W hours and within R km. Among candidates the policy picks the
largest M, then the smallest distance, then the smallest id.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Optional

from domain.models import Association, SeismicEvent


class AssociationsMixin:
    """Compute and recompute references between events."""

    def _calculate_association(self, event_id: int) -> Optional[Association]:
        event = self._find_any(event_id)
        if not event:
            return None

        candidates = self._find_candidates(event)
        if not candidates:
            assoc = Association(event_id=event_id)
            self.associations[event_id] = assoc
            event.reference_event_id = None
            return assoc

        # Largest M, then smallest distance, then smallest id
        def sort_key(c):
            dist = event.epicenter.distance_to(c.epicenter)
            return (-c.magnitude, dist, c.event_id)

        candidates.sort(key=sort_key)
        best = candidates[0]

        assoc = Association(
            event_id=event_id, reference_id=best.event_id,
            candidate_ids=[c.event_id for c in candidates],
            selection_info=f"Ref={best.format_id()} M={best.magnitude}",
        )
        self.associations[event_id] = assoc
        event.reference_event_id = best.event_id
        return assoc

    def _find_candidates(self, event: SeismicEvent) -> list[SeismicEvent]:
        window = timedelta(hours=self.W_hours)
        candidates = []
        for other in self._all_events():
            if other.event_id == event.event_id:
                continue
            if other.magnitude <= event.magnitude:
                continue
            if other.occurrence_time >= event.occurrence_time:
                continue
            if event.occurrence_time - other.occurrence_time > window:
                continue
            if event.epicenter.distance_to(other.epicenter) > self.R_km:
                continue
            candidates.append(other)
        return candidates

    def recalculate_all_associations(self):
        for event_id in list(self.event_index.keys()):
            self._calculate_association(event_id)
        for event_id in list(self.archived.keys()):
            self._calculate_association(event_id)
