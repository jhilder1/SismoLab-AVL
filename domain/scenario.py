"""
Scenario — Estado central del simulador.

Contiene el AVL, BST, índice de eventos, archivados, cola, pila, zonas,
estaciones, parámetros y métricas. Toda operación pasa por aquí.
"""

import os
from datetime import datetime, timedelta
from typing import Optional

from domain.models import (
    SeismicEvent, Report, Association, Epicenter, Zone, Station,
    Priority, AttentionState, EventStatus,
)
from domain.storage import scenario_to_dict, apply_state, read_json_file, write_json_file
from domain.loader import load_topology, load_insertions
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

        # Métricas e indicadores (Sección 14)
        self.total_events_created = 0
        self.total_reports_processed = 0
        self.total_corrections = 0
        self.total_archives = 0
        self.total_reports_discarded = 0
        self.total_conflicts = 0
        self.total_confirmations = 0

    def id_exists_anywhere(self, event_id: int) -> bool:
        return (event_id in self.event_index
                or event_id in self.archived
                or event_id in self.deleted_ids)

    def get_event(self, event_id: int) -> Optional[SeismicEvent]:
        return self.event_index.get(event_id)

    def snapshot(self) -> dict:
        """Full independent copy of the state, including the exact tree topology.

        Same format as a saved scenario file (domain/storage.py), so later
        changes to the scenario never alter a snapshot already taken.
        """
        return scenario_to_dict(self)

    def _record(self, action_type: str, before: dict, description: str) -> None:
        """Push one undoable action with the state it must return to."""
        self.undo_stack.push({
            "type": action_type, "before": before, "description": description,
        })

    def summary(self) -> dict:
        """Indicadores visibles (Sección 14) + parámetros vigentes."""
        # Contadores por prioridad y estado de atención
        p_high = 0
        p_med = 0
        p_low = 0
        pending = 0
        reviewed = 0
        costly = 0

        for e in self.event_index.values():
            if e.priority == Priority.HIGH:
                p_high += 1
                depth = self.avl.get_depth(e.build_key())
                if depth is not None and depth > self.L_depth:
                    costly += 1
            elif e.priority == Priority.MEDIUM:
                p_med += 1
            else:
                p_low += 1

            if e.attention_state == AttentionState.PENDING:
                pending += 1
            else:
                reviewed += 1

        return {
            "counts": {
                "active": self.avl.size,
                "archived": len(self.archived),
                "deleted": len(self.deleted_ids),
                "queued_reports": self.report_queue.size(),
                "undo_depth": self.undo_stack.size(),
                "priority_high": p_high,
                "priority_medium": p_med,
                "priority_low": p_low,
                "pending": pending,
                "reviewed": reviewed,
                "costly_access": costly,
            },
            "tree": {
                "height": self.avl.height,
                "leaves": self.avl.count_leaves(),
                "root": str(self.avl.root.key) if self.avl.root else None,
                "balanced": self.avl.is_balanced(),
                "nodes": self.avl.to_dict(),
            },
            "bst": {
                "height": self.bst.height,
                "leaves": self.bst.count_leaves(),
                "root": str(self.bst.root.key) if self.bst.root else None,
                "nodes": self.bst.to_dict(),
            },
            "traversals": {
                "inorder": [str(k) for k in self.avl.inorder()],
                "preorder": [str(k) for k in self.avl.preorder()],
                "postorder": [str(k) for k in self.avl.postorder()],
                "level_order": [str(k) for k in self.avl.level_order()],
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
                "reports_discarded": self.total_reports_discarded,
                "conflicts": self.total_conflicts,
                "confirmations": self.total_confirmations,
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
            "archived_events": [e.to_dict() for e in self.archived.values()],
            "queued_reports": [r.to_dict() for r in self.report_queue.get_all()],
            "zones": [z.to_dict() for z in self.zones],
            "stations": [s.to_dict() for s in self.stations.values()],
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

        self._record("CREATE", before,
            f"Crear evento {event.format_id()} M={event.magnitude}")

        self.recalculate_all_associations()
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

        self._record("CORRECT", before,
            f"Corregir evento {event.format_id()} rev={event.revision}")

        self.recalculate_all_associations()
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

        self.recalculate_all_associations()

        self._record("DELETE", before,
            f"Eliminar evento {event.format_id()}")
        return event

    # --- Marcar revisado ---

    def mark_reviewed(self, event_id: int) -> SeismicEvent:
        event = self.get_event(event_id)
        if not event:
            raise ValueError(f"Evento {event_id} no encontrado entre los activos")
        before = self.snapshot()
        event.attention_state = AttentionState.REVIEWED
        self._record("REVIEW", before,
            f"Marcar revisado {event.format_id()}")
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

        # Caso A: ID eliminado → rechazo total (Sección 6)
        if report.event_id in self.deleted_ids:
            self.total_reports_discarded += 1
            result = {"result": "REJECTED", "event_id": report.event_id,
                      "reason": "Evento eliminado, no se aceptan reportes posteriores"}

        # Caso B: ID archivado (Sección 6: reactivación con rev > vigente)
        elif report.event_id in self.archived:
            archived_event = self.archived[report.event_id]
            if report.revision > archived_event.revision:
                new_epi = Epicenter(report.epicenter.x, report.epicenter.y)
                archived_event.apply_correction(
                    magnitude=report.magnitude, depth_km=report.depth_km,
                    epicenter=new_epi, occurrence_time=report.occurrence_time,
                    zones=self.zones,
                )
                archived_event.status = EventStatus.ACTIVE
                archived_event.attention_state = AttentionState.PENDING
                archived_event.revision = report.revision
                archived_event.reporting_stations.add(report.station_id)
                del self.archived[report.event_id]
                self.event_index[report.event_id] = archived_event
                self.avl.insert(archived_event)
                self.bst.insert(archived_event.build_key())
                self.total_corrections += 1
                self._calculate_association(report.event_id)
                self.recalculate_all_associations()
                result = {"result": "REACTIVATED", "event_id": report.event_id, "revision": report.revision}
            elif report.revision == archived_event.revision:
                same_data = report.data_equals(
                    archived_event.magnitude, archived_event.depth_km,
                    archived_event.epicenter, archived_event.occurrence_time,
                )
                if same_data:
                    archived_event.reporting_stations.add(report.station_id)
                    self.total_confirmations += 1
                    result = {"result": "CONFIRMED_ARCHIVED", "event_id": report.event_id}
                else:
                    self.total_conflicts += 1
                    result = {"result": "CONFLICT", "event_id": report.event_id,
                              "reason": "Misma revisión pero datos diferentes en evento archivado"}
            else:
                self.total_reports_discarded += 1
                result = {"result": "OUTDATED", "event_id": report.event_id,
                          "report_rev": report.revision, "current_rev": archived_event.revision}

        # Caso C: ID activo
        elif event:
            if report.revision > event.revision:
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
                self.recalculate_all_associations()
                result = {"result": "CORRECTED", "event_id": report.event_id, "revision": report.revision}
            elif report.revision == event.revision:
                same_data = report.data_equals(
                    event.magnitude, event.depth_km, event.epicenter, event.occurrence_time,
                )
                if same_data:
                    event.reporting_stations.add(report.station_id)
                    self.total_confirmations += 1
                    result = {"result": "CONFIRMED", "event_id": report.event_id}
                else:
                    self.total_conflicts += 1
                    result = {"result": "CONFLICT", "event_id": report.event_id,
                              "reason": "Misma revisión pero datos diferentes"}
            else:
                self.total_reports_discarded += 1
                result = {"result": "OUTDATED", "event_id": report.event_id,
                          "report_rev": report.revision, "current_rev": event.revision}

        # Caso D: ID nuevo desconocido
        else:
            try:
                new_event = SeismicEvent(
                    event_id=report.event_id, magnitude=report.magnitude,
                    depth_km=report.depth_km,
                    epicenter=Epicenter(report.epicenter.x, report.epicenter.y),
                    occurrence_time=report.occurrence_time,
                    station_id=report.station_id, zones=self.zones,
                    revision=report.revision,
                )
                self.avl.insert(new_event)
                self.bst.insert(new_event.build_key())
                self.event_index[report.event_id] = new_event
                self.total_events_created += 1
                self._calculate_association(report.event_id)
                result = {"result": "CREATED", "event_id": report.event_id}
            except ValueError as e:
                self.total_reports_discarded += 1
                result = {"result": "REJECTED", "reason": str(e)}

        self.total_reports_processed += 1
        self._record("PROCESS_REPORT", before,
            f"Procesar reporte {report.event_id} rev={report.revision} → {result['result']}")
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
        self._record("ARCHIVE", before,
            f"Archivar {count} eventos: {event_ids}")
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

        # The snapshot already holds the queue in its original order, so undoing
        # a queue step puts the report back even when that step discarded it.
        apply_state(self, action["before"])

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
        before = self.snapshot()
        self.avl.stress_mode = not self.avl.stress_mode
        mode = "estrés" if self.avl.stress_mode else "normal"
        self._record("TOGGLE_STRESS", before, f"Cambiar a modo {mode}")
        return {"stress_mode": self.avl.stress_mode}

    def recover_balance(self) -> dict:
        if not self.avl.stress_mode:
            return {"result": "NOT_IN_STRESS", "message": "El árbol no está en modo estrés"}
        before = self.snapshot()
        cost = self.avl.recover_balance()
        self._record("RECOVER", before,
                     f"Recuperación global: altura final {cost['final_height']}")
        return {"result": "RECOVERED", "cost": cost}

    # --- Reloj y parámetros (Sections 3, 7, 9, 10) ---

    def advance_clock(self, hours: float) -> datetime:
        """Move the simulation clock forward; it never goes back (Section 3)."""
        if not hours > 0:
            raise ValueError(f"Las horas a avanzar deben ser positivas, se recibió {hours}")
        before = self.snapshot()
        self.clock += timedelta(hours=hours)
        self._record("ADVANCE_CLOCK", before,
                     f"Avanzar reloj {hours}h hasta {self.clock.isoformat()}")
        return self.clock

    def update_parameters(self, w_hours: Optional[float] = None,
                          r_km: Optional[float] = None,
                          l_depth: Optional[int] = None,
                          t_archive_hours: Optional[float] = None) -> None:
        """Change W, R, L and/or T as one action. Nothing changes if any value is invalid."""
        errors = []
        if w_hours is not None and not w_hours > 0:
            errors.append(f"W debe ser positivo, se recibió {w_hours}")
        if r_km is not None and not r_km > 0:
            errors.append(f"R debe ser positivo, se recibió {r_km}")
        if l_depth is not None and (int(l_depth) != l_depth or l_depth < 0):
            errors.append(f"L debe ser un entero no negativo, se recibió {l_depth}")
        if t_archive_hours is not None and not t_archive_hours > 0:
            errors.append(f"T debe ser positivo, se recibió {t_archive_hours}")
        if errors:
            raise ValueError("; ".join(errors))

        before = self.snapshot()
        if w_hours is not None:
            self.W_hours = float(w_hours)
        if r_km is not None:
            self.R_km = float(r_km)
        if l_depth is not None:
            self.L_depth = int(l_depth)
        if t_archive_hours is not None:
            self.T_archive_hours = float(t_archive_hours)

        # A change of W or R can change associations (Section 7).
        self.recalculate_all_associations()
        self._record("PARAM_UPDATE", before,
                     f"Actualizar parámetros W={self.W_hours}h R={self.R_km}km "
                     f"L={self.L_depth} T={self.T_archive_hours}h")

    # --- Persistence (Section 12) ---

    def save_to_file(self, path: str) -> dict:
        """Structural save: topology, history, queue, clock, parameters, mode, metrics."""
        write_json_file(path, self.snapshot())
        return {"path": path, "active": self.avl.size, "archived": len(self.archived)}

    def load_scenario_file(self, path: str) -> dict:
        """Topology load. Raises StateError with every problem and keeps the state."""
        state, info = load_topology(self, read_json_file(path))
        self._replace_state(state, "LOAD_TOPOLOGY",
                            f"Cargar escenario {os.path.basename(path)}")
        return info

    def load_insertions_file(self, path: str) -> dict:
        """Insertion load into a balanced AVL and a plain BST; returns their comparison."""
        state, comparison = load_insertions(self, read_json_file(path))
        self._replace_state(state, "LOAD_INSERTIONS",
                            f"Cargar {comparison['events']} eventos por inserción "
                            f"desde {os.path.basename(path)}")
        return comparison

    def _replace_state(self, state: dict, action_type: str, description: str) -> None:
        """A load is one undoable action (Section 13)."""
        before = self.snapshot()
        apply_state(self, state)
        self._record(action_type, before, description)

    # ================================================================
    # Consultas y análisis del desempeño (Sección 11)
    # ================================================================

    def query_top_k_pending(self, k: int) -> dict:
        """
        Los primeros k eventos pendientes de atención en orden descendente de K.
        Recorre el árbol en orden inverso (derecha a izquierda) y poda la búsqueda
        al alcanzar k elementos.
        Reporta la cantidad de nodos examinados.
        """
        if k <= 0:
            return {"results": [], "nodes_examined": 0, "k": k, "count": 0}

        results = []
        nodes_examined = 0

        def traverse_reverse(node):
            nonlocal nodes_examined
            if not node or len(results) >= k:
                return
            traverse_reverse(node.right)
            if len(results) >= k:
                return
            nodes_examined += 1
            event = node.event
            if event and event.attention_state == AttentionState.PENDING:
                results.append(event.to_dict())
            if len(results) >= k:
                return
            traverse_reverse(node.left)

        traverse_reverse(self.avl.root)
        return {
            "results": results,
            "nodes_examined": nodes_examined,
            "k": k,
            "count": len(results),
        }

    def query_by_interval(self, min_mag: float, max_mag: float,
                          max_depth: Optional[float] = None,
                          start_date: Optional[datetime] = None,
                          end_date: Optional[datetime] = None) -> dict:
        """
        Eventos dentro de un intervalo inclusivo de magnitud [min_mag, max_mag],
        y eventos con profundidad <= max_depth en intervalo de fechas [start_date, end_date].
        Reporta la cantidad de nodos del AVL examinados.
        """
        matched = []
        nodes_examined = 0

        def traverse(node):
            nonlocal nodes_examined
            if not node:
                return
            nodes_examined += 1
            e = node.event
            if e:
                mag_ok = (min_mag <= e.magnitude <= max_mag)
                depth_ok = (max_depth is None or e.depth_km <= max_depth)
                date_ok = True
                if start_date and e.occurrence_time < start_date:
                    date_ok = False
                if end_date and e.occurrence_time > end_date:
                    date_ok = False

                if mag_ok and depth_ok and date_ok:
                    matched.append(e.to_dict())

            traverse(node.left)
            traverse(node.right)

        traverse(self.avl.root)
        return {
            "results": matched,
            "nodes_examined": nodes_examined,
            "count": len(matched),
        }

    def query_event_associations(self, event_id: int) -> dict:
        """
        Candidatos y referencia elegida para un evento, así como los eventos que
        lo utilizan como referencia. Identifica si cada resultado está activo o archivado.
        """
        event = self.event_index.get(event_id) or self.archived.get(event_id)
        if not event:
            raise ValueError(f"Evento {event_id} no encontrado")

        status_str = "ACTIVO" if event_id in self.event_index else "ARCHIVADO"

        # Candidatos
        raw_candidates = self._find_candidates(event)
        candidates_info = []
        for c in raw_candidates:
            c_status = "ACTIVO" if c.event_id in self.event_index else "ARCHIVADO"
            dist = round(event.epicenter.distance_to(c.epicenter), 1)
            hours = round(abs((event.occurrence_time - c.occurrence_time).total_seconds() / 3600), 1)
            candidates_info.append({
                "event_id": c.event_id,
                "magnitude": c.magnitude,
                "depth_km": c.depth_km,
                "distance_km": dist,
                "time_delta_hours": hours,
                "status": c_status,
            })

        # Referencia elegida
        ref_info = None
        if event.reference_event_id:
            ref_event = self.event_index.get(event.reference_event_id) or self.archived.get(event.reference_event_id)
            if ref_event:
                r_status = "ACTIVO" if ref_event.event_id in self.event_index else "ARCHIVADO"
                ref_info = {
                    "event_id": ref_event.event_id,
                    "magnitude": ref_event.magnitude,
                    "status": r_status,
                }

        # Eventos que usan este evento como referencia (réplicas)
        replicas = []
        all_events = list(self.event_index.values()) + list(self.archived.values())
        for other in all_events:
            if other.reference_event_id == event_id:
                rep_status = "ACTIVO" if other.event_id in self.event_index else "ARCHIVADO"
                replicas.append({
                    "event_id": other.event_id,
                    "magnitude": other.magnitude,
                    "status": rep_status,
                })

        return {
            "event_id": event_id,
            "status": status_str,
            "reference": ref_info,
            "candidates": candidates_info,
            "replicas": replicas,
        }

    def query_costly_high_priority(self) -> dict:
        """
        Eventos de prioridad alta (P=3) con acceso costoso (profundidad > L).
        Indica profundidad del nodo, límite L y número de nodos visitados en su búsqueda por clave.
        """
        results = []
        for e in self.event_index.values():
            if e.priority == Priority.HIGH:
                key = e.build_key()
                node, visited = self.avl.search(key)
                depth = visited - 1 if node else None
                if depth is not None and depth > self.L_depth:
                    results.append({
                        "event_id": e.event_id,
                        "key": str(key),
                        "depth": depth,
                        "limit_L": self.L_depth,
                        "nodes_visited": visited,
                        "event": e.to_dict(),
                    })

        return {
            "limit_L": self.L_depth,
            "costly_events": results,
            "count": len(results),
        }

    def compare_current_trees(self) -> dict:
        """
        Compara las estructuras AVL y BST del escenario actual.
        """
        keys = self.avl.inorder()
        from core.avl_tree import compare_trees
        return compare_trees(keys)

