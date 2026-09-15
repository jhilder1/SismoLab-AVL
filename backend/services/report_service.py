from backend.models.report import Report
from backend.models.enums import AttentionState
from .scenario import Scenario
from .event_service import EventService
from .association_service import AssociationService


class ReportService:
    """Procesa reportes de la cola FIFO."""

    def __init__(self, scenario: Scenario, event_service: EventService,
                 association_service: AssociationService):
        self.sc = scenario
        self.event_svc = event_service
        self.assoc_svc = association_service

    def enqueue(self, report: Report):
        self.sc.report_queue.enqueue(report)

    def enqueue_batch(self, reports: list[Report]):
        for r in reports:
            self.sc.report_queue.enqueue(r)

    def process_next(self) -> dict:
        """Procesa el siguiente reporte de la cola. Retorna info de lo que pasó."""
        if self.sc.report_queue.is_empty():
            return {"result": "EMPTY", "message": "Cola vacía"}

        before = self.sc.snapshot()
        report = self.sc.report_queue.dequeue()

        event = self.sc.get_event(report.event_id)

        # Caso 1: ID desconocido → crear nuevo evento
        if not event and report.event_id not in self.sc.deleted_ids:
            if not self.sc.id_exists_anywhere(report.event_id):
                try:
                    new_event = self.event_svc.create_event(
                        event_id=report.event_id,
                        magnitude=report.magnitude,
                        depth_km=report.depth_km,
                        epicenter_x=report.epicenter.x,
                        epicenter_y=report.epicenter.y,
                        occurrence_time=report.occurrence_time,
                        station_id=report.station_id,
                    )
                    # Quitar el undo del create_event, vamos a poner el nuestro
                    self.sc.undo_stack.pop()
                    self.assoc_svc.calculate_for_event(report.event_id)
                    result = {"result": "CREATED", "event_id": report.event_id}
                except ValueError as e:
                    result = {"result": "REJECTED", "reason": str(e)}
            else:
                result = {"result": "REJECTED", "reason": "ID ya existe (archivado/eliminado)"}
        elif not event:
            result = {"result": "REJECTED", "reason": "Evento eliminado, no se aceptan reportes"}
        # Caso 2: Revisión mayor → corrección
        elif report.revision > event.revision:
            try:
                self.event_svc.correct_event(
                    event_id=report.event_id,
                    magnitude=report.magnitude,
                    depth_km=report.depth_km,
                    epicenter_x=report.epicenter.x,
                    epicenter_y=report.epicenter.y,
                    occurrence_time=report.occurrence_time,
                )
                # Quitar el undo del correct, ponemos el nuestro
                self.sc.undo_stack.pop()
                event.reporting_stations.add(report.station_id)
                event.revision = report.revision
                self.assoc_svc.calculate_for_event(report.event_id)
                result = {"result": "CORRECTED", "event_id": report.event_id, "revision": report.revision}
            except ValueError as e:
                result = {"result": "REJECTED", "reason": str(e)}
        # Caso 3: Misma revisión, mismos datos → confirmación
        elif report.revision == event.revision:
            same_data = report.data_equals(
                event.magnitude, event.depth_km,
                event.epicenter, event.occurrence_time,
            )
            if same_data:
                event.reporting_stations.add(report.station_id)
                result = {"result": "CONFIRMED", "event_id": report.event_id}
            else:
                # Caso 4: Misma revisión, datos diferentes → conflicto
                result = {"result": "CONFLICT", "event_id": report.event_id,
                          "reason": "Misma revisión pero datos diferentes"}
        # Caso 5: Revisión menor → descartado
        else:
            result = {"result": "OUTDATED", "event_id": report.event_id,
                      "report_rev": report.revision, "current_rev": event.revision}

        self.sc.total_reports_processed += 1

        self.sc.undo_stack.push({
            "type": "PROCESS_REPORT",
            "before": before,
            "report": report.to_dict(),
            "description": f"Procesar reporte {report.event_id} rev={report.revision} → {result['result']}",
        })

        return result
