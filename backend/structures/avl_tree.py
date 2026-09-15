from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from .avl_node import AVLNode
from .tree_key import TreeKey

if TYPE_CHECKING:
    from models.event import SeismicEvent


class AVLTree:
    """
    Self-balancing AVL tree: the central structure of the active catalog.

    Nodes are ordered by the key K = (P, M, I) and each node holds a reference
    to its SeismicEvent. Two execution modes (Section 8):

      - normal mode: every insertion and deletion ends with a valid AVL tree.
      - stress mode: the same operations keep BST order but defer rotations,
        so the AVL condition may be violated until recover_balance() runs.
    """

    def __init__(self) -> None:
        self.root: Optional[AVLNode] = None
        self.size = 0

        # Stress mode: insert as a plain BST and defer all rotations.
        self.stress_mode = False

        # Rebalancing case counters (Section 14).
        self.rotations_ll = 0
        self.rotations_rr = 0
        self.rotations_lr = 0
        self.rotations_rl = 0

        # Elementary turn counters. A double case counts as ONE LR/RL case
        # plus TWO elementary turns, as required by Section 14.
        self.simple_turns_left = 0
        self.simple_turns_right = 0

    # ------------------------------------------------------------------
    # Height and balance
    # ------------------------------------------------------------------

    def get_height(self, node: Optional[AVLNode]) -> int:
        if not node:
            return -1
        return node.height

    def get_balance(self, node: Optional[AVLNode]) -> int:
        if not node:
            return 0
        return node.balance_factor

    @property
    def height(self) -> int:
        """Height of the whole tree. Empty tree = -1, single node = 0."""
        return self.get_height(self.root)

    # ------------------------------------------------------------------
    # Insertion
    # ------------------------------------------------------------------

    def insert(self, event: "SeismicEvent") -> None:
        """
        Insert an event using the key derived from its current data.

        The caller is responsible for guaranteeing that the identifier does
        not already exist in the catalog (Section 5: "Nunca se crea un
        segundo nodo para ese terremoto").
        """
        self.root = self._insert(self.root, event, event.build_key())

    def _insert(
        self,
        node: Optional[AVLNode],
        event: "SeismicEvent",
        key: TreeKey,
    ) -> AVLNode:
        if not node:
            self.size += 1
            return AVLNode(event)

        if key < node.key:
            node.left = self._insert(node.left, event, key)
        elif key > node.key:
            node.right = self._insert(node.right, event, key)
        else:
            return node  # duplicate key: identifiers are unique, so this is a no-op

        node.update_height()

        if self.stress_mode:
            return node

        return self._balance(node)

    # ------------------------------------------------------------------
    # Rebalancing
    # ------------------------------------------------------------------

    def _balance(self, node: AVLNode) -> AVLNode:
        balance = self.get_balance(node)

        # Left heavy
        if balance > 1:
            if self.get_balance(node.left) >= 0:
                self.rotations_ll += 1
                return self._rotate_right(node)
            self.rotations_lr += 1
            node.left = self._rotate_left(node.left)
            return self._rotate_right(node)

        # Right heavy
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

    # ------------------------------------------------------------------
    # Deletion
    # ------------------------------------------------------------------

    def delete(self, key: TreeKey) -> None:
        """Remove the node holding this exact key. Descendants stay active."""
        self.root = self._delete(self.root, key)

    def _delete(self, node: Optional[AVLNode], key: TreeKey) -> Optional[AVLNode]:
        if not node:
            return None

        if key < node.key:
            node.left = self._delete(node.left, key)
        elif key > node.key:
            node.right = self._delete(node.right, key)
        else:
            # Zero or one child: splice the node out.
            if not node.left:
                self.size -= 1
                return node.right
            if not node.right:
                self.size -= 1
                return node.left

            # Two children: move the inorder successor's payload up.
            # adopt() copies the event REFERENCE, so identity is preserved.
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

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, key: TreeKey) -> tuple[Optional[AVLNode], int]:
        """
        Locate a node by its key.

        Returns (node, visited) where visited is the number of nodes examined
        from the root. Section 9 defines this as the simulated access cost:
        for an existing event it equals its depth plus one. Section 11 requires
        every query to report it.
        """
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
        """
        Depth of the node holding this key. Root depth is 0 (Section 9).

        Depth is computed on demand and never stored in the node: a single
        rotation changes the depth of a whole subtree, so a cached value would
        have to be refreshed across the tree after every operation.
        """
        node, visited = self.search(key)
        return None if node is None else visited - 1

    # ------------------------------------------------------------------
    # Global recovery from stress mode (Section 8)
    # ------------------------------------------------------------------

    def recover_balance(self) -> dict:
        """
        Restore the AVL property after stress mode, rotating in place.

        The tree is never emptied and rebuilt from a sorted list, which the
        specification forbids. Returns the cost of the repair so the interface
        can display it.

        Termination: rotations preserve the inorder traversal, so BST order
        never breaks; each iteration of the loop strictly reduces the height
        of the tallest subtree, which is bounded below, so the process ends.
        """
        before = {
            "ll": self.rotations_ll,
            "rr": self.rotations_rr,
            "lr": self.rotations_lr,
            "rl": self.rotations_rl,
            "left": self.simple_turns_left,
            "right": self.simple_turns_right,
        }

        self.root = self._recover_balance_recursive(self.root)

        # Normal mode is only restored once the structure is balanced again.
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

        # Postorder: repair the children first.
        node.left = self._recover_balance_recursive(node.left)
        node.right = self._recover_balance_recursive(node.right)
        node.update_height()

        # Loop to absorb imbalances greater than 2.
        while abs(self.get_balance(node)) > 1:
            node = self._balance(node)
            # A rotation demotes a child that may now be unbalanced itself,
            # and the postorder pass already went past it: repair it again.
            node.left = self._recover_balance_recursive(node.left)
            node.right = self._recover_balance_recursive(node.right)
            node.update_height()

        return node