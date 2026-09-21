"""
Árbol AVL, BST y clave de comparación K = (P, M, I).

TreeKey   — tupla (prioridad, magnitud, id) con comparación lexicográfica.
AVLNode   — nodo del árbol AVL (guarda referencia al evento).
AVLTree   — árbol AVL auto-balanceado (rotaciones, modo estrés, recuperación).
BSTNode   — nodo del BST simple (solo clave).
BSTTree   — BST sin balanceo (para comparación con AVL).
"""

from __future__ import annotations
import math
from typing import Optional


# =====================================================================
# TreeKey
# =====================================================================

class TreeKey:
    """Clave K = (P, M, I) con comparación lexicográfica."""

    __slots__ = ("priority", "magnitude", "event_id")

    def __init__(self, priority: int, magnitude: float, event_id: int) -> None:
        self.priority: int = priority
        self.magnitude: float = round(magnitude, 1)
        self.event_id: int = event_id

    def to_tuple(self) -> tuple[int, float, int]:
        return (self.priority, self.magnitude, self.event_id)

    # --- Comparación ---
    def __lt__(self, other: "TreeKey") -> bool:
        if not isinstance(other, TreeKey):
            return NotImplemented
        return self.to_tuple() < other.to_tuple()

    def __le__(self, other: "TreeKey") -> bool:
        if not isinstance(other, TreeKey):
            return NotImplemented
        return self.to_tuple() <= other.to_tuple()

    def __gt__(self, other: "TreeKey") -> bool:
        if not isinstance(other, TreeKey):
            return NotImplemented
        return self.to_tuple() > other.to_tuple()

    def __ge__(self, other: "TreeKey") -> bool:
        if not isinstance(other, TreeKey):
            return NotImplemented
        return self.to_tuple() >= other.to_tuple()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TreeKey):
            return NotImplemented
        return self.to_tuple() == other.to_tuple()

    def __ne__(self, other: object) -> bool:
        if not isinstance(other, TreeKey):
            return NotImplemented
        return self.to_tuple() != other.to_tuple()

    def __hash__(self) -> int:
        return hash(self.to_tuple())

    # --- Display ---
    def __repr__(self) -> str:
        return f"TreeKey(P={self.priority}, M={self.magnitude}, I={self.event_id})"

    def __str__(self) -> str:
        return f"({self.priority}, {self.magnitude}, {self.event_id})"

    # --- Serialización ---
    def to_dict(self) -> dict:
        return {"priority": self.priority, "magnitude": self.magnitude, "event_id": self.event_id}

    def to_list(self) -> list:
        return [self.priority, self.magnitude, self.event_id]

    @classmethod
    def from_dict(cls, data: dict) -> "TreeKey":
        return cls(priority=data["priority"], magnitude=data["magnitude"], event_id=data["event_id"])

    @classmethod
    def from_list(cls, data: list) -> "TreeKey":
        return cls(priority=data[0], magnitude=data[1], event_id=data[2])


# =====================================================================
# AVLNode
# =====================================================================

class AVLNode:
    """Nodo del árbol AVL. Guarda una REFERENCIA al evento, nunca una copia."""

    __slots__ = ("key", "event", "event_id", "left", "right", "height")

    def __init__(self, event) -> None:
        self.event = event
        self.event_id: int = event.event_id
        self.key: TreeKey = event.build_key()
        self.left: Optional[AVLNode] = None
        self.right: Optional[AVLNode] = None
        self.height: int = 0

    @property
    def balance_factor(self) -> int:
        left_h = self.left.height if self.left else -1
        right_h = self.right.height if self.right else -1
        return left_h - right_h

    def update_height(self) -> None:
        left_h = self.left.height if self.left else -1
        right_h = self.right.height if self.right else -1
        self.height = 1 + max(left_h, right_h)

    def adopt(self, other: "AVLNode") -> None:
        """Copia payload de otro nodo (usado en eliminación con dos hijos)."""
        self.key = other.key
        self.event = other.event
        self.event_id = other.event_id

    def __repr__(self) -> str:
        return f"AVLNode(key={self.key}, h={self.height})"


# =====================================================================
# AVLTree
# =====================================================================

