"""
Report — incoming data from a seismic station.

Each report contains full event data, an identifier, a revision number,
and the emitting station. Reports enter the FIFO queue and are processed
one at a time.

The revision numbering is global per event (not per station).
Processing rules are defined in Section 6 of the specification:
  - Unknown ID       → create new event
  - Higher revision  → substitute data (correction)
  - Same rev, same data → confirm (add station)
  - Same rev, different data → conflict (reject)
  - Lower revision   → outdated (discard)
"""

from __future__ import annotations

from datetime import datetime

from .epicenter import Epicenter


class Report:
    """
    An incoming seismic report from a monitoring station.

    Attributes:
        event_id:        numeric event identifier referenced by this report.
        revision:        revision number for this report.
        station_id:      ID of the emitting station.
        magnitude:       reported magnitude.
        depth_km:        reported hypocentral depth in km.
        epicenter:       reported epicenter coordinates.
        occurrence_time: reported time of occurrence (UTC).
    """

    __slots__ = (
        "event_id",
        "revision",
        "station_id",
        "magnitude",
        "depth_km",
        "epicenter",
        "occurrence_time",
    )

    def __init__(
        self,
        event_id: int,
        revision: int,
        station_id: str,
        magnitude: float,
        depth_km: float,
        epicenter: Epicenter,
        occurrence_time: datetime,
    ) -> None:
        self.event_id: int = event_id
        self.revision: int = revision
        self.station_id: str = station_id
        self.magnitude: float = round(magnitude, 1)
        self.depth_km: float = round(depth_km, 1)
        self.epicenter: Epicenter = epicenter
        self.occurrence_time: datetime = occurrence_time

    def data_equals(self, other_mag: float, other_depth: float,
                    other_epi: Epicenter, other_time: datetime) -> bool:
        """
        Compare physical data for confirmation vs conflict detection.

        Compares magnitude, depth, epicenter (x, y), and occurrence time.
        All floats are pre-normalized to 1 decimal, so exact == is safe.
        """
        return (
            self.magnitude == round(other_mag, 1)
            and self.depth_km == round(other_depth, 1)
            and self.epicenter == other_epi
            and self.occurrence_time == other_time
        )

    def __repr__(self) -> str:
        return (
            f"Report(event={self.event_id}, rev={self.revision}, "
            f"station='{self.station_id}', M={self.magnitude})"
        )

    # ----------------------------------------------------------------
    # Serialization
    # ----------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "event_id": self.event_id,
            "revision": self.revision,
            "station_id": self.station_id,
            "magnitude": self.magnitude,
            "depth_km": self.depth_km,
            "epicenter": self.epicenter.to_dict(),
            "occurrence_time": self.occurrence_time.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Report":
        """Deserialize from a dictionary."""
        return cls(
            event_id=data["event_id"],
            revision=data["revision"],
            station_id=data["station_id"],
            magnitude=data["magnitude"],
            depth_km=data["depth_km"],
            epicenter=Epicenter.from_dict(data["epicenter"]),
            occurrence_time=datetime.fromisoformat(data["occurrence_time"]),
        )
