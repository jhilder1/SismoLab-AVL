"""
Audit — global consistency check of the scenario (Section 14).
"""

from __future__ import annotations

from datetime import timedelta

from domain.models import SeismicEvent
from domain.validation import check_tree


class AuditMixin:
    """`run_audit` and the individual checks it combines."""

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

        Every check yields (event_id, problem). `errors` lists the problems;
        `report` groups them by event, one entry per inconsistent event, as
        Section 14 asks ("un reporte por evento inconsistente").
        """
        tree_report = check_tree(self.avl)
        issues = list(tree_report["by_event"])
        issues += self._audit_unique_ids()
        issues += self._audit_index_consistency()
        issues += self._audit_associations()

        unbalanced = tree_report["unbalanced"]
        if not self.avl.stress_mode:
            issues += [(event_id, f"Evento {event_id}: factor de balance {bf} (fuera de {{-1,0,1}})")
                       for event_id, bf in unbalanced]
        errors = [problem for _, problem in issues]

        return {
            "is_valid": len(errors) == 0,
            "is_avl": len(unbalanced) == 0,
            "errors": errors,
            "report": self._audit_report(issues),
            "nodes_checked": self.avl.size,
            "stress_mode": self.avl.stress_mode,
            "unbalanced_nodes": [{"event_id": event_id, "balance_factor": bf}
                                 for event_id, bf in unbalanced],
        }

    def _audit_report(self, issues: list[tuple[int, str]]) -> list[dict]:
        """One entry per inconsistent event, ordered by id, with every problem
        found for it and where the event is (active, archived or deleted)."""
        problems: dict[int, list[str]] = {}
        for event_id, problem in issues:
            problems.setdefault(event_id, []).append(problem)
        return [{"event_id": event_id, "status": self.lookup_event(event_id)["status"],
                 "problems": found}
                for event_id, found in sorted(problems.items())]

    def _audit_unique_ids(self) -> list[tuple[int, str]]:
        errors = []
        seen = set()
        for eid in self.avl.get_all_event_ids():
            if eid in seen:
                errors.append((eid, f"ID duplicado en AVL: {eid}"))
            seen.add(eid)
        return errors

    def _audit_index_consistency(self) -> list[tuple[int, str]]:
        errors = []
        avl_ids = set(self.avl.get_all_event_ids())
        index_ids = set(self.event_index.keys())
        for eid in avl_ids - index_ids:
            errors.append((eid, f"ID {eid} en AVL pero no en event_index"))
        for eid in index_ids - avl_ids:
            errors.append((eid, f"ID {eid} en event_index pero no en AVL"))
        return errors

    def _audit_associations(self) -> list[tuple[int, str]]:
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
                errors.append((event_id, f"Evento {origin} {event_id} referencia a ID "
                                         f"inexistente/eliminado: {ref_id}"))
                continue
            errors += self._audit_one_reference(event_id, event, ref_id, ref, origin)

        errors += self._audit_association_cycles(all_events)
        return errors

    def _audit_one_reference(self, event_id: int, event: SeismicEvent, ref_id: int,
                             ref: SeismicEvent, origin: str) -> list[tuple[int, str]]:
        """The four Section 7 conditions for one existing reference."""
        errors = []
        if ref.magnitude <= event.magnitude:
            errors.append((event_id,
                f"Evento {origin} {event_id} (M={event.magnitude}) referencia a "
                f"{ref_id} (M={ref.magnitude}): la referencia no tiene magnitud mayor"))
        if ref.occurrence_time >= event.occurrence_time:
            errors.append((event_id,
                f"Evento {origin} {event_id} referencia a {ref_id}, que no ocurrió "
                f"estrictamente antes"))
        else:
            delta = event.occurrence_time - ref.occurrence_time
            if delta > timedelta(hours=self.W_hours):
                errors.append((event_id,
                    f"Evento {origin} {event_id} referencia a {ref_id} fuera de la "
                    f"ventana W={self.W_hours}h (diferencia real: {delta})"))
        dist = event.epicenter.distance_to(ref.epicenter)
        if dist > self.R_km:
            errors.append((event_id,
                f"Evento {origin} {event_id} referencia a {ref_id} a distancia "
                f"{dist:.2f}km, fuera de R={self.R_km}km"))
        return errors

    def _audit_association_cycles(self, all_events: dict[int, SeismicEvent]) -> list[tuple[int, str]]:
        """Cycle detection over the reference graph (each event has at most
        one outgoing reference_event_id, so this is a functional graph: one
        pass with a 3-color mark, O(n) total, no recursion). A cycle is
        reported once, under its smallest id."""
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
                errors.append((min(cycle), "Ciclo de referencias: "
                               + " -> ".join(str(c) for c in cycle)))

            for node in path:
                state[node] = DONE

        return errors
