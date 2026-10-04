"""
BSTTree — plain binary search tree without balancing (Sections 11 and 15).

Receives the same operations as the AVL so both can be compared: its shape
depends only on the insertion order.
"""

from __future__ import annotations

from typing import Optional

from core.binary_tree import BinaryTree, iter_postorder
from core.tree_key import TreeKey


class BSTNode:
    """Plain BST node (key only, no balancing)."""

    def __init__(self, key: TreeKey):
        self.key = key
        self.event_id = key.event_id
        self.left: Optional[BSTNode] = None
        self.right: Optional[BSTNode] = None


class BSTTree(BinaryTree):
    """BST without balancing (to compare with the AVL)."""

    def __init__(self):
        self.root: Optional[BSTNode] = None
        self.size = 0

    # --- Height (nodes do not store it: computed bottom-up) ---

    def get_height(self, node: Optional[BSTNode]) -> int:
        if not node:
            return -1
        heights = {}
        for current in iter_postorder(node):
            left_h = heights.get(id(current.left), -1) if current.left else -1
            right_h = heights.get(id(current.right), -1) if current.right else -1
            heights[id(current)] = 1 + max(left_h, right_h)
        return heights[id(node)]

    @property
    def height(self) -> int:
        return self.get_height(self.root)

    # --- Insertion ---

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

    # --- Deletion ---

    def delete(self, key: TreeKey):
        if not self.root:
            return

        parent, direction = None, None
        current = self.root
        while current:
            if key < current.key:
                parent, direction, current = current, "left", current.left
            elif key > current.key:
                parent, direction, current = current, "right", current.right
            else:
                break

        if not current:
            return

        if not current.left or not current.right:
            sub = current.right if not current.left else current.left
            self.size -= 1
            if parent is None:
                self.root = sub
            elif direction == "left":
                parent.left = sub
            else:
                parent.right = sub
            return

        # Two children: copy the in-order successor, then unlink it.
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

    # --- Serialization ---

    def _node_extra(self, node, left: Optional[dict], right: Optional[dict]) -> dict:
        return {"height": 1 + max(left["height"] if left else -1,
                                  right["height"] if right else -1)}
