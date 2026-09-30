"""
Modelos de dominio: enums, epicentro, zona, estación, reporte, asociación y evento sísmico.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from enum import IntEnum, Enum
from typing import Optional


# =====================================================================
# UTC time format for JSON (Section 3: ISO 8601, e.g. 2026-09-07T10:00:00Z)
# =====================================================================

def format_time(moment: datetime) -> str:
    """Serialize a naive UTC datetime as ISO 8601 with the 'Z' suffix."""
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_time(text: str) -> datetime:
    """Parse ISO 8601 text into a naive UTC datetime with second precision.

    Accepts the 'Z' suffix, explicit offsets and plain text without zone
    (read as UTC), so comparisons never mix aware and naive datetimes.
    """
    value = text.strip()
    if value.endswith(("Z", "z")):
        value = value[:-1] + "+00:00"
    moment = datetime.fromisoformat(value)
    if moment.tzinfo is not None:
        moment = moment.astimezone(timezone.utc).replace(tzinfo=None)
    return moment.replace(microsecond=0)


def has_max_one_decimal(value: float) -> bool:
    """Section 3: magnitudes, depths and coordinates carry at most one decimal.

    Compares in tenths with a tiny tolerance, so 4.5 passes (stored as
    4.4999...) and 4.46 fails instead of being rounded silently.
    """
    tenths = value * 10
    return abs(tenths - round(tenths)) < 1e-9


def normalize_tenths(value: float) -> float:
    """Remove float noise (0.30000000000000004 -> 0.3) from a value that
    already has at most one decimal. Any other value is returned unchanged,
    so validation still sees 4.46 and rejects it instead of storing 4.5."""
    if math.isfinite(value) and has_max_one_decimal(value):
        return round(value, 1)
    return value


# =====================================================================
# Enumeraciones
# =====================================================================

class Priority(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3


class AttentionState(str, Enum):
    PENDING = "pending"
    REVIEWED = "reviewed"


class EventStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


# =====================================================================
# Epicenter
# =====================================================================

class Epicenter:
    """Coordenadas (x, y) del epicentro en el plano 2D (0–1000 km)."""

    __slots__ = ("x", "y")

    def __init__(self, x: float, y: float) -> None:
        self.x: float = normalize_tenths(x)
        self.y: float = normalize_tenths(y)

    def distance_to(self, other: "Epicenter") -> float:
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)

    def is_inside(self, zone: "Zone") -> bool:
        return (zone.x_min <= self.x <= zone.x_max
                and zone.y_min <= self.y <= zone.y_max)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Epicenter):
            return NotImplemented
        return self.x == other.x and self.y == other.y

    def __repr__(self) -> str:
        return f"Epicenter(x={self.x}, y={self.y})"

    def to_dict(self) -> dict:
        return {"x": self.x, "y": self.y}

    @classmethod
    def from_dict(cls, data: dict) -> "Epicenter":
        return cls(x=data["x"], y=data["y"])

    @staticmethod
    def validate_coordinate(value: float, name: str) -> None:
        if not (0.0 <= value <= 1000.0):
            raise ValueError(f"{name} must be between 0.0 and 1000.0, got {value}")


# =====================================================================
# Zone
# =====================================================================

class Zone:
    """Zona rectangular en el plano 2D. Puede ser poblada o no."""

    __slots__ = ("name", "x_min", "x_max", "y_min", "y_max", "is_populated")

    def __init__(self, name: str, x_min: float, x_max: float,
                 y_min: float, y_max: float, is_populated: bool) -> None:
        self.name = name
        self.x_min = round(x_min, 1)
        self.x_max = round(x_max, 1)
        self.y_min = round(y_min, 1)
        self.y_max = round(y_max, 1)
        self.is_populated = is_populated

    def contains(self, epicenter: "Epicenter") -> bool:
        return (self.x_min <= epicenter.x <= self.x_max
                and self.y_min <= epicenter.y <= self.y_max)

    def __repr__(self) -> str:
        pop = "populated" if self.is_populated else "unpopulated"
        return f"Zone('{self.name}', x=[{self.x_min},{self.x_max}], y=[{self.y_min},{self.y_max}], {pop})"

    def to_dict(self) -> dict:
        return {"name": self.name, "x_min": self.x_min, "x_max": self.x_max,
                "y_min": self.y_min, "y_max": self.y_max, "is_populated": self.is_populated}

    @classmethod
    def from_dict(cls, data: dict) -> "Zone":
        return cls(name=data["name"], x_min=data["x_min"], x_max=data["x_max"],
                   y_min=data["y_min"], y_max=data["y_max"], is_populated=data["is_populated"])


# =====================================================================
# Station
# =====================================================================

class Station:
    """Estación de monitoreo sísmico."""

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
        return {"station_id": self.station_id, "name": self.name}

    @classmethod
    def from_dict(cls, data: dict) -> "Station":
        return cls(station_id=data["station_id"], name=data["name"])


# =====================================================================
# Report
# =====================================================================

class Report:
    """Reporte de una estación sísmica (entra a la cola FIFO)."""

    __slots__ = ("event_id", "revision", "station_id", "magnitude",
                 "depth_km", "epicenter", "occurrence_time")

    def __init__(self, event_id: int, revision: int, station_id: str,
                 magnitude: float, depth_km: float, epicenter: Epicenter,
                 occurrence_time: datetime) -> None:
        self.event_id: int = event_id
        self.revision: int = revision
        self.station_id: str = station_id
        self.magnitude: float = normalize_tenths(magnitude)
        self.depth_km: float = normalize_tenths(depth_km)
        self.epicenter: Epicenter = epicenter
        self.occurrence_time: datetime = occurrence_time

    def data_equals(self, other_mag: float, other_depth: float,
                    other_epi: Epicenter, other_time: datetime) -> bool:
        return (self.magnitude == round(other_mag, 1)
                and self.depth_km == round(other_depth, 1)
                and self.epicenter == other_epi
                and self.occurrence_time == other_time)

    def __repr__(self) -> str:
        return f"Report(event={self.event_id}, rev={self.revision}, station='{self.station_id}', M={self.magnitude})"

    def to_dict(self) -> dict:
        return {"event_id": self.event_id, "revision": self.revision,
                "station_id": self.station_id, "magnitude": self.magnitude,
                "depth_km": self.depth_km, "epicenter": self.epicenter.to_dict(),
                "occurrence_time": format_time(self.occurrence_time)}

    @classmethod
    def from_dict(cls, data: dict) -> "Report":
        return cls(event_id=data["event_id"], revision=data["revision"],
                   station_id=data["station_id"], magnitude=data["magnitude"],
                   depth_km=data["depth_km"], epicenter=Epicenter.from_dict(data["epicenter"]),
                   occurrence_time=parse_time(data["occurrence_time"]))


# =====================================================================
# Association
# =====================================================================

class Association:
    """Relación entre un evento y su posible sismo principal (mainshock)."""

    __slots__ = ("event_id", "reference_id", "candidate_ids", "selection_info")

    def __init__(self, event_id: int, reference_id: Optional[int] = None,
                 candidate_ids: Optional[list[int]] = None, selection_info: str = "") -> None:
        self.event_id: int = event_id
        self.reference_id: Optional[int] = reference_id
        self.candidate_ids: list[int] = candidate_ids if candidate_ids else []
        self.selection_info: str = selection_info

    def has_reference(self) -> bool:
        return self.reference_id is not None

    def __repr__(self) -> str:
        ref = self.reference_id if self.reference_id else "None"
        return f"Association(event={self.event_id}, ref={ref}, candidates={self.candidate_ids})"

    def to_dict(self) -> dict:
        return {"event_id": self.event_id, "reference_id": self.reference_id,
                "candidates": self.candidate_ids, "selection_info": self.selection_info}

    @classmethod
    def from_dict(cls, data: dict) -> "Association":
        return cls(event_id=data["event_id"], reference_id=data.get("reference_id"),
                   candidate_ids=data.get("candidates", []), selection_info=data.get("selection_info", ""))


# =====================================================================
# SeismicEvent
# =====================================================================

class SeismicEvent:
    """Evento sísmico: la entidad central del dominio."""

    __slots__ = (
        "event_id", "magnitude", "depth_km", "epicenter", "occurrence_time",
        "revision", "reporting_stations", "priority", "attention_state",
        "status", "in_populated_zone", "reference_event_id",
    )

    def __init__(self, event_id: int, magnitude: float, depth_km: float,
                 epicenter: Epicenter, occurrence_time: datetime, station_id: str,
                 zones: list[Zone], revision: int = 1) -> None:
        self.event_id: int = event_id
        self.magnitude: float = normalize_tenths(magnitude)
        self.depth_km: float = normalize_tenths(depth_km)
        self.epicenter: Epicenter = epicenter
        self.occurrence_time: datetime = occurrence_time
        self.revision: int = revision
        self.reporting_stations: set[str] = {station_id}
        self.in_populated_zone: bool = self._check_populated_zone(zones)
        self.priority: Priority = self._calculate_priority()
        self.attention_state: AttentionState = AttentionState.PENDING
        self.status: EventStatus = EventStatus.ACTIVE
        self.reference_event_id: Optional[int] = None

    # --- Cálculo de prioridad (Sección 4) ---

    def _calculate_priority(self) -> Priority:
        if self.magnitude >= 6.0:
            return Priority.HIGH
        if self.magnitude >= 4.5:
            if self.depth_km <= 30.0 and self.in_populated_zone:
                return Priority.HIGH
            return Priority.MEDIUM
        return Priority.LOW

    def _check_populated_zone(self, zones: list[Zone]) -> bool:
        for zone in zones:
            if zone.contains(self.epicenter) and zone.is_populated:
                return True
        return False

    def recalculate_priority(self, zones: list[Zone]) -> Priority:
        self.in_populated_zone = self._check_populated_zone(zones)
        self.priority = self._calculate_priority()
        return self.priority

    # --- Clave AVL: K = (P, M, I) ---

    def build_key(self):
        from core.avl_tree import TreeKey
        return TreeKey(priority=int(self.priority), magnitude=self.magnitude, event_id=self.event_id)

    # --- Correcciones ---

    def apply_correction(self, magnitude: Optional[float] = None,
                         depth_km: Optional[float] = None,
                         epicenter: Optional[Epicenter] = None,
                         occurrence_time: Optional[datetime] = None,
                         zones: list[Zone] = None):
        if zones is None:
            zones = []
        if magnitude is not None:
            self.magnitude = normalize_tenths(magnitude)
        if depth_km is not None:
            self.depth_km = normalize_tenths(depth_km)
        if epicenter is not None:
            self.epicenter = epicenter
        if occurrence_time is not None:
            self.occurrence_time = occurrence_time
        self.revision += 1
        self.attention_state = AttentionState.PENDING
        self.recalculate_priority(zones)
        return self.build_key()

    # --- Display ---

    def format_id(self) -> str:
        return f"SIS-{self.event_id:06d}"

    def __repr__(self) -> str:
        return (f"SeismicEvent({self.format_id()}, M={self.magnitude}, "
                f"P={self.priority.name}, {self.attention_state.value}, rev={self.revision})")

    # --- Serialización JSON ---

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id, "magnitude": self.magnitude,
            "depth_km": self.depth_km, "epicenter": self.epicenter.to_dict(),
            "occurrence_time": format_time(self.occurrence_time),
            "revision": self.revision,
            "reporting_stations": sorted(self.reporting_stations),
            "priority": int(self.priority),
            "attention_state": self.attention_state.value,
            "status": self.status.value,
            "in_populated_zone": self.in_populated_zone,
            "reference_event_id": self.reference_event_id,
        }

    @classmethod
    def from_dict(cls, data: dict, zones: list[Zone]) -> "SeismicEvent":
        event = cls.__new__(cls)
        event.event_id = data["event_id"]
        event.magnitude = normalize_tenths(data["magnitude"])
        event.depth_km = normalize_tenths(data["depth_km"])
        event.epicenter = Epicenter.from_dict(data["epicenter"])
        event.occurrence_time = parse_time(data["occurrence_time"])
        event.revision = data.get("revision", 1)
        event.reporting_stations = set(data.get("reporting_stations", []))
        event.attention_state = AttentionState(data.get("attention_state", "pending"))
        event.status = EventStatus(data.get("status", "active"))
        event.reference_event_id = data.get("reference_event_id")
        event.in_populated_zone = event._check_populated_zone(zones)
        event.priority = event._calculate_priority()
        return event

    # --- Validación ---

    @staticmethod
    def validate_data(event_id: int, magnitude: float, depth_km: float,
                      epicenter_x: float, epicenter_y: float,
                      occurrence_time: datetime, simulation_clock: datetime) -> list[str]:
        errors: list[str] = []
        if not (1 <= event_id <= 999999):
            errors.append(f"event_id must be between 1 and 999999, got {event_id}")
        for name, value, low, high in (("magnitude", magnitude, -2.0, 10.0),
                                       ("depth_km", depth_km, 0.0, 700.0),
                                       ("epicenter.x", epicenter_x, 0.0, 1000.0),
                                       ("epicenter.y", epicenter_y, 0.0, 1000.0)):
            if not (math.isfinite(value) and low <= value <= high):
                errors.append(f"{name} must be between {low} and {high}, got {value}")
            elif not has_max_one_decimal(value):
                errors.append(f"{name} must have at most one decimal, got {value}")
        if occurrence_time > simulation_clock:
            errors.append(f"occurrence_time ({occurrence_time.isoformat()}) cannot be "
                          f"after simulation clock ({simulation_clock.isoformat()})")
        return errors
