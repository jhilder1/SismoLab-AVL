"""
Reports — the FIFO queue of station reports (Section 8).

`process_next_report` dequeues one report and dispatches it to exactly one
of four cases, each in its own method:
    deleted id   -> always rejected                      (_reject_deleted)
    archived id  -> reactivate / confirm / conflict / outdated (_apply_to_archived)
    active id    -> correct / confirm / conflict / outdated    (_apply_to_active)
    unknown id   -> new event                            (_create_from_report)
"""

from __future__ import annotations

from domain.models import AttentionState, Epicenter, EventStatus, Report, SeismicEvent


class ReportsMixin:
    """Enqueue and process station reports."""

    def enqueue_report(self, report: Report):
        self._validate_event_data(
            report.event_id, report.magnitude, report.depth_km,
            report.epicenter.x, report.epicenter.y, report.occurrence_time,
        )
        self._require_station(report.station_id)
        if report.revision < 1:
            raise ValueError(f"La revisión debe ser >= 1, se recibió {report.revision}")

        before = self.snapshot()
        self.report_queue.enqueue(report)
        self._record("ENQUEUE_REPORT", before, f"Encolar reporte {report.event_id} rev={report.revision}")

    def process_next_report(self) -> dict:
        if self._recovery_in_progress:
            return {"result": "PAUSED", "message": "Recuperación global en curso: la cola está en pausa"}
        if self.report_queue.is_empty():
            return {"result": "EMPTY", "message": "Cola vacía"}

        before = self.snapshot()
        report = self.report_queue.dequeue()
        event = self.get_event(report.event_id)

        if report.event_id in self.deleted_ids:
            result = self._reject_deleted(report)
        elif report.event_id in self.archived:
            result = self._apply_to_archived(report, self.archived[report.event_id])
        elif event:
            result = self._apply_to_active(report, event)
        else:
            result = self._create_from_report(report)

        self.total_reports_processed += 1
        reason = f" ({result['reason']})" if result.get("reason") else ""
        self._record("PROCESS_REPORT", before,
            f"Procesar reporte de {report.station_id}: evento {report.event_id} "
            f"rev={report.revision} → {result['result']}{reason}")
        return result

    # ================================================================
    # The four cases
    # ================================================================

    def _reject_deleted(self, report: Report) -> dict:
        """Case A: deleted id -> always rejected (Section 6)."""
        self.total_reports_discarded += 1
        return {"result": "REJECTED", "event_id": report.event_id,
                "reason": "Evento eliminado, no se aceptan reportes posteriores"}

    def _apply_to_archived(self, report: Report, event: SeismicEvent) -> dict:
        """Case B: archived id (Section 6: a higher revision reactivates it)."""
        if report.revision > event.revision:
            self._apply_report_data(event, report)
            event.status = EventStatus.ACTIVE
            event.attention_state = AttentionState.PENDING
            event.revision = report.revision
            event.reporting_stations.add(report.station_id)
            del self.archived[report.event_id]
            self._index_active(event)
            self._after_accepted_correction(report.event_id)
            return {"result": "REACTIVATED", "event_id": report.event_id, "revision": report.revision}
        if report.revision == event.revision:
            return self._same_revision(report, event, "CONFIRMED_ARCHIVED",
                                       "Misma revisión pero datos diferentes en evento archivado")
        return self._outdated(report, event)

    def _apply_to_active(self, report: Report, event: SeismicEvent) -> dict:
        """Case C: active id."""
        if report.revision > event.revision:
            old_key = event.build_key()
            new_key = self._apply_report_data(event, report)
            self._reindex(event, old_key, new_key)
            event.reporting_stations.add(report.station_id)
            event.revision = report.revision
            self._after_accepted_correction(report.event_id)
            return {"result": "CORRECTED", "event_id": report.event_id, "revision": report.revision}
        if report.revision == event.revision:
            return self._same_revision(report, event, "CONFIRMED",
                                       "Misma revisión pero datos diferentes")
        return self._outdated(report, event)

    def _create_from_report(self, report: Report) -> dict:
        """Case D: unknown id, a new event."""
        try:
            new_event = SeismicEvent(
                event_id=report.event_id, magnitude=report.magnitude,
                depth_km=report.depth_km,
                epicenter=Epicenter(report.epicenter.x, report.epicenter.y),
                occurrence_time=report.occurrence_time,
                station_id=report.station_id, zones=self.zones,
                revision=report.revision,
            )
            self._index_active(new_event)
            self.total_events_created += 1
            self._calculate_association(report.event_id)
            self.recalculate_all_associations()
            return {"result": "CREATED", "event_id": report.event_id}
        except ValueError as e:
            self.total_reports_discarded += 1
            return {"result": "REJECTED", "reason": str(e)}

    # ================================================================
    # Helpers shared by the archived and active cases
    # ================================================================

    def _apply_report_data(self, event: SeismicEvent, report: Report):
        """Copy the report's data into the event; returns the new key."""
        return event.apply_correction(
            magnitude=report.magnitude, depth_km=report.depth_km,
            epicenter=Epicenter(report.epicenter.x, report.epicenter.y),
            occurrence_time=report.occurrence_time,
            zones=self.zones,
        )

    def _after_accepted_correction(self, event_id: int) -> None:
        self.total_corrections += 1
        self._calculate_association(event_id)
        self.recalculate_all_associations()

    def _same_revision(self, report: Report, event: SeismicEvent,
                       confirmed_result: str, conflict_reason: str) -> dict:
        """Same revision: identical data confirms (adds the station), any
        difference is a conflict."""
        same_data = report.data_equals(
            event.magnitude, event.depth_km, event.epicenter, event.occurrence_time,
        )
        if same_data:
            event.reporting_stations.add(report.station_id)
            self.total_confirmations += 1
            return {"result": confirmed_result, "event_id": report.event_id}
        self.total_conflicts += 1
        return {"result": "CONFLICT", "event_id": report.event_id, "reason": conflict_reason}

    def _outdated(self, report: Report, event: SeismicEvent) -> dict:
        self.total_reports_discarded += 1
        return {"result": "OUTDATED", "event_id": report.event_id,
                "report_rev": report.revision, "current_rev": event.revision}
