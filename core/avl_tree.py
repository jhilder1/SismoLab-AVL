"""
AVL tree, BST and the comparison key K = (P, M, I).

TreeKey   — tuple (priority, magnitude, id) compared lexicographically.
AVLNode   — AVL tree node (holds a reference to its event).
AVLTree   — self-balancing AVL tree (rotations, stress mode, recovery).
BSTNode   — plain BST node (key only).
BSTTree   — BST without balancing (to compare with the AVL).
"""

from __future__ import annotations
import math
import collections
from typing import Optional


# =====================================================================
# TreeKey
# =====================================================================

class TreeKey:
    """Key K = (P, M, I) compared lexicographically."""

    __slots__ = ("priority", "magnitude", "event_id")

    def __init__(self, priority: int, magnitude: float, event_id: int) -> None:
        self.priority: int = priority
        self.magnitude: float = round(magnitude, 1)
        self.event_id: int = event_id

    def to_tuple(self) -> tuple[int, float, int]:
        return (self.priority, self.magnitude, self.event_id)

    # --- Comparison ---
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

    def __repr__(self) -> str:
        return f"({self.priority}, {self.magnitude}, {self.event_id})"

    def to_list(self) -> list:
        return [self.priority, self.magnitude, self.event_id]

    @classmethod
    def from_list(cls, data: list) -> "TreeKey":
        return cls(data[0], data[1], data[2])

    def to_dict(self) -> dict:
        return {"priority": self.priority, "magnitude": self.magnitude, "event_id": self.event_id}

    @classmethod
    def from_dict(cls, data: dict) -> "TreeKey":
        return cls(data["priority"], data["magnitude"], data["event_id"])


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

class AVLTree:
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

        # Backtrack
        while path:
            node, _ = path.pop()
            node.update_height()
            if not self.stress_mode:
                node = self._balance(node)
            
            if path:
                parent, direction = path[-1]
                if direction == 'left':
                    parent.left = node
                else:
                    parent.right = node
            else:
                self.root = node

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
            if path:
                parent, direction = path[-1]
                if direction == 'left':
                    parent.left = sub
                else:
                    parent.right = sub
            else:
                self.root = sub
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

        while path:
            node, _ = path.pop()
            node.update_height()
            if not self.stress_mode:
                node = self._balance(node)
                
            if path:
                parent, direction = path[-1]
                if direction == 'left':
                    parent.left = node
                else:
                    parent.right = node
            else:
                self.root = node

    # --- Search ---

    def search(self, key: TreeKey) -> tuple[Optional[AVLNode], int]:
        """Returns (node, nodes_visited). Cost = depth + 1."""
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
                    if parent:
                        if direction == 'left':
                            parent.left = node
                        else:
                            parent.right = node
                    else:
                        self.root = node

    # --- Traversals (iterative) ---

    def inorder(self) -> list[TreeKey]:
        result = []
        stack = []
        current = self.root
        while stack or current:
            if current:
                stack.append(current)
                current = current.left
            else:
                current = stack.pop()
                result.append(current.key)
                current = current.right
        return result

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

    def preorder(self) -> list[TreeKey]:
        if not self.root:
            return []
        result = []
        stack = [self.root]
        while stack:
            current = stack.pop()
            result.append(current.key)
            if current.right:
                stack.append(current.right)
            if current.left:
                stack.append(current.left)
        return result

    def postorder(self) -> list[TreeKey]:
        if not self.root:
            return []
        result = []
        stack = [(self.root, False)]
        while stack:
            current, visited = stack.pop()
            if visited:
                result.append(current.key)
            else:
                stack.append((current, True))
                if current.right:
                    stack.append((current.right, False))
                if current.left:
                    stack.append((current.left, False))
        return result

    def level_order(self) -> list[TreeKey]:
        if not self.root:
            return []
        result = []
        queue = collections.deque([self.root])
        while queue:
            current = queue.popleft()
            result.append(current.key)
            if current.left:
                queue.append(current.left)
            if current.right:
                queue.append(current.right)
        return result

    def get_all_event_ids(self) -> list[int]:
        result = []
        stack = []
        current = self.root
        while stack or current:
            if current:
                stack.append(current)
                current = current.left
            else:
                current = stack.pop()
                result.append(current.event_id)
                current = current.right
        return result

    def collect_subtree_ids(self, node: Optional[AVLNode]) -> list[int]:
        result = []
        stack = []
        current = node
        while stack or current:
            if current:
                stack.append(current)
                current = current.left
            else:
                current = stack.pop()
                result.append(current.event_id)
                current = current.right
        return result

    def is_balanced(self) -> bool:
        if not self.root:
            return True
        stack = [self.root]
        while stack:
            current = stack.pop()
            if abs(self.get_balance(current)) > 1:
                return False
            if current.right:
                stack.append(current.right)
            if current.left:
                stack.append(current.left)
        return True

    def reset_rotation_counts(self):
        self.rotations_ll = 0
        self.rotations_rr = 0
        self.rotations_lr = 0
        self.rotations_rl = 0

    def total_rotations(self) -> int:
        return self.rotations_ll + self.rotations_rr + self.rotations_lr + self.rotations_rl

    def count_leaves(self) -> int:
        if not self.root:
            return 0
        count = 0
        stack = [self.root]
        while stack:
            current = stack.pop()
            if not current.left and not current.right:
                count += 1
            if current.right:
                stack.append(current.right)
            if current.left:
                stack.append(current.left)
        return count

    def to_dict(self) -> Optional[dict]:
        """Serializes the whole tree to JSON (to draw it in the front end)."""
        if not self.root:
            return None
        dicts = {}
        stack = [(self.root, False)]
        while stack:
            current, visited = stack.pop()
            if visited:
                left_dict = dicts.get(id(current.left)) if current.left else None
                right_dict = dicts.get(id(current.right)) if current.right else None
                d = {
                    "key": str(current.key),
                    "event_id": current.event_id,
                    "priority": current.key.priority,
                    "magnitude": current.key.magnitude,
                    "height": current.height,
                    "bf": current.balance_factor,
                    "left": left_dict,
                    "right": right_dict,
                }
                dicts[id(current)] = d
            else:
                stack.append((current, True))
                if current.right:
                    stack.append((current.right, False))
                if current.left:
                    stack.append((current.left, False))
        return dicts[id(self.root)]