class AVLTree:
    """Árbol AVL auto-balanceado con modo estrés y recuperación global."""

    def __init__(self) -> None:
        self.root: Optional[AVLNode] = None
        self.size = 0
        self.stress_mode = False

        # Contadores de rotación (Sección 14)
        self.rotations_ll = 0
        self.rotations_rr = 0
        self.rotations_lr = 0
        self.rotations_rl = 0
        self.simple_turns_left = 0
        self.simple_turns_right = 0

    # --- Altura y balance ---

    def get_height(self, node: Optional[AVLNode]) -> int:
        return node.height if node else -1

    def get_balance(self, node: Optional[AVLNode]) -> int:
        return node.balance_factor if node else 0

    @property
    def height(self) -> int:
        return self.get_height(self.root)

    # --- Inserción ---

    def insert(self, event) -> None:
        self.root = self._insert(self.root, event, event.build_key())

    def _insert(self, node: Optional[AVLNode], event, key: TreeKey) -> AVLNode:
        if not node:
            self.size += 1
            return AVLNode(event)

        if key < node.key:
            node.left = self._insert(node.left, event, key)
        elif key > node.key:
            node.right = self._insert(node.right, event, key)
        else:
            return node

        node.update_height()
        if self.stress_mode:
            return node
        return self._balance(node)

    # --- Balanceo ---

    def _balance(self, node: AVLNode) -> AVLNode:
        balance = self.get_balance(node)

        if balance > 1:
            if self.get_balance(node.left) >= 0:
                self.rotations_ll += 1
                return self._rotate_right(node)
            self.rotations_lr += 1
            node.left = self._rotate_left(node.left)
            return self._rotate_right(node)

        if balance < -1:
            if self.get_balance(node.right) <= 0:
                self.rotations_rr += 1
                return self._rotate_left(node)
            self.rotations_rl += 1
            node.right = self._rotate_right(node.right)
            return self._rotate_left(node)

        return node

    def _rotate_right(self, y: AVLNode) -> AVLNode:
        self.simple_turns_right += 1
        x = y.left
        t2 = x.right
        x.right = y
        y.left = t2
        y.update_height()
        x.update_height()
        return x

    def _rotate_left(self, x: AVLNode) -> AVLNode:
        self.simple_turns_left += 1
        y = x.right
        t2 = y.left
        y.left = x
        x.right = t2
        x.update_height()
        y.update_height()
        return y

    # --- Eliminación ---

    def delete(self, key: TreeKey) -> None:
        self.root = self._delete(self.root, key)

    def _delete(self, node: Optional[AVLNode], key: TreeKey) -> Optional[AVLNode]:
        if not node:
            return None

        if key < node.key:
            node.left = self._delete(node.left, key)
        elif key > node.key:
            node.right = self._delete(node.right, key)
        else:
            if not node.left:
                self.size -= 1
                return node.right
            if not node.right:
                self.size -= 1
                return node.left
            successor = self._get_min_value_node(node.right)
            node.adopt(successor)
            node.right = self._delete(node.right, successor.key)

        node.update_height()
        if self.stress_mode:
            return node
        return self._balance(node)

    def _get_min_value_node(self, node: AVLNode) -> AVLNode:
        current = node
        while current.left is not None:
            current = current.left
        return current

    # --- Búsqueda ---

    def search(self, key: TreeKey) -> tuple[Optional[AVLNode], int]:
        """Retorna (nodo, nodos_visitados). Costo = profundidad + 1."""
        current = self.root
        visited = 0
        while current is not None:
            visited += 1
            if key == current.key:
                return current, visited
            current = current.left if key < current.key else current.right
        return None, visited

    def contains(self, key: TreeKey) -> bool:
        node, _ = self.search(key)
        return node is not None

    def get_depth(self, key: TreeKey) -> Optional[int]:
        node, visited = self.search(key)
        return None if node is None else visited - 1

    # --- Recuperación de balance (Sección 8) ---

    def recover_balance(self) -> dict:
        before = {
            "ll": self.rotations_ll, "rr": self.rotations_rr,
            "lr": self.rotations_lr, "rl": self.rotations_rl,
            "left": self.simple_turns_left, "right": self.simple_turns_right,
        }
        self.root = self._recover_balance_recursive(self.root)
        self.stress_mode = False
        return {
            "ll": self.rotations_ll - before["ll"],
            "rr": self.rotations_rr - before["rr"],
            "lr": self.rotations_lr - before["lr"],
            "rl": self.rotations_rl - before["rl"],
            "simple_turns_left": self.simple_turns_left - before["left"],
            "simple_turns_right": self.simple_turns_right - before["right"],
            "final_height": self.height,
        }

    def _recover_balance_recursive(self, node: Optional[AVLNode]) -> Optional[AVLNode]:
        if not node:
            return None
        node.left = self._recover_balance_recursive(node.left)
        node.right = self._recover_balance_recursive(node.right)
        node.update_height()
        while abs(self.get_balance(node)) > 1:
            node = self._balance(node)
            node.left = self._recover_balance_recursive(node.left)
            node.right = self._recover_balance_recursive(node.right)
            node.update_height()
        return node

    # --- Recorridos ---

    def inorder(self) -> list[TreeKey]:
        result = []
        self._inorder(self.root, result)
        return result

    def _inorder(self, node: Optional[AVLNode], result: list):
        if not node:
            return
        self._inorder(node.left, result)
        result.append(node.key)
        self._inorder(node.right, result)

    def inorder_reverse(self) -> list[TreeKey]:
        result = []
        self._inorder_reverse(self.root, result)
        return result

    def _inorder_reverse(self, node: Optional[AVLNode], result: list):
        if not node:
            return
        self._inorder_reverse(node.right, result)
        result.append(node.key)
        self._inorder_reverse(node.left, result)

    def preorder(self) -> list[TreeKey]:
        result = []
        self._preorder(self.root, result)
        return result

    def _preorder(self, node: Optional[AVLNode], result: list):
        if not node:
            return
        result.append(node.key)
        self._preorder(node.left, result)
        self._preorder(node.right, result)

    def postorder(self) -> list[TreeKey]:
        result = []
        self._postorder(self.root, result)
        return result

    def _postorder(self, node: Optional[AVLNode], result: list):
        if not node:
            return
        self._postorder(node.left, result)
        self._postorder(node.right, result)
        result.append(node.key)

    def level_order(self) -> list[TreeKey]:
        if not self.root:
            return []
        result = []
        queue = [self.root]
        while queue:
            current = queue.pop(0)
            result.append(current.key)
            if current.left:
                queue.append(current.left)
            if current.right:
                queue.append(current.right)
        return result

    def get_all_event_ids(self) -> list[int]:
        result = []
        self._collect_ids(self.root, result)
        return result

    def _collect_ids(self, node: Optional[AVLNode], result: list):
        if not node:
            return
        self._collect_ids(node.left, result)
        result.append(node.event_id)
        self._collect_ids(node.right, result)

    def collect_subtree_ids(self, node: Optional[AVLNode]) -> list[int]:
        result = []
        self._collect_ids(node, result)
        return result

    def is_balanced(self) -> bool:
        return self._check_balanced(self.root)

    def _check_balanced(self, node: Optional[AVLNode]) -> bool:
        if not node:
            return True
        if abs(self.get_balance(node)) > 1:
            return False
        return self._check_balanced(node.left) and self._check_balanced(node.right)

    def reset_rotation_counts(self):
        self.rotations_ll = 0
        self.rotations_rr = 0
        self.rotations_lr = 0
        self.rotations_rl = 0

    def total_rotations(self) -> int:
        return self.rotations_ll + self.rotations_rr + self.rotations_lr + self.rotations_rl

    def count_leaves(self) -> int:
        return self._count_leaves(self.root)

    def _count_leaves(self, node) -> int:
        if not node:
            return 0
        if not node.left and not node.right:
            return 1
        return self._count_leaves(node.left) + self._count_leaves(node.right)

    def to_dict(self) -> dict:
        """Serializa el árbol completo a JSON (para dibujar en el front)."""
        return self._node_to_dict(self.root)

    def _node_to_dict(self, node: Optional[AVLNode]) -> Optional[dict]:
        if not node:
            return None
        return {
            "key": str(node.key),
            "event_id": node.event_id,
            "priority": node.key.priority,
            "magnitude": node.key.magnitude,
            "height": node.height,
            "bf": node.balance_factor,
            "left": self._node_to_dict(node.left),
            "right": self._node_to_dict(node.right),
        }


