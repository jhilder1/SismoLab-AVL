"""
Association — relationship between a seismic event and its possible mainshock.

An event B can be associated with a reference event A (possible mainshock)
when A has greater magnitude, occurred strictly before B, and both:
  - Time difference <= W hours
  - Euclidean distance <= R km

The selection criterion (when multiple candidates exist) is deterministic
and depends only on data, not on insertion order or AVL topology:
  1. Greatest magnitude among candidates.
  2. Tie-break: shortest euclidean distance.
  3. Tie-break: smallest event ID.

Associations consider active AND archived events, but NOT deleted ones.
"""

from __future__ import annotations

from typing import Optional


class Association:
    """
    Tracks the association between an event and its reference.

    Attributes:
        event_id:       the event that may be a replica/aftershock.
        reference_id:   the selected reference event ID, or None.
        candidate_ids:  list of all valid candidate IDs.
        selection_info: human-readable explanation of why the reference was chosen.
    """

    __slots__ = ("event_id", "reference_id", "candidate_ids", "selection_info")

    def __init__(
        self,
        event_id: int,
        reference_id: Optional[int] = None,
        candidate_ids: Optional[list[int]] = None,
        selection_info: str = "",
    ) -> None:
        self.event_id: int = event_id
        self.reference_id: Optional[int] = reference_id
        self.candidate_ids: list[int] = candidate_ids if candidate_ids else []
        self.selection_info: str = selection_info

    def has_reference(self) -> bool:
        """Whether this event has an associated reference."""
        return self.reference_id is not None

    def __repr__(self) -> str:
        ref = self.reference_id if self.reference_id else "None"
        return (
            f"Association(event={self.event_id}, ref={ref}, "
            f"candidates={self.candidate_ids})"
        )

    # ----------------------------------------------------------------
    # Serialization
    # ----------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "event_id": self.event_id,
            "reference_id": self.reference_id,
            "candidates": self.candidate_ids,
            "selection_info": self.selection_info,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Association":
        """Deserialize from a dictionary."""
        return cls(
            event_id=data["event_id"],
            reference_id=data.get("reference_id"),
            candidate_ids=data.get("candidates", []),
            selection_info=data.get("selection_info", ""),
        )
