from datetime import timedelta
from typing import Optional

from backend.models.enums import EventStatus, Priority
from backend.structures.avl_node import AVLNode
from .scenario import Scenario


class ArchiveService:
    """Archiva ramas elegibles del AVL."""

    def __init__(self, scenario: Scenario):
        self.sc = scenario

    def find_eligible_branches(self) -> list[dict]:
        """Encuentra todos los subárboles elegibles para archivo."""
        result = []
        self._find_eligible(self.sc.avl.root, result)
        # Ordenar por tamaño (mayor primero)
        result.sort(key=lambda x: x["count"], reverse=True)
        return result

    def _find_eligible(self, node: Optional[AVLNode], result: list):
        if not node:
            return

        # Verificar si TODO el subárbol con raíz en este nodo es elegible
        ids = []
        if self._is_subtree_eligible(node, ids):
            result.append({
                "root_key": node.key,
                "event_ids": ids,
                "count": len(ids),
            })
        else:
            # Si no, revisar hijos individualmente
            self._find_eligible(node.left, result)
            self._find_eligible(node.right, result)

    def _is_subtree_eligible(self, node: Optional[AVLNode], ids: list) -> bool:
        if not node:
            return True

        event = self.sc.event_index.get(node.event_id)
        if not event:
            return False

        # Prioridad debe ser baja
        if event.priority != Priority.LOW:
            return False

        # Antigüedad mayor a T horas
        age = self.sc.clock - event.occurrence_time
        if age < timedelta(hours=self.sc.T_archive_hours):
            return False

        ids.append(node.event_id)

        # Los hijos también deben ser elegibles
        return (self._is_subtree_eligible(node.left, ids) and
                self._is_subtree_eligible(node.right, ids))

    def archive_branch(self, event_ids: list[int]) -> int:
        """Archiva una lista de eventos. Retorna la cantidad archivada."""
        before = self.sc.snapshot()
        count = 0

        for eid in event_ids:
            event = self.sc.event_index.get(eid)
            if not event:
                continue

            key = event.build_key()
            self.sc.avl.delete(key)
            self.sc.bst.delete(key)
            del self.sc.event_index[eid]

            event.status = EventStatus.ARCHIVED
            self.sc.archived[eid] = event
            count += 1

        self.sc.total_archives += count

        self.sc.undo_stack.push({
            "type": "ARCHIVE",
            "before": before,
            "description": f"Archivar {count} eventos: {event_ids}",
        })

        return count

    def archive_largest_eligible(self) -> dict:
        """Archiva la rama elegible más grande."""
        branches = self.find_eligible_branches()
        if not branches:
            return {"result": "NO_ELIGIBLE", "message": "No hay ramas elegibles"}

        best = branches[0]
        count = self.archive_branch(best["event_ids"])
        return {
            "result": "ARCHIVED",
            "count": count,
            "event_ids": best["event_ids"],
        }
