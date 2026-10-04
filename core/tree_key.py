"""
TreeKey — the comparison key K = (P, M, I) shared by the AVL and the BST.
"""

from __future__ import annotations


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

    # --- Serialization ---
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
