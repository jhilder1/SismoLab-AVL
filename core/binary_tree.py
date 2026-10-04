"""
BinaryTree — behaviour shared by the AVL and the BST.

Both trees use nodes with `key`, `event_id`, `left` and `right`. Everything
that only reads that shape lives here once: search, traversals, leaf count
and serialization. Every walk is iterative, so a degenerate tree (a chain of
thousands of nodes, e.g. a BST or the AVL in stress mode) cannot overflow
the recursion stack.

Subclasses only decide the extra fields each serialized node carries
(`_node_extra`, template method).
"""

from __future__ import annotations

import collections
from typing import Iterator, Optional


def iter_inorder(node) -> Iterator:
    """Nodes of the subtree rooted at `node`, in ascending key order."""
    stack = []
    current = node
    while stack or current:
        if current:
            stack.append(current)
            current = current.left
        else:
            current = stack.pop()
            yield current
            current = current.right


def iter_preorder(node) -> Iterator:
    """Nodes of the subtree rooted at `node`: root, left, right."""
    stack = [node] if node else []
    while stack:
        current = stack.pop()
        yield current
        if current.right:
            stack.append(current.right)
        if current.left:
            stack.append(current.left)


def iter_postorder(node) -> Iterator:
    """Nodes of the subtree rooted at `node`: left, right, root."""
    stack = [(node, False)] if node else []
    while stack:
        current, visited = stack.pop()
        if visited:
            yield current
        else:
            stack.append((current, True))
            if current.right:
                stack.append((current.right, False))
            if current.left:
                stack.append((current.left, False))


class BinaryTree:
    """Base class: read-only operations of a binary search tree."""

    root = None

    # --- Search ---

    def search(self, key) -> tuple[Optional[object], int]:
        """Returns (node, nodes_visited). Cost = depth + 1."""
        current = self.root
        visited = 0
        while current is not None:
            visited += 1
            if key == current.key:
                return current, visited
            current = current.left if key < current.key else current.right
        return None, visited

    # --- Traversals ---

    def inorder(self) -> list:
        return [node.key for node in iter_inorder(self.root)]

    def preorder(self) -> list:
        return [node.key for node in iter_preorder(self.root)]

    def postorder(self) -> list:
        return [node.key for node in iter_postorder(self.root)]

    def level_order(self) -> list:
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

    # --- Shape ---

    def count_leaves(self) -> int:
        return sum(1 for node in iter_preorder(self.root)
                   if not node.left and not node.right)

    # --- Serialization (to draw the tree in the front end) ---

    def to_dict(self) -> Optional[dict]:
        """Serializes the whole tree to nested dicts, built bottom-up."""
        if not self.root:
            return None
        dicts = {}
        for node in iter_postorder(self.root):
            left = dicts.get(id(node.left)) if node.left else None
            right = dicts.get(id(node.right)) if node.right else None
            data = {
                "key": str(node.key),
                "event_id": node.event_id,
                "priority": node.key.priority,
                "magnitude": node.key.magnitude,
            }
            data.update(self._node_extra(node, left, right))
            data["left"] = left
            data["right"] = right
            dicts[id(node)] = data
        return dicts[id(self.root)]

    def _node_extra(self, node, left: Optional[dict], right: Optional[dict]) -> dict:
        """Extra fields of one serialized node (height, balance factor...)."""
        return {}
