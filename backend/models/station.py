"""
Station entity.

Represents a seismic monitoring station. Stations are parameterized
at scenario start and immutable during execution.
"""

from __future__ import annotations


class Station:
    """
    A seismic monitoring station.

    Attributes:
        station_id: unique identifier for the station (e.g. 'EST-001').
        name: human-readable station name.
    """

    __slots__ = ("station_id", "name")

    def __init__(self, station_id: str, name: str) -> None:
        self.station_id = station_id
        self.name = name

    def __repr__(self) -> str:
        return f"Station('{self.station_id}', '{self.name}')"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Station):
            return NotImplemented
        return self.station_id == other.station_id

    def __hash__(self) -> int:
        return hash(self.station_id)

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "station_id": self.station_id,
            "name": self.name,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Station":
        """Deserialize from a dictionary."""
        return cls(
            station_id=data["station_id"],
            name=data["name"],
        )
