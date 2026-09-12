from typing import Optional
from .bst_node import BSTNode
from .tree_key import TreeKey

class BSTTree:
    def __init__(self):
        self.root: Optional[BSTNode] = None
        self.size = 0

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
