from typing import Optional
from .avl_node import AVLNode
from .tree_key import TreeKey

class AVLTree:
    def __init__(self):
        self.root: Optional[AVLNode] = None
        self.size = 0
        
        # Modo estrés: si es True, inserta como BST normal y no balancea.
        self.stress_mode = False
        
        # Métricas de rotaciones
        self.rotations_ll = 0
        self.rotations_rr = 0
        self.rotations_lr = 0
        self.rotations_rl = 0

    def get_height(self, node: Optional[AVLNode]) -> int:
        if not node:
            return -1
        return node.height

    def get_balance(self, node: Optional[AVLNode]) -> int:
        if not node:
            return 0
        return node.balance_factor

    def insert(self, key: TreeKey):
        self.root = self._insert(self.root, key)

    def _insert(self, node: Optional[AVLNode], key: TreeKey) -> AVLNode:
        if not node:
            self.size += 1
            return AVLNode(key)

        if key < node.key:
            node.left = self._insert(node.left, key)
        elif key > node.key:
            node.right = self._insert(node.right, key)
        else:
            return node  # Clave duplicada (no debería pasar por el event_id único)

        node.update_height()

        if self.stress_mode:
            return node

        return self._balance(node)

    def _balance(self, node: AVLNode) -> AVLNode:
        balance = self.get_balance(node)

        # Left Heavy
        if balance > 1:
            if self.get_balance(node.left) >= 0:
                self.rotations_ll += 1
                return self._rotate_right(node)
            else:
                self.rotations_lr += 1
                node.left = self._rotate_left(node.left)
                return self._rotate_right(node)

        # Right Heavy
        if balance < -1:
            if self.get_balance(node.right) <= 0:
                self.rotations_rr += 1
                return self._rotate_left(node)
            else:
                self.rotations_rl += 1
                node.right = self._rotate_right(node.right)
                return self._rotate_left(node)

        return node

    def _rotate_right(self, y: AVLNode) -> AVLNode:
        x = y.left
        T2 = x.right

        x.right = y
        y.left = T2

        y.update_height()
        x.update_height()

        return x

    def _rotate_left(self, x: AVLNode) -> AVLNode:
        y = x.right
        T2 = y.left

        y.left = x
        x.right = T2

        x.update_height()
        y.update_height()

        return y

    def delete(self, key: TreeKey):
        self.root = self._delete(self.root, key)

    def _delete(self, node: Optional[AVLNode], key: TreeKey) -> Optional[AVLNode]:
        if not node:
            return node

        if key < node.key:
            node.left = self._delete(node.left, key)
        elif key > node.key:
            node.right = self._delete(node.right, key)
        else:
            # Nodo con un hijo o sin hijos
            if not node.left:
                self.size -= 1
                return node.right
            elif not node.right:
                self.size -= 1
                return node.left

            # Nodo con dos hijos: buscar sucesor inorden
            temp = self._get_min_value_node(node.right)
            node.key = temp.key
            node.event_id = temp.event_id
            node.right = self._delete(node.right, temp.key)

        if not node:
            return node

        node.update_height()

        if self.stress_mode:
            return node

        return self._balance(node)

    def _get_min_value_node(self, node: AVLNode) -> AVLNode:
        current = node
        while current.left is not None:
            current = current.left
        return current

    def recover_balance(self):
        """Recupera el balance completo tras modo estrés."""
        self.stress_mode = False
        # Repetir pasadas hasta que todo esté balanceado
        while not self.is_balanced():
            self.root = self._recover_pass(self.root)

    def _recover_pass(self, node: Optional[AVLNode]) -> Optional[AVLNode]:
        if not node:
            return None
        
        node.left = self._recover_pass(node.left)
        node.right = self._recover_pass(node.right)
        node.update_height()

        while abs(self.get_balance(node)) > 1:
            node = self._balance(node)
            node.update_height()
            
        return node

    # --- Recorridos y búsquedas ---

    def search(self, key: TreeKey) -> Optional[AVLNode]:
        return self._search(self.root, key)

    def _search(self, node: Optional[AVLNode], key: TreeKey) -> Optional[AVLNode]:
        if not node:
            return None
        if key == node.key:
            return node
        if key < node.key:
            return self._search(node.left, key)
        return self._search(node.right, key)

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

    def get_depth(self, key: TreeKey) -> int:
        return self._get_depth(self.root, key, 0)

    def _get_depth(self, node: Optional[AVLNode], key: TreeKey, depth: int) -> int:
        if not node:
            return -1
        if key == node.key:
            return depth
        if key < node.key:
            return self._get_depth(node.left, key, depth + 1)
        return self._get_depth(node.right, key, depth + 1)

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
