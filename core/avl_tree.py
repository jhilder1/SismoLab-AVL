"""
AVL tree indexed by the comparison key K = (P, M, I).

AVLNode   — AVL tree node (holds a reference to its event).
AVLTree   — self-balancing AVL tree (rotations, stress mode, recovery).

The rest of the tree family lives in its own modules and is re-exported here
so existing imports (`from core.avl_tree import ...`) keep working:
    core.tree_key      TreeKey
    core.binary_tree   BinaryTree (shared search / traversals / to_dict)
    core.bst_tree      BSTNode, BSTTree
    core.tree_compare  compare_trees
"""

from __future__ import annotations

from typing import Optional

from core.binary_tree import BinaryTree, iter_inorder, iter_preorder
from core.bst_tree import BSTNode, BSTTree
from core.tree_key import TreeKey

__all__ = ["TreeKey", "AVLNode", "AVLTree", "BSTNode", "BSTTree", "compare_trees"]


# =====================================================================
# AVLNode
# =====================================================================

class AVLNode:
    """AVL tree node."""

    __slots__ = ("event", "key", "event_id", "left", "right", "height")

    def __init__(self, event):
        self.event = event
        self.key = event.build_key()
        self.event_id = event.event_id
        self.left: Optional[AVLNode] = None
        self.right: Optional[AVLNode] = None
        self.height: int = 0

    def adopt(self, other: "AVLNode") -> None:
        """Copies the physical content while keeping the node's identity in the tree."""
        self.event = other.event
        self.key = other.key
        self.event_id = other.event_id

    @property
    def balance_factor(self) -> int:
        hl = self.left.height if self.left else -1
        hr = self.right.height if self.right else -1
        return hl - hr

    def update_height(self) -> None:
        hl = self.left.height if self.left else -1
        hr = self.right.height if self.right else -1
        self.height = 1 + max(hl, hr)


# =====================================================================
# AVLTree
# =====================================================================

