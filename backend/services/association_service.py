import math
from datetime import timedelta
from typing import Optional

from backend.models.event import SeismicEvent
from backend.models.association import Association
from .scenario import Scenario


class AssociationService:
    """Busca candidatos y selecciona la referencia para un evento."""

    def __init__(self, scenario: Scenario):
        self.sc = scenario

    def calculate_for_event(self, event_id: int) -> Optional[Association]:
        event = self.sc.get_event(event_id)
        if not event:
            return None

        candidates = self._find_candidates(event)

        if not candidates:
            assoc = Association(event_id=event_id)
            self.sc.associations[event_id] = assoc
            event.reference_event_id = None
            return assoc

        # Selección determinista: mayor M -> menor distancia -> menor ID
        best = self._select_best(event, candidates)

        assoc = Association(
            event_id=event_id,
            reference_id=best.event_id,
            candidate_ids=[c.event_id for c in candidates],
            selection_info=f"Ref={best.format_id()} M={best.magnitude}",
        )
        self.sc.associations[event_id] = assoc
        event.reference_event_id = best.event_id
        return assoc

    def _find_candidates(self, event: SeismicEvent) -> list[SeismicEvent]:
        candidates = []
        all_events = list(self.sc.event_index.values()) + list(self.sc.archived.values())

        for other in all_events:
            if other.event_id == event.event_id:
                continue
            # Magnitud estrictamente mayor
            if other.magnitude <= event.magnitude:
                continue
            # Ocurrió estrictamente antes
            if other.occurrence_time >= event.occurrence_time:
                continue
            # Dentro de la ventana temporal W
            delta = event.occurrence_time - other.occurrence_time
            if delta > timedelta(hours=self.sc.W_hours):
                continue
            # Dentro del radio R
            dist = event.epicenter.distance_to(other.epicenter)
            if dist > self.sc.R_km:
                continue

            candidates.append(other)

        return candidates

    def _select_best(self, event: SeismicEvent, candidates: list[SeismicEvent]) -> SeismicEvent:
        # Ordenar: mayor magnitud, menor distancia, menor ID
        def sort_key(c: SeismicEvent):
            dist = event.epicenter.distance_to(c.epicenter)
            return (-c.magnitude, dist, c.event_id)

        candidates.sort(key=sort_key)
        return candidates[0]

    def recalculate_all(self):
        """Recalcula asociaciones para todos los eventos activos."""
        for event_id in list(self.sc.event_index.keys()):
            self.calculate_for_event(event_id)
