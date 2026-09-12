"""
Epicenter value object.

Represents the (x, y) coordinates of an earthquake's epicenter
on the simulated 2D geographic plane (0–1000 km on both axes).

All coordinates are normalized to 1 decimal place on creation
to ensure consistent equality comparisons without epsilon.
"""

from __future__ import annotations
import math


class Epicenter:
    """
    Immutable-style value object for epicenter coordinates.

    Attributes:
        x: horizontal position in km, [0.0, 1000.0], 1 decimal.
        y: vertical position in km, [0.0, 1000.0], 1 decimal.
    """

    __slots__ = ("x", "y")

    def __init__(self, x: float, y: float) -> None:
        # Normalize to 1 decimal for exact comparisons
        self.x: float = round(x, 1)
        self.y: float = round(y, 1)

    # ----- Geometric helpers -----

    def distance_to(self, other: "Epicenter") -> float:
        """Euclidean distance in km between two epicenters."""
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)

    def is_inside(self, zone: "Zone") -> bool:  # noqa: F821
        """
        Check whether this epicenter is inside (or on the border of) a zone.

        Border-inclusive: uses <= and >= so that points exactly on a zone
        boundary are considered inside.
        """
        return (
            zone.x_min <= self.x <= zone.x_max
            and zone.y_min <= self.y <= zone.y_max
        )

    # ----- Equality and serialization -----

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Epicenter):
            return NotImplemented
        return self.x == other.x and self.y == other.y

    def __repr__(self) -> str:
        return f"Epicenter(x={self.x}, y={self.y})"

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dictionary."""
        return {"x": self.x, "y": self.y}

    @classmethod
    def from_dict(cls, data: dict) -> "Epicenter":
        """Deserialize from a dictionary."""
        return cls(x=data["x"], y=data["y"])

    # ----- Validation -----

    @staticmethod
    def validate_coordinate(value: float, name: str) -> None:
        """
        Raise ValueError if the coordinate is out of range.

        Args:
            value: raw coordinate value before normalization.
            name: field name for the error message (e.g. 'epicenter.x').
        """
        if not (0.0 <= value <= 1000.0):
            raise ValueError(
                f"{name} must be between 0.0 and 1000.0, got {value}"
            )
