from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from .tree_key import TreeKey

if TYPE_CHECKING:
    from models.event import SeismicEvent


class AVLNode:
    """
    A node of the active catalog AVL tree.

    Each node represents exactly one active seismic event (Section 5).
    The node holds a REFERENCE to the event, never a copy: the event object
    is the single source of truth for magnitude, depth, revision, stations
    and attention state, so any change made through the service is visible
    here immediately.

    The key, on the other hand, is a FROZEN SNAPSHOT taken when the node was
    inserted. It must not be recomputed from the event on the fly: if a
    correction changes P or M, the event must be removed with its OLD key and
    reinserted with the NEW one (Section 5, "Identidad y cambios de clave").
    Deriving the key dynamically would silently corrupt the BST order, because
    the node would start comparing differently than the position it occupies.
    """

    __slots__ = ("key", "event", "event_id", "left", "right", "height")

    def __init__(self, event: "SeismicEvent") -> None:
        self.event: "SeismicEvent" = event
        self.event_id: int = event.event_id
        self.key: TreeKey = event.build_key()

        self.left: Optional[AVLNode] = None
        self.right: Optional[AVLNode] = None
        self.height: int = 0

    @property
    def balance_factor(self) -> int:
        """Balance factor = height(left) - height(right), per Section 14."""
        left_h = self.left.height if self.left else -1
        right_h = self.right.height if self.right else -1
        return left_h - right_h

    def update_height(self) -> None:
        """Recompute this node's height from its children. Empty subtree = -1."""
        left_h = self.left.height if self.left else -1
        right_h = self.right.height if self.right else -1
        self.height = 1 + max(left_h, right_h)

    def adopt(self, other: "AVLNode") -> None:
        """
        Take over the payload of another node (key, event and identifier).

        Used by deletion of a node with two children, where the inorder
        successor's payload is moved into this node. The event object itself
        is never copied, only the reference, so external structures that point
        to the event (the id index, associations) stay valid.
        """
        self.key = other.key
        self.event = other.event
        self.event_id = other.event_id

    def __repr__(self) -> str:
        return f"AVLNode(key={self.key}, h={self.height})"