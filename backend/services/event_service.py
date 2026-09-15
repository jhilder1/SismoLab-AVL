from datetime import datetime
from typing import Optional

from backend.models.event import SeismicEvent
from backend.models.epicenter import Epicenter
from backend.models.enums import AttentionState, EventStatus
from backend.structures.tree_key import TreeKey
from .scenario import Scenario


class EventService:
    """Gestiona crear, corregir, eliminar y revisar eventos."""

    def __init__(self, scenario: Scenario):
        self.sc = scenario

    def create_event(
        self,
        event_id: int,
        magnitude: float,
        depth_km: float,
        epicenter_x: float,
        epicenter_y: float,
        occurrence_time: datetime,
        station_id: str,
    ) -> SeismicEvent:
        # Validar datos
        errors = SeismicEvent.validate_data(
            event_id, magnitude, depth_km,
            epicenter_x, epicenter_y,
            occurrence_time, self.sc.clock,
        )
        if errors:
            raise ValueError("; ".join(errors))

        # Verificar que el ID no exista
        if self.sc.id_exists_anywhere(event_id):
            raise ValueError(f"El ID {event_id} ya existe en el sistema")

        # Verificar estación
        if station_id not in self.sc.stations:
            raise ValueError(f"Estación '{station_id}' no existe en el escenario")

        # Guardar estado para undo
        before = self.sc.snapshot()

        # Crear el evento
        event = SeismicEvent(
            event_id=event_id,
            magnitude=magnitude,
            depth_km=depth_km,
            epicenter=Epicenter(epicenter_x, epicenter_y),
            occurrence_time=occurrence_time,
            station_id=station_id,
            zones=self.sc.zones,
        )

        # Insertar en AVL, BST e índice
        key = event.build_key()
        self.sc.avl.insert(key)
        self.sc.bst.insert(key)
        self.sc.event_index[event_id] = event

        # Métricas
        self.sc.total_events_created += 1

        # Guardar en undo
        self.sc.undo_stack.push({
            "type": "CREATE",
            "before": before,
            "description": f"Crear evento {event.format_id()} M={event.magnitude}",
        })

        return event

    def correct_event(
        self,
        event_id: int,
        magnitude: Optional[float] = None,
        depth_km: Optional[float] = None,
        epicenter_x: Optional[float] = None,
        epicenter_y: Optional[float] = None,
        occurrence_time: Optional[datetime] = None,
    ) -> SeismicEvent:
        event = self.sc.get_event(event_id)
        if not event:
            raise ValueError(f"Evento {event_id} no encontrado entre los activos")

        # Guardar estado para undo
        before = self.sc.snapshot()

        # Clave anterior
        old_key = event.build_key()

        # Preparar nuevo epicentro si se proporcionó
        new_epicenter = None
        if epicenter_x is not None or epicenter_y is not None:
            new_epicenter = Epicenter(
                epicenter_x if epicenter_x is not None else event.epicenter.x,
                epicenter_y if epicenter_y is not None else event.epicenter.y,
            )

        # Aplicar corrección (recalcula prioridad automáticamente)
        new_key = event.apply_correction(
            magnitude=magnitude,
            depth_km=depth_km,
            epicenter=new_epicenter,
            occurrence_time=occurrence_time,
            zones=self.sc.zones,
        )

        # Si la clave cambió, mover en los árboles
        if old_key != new_key:
            self.sc.avl.delete(old_key)
            self.sc.avl.insert(new_key)
            self.sc.bst.delete(old_key)
            self.sc.bst.insert(new_key)

        self.sc.total_corrections += 1

        self.sc.undo_stack.push({
            "type": "CORRECT",
            "before": before,
            "description": f"Corregir evento {event.format_id()} rev={event.revision}",
        })

        return event

    def delete_event(self, event_id: int) -> SeismicEvent:
        event = self.sc.get_event(event_id)
        if not event:
            raise ValueError(f"Evento {event_id} no encontrado entre los activos")

        before = self.sc.snapshot()

        # Quitar del AVL, BST e índice
        key = event.build_key()
        self.sc.avl.delete(key)
        self.sc.bst.delete(key)
        del self.sc.event_index[event_id]

        # Marcar como eliminado
        event.status = EventStatus.DELETED
        self.sc.deleted_ids.add(event_id)

        # Limpiar asociaciones
        if event_id in self.sc.associations:
            del self.sc.associations[event_id]

        self.sc.undo_stack.push({
            "type": "DELETE",
            "before": before,
            "description": f"Eliminar evento {event.format_id()}",
        })

        return event

    def mark_reviewed(self, event_id: int) -> SeismicEvent:
        event = self.sc.get_event(event_id)
        if not event:
            raise ValueError(f"Evento {event_id} no encontrado entre los activos")

        before = self.sc.snapshot()

        event.attention_state = AttentionState.REVIEWED

        self.sc.undo_stack.push({
            "type": "REVIEW",
            "before": before,
            "description": f"Marcar revisado {event.format_id()}",
        })

        return event