class AVLTree(BinaryTree):
    """AVL tree that indexes the events by their TreeKey."""

    def __init__(self):
        self.root: Optional[AVLNode] = None
        self.size = 0
        self.stress_mode = False

        self.rotations_ll = 0
        self.rotations_rr = 0
        self.rotations_lr = 0
        self.rotations_rl = 0
        self.simple_turns_left = 0
        self.simple_turns_right = 0

    def get_height(self, node: Optional[AVLNode]) -> int:
        return node.height if node else -1

    def get_balance(self, node: Optional[AVLNode]) -> int:
        return node.balance_factor if node else 0

    @property
    def height(self) -> int:
        return self.get_height(self.root)

    # --- Shared helpers for insert / delete ---

    def _link(self, parent: Optional[AVLNode], direction: Optional[str], node) -> None:
        """Hang `node` under `parent` on `direction`, or make it the root."""
        if parent is None:
            self.root = node
        elif direction == 'left':
            parent.left = node
        else:
            parent.right = node

    def _rebalance_path(self, path: list) -> None:
        """Walk back up the (node, direction) path: update heights and, in
        normal mode, rebalance each node and re-link it to its parent."""
        while path:
            node, _ = path.pop()
            node.update_height()
            if not self.stress_mode:
                node = self._balance(node)
            parent, direction = path[-1] if path else (None, None)
            self._link(parent, direction, node)

    # --- Insertion (iterative) ---

    def insert(self, event) -> None:
        key = event.build_key()
        if not self.root:
            self.root = AVLNode(event)
            self.size += 1
            return

        path = []
        current = self.root
        while current:
            if key < current.key:
                path.append((current, 'left'))
                if current.left is None:
                    current.left = AVLNode(event)
                    self.size += 1
                    break
                current = current.left
            elif key > current.key:
                path.append((current, 'right'))
                if current.right is None:
                    current.right = AVLNode(event)
                    self.size += 1
                    break
                current = current.right
            else:
                return  # Already present

        self._rebalance_path(path)

    # --- Balancing ---

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

    # --- Deletion (iterative) ---

    def delete(self, key: TreeKey) -> None:
        if not self.root:
            return

        path = []
        current = self.root
        while current:
            if key < current.key:
                path.append((current, 'left'))
                current = current.left
            elif key > current.key:
                path.append((current, 'right'))
                current = current.right
            else:
                break

        if not current:
            return

        if not current.left or not current.right:
            sub = current.right if not current.left else current.left
            self.size -= 1
            parent, direction = path[-1] if path else (None, None)
            self._link(parent, direction, sub)
        else:
            path.append((current, 'right'))
            succ_parent = current
            succ = current.right
            succ_path = []
            while succ.left:
                succ_path.append((succ, 'left'))
                succ_parent = succ
                succ = succ.left

            current.adopt(succ)
            self.size -= 1

            if succ_path:
                succ_parent.left = succ.right
            else:
                current.right = succ.right

            path.extend(succ_path)

        self._rebalance_path(path)

    # --- Search helpers ---

    def contains(self, key: TreeKey) -> bool:
        node, _ = self.search(key)
        return node is not None

    def get_depth(self, key: TreeKey) -> Optional[int]:
        node, visited = self.search(key)
        return None if node is None else visited - 1

    # --- Balance recovery (Section 8, iterative) ---

    def recover_balance(self) -> dict:
        before = {
            "ll": self.rotations_ll, "rr": self.rotations_rr,
            "lr": self.rotations_lr, "rl": self.rotations_rl,
            "left": self.simple_turns_left, "right": self.simple_turns_right,
        }

        self._recover_balance_iterative()
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

    def _recover_balance_iterative(self) -> None:
        if not self.root:
            return

        stack = [(self.root, None, None, 0)]
        while stack:
            node, parent, direction, state = stack.pop()
            if not node:
                continue

            if state == 0:
                stack.append((node, parent, direction, 1))
                if node.left:
                    stack.append((node.left, node, 'left', 0))
            elif state == 1:
                stack.append((node, parent, direction, 2))
                if node.right:
                    stack.append((node.right, node, 'right', 0))
            elif state == 2:
                node.update_height()
                changed = False
                while abs(self.get_balance(node)) > 1:
                    node = self._balance(node)
                    changed = True

                if changed:
                    stack.append((node, parent, direction, 0))
                else:
                    self._link(parent, direction, node)

    # --- AVL-specific traversals and queries ---

    def inorder_reverse(self) -> list[TreeKey]:
        result = []
        stack = []
        current = self.root
        while stack or current:
            if current:
                stack.append(current)
                current = current.right
            else:
                current = stack.pop()
                result.append(current.key)
                current = current.left
        return result

    def get_all_event_ids(self) -> list[int]:
        return [node.event_id for node in iter_inorder(self.root)]

    def collect_subtree_ids(self, node: Optional[AVLNode]) -> list[int]:
        return [n.event_id for n in iter_inorder(node)]

    def is_balanced(self) -> bool:
        return all(abs(self.get_balance(node)) <= 1 for node in iter_preorder(self.root))

    # --- Rotation counters ---

    def reset_rotation_counts(self):
        self.rotations_ll = 0
        self.rotations_rr = 0
        self.rotations_lr = 0
        self.rotations_rl = 0

    def total_rotations(self) -> int:
        return self.rotations_ll + self.rotations_rr + self.rotations_lr + self.rotations_rl

    # --- Serialization ---

    def _node_extra(self, node, left: Optional[dict], right: Optional[dict]) -> dict:
        return {"height": node.height, "bf": node.balance_factor}


def compare_trees(keys: list[TreeKey]) -> dict:
    """Kept here for backward compatibility; see core.tree_compare.
    Imported lazily because core.tree_compare itself imports AVLTree."""
    from core.tree_compare import compare_trees as _compare_trees
    return _compare_trees(keys)