# =====================================================================
# BSTNode
# =====================================================================

class BSTNode:
    """Plain BST node (key only, no balancing)."""

    def __init__(self, key: TreeKey):
        self.key = key
        self.event_id = key.event_id
        self.left: Optional[BSTNode] = None
        self.right: Optional[BSTNode] = None


# =====================================================================
# BSTTree
# =====================================================================

class BSTTree:
    """BST without balancing (to compare with the AVL)."""

    def __init__(self):
        self.root: Optional[BSTNode] = None
        self.size = 0

    def get_height(self, node: Optional[BSTNode]) -> int:
        if not node:
            return -1
        heights = {}
        stack = [(node, False)]
        while stack:
            curr, visited = stack.pop()
            if visited:
                left_h = heights.get(id(curr.left), -1) if curr.left else -1
                right_h = heights.get(id(curr.right), -1) if curr.right else -1
                heights[id(curr)] = 1 + max(left_h, right_h)
            else:
                stack.append((curr, True))
                if curr.right:
                    stack.append((curr.right, False))
                if curr.left:
                    stack.append((curr.left, False))
        return heights[id(node)]

    @property
    def height(self) -> int:
        return self.get_height(self.root)

    def count_leaves(self) -> int:
        if not self.root:
            return 0
        count = 0
        stack = [self.root]
        while stack:
            current = stack.pop()
            if not current.left and not current.right:
                count += 1
            if current.right:
                stack.append(current.right)
            if current.left:
                stack.append(current.left)
        return count

    def insert(self, key: TreeKey):
        if not self.root:
            self.root = BSTNode(key)
            self.size += 1
            return
            
        current = self.root
        while current:
            if key < current.key:
                if current.left is None:
                    current.left = BSTNode(key)
                    self.size += 1
                    break
                current = current.left
            elif key > current.key:
                if current.right is None:
                    current.right = BSTNode(key)
                    self.size += 1
                    break
                current = current.right
            else:
                return

    def delete(self, key: TreeKey):
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
            if path:
                parent, direction = path[-1]
                if direction == 'left':
                    parent.left = sub
                else:
                    parent.right = sub
            else:
                self.root = sub
        else:
            succ_parent = current
            succ = current.right
            is_right_child = True
            while succ.left:
                succ_parent = succ
                succ = succ.left
                is_right_child = False
                
            current.key = succ.key
            current.event_id = succ.event_id
            self.size -= 1
            
            if is_right_child:
                succ_parent.right = succ.right
            else:
                succ_parent.left = succ.right

    def search(self, key: TreeKey) -> tuple[Optional[BSTNode], int]:
        """Searches the BST. Returns (node, comparisons)."""
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
        stack = []
        current = self.root
        while stack or current:
            if current:
                stack.append(current)
                current = current.left
            else:
                current = stack.pop()
                result.append(current.key)
                current = current.right
        return result

    def preorder(self) -> list[TreeKey]:
        if not self.root:
            return []
        result = []
        stack = [self.root]
        while stack:
            current = stack.pop()
            result.append(current.key)
            if current.right:
                stack.append(current.right)
            if current.left:
                stack.append(current.left)
        return result

    def postorder(self) -> list[TreeKey]:
        if not self.root:
            return []
        result = []
        stack = [(self.root, False)]
        while stack:
            current, visited = stack.pop()
            if visited:
                result.append(current.key)
            else:
                stack.append((current, True))
                if current.right:
                    stack.append((current.right, False))
                if current.left:
                    stack.append((current.left, False))
        return result

    def level_order(self) -> list[TreeKey]:
        if not self.root:
            return []
        result = []
        queue = collections.deque([self.root])
        while queue:
            current = queue.popleft()
            result.append(current.key)
            if current.left:
                queue.append(current.left)
            if current.right:
                queue.append(current.right)
        return result

    def to_dict(self) -> Optional[dict]:
        if not self.root:
            return None
        dicts = {}
        stack = [(self.root, False)]
        while stack:
            current, visited = stack.pop()
            if visited:
                left_dict = dicts.get(id(current.left)) if current.left else None
                right_dict = dicts.get(id(current.right)) if current.right else None
                d = {
                    "key": str(current.key),
                    "event_id": current.event_id,
                    "priority": current.key.priority,
                    "magnitude": current.key.magnitude,
                    "height": 1 + max(left_dict["height"] if left_dict else -1, 
                                      right_dict["height"] if right_dict else -1),
                    "left": left_dict,
                    "right": right_dict,
                }
                dicts[id(current)] = d
            else:
                stack.append((current, True))
                if current.right:
                    stack.append((current.right, False))
                if current.left:
                    stack.append((current.left, False))
        return dicts[id(self.root)]


# =====================================================================
# AVL vs BST comparison (Sections 11 and 15)
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
    Inserts exactly the same key sequence into an AVL and into a BST.
    Compares roots, heights, leaf counts and search comparisons.
    """
    avl = AVLTree()
    bst = BSTTree()

    for k in keys:
        avl.insert(_DummyEvent(k))
        bst.insert(k)

    # Compare the search of every key
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
