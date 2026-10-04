"""
Archive — moving whole branches of old low-priority events to the history
(Section 10).

A branch (a subtree of the AVL) is eligible when every event in it has LOW
priority and is older than T hours. The rule picks the eligible branch with
more nodes, then the deeper root, then the larger root id. The preview shows
that choice and why, and `archive_branch` only accepts that exact branch.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Optional

from domain.models import EventStatus, Priority, SeismicEvent


class ArchiveMixin:
    """Eligible branches, archive preview and the archive operation."""

    # ================================================================
    # Eligibility
    # ================================================================

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
        # Tie-break: 1. more nodes, 2. deeper root, 3. larger root id
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

    # ================================================================
    # Preview (read only)
    # ================================================================

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
        for other in others:
            other["why_not"] = self._lost_tie_break(best, other)
        return {"selected": best, "others": others, "rejected_low_roots": rejected,
                "criteria": criteria, "justification": self._justify_selection(best, others)}

    def _justify_selection(self, best: dict, others: list[dict]) -> list[str]:
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
        return justification

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

    # ================================================================
    # Archive operations
    # ================================================================

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

    def archive_largest_eligible(self) -> dict:
        branches = self.find_eligible_branches()
        if not branches:
            return {"result": "NO_ELIGIBLE", "message": "No hay ramas elegibles"}
        best = branches[0]
        count = self._archive_ids(best["event_ids"], best["root_id"])
        return {"result": "ARCHIVED", "count": count, "event_ids": best["event_ids"]}

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
            self._unindex_active(event)
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
