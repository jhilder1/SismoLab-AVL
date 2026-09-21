"""
Scenario — Estado central del simulador.

Contiene el AVL, BST, índice de eventos, archivados, cola, pila, zonas,
estaciones, parámetros y métricas. Toda operación pasa por aquí.
"""

import copy
from datetime import datetime, timedelta
from typing import Optional

from domain.models import (
    SeismicEvent, Report, Association, Epicenter, Zone, Station,
    Priority, AttentionState, EventStatus,
)
from core.avl_tree import AVLTree, BSTTree, TreeKey
from core.linear import UndoStack, ReportQueue


class Scenario:
    """Contenedor central del estado del simulador."""

    def __init__(self):
        self.avl = AVLTree()
        self.bst = BSTTree()
        self.event_index: dict[int, SeismicEvent] = {}
        self.archived: dict[int, SeismicEvent] = {}
        self.deleted_ids: set[int] = set()
        self.associations: dict[int, Association] = {}
        self.report_queue = ReportQueue()
        self.undo_stack = UndoStack()
        self.zones: list[Zone] = []
        self.stations: dict[str, Station] = {}

        # Parámetros ajustables
        self.W_hours: float = 48.0
        self.R_km: float = 40.0
        self.L_depth: int = 3
        self.T_archive_hours: float = 72.0

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
        """Indicadores visibles (Sección 14) + parámetros vigentes."""
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
                "nodes": self.avl.to_dict(),
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
            "events": [e.to_dict() for e in self.event_index.values()],
        }

    # ================================================================
    # Operaciones de negocio (antes repartidas en 6 servicios)
    # ================================================================

    # --- Crear evento ---

    def create_event(self, event_id: int, magnitude: float, depth_km: float,
                     epicenter_x: float, epicenter_y: float,
                     occurrence_time: datetime, station_id: str) -> SeismicEvent:
        errors = SeismicEvent.validate_data(
            event_id, magnitude, depth_km,
            epicenter_x, epicenter_y,
            occurrence_time, self.clock,
        )
        if errors:
            raise ValueError("; ".join(errors))
        if self.id_exists_anywhere(event_id):
            raise ValueError(f"El ID {event_id} ya existe en el sistema")
        if station_id not in self.stations:
            raise ValueError(f"Estación '{station_id}' no existe en el escenario")

        before = self.snapshot()

        event = SeismicEvent(
            event_id=event_id, magnitude=magnitude, depth_km=depth_km,
            epicenter=Epicenter(epicenter_x, epicenter_y),
            occurrence_time=occurrence_time, station_id=station_id,
            zones=self.zones,
        )

        self.avl.insert(event)
        self.bst.insert(event.build_key())
        self.event_index[event_id] = event
        self.total_events_created += 1

        self.undo_stack.push({
            "type": "CREATE", "before": before,
            "description": f"Crear evento {event.format_id()} M={event.magnitude}",
        })

        self._calculate_association(event_id)
        return event

    # --- Corregir evento ---

    def correct_event(self, event_id: int, magnitude: Optional[float] = None,
                      depth_km: Optional[float] = None,
                      epicenter_x: Optional[float] = None,
                      epicenter_y: Optional[float] = None,
                      occurrence_time: Optional[datetime] = None) -> SeismicEvent:
        event = self.get_event(event_id)
        if not event:
            raise ValueError(f"Evento {event_id} no encontrado entre los activos")

        before = self.snapshot()
        old_key = event.build_key()

        new_epicenter = None
        if epicenter_x is not None or epicenter_y is not None:
            new_epicenter = Epicenter(
                epicenter_x if epicenter_x is not None else event.epicenter.x,
                epicenter_y if epicenter_y is not None else event.epicenter.y,
            )

        new_key = event.apply_correction(
            magnitude=magnitude, depth_km=depth_km,
            epicenter=new_epicenter, occurrence_time=occurrence_time,
            zones=self.zones,
        )

        if old_key != new_key:
            self.avl.delete(old_key)
            self.avl.insert(event)
            self.bst.delete(old_key)
            self.bst.insert(new_key)

        self.total_corrections += 1

        self.undo_stack.push({
            "type": "CORRECT", "before": before,
            "description": f"Corregir evento {event.format_id()} rev={event.revision}",
        })

        self._calculate_association(event_id)
        return event

    # --- Eliminar evento ---

    def delete_event(self, event_id: int) -> SeismicEvent:
        event = self.get_event(event_id)
        if not event:
            raise ValueError(f"Evento {event_id} no encontrado entre los activos")

        before = self.snapshot()
        key = event.build_key()
        self.avl.delete(key)
        self.bst.delete(key)
        del self.event_index[event_id]
        event.status = EventStatus.DELETED
        self.deleted_ids.add(event_id)

        if event_id in self.associations:
            del self.associations[event_id]

        self.undo_stack.push({
            "type": "DELETE", "before": before,
            "description": f"Eliminar evento {event.format_id()}",
        })
        return event

    # --- Marcar revisado ---

    def mark_reviewed(self, event_id: int) -> SeismicEvent:
        event = self.get_event(event_id)
        if not event:
            raise ValueError(f"Evento {event_id} no encontrado entre los activos")
        before = self.snapshot()
        event.attention_state = AttentionState.REVIEWED
        self.undo_stack.push({
            "type": "REVIEW", "before": before,
            "description": f"Marcar revisado {event.format_id()}",
        })
        return event

    # --- Encolar y procesar reportes ---

    def enqueue_report(self, report: Report):
        self.report_queue.enqueue(report)

    def process_next_report(self) -> dict:
        if self.report_queue.is_empty():
            return {"result": "EMPTY", "message": "Cola vacía"}

        before = self.snapshot()
        report = self.report_queue.dequeue()
        event = self.get_event(report.event_id)

        # Caso 1: ID desconocido → crear nuevo
        if not event and report.event_id not in self.deleted_ids:
            if not self.id_exists_anywhere(report.event_id):
                try:
                    new_event = SeismicEvent(
                        event_id=report.event_id, magnitude=report.magnitude,
                        depth_km=report.depth_km,
                        epicenter=Epicenter(report.epicenter.x, report.epicenter.y),
                        occurrence_time=report.occurrence_time,
                        station_id=report.station_id, zones=self.zones,
                    )
                    self.avl.insert(new_event)
                    self.bst.insert(new_event.build_key())
                    self.event_index[report.event_id] = new_event
                    self.total_events_created += 1
                    self._calculate_association(report.event_id)
                    result = {"result": "CREATED", "event_id": report.event_id}
                except ValueError as e:
                    result = {"result": "REJECTED", "reason": str(e)}
            else:
                result = {"result": "REJECTED", "reason": "ID ya existe (archivado/eliminado)"}
        elif not event:
            result = {"result": "REJECTED", "reason": "Evento eliminado, no se aceptan reportes"}
        # Caso 2: Revisión mayor → corrección
        elif report.revision > event.revision:
            old_key = event.build_key()
            new_epi = Epicenter(report.epicenter.x, report.epicenter.y)
            new_key = event.apply_correction(
                magnitude=report.magnitude, depth_km=report.depth_km,
                epicenter=new_epi, occurrence_time=report.occurrence_time,
                zones=self.zones,
            )
            if old_key != new_key:
                self.avl.delete(old_key)
                self.avl.insert(event)
                self.bst.delete(old_key)
                self.bst.insert(new_key)
            event.reporting_stations.add(report.station_id)
            event.revision = report.revision
            self.total_corrections += 1
            self._calculate_association(report.event_id)
            result = {"result": "CORRECTED", "event_id": report.event_id, "revision": report.revision}
        # Caso 3: Misma revisión, mismos datos → confirmación
        elif report.revision == event.revision:
            same_data = report.data_equals(
                event.magnitude, event.depth_km, event.epicenter, event.occurrence_time)
            if same_data:
                event.reporting_stations.add(report.station_id)
                result = {"result": "CONFIRMED", "event_id": report.event_id}
            else:
                result = {"result": "CONFLICT", "event_id": report.event_id,
                          "reason": "Misma revisión pero datos diferentes"}
        # Caso 4: Revisión menor → descartado
        else:
            result = {"result": "OUTDATED", "event_id": report.event_id,
                      "report_rev": report.revision, "current_rev": event.revision}

        self.total_reports_processed += 1
        self.undo_stack.push({
            "type": "PROCESS_REPORT", "before": before,
            "report": report.to_dict(),
            "description": f"Procesar reporte {report.event_id} rev={report.revision} → {result['result']}",
        })
        return result

    # --- Asociaciones ---

    def _calculate_association(self, event_id: int) -> Optional[Association]:
        event = self.get_event(event_id)
        if not event:
            return None

        candidates = self._find_candidates(event)
        if not candidates:
            assoc = Association(event_id=event_id)
            self.associations[event_id] = assoc
            event.reference_event_id = None
            return assoc

        # Mayor M → menor distancia → menor ID
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
        candidates = []
        all_events = list(self.event_index.values()) + list(self.archived.values())
        for other in all_events:
            if other.event_id == event.event_id:
                continue
            if other.magnitude <= event.magnitude:
                continue
            if other.occurrence_time >= event.occurrence_time:
                continue
            delta = event.occurrence_time - other.occurrence_time
            if delta > timedelta(hours=self.W_hours):
                continue
            dist = event.epicenter.distance_to(other.epicenter)
            if dist > self.R_km:
                continue
            candidates.append(other)
        return candidates

    def recalculate_all_associations(self):
        for event_id in list(self.event_index.keys()):
            self._calculate_association(event_id)

    # --- Archivo ---

    def find_eligible_branches(self) -> list[dict]:
        result = []
        self._find_eligible(self.avl.root, result)
        result.sort(key=lambda x: x["count"], reverse=True)
        return result

    def _find_eligible(self, node, result: list):
        if not node:
            return
        ids = []
        if self._is_subtree_eligible(node, ids):
            result.append({"root_key": node.key, "event_ids": ids, "count": len(ids)})
        else:
            self._find_eligible(node.left, result)
            self._find_eligible(node.right, result)

    def _is_subtree_eligible(self, node, ids: list) -> bool:
        if not node:
            return True
        event = self.event_index.get(node.event_id)
        if not event:
            return False
        if event.priority != Priority.LOW:
            return False
        age = self.clock - event.occurrence_time
        if age < timedelta(hours=self.T_archive_hours):
            return False
        ids.append(node.event_id)
        return (self._is_subtree_eligible(node.left, ids)
                and self._is_subtree_eligible(node.right, ids))

    def archive_branch(self, event_ids: list[int]) -> int:
        before = self.snapshot()
        count = 0
        for eid in event_ids:
            event = self.event_index.get(eid)
            if not event:
                continue
            key = event.build_key()
            self.avl.delete(key)
            self.bst.delete(key)
            del self.event_index[eid]
            event.status = EventStatus.ARCHIVED
            self.archived[eid] = event
            count += 1
        self.total_archives += count
        self.undo_stack.push({
            "type": "ARCHIVE", "before": before,
            "description": f"Archivar {count} eventos: {event_ids}",
        })
        return count

    def archive_largest_eligible(self) -> dict:
        branches = self.find_eligible_branches()
        if not branches:
            return {"result": "NO_ELIGIBLE", "message": "No hay ramas elegibles"}
        best = branches[0]
        count = self.archive_branch(best["event_ids"])
        return {"result": "ARCHIVED", "count": count, "event_ids": best["event_ids"]}

    # --- Undo ---

    def undo(self) -> dict:
        if self.undo_stack.is_empty():
            return {"result": "EMPTY", "message": "No hay acciones para deshacer"}

        action = self.undo_stack.pop()
        before = action["before"]

        self.avl.__init__()
        self.bst.__init__()
        self.event_index.clear()
        self.archived.clear()
        self.deleted_ids = before["deleted_ids"]
        self.clock = before["clock"]
        self.W_hours = before["W_hours"]
        self.R_km = before["R_km"]
        self.L_depth = before["L_depth"]
        self.T_archive_hours = before["T_archive_hours"]
        self.total_events_created = before["total_events_created"]
        self.total_reports_processed = before["total_reports_processed"]
        self.total_corrections = before["total_corrections"]
        self.total_archives = before["total_archives"]
        self.avl.stress_mode = before["stress_mode"]

        for eid, snap in before["event_index"].items():
            event = SeismicEvent.__new__(SeismicEvent)
            event.event_id = snap["event_id"]
            event.magnitude = snap["magnitude"]
            event.depth_km = snap["depth_km"]
            event.epicenter = snap["epicenter"]
            event.occurrence_time = snap["occurrence_time"]
            event.revision = snap["revision"]
            event.reporting_stations = snap["reporting_stations"]
            event.priority = snap["priority"]
            event.attention_state = snap["attention_state"]
            event.status = snap["status"]
            event.in_populated_zone = snap["in_populated_zone"]
            event.reference_event_id = snap["reference_event_id"]
            self.event_index[eid] = event
            self.avl.insert(event)
            self.bst.insert(event.build_key())

        for eid, snap in before["archived"].items():
            event = SeismicEvent.__new__(SeismicEvent)
            event.event_id = snap["event_id"]
            event.magnitude = snap["magnitude"]
            event.depth_km = snap["depth_km"]
            event.epicenter = snap["epicenter"]
            event.occurrence_time = snap["occurrence_time"]
            event.revision = snap["revision"]
            event.reporting_stations = snap["reporting_stations"]
            event.priority = snap["priority"]
            event.attention_state = snap["attention_state"]
            event.status = snap["status"]
            event.in_populated_zone = snap["in_populated_zone"]
            event.reference_event_id = snap["reference_event_id"]
            self.archived[eid] = event

        self.associations.clear()
        for eid, a_dict in before["associations"].items():
            self.associations[eid] = Association.from_dict(a_dict)

        return {
            "result": "UNDONE",
            "action_type": action["type"],
            "description": action["description"],
        }

    def can_undo(self) -> bool:
        return not self.undo_stack.is_empty()

    # --- Auditoría ---

    def run_audit(self) -> dict:
        errors = []
        errors += self._audit_bst_order()
        errors += self._audit_avl_balance()
        errors += self._audit_heights()
        errors += self._audit_unique_ids()
        errors += self._audit_index_consistency()
        return {"is_valid": len(errors) == 0, "errors": errors, "nodes_checked": self.avl.size}

    def _audit_bst_order(self) -> list[str]:
        errors = []
        keys = self.avl.inorder()
        for i in range(len(keys) - 1):
            if keys[i] >= keys[i + 1]:
                errors.append(f"Orden BST violado: {keys[i]} >= {keys[i+1]}")
        return errors

    def _audit_avl_balance(self) -> list[str]:
        errors = []
        if not self.avl.stress_mode:
            self._check_balance_node(self.avl.root, errors)
        return errors

    def _check_balance_node(self, node, errors):
        if not node:
            return
        bf = node.balance_factor
        if abs(bf) > 1:
            errors.append(f"Nodo {node.key} tiene BF={bf}")
        self._check_balance_node(node.left, errors)
        self._check_balance_node(node.right, errors)

    def _audit_heights(self) -> list[str]:
        errors = []
        self._verify_height(self.avl.root, errors)
        return errors

    def _verify_height(self, node, errors):
        if not node:
            return -1
        left_h = self._verify_height(node.left, errors)
        right_h = self._verify_height(node.right, errors)
        expected = 1 + max(left_h, right_h)
        if node.height != expected:
            errors.append(f"Nodo {node.key}: height={node.height}, esperado={expected}")
        return expected

    def _audit_unique_ids(self) -> list[str]:
        errors = []
        ids = self.avl.get_all_event_ids()
        seen = set()
        for eid in ids:
            if eid in seen:
                errors.append(f"ID duplicado en AVL: {eid}")
            seen.add(eid)
        return errors

    def _audit_index_consistency(self) -> list[str]:
        errors = []
        avl_ids = set(self.avl.get_all_event_ids())
        index_ids = set(self.event_index.keys())
        for eid in avl_ids - index_ids:
            errors.append(f"ID {eid} en AVL pero no en event_index")
        for eid in index_ids - avl_ids:
            errors.append(f"ID {eid} en event_index pero no en AVL")
        return errors

    # --- Modo estrés ---

    def toggle_stress(self) -> dict:
        self.avl.stress_mode = not self.avl.stress_mode
        return {"stress_mode": self.avl.stress_mode}

    def recover_balance(self) -> dict:
        if not self.avl.stress_mode:
            return {"result": "NOT_IN_STRESS", "message": "El árbol no está en modo estrés"}
        cost = self.avl.recover_balance()
        return {"result": "RECOVERED", "cost": cost}
