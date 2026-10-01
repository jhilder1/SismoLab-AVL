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
from domain.loader import load_topology, load_insertions, compare_loaded_trees
from domain.validation import check_tree
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
        self.redo_stack = UndoStack()
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
        self.total_archives = 0              # events archived, cumulative
        self.total_archive_operations = 0    # mass-archive operations (Section 14)
        self.total_reports_discarded = 0
        self.total_conflicts = 0
        self.total_confirmations = 0

        # Section 8: the queue is paused while a global recovery is running.
        self._recovery_in_progress = False

    def id_exists_anywhere(self, event_id: int) -> bool:
        return (event_id in self.event_index
                or event_id in self.archived
                or event_id in self.deleted_ids)

    def get_event(self, event_id: int) -> Optional[SeismicEvent]:
        return self.event_index.get(event_id)

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
        def find(event_id):
            return self.event_index.get(event_id) or self.archived.get(event_id)

        def describe(other):
            return {"event_id": other.event_id, "magnitude": other.magnitude,
                    "status": "active" if other.event_id in self.event_index else "archived"}

        reference = find(event.reference_event_id) if event.reference_event_id is not None else None
        assoc = self.associations.get(event.event_id)
        candidates = [describe(c) for c in (find(i) for i in (assoc.candidate_ids if assoc else []))
                      if c is not None]
        replicas = sorted((describe(e) for e in (*self.event_index.values(), *self.archived.values())
                           if e.reference_event_id == event.event_id),
                          key=lambda r: r["event_id"])
        return {"reference": describe(reference) if reference else None,
                "candidates": candidates, "replicas": replicas}

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
        self.redo_stack = UndoStack()

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
                "archive_operations": self.total_archive_operations,
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

        mag_to_check = magnitude if magnitude is not None else event.magnitude
        dep_to_check = depth_km if depth_km is not None else event.depth_km
        ep_x_to_check = epicenter_x if epicenter_x is not None else event.epicenter.x
        ep_y_to_check = epicenter_y if epicenter_y is not None else event.epicenter.y
        time_to_check = occurrence_time if occurrence_time is not None else event.occurrence_time

        errors = SeismicEvent.validate_data(
            event_id, mag_to_check, dep_to_check,
            ep_x_to_check, ep_y_to_check,
            time_to_check, self.clock,
        )
        if errors:
            raise ValueError("; ".join(errors))

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

    def preview_delete(self, event_id: int) -> dict:
        """What deleting an event will do, shown before running it (Section 6).

        Read only. Lists the node's current descendants, which stay active
        (unlike archiving a branch, Section 10), and the events that use it as
        reference, whose association is recalculated after the deletion.
        """
        event = self.get_event(event_id)
        if not event:
            raise ValueError(f"Evento {event_id} no encontrado entre los activos")
        key = event.build_key()
        node, visited = self.avl.search(key)
        descendants = [i for i in self.avl.collect_subtree_ids(node) if i != event_id]
        dependents = sorted(e.event_id for e in list(self.event_index.values())
                            + list(self.archived.values())
                            if e.reference_event_id == event_id)
        return {
            "event": event.to_dict(),
            "key": str(key),
            "depth": visited - 1,
            "descendants": descendants,
            "dependents": dependents,
        }

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
        errors = SeismicEvent.validate_data(
            report.event_id, report.magnitude, report.depth_km,
            report.epicenter.x, report.epicenter.y,
            report.occurrence_time, self.clock,
        )
        if errors:
            raise ValueError("; ".join(errors))
        if report.station_id not in self.stations:
            raise ValueError(f"Estación '{report.station_id}' no existe en el escenario")
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
                self.recalculate_all_associations()
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
        event = self.event_index.get(event_id) or self.archived.get(event_id)
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
        for event_id in list(self.archived.keys()):
            self._calculate_association(event_id)

    # --- Archivo ---

    def find_eligible_branches(self) -> list[dict]:
        # Iterative pre-order search (explicit stack of (node, depth)): only
        # recurses into children when the current subtree is NOT fully
        # eligible, same pruning as the old recursive version. No node
        # revisits its own subtree twice, so it stays O(n) on any tree shape,
        # including a degenerate chain of thousands of nodes.
        result = []
        stack = [(self.avl.root, 0)]
        while stack:
            node, depth = stack.pop()
            if node is None:
                continue
            ids = self._is_subtree_eligible(node)
            if ids is not None:
                result.append({
                    "root_key": node.key,
                    "event_ids": ids,
                    "count": len(ids),
                    "root_depth": depth,
                    "root_id": node.event_id,
                })
            else:
                stack.append((node.right, depth + 1))
                stack.append((node.left, depth + 1))
        # Desempates: 1. Mayor cantidad, 2. Mayor profundidad de raíz, 3. Mayor ID
        result.sort(key=lambda x: (x["count"], x["root_depth"], x["root_id"]), reverse=True)
        return result

    def _is_subtree_eligible(self, node) -> Optional[list]:
        """Pre-order ids of the subtree if every node in it is eligible
        (LOW priority and older than T), else None."""
        ids, _ = self._check_subtree(node)
        return ids

    def _is_event_archivable(self, event: Optional[SeismicEvent]) -> bool:
        """Section 10: LOW priority and age strictly greater than T hours."""
        return (event is not None and event.priority == Priority.LOW
                and self.clock - event.occurrence_time > timedelta(hours=self.T_archive_hours))

    def _check_subtree(self, node) -> tuple[Optional[list], Optional[SeismicEvent]]:
        """(pre-order ids, None) when the whole subtree is eligible, else
        (None, first non-eligible event found). Iterative pre-order walk with
        an early exit at the first non-eligible node, so a degenerate chain of
        any size cannot overflow the stack."""
        if node is None:
            return [], None
        ids = []
        stack = [node]
        while stack:
            current = stack.pop()
            event = self.event_index.get(current.event_id)
            if not self._is_event_archivable(event):
                return None, event
            ids.append(current.event_id)
            if current.right:
                stack.append(current.right)
            if current.left:
                stack.append(current.left)
        return ids, None

    def preview_archive(self) -> dict:
        """What "Archivar rama de eventos antiguos" will do, before doing it
        (Section 10): the branch the rule selects, its ids and count, and why
        it was selected. Read only.

        Also lists the other eligible branches with the reason they lost the
        tie-break, and the LOW-priority roots that are not eligible because a
        descendant fails the rule (Section 16 asks to show that case).
        """
        branches = [self._describe_branch(b) for b in self.find_eligible_branches()]
        criteria = (f"Elegible: todos los eventos del subárbol con prioridad BAJA y antigüedad "
                    f"mayor que T = {self.T_archive_hours:g} h (reloj {self.clock.isoformat()}). "
                    f"Desempate: más nodos, luego raíz más profunda, luego mayor ID de la raíz.")
        rejected = self._rejected_low_roots()
        if not branches:
            return {"selected": None, "others": [], "rejected_low_roots": rejected,
                    "criteria": criteria,
                    "justification": ["No hay ramas elegibles: no se archivará nada."]}

        best, others = branches[0], branches[1:]
        justification = [
            f"Sus {best['count']} eventos tienen prioridad BAJA y antigüedad mayor que "
            f"T = {self.T_archive_hours:g} h (el más reciente tiene {best['youngest_age_hours']:g} h).",
        ]
        if not others:
            justification.append("Es la única rama elegible.")
        else:
            runner_up = others[0]
            if best["count"] > runner_up["count"]:
                justification.append(f"Es la de más nodos ({best['count']} frente a "
                                     f"{runner_up['count']} de la siguiente).")
            elif best["root_depth"] > runner_up["root_depth"]:
                justification.append(f"Empata en nodos con la siguiente y su raíz es más profunda "
                                     f"({best['root_depth']} frente a {runner_up['root_depth']}).")
            else:
                justification.append(f"Empata en nodos y profundidad con la siguiente y su raíz "
                                     f"tiene mayor ID ({best['root_id']} frente a {runner_up['root_id']}).")
        justification.append("El conjunto se fija con la topología actual: las rotaciones "
                             "durante el archivo no agregan ni quitan eventos.")
        for other in others:
            other["why_not"] = self._lost_tie_break(best, other)
        return {"selected": best, "others": others, "rejected_low_roots": rejected,
                "criteria": criteria, "justification": justification}

    def _describe_branch(self, branch: dict) -> dict:
        ages = [(self.clock - self.event_index[i].occurrence_time).total_seconds() / 3600
                for i in branch["event_ids"]]
        return {
            "root_id": branch["root_id"],
            "root_key": str(branch["root_key"]),
            "root_depth": branch["root_depth"],
            "count": branch["count"],
            "event_ids": branch["event_ids"],
            "youngest_age_hours": round(min(ages), 1),
        }

    @staticmethod
    def _lost_tie_break(best: dict, other: dict) -> str:
        if other["count"] < best["count"]:
            return f"tiene menos nodos ({other['count']} frente a {best['count']})"
        if other["root_depth"] < best["root_depth"]:
            return (f"empata en nodos y su raíz es menos profunda "
                    f"({other['root_depth']} frente a {best['root_depth']})")
        return (f"empata en nodos y profundidad, y el ID de su raíz es menor "
                f"({other['root_id']} frente a {best['root_id']})")

    def _rejected_low_roots(self) -> list[dict]:
        """Nodes that are LOW and old enough themselves but whose subtree
        holds a non-eligible event. One post-order pass (iterative): the first
        offender of a subtree is the node itself, else its left subtree's,
        else its right subtree's, so the whole scan is O(n)."""
        order, stack = [], [self.avl.root] if self.avl.root else []
        while stack:
            node = stack.pop()
            order.append(node)
            stack.extend(child for child in (node.left, node.right) if child)

        offender: dict[int, Optional[SeismicEvent]] = {}
        rejected = []
        for node in reversed(order):  # every child is handled before its parent
            event = self.event_index.get(node.event_id)
            below = None
            for child in (node.left, node.right):
                if child and offender[child.event_id] is not None:
                    below = offender[child.event_id]
                    break
            if not self._is_event_archivable(event):
                offender[node.event_id] = event
                continue
            offender[node.event_id] = below
            if below is not None:
                if below.priority != Priority.LOW:
                    reason = f"prioridad {below.priority.name}"
                else:
                    age = (self.clock - below.occurrence_time).total_seconds() / 3600
                    reason = f"antigüedad {age:.1f} h, no supera T"
                rejected.append({"root_id": node.event_id, "offender_id": below.event_id,
                                 "reason": reason})
        return rejected

    def archive_branch(self, event_ids: list[int]) -> int:
        """Archive the branch the rule selects, given the ids the user saw in
        the preview. The selection is recomputed on the current topology; any
        other set (a stale preview, an arbitrary list) is refused, so only the
        branch required by Section 10 can ever be archived."""
        branches = self.find_eligible_branches()
        if not branches:
            raise ValueError("No hay ramas elegibles: no se archivó nada")
        best = branches[0]
        if set(event_ids) != set(best["event_ids"]):
            raise ValueError(
                f"Solo se puede archivar la rama que selecciona la regla de la sección 10 "
                f"(raíz {best['root_id']}, {best['count']} eventos). "
                f"Vuelve a consultar la vista previa.")
        return self._archive_ids(best["event_ids"], best["root_id"])

    def _archive_ids(self, event_ids: list[int], root_id: Optional[int] = None) -> int:
        """Move the given active events to the history as one undoable action.
        The set is fixed before the first deletion, so rotations cannot add
        or remove events from it."""
        before = self.snapshot()
        count = 0
        for eid in list(event_ids):
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
        if count:
            self.total_archive_operations += 1
        # Archived events stay candidates (Section 7), so this changes no
        # reference; it keeps the stored associations aligned with the rule.
        self.recalculate_all_associations()
        root = f" (raíz {root_id})" if root_id is not None else ""
        self._record("ARCHIVE", before, f"Archivar {count} eventos{root}: {list(event_ids)}")
        return count

    def archive_largest_eligible(self) -> dict:
        branches = self.find_eligible_branches()
        if not branches:
            return {"result": "NO_ELIGIBLE", "message": "No hay ramas elegibles"}
        best = branches[0]
        count = self._archive_ids(best["event_ids"], best["root_id"])
        return {"result": "ARCHIVED", "count": count, "event_ids": best["event_ids"]}

    # --- Undo ---

    def undo(self) -> dict:
        if self.undo_stack.is_empty():
            return {"result": "EMPTY", "message": "No hay acciones para deshacer"}

        action = self.undo_stack.pop()
        current_state = self.snapshot()
        
        if not hasattr(self, "redo_stack"):
            self.redo_stack = UndoStack()
            
        self.redo_stack.push({
            "type": action["type"],
            "before": current_state,
            "description": action["description"],
        })

        # The snapshot already holds the queue in its original order, so undoing
        # a queue step puts the report back even when that step discarded it.
        apply_state(self, action["before"])

        return {
            "result": "UNDONE",
            "action_type": action["type"],
            "description": action["description"],
        }

    def redo(self) -> dict:
        if not hasattr(self, "redo_stack") or self.redo_stack.is_empty():
            return {"result": "EMPTY", "message": "No hay acciones para rehacer"}

        action = self.redo_stack.pop()
        current_state = self.snapshot()
        
        self.undo_stack.push({
            "type": action["type"],
            "before": current_state,
            "description": action["description"],
        })

        apply_state(self, action["before"])

        return {
            "result": "REDONE",
            "action_type": action["type"],
            "description": action["description"],
        }

    def can_undo(self) -> bool:
        return not self.undo_stack.is_empty()

    # --- Auditoría ---

    def run_audit(self) -> dict:
        """Global consistency check (Section 14).

        Order, heights, unique ids and AVL/event_index consistency are always
        real errors, in both modes: nothing about stress mode can excuse them
        (deferred rotations never touch the BST order or the stored height,
        both kept up to date by every insert/delete regardless of mode).

        Balance factors are recalculated the same way in both modes, with the
        iterative domain.validation.check_tree (order and heights are also
        taken from there, so a single walk of the tree serves everything).
        Their meaning differs by mode, though: in stress mode a factor outside
        {-1, 0, 1} is the deferred-rotation effect the section describes, so
        it is reported separately in `unbalanced_nodes` instead of counting
        against `is_valid`; in normal mode every such factor is still a real
        error, exactly as before. `is_avl` reports whether the tree currently
        has the AVL property, independently of the mode.
        """
        tree_report = check_tree(self.avl)
        errors = list(tree_report["order"]) + list(tree_report["metadata"])
        errors += self._audit_unique_ids()
        errors += self._audit_index_consistency()
        errors += self._audit_associations()

        unbalanced = tree_report["unbalanced"]
        if not self.avl.stress_mode:
            errors += [f"Evento {event_id}: factor de balance {bf} (fuera de {{-1,0,1}})"
                       for event_id, bf in unbalanced]

        return {
            "is_valid": len(errors) == 0,
            "is_avl": len(unbalanced) == 0,
            "errors": errors,
            "nodes_checked": self.avl.size,
            "stress_mode": self.avl.stress_mode,
            "unbalanced_nodes": [{"event_id": event_id, "balance_factor": bf}
                                 for event_id, bf in unbalanced],
        }

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

    def _audit_associations(self) -> list[str]:
        """Check every stored reference against the same four conditions
        _find_candidates applies when an association is (re)computed: the
        referenced event must have strictly greater magnitude, have occurred
        strictly before, within W hours and within R km. These are counted
        as real errors (they affect is_valid), not separate warnings: the
        audit is here to prove the promise of Section 7 (an association
        always reflects the *current* W/R and the *current* set of events),
        so a reference that breaks any of the four rules is exactly the kind
        of silent data corruption an audit exists to catch -- for example a
        stale reference left behind by a code path that changes W, R or the
        event set without calling recalculate_all_associations. If every
        such path does call it correctly, this audit finds nothing, which is
        also how it was verified: recalculate_all_associations is what is
        expected to keep the graph clean after every change Section 7 lists
        (create, correct, delete, archive, parameter update).

        Also checks the reference graph for cycles. Every valid reference
        points strictly backward in time, so a cycle cannot form between
        references that all individually pass the checks above -- but the
        graph is checked anyway, independently of those checks, in case a
        loaded file or a future code path ties two events together without
        going through _calculate_association at all.
        """
        errors = []
        all_events: dict[int, SeismicEvent] = {}
        all_events.update(self.event_index)
        all_events.update(self.archived)

        for event_id, event in all_events.items():
            ref_id = event.reference_event_id
            if ref_id is None:
                continue
            origin = "archivado" if event_id in self.archived else "activo"
            ref = all_events.get(ref_id)
            if ref is None:
                errors.append(f"Evento {origin} {event_id} referencia a ID "
                              f"inexistente/eliminado: {ref_id}")
                continue
            if ref.magnitude <= event.magnitude:
                errors.append(
                    f"Evento {origin} {event_id} (M={event.magnitude}) referencia a "
                    f"{ref_id} (M={ref.magnitude}): la referencia no tiene magnitud mayor")
            if ref.occurrence_time >= event.occurrence_time:
                errors.append(
                    f"Evento {origin} {event_id} referencia a {ref_id}, que no ocurrió "
                    f"estrictamente antes")
            else:
                delta = event.occurrence_time - ref.occurrence_time
                if delta > timedelta(hours=self.W_hours):
                    errors.append(
                        f"Evento {origin} {event_id} referencia a {ref_id} fuera de la "
                        f"ventana W={self.W_hours}h (diferencia real: {delta})")
            dist = event.epicenter.distance_to(ref.epicenter)
            if dist > self.R_km:
                errors.append(
                    f"Evento {origin} {event_id} referencia a {ref_id} a distancia "
                    f"{dist:.2f}km, fuera de R={self.R_km}km")

        errors += self._audit_association_cycles(all_events)
        return errors

    def _audit_association_cycles(self, all_events: dict[int, SeismicEvent]) -> list[str]:
        """Cycle detection over the reference graph (each event has at most
        one outgoing reference_event_id, so this is a functional graph: one
        pass with a 3-color mark, O(n) total, no recursion)."""
        errors = []
        UNVISITED, IN_PATH, DONE = 0, 1, 2
        state = {eid: UNVISITED for eid in all_events}

        for start_id in all_events:
            if state[start_id] != UNVISITED:
                continue
            path = []
            current = start_id
            while current is not None and state.get(current) == UNVISITED:
                state[current] = IN_PATH
                path.append(current)
                event = all_events.get(current)
                current = event.reference_event_id if event else None

            if current is not None and state.get(current) == IN_PATH:
                cycle = path[path.index(current):] + [current]
                errors.append("Ciclo de referencias: "
                              + " -> ".join(str(c) for c in cycle))

            for node in path:
                state[node] = DONE

        return errors

    # --- Modo estrés ---

    def _run_recovery(self) -> dict:
        """Rebalance the AVL, with the report queue paused meanwhile (Section 8).

        core.avl_tree.AVLTree.recover_balance always turns its own
        stress_mode off as part of rebalancing; the two callers below
        restore it afterwards when the scenario's declared mode should not
        change by itself (see recover_balance and toggle_stress).

        The engine is single-threaded and synchronous (Section 8 does not
        require threads), so no report can actually be dequeued while this
        call is on the stack. The flag is still real, not decorative: it is
        what process_next_report checks, so a recovery started from inside
        report processing (or a future asynchronous caller) is guarded too,
        not just this call's immediate synchronous extent.
        """
        self._recovery_in_progress = True
        try:
            return self.avl.recover_balance()
        finally:
            self._recovery_in_progress = False

    def toggle_stress(self) -> dict:
        """Enter or leave stress mode (Section 8).

        Entering is unconditional: deferred balancing can start at any time.
        Leaving runs a global recovery first and only completes when the
        audit that follows confirms the tree is an AVL again ("El retorno al
        modo normal solo se completa cuando la auditoría confirma el
        equilibrio"). If the audit still finds a problem, stress mode stays
        on, the attempted recovery is rolled back and nothing is recorded.
        """
        if not self.avl.stress_mode:
            before = self.snapshot()
            self.avl.stress_mode = True
            self._record("TOGGLE_STRESS", before, "Entrar en modo estrés")
            return {"stress_mode": True, "message": "Modo estrés activado"}

        before = self.snapshot()
        cost = self._run_recovery()          # also turns avl.stress_mode off
        audit = self.run_audit()             # mode is already normal: balance counts as error
        if not audit["is_valid"]:
            apply_state(self, before)        # undo the attempt: tree and stress mode as they were
            return {
                "stress_mode": True,
                "message": "La auditoría no confirma el equilibrio: el árbol sigue en modo estrés",
                "errors": audit["errors"],
            }

        self._record("TOGGLE_STRESS", before,
                     f"Salir de modo estrés: recuperación global, altura final {cost['final_height']}")
        return {"stress_mode": False, "message": "Modo normal: la auditoría confirma el equilibrio",
                "cost": cost}

    def recover_balance(self) -> dict:
        """Global recovery (Section 8): can run in either mode.

        Rebalancing the structure is independent of the mode switch itself,
        which only toggle_stress decides, with its audit gate: the mode is
        restored to whatever it was before this call, so running this while
        in stress mode fixes the tree without granting an unaudited exit. In
        normal mode the tree should already be an AVL, so a call that finds
        nothing to rotate is not recorded as an action (same reasoning as
        save_version: nothing changed, so there is nothing to undo); if it
        were unbalanced anyway, it gets repaired the same way.
        """
        stress_before = self.avl.stress_mode
        before = self.snapshot()
        cost = self._run_recovery()
        self.avl.stress_mode = stress_before

        rotated = any(cost[k] for k in ("ll", "rr", "lr", "rl"))
        if not rotated:
            message = "El árbol ya cumplía la propiedad AVL: no hubo rotaciones que aplicar"
            return {"result": "ALREADY_BALANCED", "message": message,
                    "cost": cost, "stress_mode": self.avl.stress_mode}

        message = f"Recuperación global aplicada: altura final {cost['final_height']}"
        self._record("RECOVER", before, message)
        return {"result": "RECOVERED", "message": message,
                "cost": cost, "stress_mode": self.avl.stress_mode}

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

    # --- Named versions (Section 13) ---

    def save_version(self, store, name: str) -> dict:
        """Store the current operational state under a name. Not an action:
        the scenario does not change, so there is nothing to undo."""
        return store.save(name, self.snapshot())

    def restore_version(self, store, version_id: str) -> dict:
        """Replace the state with a saved version as one undoable action.

        The stored state is validated like a topology file, so an edited or
        damaged version raises StateError and the scenario stays untouched.
        """
        name, stored = store.load_state(version_id)
        state, info = load_topology(self, stored)
        self._replace_state(state, "RESTORE_VERSION", f"Restaurar versión '{name}'")
        return {"name": name, **info}

    def _replace_state(self, state: dict, action_type: str, description: str) -> None:
        """A load or a version restore is one undoable action (Section 13)."""
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

        Iterative reverse in-order walk (explicit stack: push the right spine,
        pop, then descend left), so a degenerate tree of any size cannot
        overflow the recursion stack. The pruning happens at the same point as
        the old recursive version: a node is only counted once its whole right
        subtree has been explored, and the walk stops the instant results
        reach k, so nodes_examined matches the recursive version exactly.
        """
        if k <= 0:
            return {"results": [], "nodes_examined": 0, "k": k, "count": 0}

        results = []
        nodes_examined = 0
        stack = []
        node = self.avl.root
        while (stack or node) and len(results) < k:
            while node:
                stack.append(node)
                node = node.right
            node = stack.pop()
            nodes_examined += 1
            event = node.event
            if event and event.attention_state == AttentionState.PENDING:
                results.append(event.to_dict())
            if len(results) >= k:
                break
            node = node.left

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

        # Iterative pre-order walk (explicit stack): visits every node exactly
        # once, so a degenerate tree of any size cannot overflow the stack.
        stack = [self.avl.root] if self.avl.root else []
        while stack:
            node = stack.pop()
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

            if node.right:
                stack.append(node.right)
            if node.left:
                stack.append(node.left)

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
            "nodes_examined": len(self.event_index) + len(self.archived),
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
        """Compare the scenario's own AVL and BST (Sections 11 and 15).

        Both trees hold the same keys and received the same operations in the
        same order, so they are compared as they are. Rebuilding them from the
        sorted keys would always describe the worst-case BST (a chain), not
        the one the user sees in the BST tab.
        """
        comparison = compare_loaded_trees(self)
        comparison["size"] = comparison["events"]
        return comparison