# =====================================================================
# BSTNode
# =====================================================================

class BSTNode:
    """Nodo de BST simple (solo clave, sin balanceo)."""

    def __init__(self, key: TreeKey):
        self.key = key
        self.event_id = key.event_id
        self.left: Optional[BSTNode] = None
        self.right: Optional[BSTNode] = None


# =====================================================================
# BSTTree
# =====================================================================

class BSTTree:
    """BST sin balanceo (para comparación con AVL)."""

    def __init__(self):
        self.root: Optional[BSTNode] = None
        self.size = 0

    def get_height(self, node: Optional[BSTNode]) -> int:
        if not node:
            return -1
        return 1 + max(self.get_height(node.left), self.get_height(node.right))

    @property
    def height(self) -> int:
        return self.get_height(self.root)

    def count_leaves(self) -> int:
        return self._count_leaves(self.root)

    def _count_leaves(self, node: Optional[BSTNode]) -> int:
        if not node:
            return 0
        if not node.left and not node.right:
            return 1
        return self._count_leaves(node.left) + self._count_leaves(node.right)

    def insert(self, key: TreeKey):
        self.root = self._insert(self.root, key)

    def _insert(self, node: Optional[BSTNode], key: TreeKey) -> BSTNode:
        if not node:
            self.size += 1
            return BSTNode(key)
        if key < node.key:
            node.left = self._insert(node.left, key)
        elif key > node.key:
            node.right = self._insert(node.right, key)
        return node

    def delete(self, key: TreeKey):
        self.root = self._delete(self.root, key)

    def _delete(self, node: Optional[BSTNode], key: TreeKey) -> Optional[BSTNode]:
        if not node:
            return node
        if key < node.key:
            node.left = self._delete(node.left, key)
        elif key > node.key:
            node.right = self._delete(node.right, key)
        else:
            if not node.left:
                self.size -= 1
                return node.right
            elif not node.right:
                self.size -= 1
                return node.left
            temp = self._get_min_value_node(node.right)
            node.key = temp.key
            node.event_id = temp.event_id
            node.right = self._delete(node.right, temp.key)
        return node

    def _get_min_value_node(self, node: BSTNode) -> BSTNode:
        current = node
        while current.left is not None:
            current = current.left
        return current

    def search(self, key: TreeKey) -> tuple[Optional[BSTNode], int]:
        """Busca en el BST. Retorna (nodo, comparaciones)."""
        current = self.root
        visited = 0
        while current is not None:
            visited += 1
            if key == current.key:
                return current, visited
            current = current.left if key < current.key else current.right
        return None, visited

    def inorder(self) -> list[TreeKey]:
        result = []
        self._inorder(self.root, result)
        return result

    def _inorder(self, node: Optional[BSTNode], result: list):
        if not node:
            return
        self._inorder(node.left, result)
        result.append(node.key)
        self._inorder(node.right, result)

    def preorder(self) -> list[TreeKey]:
        result = []
        self._preorder(self.root, result)
        return result

    def _preorder(self, node: Optional[BSTNode], result: list):
        if not node:
            return
        result.append(node.key)
        self._preorder(node.left, result)
        self._preorder(node.right, result)

    def postorder(self) -> list[TreeKey]:
        result = []
        self._postorder(self.root, result)
        return result

    def _postorder(self, node: Optional[BSTNode], result: list):
        if not node:
            return
        self._postorder(node.left, result)
        self._postorder(node.right, result)
        result.append(node.key)

    def level_order(self) -> list[TreeKey]:
        if not self.root:
            return []
        result = []
        queue = [self.root]
        while queue:
            current = queue.pop(0)
            result.append(current.key)
            if current.left:
                queue.append(current.left)
            if current.right:
                queue.append(current.right)
        return result

    def to_dict(self) -> Optional[dict]:
        return self._node_to_dict(self.root)

    def _node_to_dict(self, node: Optional[BSTNode]) -> Optional[dict]:
        if not node:
            return None
        return {
            "key": str(node.key),
            "event_id": node.event_id,
            "priority": node.key.priority,
            "magnitude": node.key.magnitude,
            "height": self.get_height(node),
            "left": self._node_to_dict(node.left),
            "right": self._node_to_dict(node.right),
        }


