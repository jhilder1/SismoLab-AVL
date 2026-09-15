from backend.structures.avl_node import AVLNode
from .scenario import Scenario


class AuditService:
    """Verifica las invariantes del sistema."""

    def __init__(self, scenario: Scenario):
        self.sc = scenario

    def run_full_audit(self) -> dict:
        errors = []
        errors += self._check_bst_order()
        errors += self._check_avl_balance()
        errors += self._check_heights()
        errors += self._check_unique_ids()
        errors += self._check_index_consistency()

        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "nodes_checked": self.sc.avl.size,
        }

    def _check_bst_order(self) -> list[str]:
        errors = []
        keys = self.sc.avl.inorder()
        for i in range(len(keys) - 1):
            if keys[i] >= keys[i + 1]:
                errors.append(f"Orden BST violado: {keys[i]} >= {keys[i+1]}")
        return errors

    def _check_avl_balance(self) -> list[str]:
        errors = []
        if not self.sc.avl.stress_mode:
            self._check_balance_node(self.sc.avl.root, errors)
        return errors

    def _check_balance_node(self, node, errors):
        if not node:
            return
        bf = node.balance_factor
        if abs(bf) > 1:
            errors.append(f"Nodo {node.key} tiene BF={bf}")
        self._check_balance_node(node.left, errors)
        self._check_balance_node(node.right, errors)

    def _check_heights(self) -> list[str]:
        errors = []
        self._verify_height(self.sc.avl.root, errors)
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

    def _check_unique_ids(self) -> list[str]:
        errors = []
        ids = self.sc.avl.get_all_event_ids()
        seen = set()
        for eid in ids:
            if eid in seen:
                errors.append(f"ID duplicado en AVL: {eid}")
            seen.add(eid)
        return errors

    def _check_index_consistency(self) -> list[str]:
        errors = []
        avl_ids = set(self.sc.avl.get_all_event_ids())
        index_ids = set(self.sc.event_index.keys())

        for eid in avl_ids - index_ids:
            errors.append(f"ID {eid} en AVL pero no en event_index")
        for eid in index_ids - avl_ids:
            errors.append(f"ID {eid} en event_index pero no en AVL")

        return errors
