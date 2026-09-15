"""
Tests for priority calculation (Section 4 of the specification).

Mandatory rules:
  Priority 3 (HIGH):   M >= 6.0
                        OR (M >= 4.5 AND H <= 30.0 AND populated zone)
  Priority 2 (MEDIUM): not HIGH and M >= 4.5
  Priority 1 (LOW):    everything else

Boundary values from the spec and Section 16 test cases:
  - M = 4.5, M = 6.0, H = 30.0
  - Epicenter on the border of a populated zone
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.models.enums import Priority
from backend.models.epicenter import Epicenter
from backend.models.zone import Zone
from backend.models.event import SeismicEvent


# ---- Shared test fixtures ----

CLOCK = datetime(2026, 9, 7, 12, 0, 0)

POPULATED_ZONE = Zone(
    name="Zona Capital",
    x_min=100.0, x_max=300.0,
    y_min=200.0, y_max=400.0,
    is_populated=True,
)

UNPOPULATED_ZONE = Zone(
    name="Zona Desierta",
    x_min=500.0, x_max=700.0,
    y_min=500.0, y_max=700.0,
    is_populated=False,
)

ZONES = [POPULATED_ZONE, UNPOPULATED_ZONE]


def _make_event(
    event_id: int,
    magnitude: float,
    depth_km: float,
    x: float,
    y: float,
) -> SeismicEvent:
    """Helper to create an event with minimal boilerplate."""
    return SeismicEvent(
        event_id=event_id,
        magnitude=magnitude,
        depth_km=depth_km,
        epicenter=Epicenter(x, y),
        occurrence_time=CLOCK,
        station_id="EST-001",
        zones=ZONES,
    )


class TestPriorityHigh:
    """Priority 3 (HIGH) cases."""

    def test_magnitude_6_0_is_high(self):
        """M = 6.0 → always HIGH regardless of depth or zone."""
        event = _make_event(1, magnitude=6.0, depth_km=500.0, x=600.0, y=600.0)
        assert event.priority == Priority.HIGH

    def test_magnitude_above_6_is_high(self):
        """M = 7.5 → HIGH."""
        event = _make_event(2, magnitude=7.5, depth_km=100.0, x=50.0, y=50.0)
        assert event.priority == Priority.HIGH

    def test_magnitude_10_is_high(self):
        """M = 10.0 (max) → HIGH."""
        event = _make_event(3, magnitude=10.0, depth_km=0.0, x=0.0, y=0.0)
        assert event.priority == Priority.HIGH

    def test_m45_h30_populated_is_high(self):
        """M = 4.5, H = 30.0, populated zone → HIGH (all limits inclusive)."""
        # Epicenter inside populated zone
        event = _make_event(4, magnitude=4.5, depth_km=30.0, x=200.0, y=300.0)
        assert event.priority == Priority.HIGH

    def test_m55_h25_populated_is_high(self):
        """M = 5.5, H = 25.0, populated zone → HIGH."""
        event = _make_event(5, magnitude=5.5, depth_km=25.0, x=150.0, y=250.0)
        assert event.priority == Priority.HIGH


class TestPriorityMedium:
    """Priority 2 (MEDIUM) cases."""

    def test_m45_unpopulated_is_medium(self):
        """M = 4.5, outside populated zone → MEDIUM."""
        event = _make_event(10, magnitude=4.5, depth_km=10.0, x=600.0, y=600.0)
        assert event.priority == Priority.MEDIUM

    def test_m45_h31_populated_is_medium(self):
        """M = 4.5, H = 31.0, populated zone → MEDIUM (depth > 30)."""
        event = _make_event(11, magnitude=4.5, depth_km=31.0, x=200.0, y=300.0)
        assert event.priority == Priority.MEDIUM

    def test_m59_deep_is_medium(self):
        """M = 5.9 (just below 6.0), deep, not populated → MEDIUM."""
        event = _make_event(12, magnitude=5.9, depth_km=100.0, x=50.0, y=50.0)
        assert event.priority == Priority.MEDIUM

    def test_m45_h30_unpopulated_is_medium(self):
        """
        M = 4.5, H = 30.0, UNpopulated zone → MEDIUM.
        Same event from spec example: outside populated zone produces P=2.
        """
        event = _make_event(13, magnitude=4.5, depth_km=30.0, x=600.0, y=600.0)
        assert event.priority == Priority.MEDIUM


class TestPriorityLow:
    """Priority 1 (LOW) cases."""

    def test_m44_is_low(self):
        """M = 4.4 (just below 4.5) → LOW."""
        event = _make_event(20, magnitude=4.4, depth_km=10.0, x=200.0, y=300.0)
        assert event.priority == Priority.LOW

    def test_m0_is_low(self):
        """M = 0.0 → LOW."""
        event = _make_event(21, magnitude=0.0, depth_km=50.0, x=500.0, y=500.0)
        assert event.priority == Priority.LOW

    def test_negative_magnitude_is_low(self):
        """M = -2.0 (minimum) → LOW."""
        event = _make_event(22, magnitude=-2.0, depth_km=0.0, x=0.0, y=0.0)
        assert event.priority == Priority.LOW

    def test_m3_shallow_populated_is_low(self):
        """M = 3.0, H = 5.0, populated zone → LOW (M < 4.5)."""
        event = _make_event(23, magnitude=3.0, depth_km=5.0, x=200.0, y=300.0)
        assert event.priority == Priority.LOW


class TestZoneBorder:
    """Epicenter on the border of zones (Section 3 rules)."""

    def test_on_border_of_populated_zone_is_populated(self):
        """
        Epicenter exactly on x_min of populated zone (border-inclusive).
        The zone boundary is [100, 300] x [200, 400].
        Point (100.0, 200.0) is on the corner → inside.
        """
        event = _make_event(30, magnitude=4.5, depth_km=30.0, x=100.0, y=200.0)
        assert event.in_populated_zone is True
        assert event.priority == Priority.HIGH

    def test_on_border_of_unpopulated_only_is_not_populated(self):
        """Epicenter only on border of unpopulated zone → not populated."""
        event = _make_event(31, magnitude=4.5, depth_km=30.0, x=500.0, y=500.0)
        assert event.in_populated_zone is False
        assert event.priority == Priority.MEDIUM

    def test_outside_all_zones(self):
        """Epicenter outside all zones → not populated."""
        event = _make_event(32, magnitude=5.0, depth_km=20.0, x=50.0, y=50.0)
        assert event.in_populated_zone is False
        assert event.priority == Priority.MEDIUM


class TestPriorityCorrectionCase:
    """
    Section 16 mandatory case: correction that changes priority.

    Event starts at M=4.8, H=70.0 → P=2 (MEDIUM).
    Corrected to M=6.2, H=15.0 → P=3 (HIGH).
    """

    def test_correction_changes_priority(self):
        """M=4.8 → M=6.2 changes priority from MEDIUM to HIGH."""
        event = _make_event(42, magnitude=4.8, depth_km=70.0, x=600.0, y=600.0)
        assert event.priority == Priority.MEDIUM
        assert event.revision == 1

        # Apply correction
        new_key = event.apply_correction(
            magnitude=6.2,
            depth_km=15.0,
            zones=ZONES,
        )

        assert event.priority == Priority.HIGH
        assert event.magnitude == 6.2
        assert event.depth_km == 15.0
        assert event.revision == 2
        assert new_key.priority == 3
        assert new_key.magnitude == 6.2
        assert new_key.event_id == 42


class TestEventValidation:
    """Data validation tests."""

    def test_valid_data_no_errors(self):
        errors = SeismicEvent.validate_data(
            event_id=1, magnitude=5.0, depth_km=50.0,
            epicenter_x=500.0, epicenter_y=500.0,
            occurrence_time=CLOCK, simulation_clock=CLOCK,
        )
        assert errors == []

    def test_id_out_of_range(self):
        errors = SeismicEvent.validate_data(
            event_id=0, magnitude=5.0, depth_km=50.0,
            epicenter_x=500.0, epicenter_y=500.0,
            occurrence_time=CLOCK, simulation_clock=CLOCK,
        )
        assert len(errors) == 1
        assert "event_id" in errors[0]

    def test_magnitude_out_of_range(self):
        errors = SeismicEvent.validate_data(
            event_id=1, magnitude=10.1, depth_km=50.0,
            epicenter_x=500.0, epicenter_y=500.0,
            occurrence_time=CLOCK, simulation_clock=CLOCK,
        )
        assert len(errors) == 1
        assert "magnitude" in errors[0]

    def test_future_time_rejected(self):
        future = datetime(2026, 12, 1, 0, 0, 0)
        errors = SeismicEvent.validate_data(
            event_id=1, magnitude=5.0, depth_km=50.0,
            epicenter_x=500.0, epicenter_y=500.0,
            occurrence_time=future, simulation_clock=CLOCK,
        )
        assert len(errors) == 1
        assert "occurrence_time" in errors[0]

    def test_multiple_errors(self):
        errors = SeismicEvent.validate_data(
            event_id=0, magnitude=11.0, depth_km=800.0,
            epicenter_x=-1.0, epicenter_y=1001.0,
            occurrence_time=CLOCK, simulation_clock=CLOCK,
        )
        assert len(errors) == 5  # id, mag, depth, x, y


class TestEventFormatId:
    """Event ID formatting."""

    def test_format_id_padded(self):
        event = _make_event(10, magnitude=3.0, depth_km=50.0, x=500.0, y=500.0)
        assert event.format_id() == "SIS-000010"

    def test_format_id_large(self):
        event = _make_event(999999, magnitude=3.0, depth_km=50.0, x=500.0, y=500.0)
        assert event.format_id() == "SIS-999999"