# =====================================================================
# Comparativa AVL vs BST (Sección 11 y 15)
# =====================================================================

class _DummyEvent:
    def __init__(self, key: TreeKey):
        self.key = key
        self.event_id = key.event_id
        self.priority = key.priority
        self.magnitude = key.magnitude

    def build_key(self) -> TreeKey:
        return self.key


def compare_trees(keys: list[TreeKey]) -> dict:
    """
    Inserta exactamente la misma secuencia de claves en un AVL y en un BST.
    Compara: raíces, alturas, cantidad de hojas y número de comparaciones de búsqueda.
    """
    avl = AVLTree()
    bst = BSTTree()

    for k in keys:
        avl.insert(_DummyEvent(k))
        bst.insert(k)

    # Comparar búsquedas de cada clave
    avl_comps = [avl.search(k)[1] for k in keys]
    bst_comps = [bst.search(k)[1] for k in keys]

    total_keys = len(keys)
    avg_avl_comps = (sum(avl_comps) / total_keys) if total_keys > 0 else 0.0
    avg_bst_comps = (sum(bst_comps) / total_keys) if total_keys > 0 else 0.0

    return {
        "size": total_keys,
        "avl": {
            "root": str(avl.root.key) if avl.root else None,
            "height": avl.height,
            "leaves": avl.count_leaves(),
            "total_comparisons": sum(avl_comps),
            "avg_comparisons": round(avg_avl_comps, 2),
            "tree": avl.to_dict(),
        },
        "bst": {
            "root": str(bst.root.key) if bst.root else None,
            "height": bst.height,
            "leaves": bst.count_leaves(),
            "total_comparisons": sum(bst_comps),
            "avg_comparisons": round(avg_bst_comps, 2),
            "tree": bst.to_dict(),
        },
    }

