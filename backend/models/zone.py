"""
Zone entity.

Represents a rectangular geographic zone on the simulated 2D plane.
Zones may be populated or unpopulated, which affects priority calculation
when an epicenter lies inside or on the border.

Geometry is immutable during a scenario execution.
"""

from __future__ import annotations


class Zone:
    """
    A rectangular zone defined by its x/y boundaries.

    Attributes:
        name: human-readable zone identifier.
        x_min: left boundary in km.
        x_max: right boundary in km.
        y_min: bottom boundary in km.
        y_max: top boundary in km.
        is_populated: whether this zone is classified as populated.
    """

    __slots__ = ("name", "x_min", "x_max", "y_min", "y_max", "is_populated")

    def __init__(
        self,
        name: str,
        x_min: float,
        x_max: float,
        y_min: float,
        y_max: float,
        is_populated: bool,
    ) -> None:
        self.name = name
        self.x_min = round(x_min, 1)
        self.x_max = round(x_max, 1)
        self.y_min = round(y_min, 1)
        self.y_max = round(y_max, 1)
        self.is_populated = is_populated

    def contains(self, epicenter: "Epicenter") -> bool:  # noqa: F821
        """
        Check whether an epicenter is inside this zone (border-inclusive).

        This is equivalent to epicenter.is_inside(self) but allows calling
        from the zone's perspective for readability.
        """
        return (
            self.x_min <= epicenter.x <= self.x_max
            and self.y_min <= epicenter.y <= self.y_max
        )

    def __repr__(self) -> str:
        pop = "populated" if self.is_populated else "unpopulated"
        return (
            f"Zone('{self.name}', x=[{self.x_min},{self.x_max}], "
            f"y=[{self.y_min},{self.y_max}], {pop})"
        )

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "name": self.name,
            "x_min": self.x_min,
            "x_max": self.x_max,
            "y_min": self.y_min,
            "y_max": self.y_max,
            "is_populated": self.is_populated,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Zone":
        """Deserialize from a dictionary."""
        return cls(
            name=data["name"],
            x_min=data["x_min"],
            x_max=data["x_max"],
            y_min=data["y_min"],
            y_max=data["y_max"],
            is_populated=data["is_populated"],
        )
