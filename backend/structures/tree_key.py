"""
TreeKey — the comparison key for AVL and BST nodes.

The key is the ordered tuple K = (P, M, I) where:
  P = calculated priority (1=LOW, 2=MEDIUM, 3=HIGH)
  M = current magnitude (decimal, 1 decimal place)
  I = numeric event identifier (integer, immutable)

Lexicographic comparison rules (Section 5 of the specification):
  1. If priorities differ → lower priority is the lesser key.
  2. If priorities match → lower magnitude is the lesser key.
  3. If priority AND magnitude match → lower ID is the lesser key.

A lesser key goes to the LEFT child; a greater key goes to the RIGHT child.
Inorder traversal produces ascending keys; reverse inorder produces descending.

IMPORTANT: Two keys are never equal because each event ID is unique.
"""

from __future__ import annotations


class TreeKey:
    """
    Immutable comparison key for the AVL/BST catalog.

    Supports all comparison operators (<, <=, >, >=, ==, !=)
    using strict lexicographic order on (priority, magnitude, event_id).

    Attributes:
        priority: integer priority level (1, 2, or 3).
        magnitude: event magnitude normalized to 1 decimal place.
        event_id: unique numeric event identifier.
    """

    __slots__ = ("priority", "magnitude", "event_id")

    def __init__(self, priority: int, magnitude: float, event_id: int) -> None:
        self.priority: int = priority
        self.magnitude: float = round(magnitude, 1)
        self.event_id: int = event_id

    def to_tuple(self) -> tuple[int, float, int]:
        """Return the key as a comparable tuple (P, M, I)."""
        return (self.priority, self.magnitude, self.event_id)

    # ----- Lexicographic comparison operators -----
    # Python tuple comparison is already lexicographic, so we delegate
    # to the tuple representation for clarity and correctness.

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

    # ----- Display -----

    def __repr__(self) -> str:
        return f"TreeKey(P={self.priority}, M={self.magnitude}, I={self.event_id})"

    def __str__(self) -> str:
        return f"({self.priority}, {self.magnitude}, {self.event_id})"

    # ----- Serialization -----

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dictionary."""
        return {
            "priority": self.priority,
            "magnitude": self.magnitude,
            "event_id": self.event_id,
        }

    def to_list(self) -> list:
        """Serialize as a JSON array [P, M, I] for compact representation."""
        return [self.priority, self.magnitude, self.event_id]

    @classmethod
    def from_dict(cls, data: dict) -> "TreeKey":
        """Deserialize from a dictionary."""
        return cls(
            priority=data["priority"],
            magnitude=data["magnitude"],
            event_id=data["event_id"],
        )

    @classmethod
    def from_list(cls, data: list) -> "TreeKey":
        """Deserialize from a [P, M, I] array."""
        return cls(priority=data[0], magnitude=data[1], event_id=data[2])
