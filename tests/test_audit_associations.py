"""
Tests for Scenario._audit_associations (called from run_audit, Section 14).

Before this round, it only checked that a stored reference_event_id pointed
to an event that still exists. A reference that exists but breaks one of the
Section 7 rules -- greater magnitude, strictly earlier, within W, within R --
used to pass the audit silently. These tests tamper with reference_event_id
directly (bypassing Scenario._calculate_association) to simulate that kind
of data corruption, since the normal creation/recalculation path never
produces an invalid reference on its own -- which is itself the point of the
last test below: a parameter change followed by its automatic recalculation
must leave nothing for the audit to catch.
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.models import Station, Zone
from domain.scenario import Scenario


def _make_scenario():
    sc = Scenario()
    sc.stations = {"EST-001": Station("EST-001", "Estacion 1")}
    sc.zones = [Zone("Centro", 0, 500, 0, 500, True)]
    sc.clock = datetime(2026, 6, 1, 12, 0, 0)
    return sc


def test_audit_clean_scenario_passes():
    sc = _make_scenario()
    sc.create_event(1, 6.0, 10.0, 100.0, 100.0, datetime(2026, 6, 1, 8, 0, 0), "EST-001")
    sc.create_event(2, 4.0, 10.0, 105.0, 100.0, datetime(2026, 6, 1, 9, 0, 0), "EST-001")
    assert sc.get_event(2).reference_event_id == 1

    audit = sc.run_audit()
    assert audit["is_valid"] is True
    assert audit["errors"] == []


def test_audit_reference_to_nonexistent_id():
    sc = _make_scenario()
    sc.create_event(1, 5.0, 10.0, 100.0, 100.0, datetime(2026, 6, 1, 8, 0, 0), "EST-001")
    sc.get_event(1).reference_event_id = 999999

    audit = sc.run_audit()
    assert audit["is_valid"] is False
    assert any("inexistente" in e for e in audit["errors"])


def test_audit_reference_with_lower_or_equal_magnitude():
    sc = _make_scenario()
    sc.create_event(1, 5.0, 10.0, 100.0, 100.0, datetime(2026, 6, 1, 8, 0, 0), "EST-001")
    sc.create_event(2, 6.0, 10.0, 100.0, 100.0, datetime(2026, 6, 1, 9, 0, 0), "EST-001")
    # Force 2 (M=6.0) to reference 1 (M=5.0): not strictly greater.
    sc.get_event(2).reference_event_id = 1

    audit = sc.run_audit()
    assert audit["is_valid"] is False
    assert any("magnitud mayor" in e for e in audit["errors"])


def test_audit_reference_that_did_not_occur_before():
    sc = _make_scenario()
    sc.create_event(1, 3.0, 10.0, 100.0, 100.0, datetime(2026, 6, 1, 8, 0, 0), "EST-001")
    sc.create_event(2, 6.0, 10.0, 100.0, 100.0, datetime(2026, 6, 1, 9, 0, 0), "EST-001")
    # Force 1 (earlier) to reference 2 (later, higher magnitude): time order broken.
    sc.get_event(1).reference_event_id = 2

    audit = sc.run_audit()
    assert audit["is_valid"] is False
    assert any("no ocurrió" in e for e in audit["errors"])


def test_audit_reference_outside_time_window_w():
    sc = _make_scenario()
    sc.clock = datetime(2026, 6, 4, 0, 0, 0)
    sc.W_hours = 24.0
    sc.create_event(1, 6.0, 10.0, 100.0, 100.0, datetime(2026, 6, 1, 0, 0, 0), "EST-001")
    sc.create_event(2, 4.0, 10.0, 100.0, 100.0, datetime(2026, 6, 3, 0, 0, 0), "EST-001")
    # 48h apart: too far for W=24h, so the normal calculation left no reference.
    assert sc.get_event(2).reference_event_id is None
    sc.get_event(2).reference_event_id = 1

    audit = sc.run_audit()
    assert audit["is_valid"] is False
    assert any("ventana W" in e for e in audit["errors"])


def test_audit_reference_outside_distance_r():
    sc = _make_scenario()
    sc.R_km = 10.0
    sc.create_event(1, 6.0, 10.0, 0.0, 0.0, datetime(2026, 6, 1, 8, 0, 0), "EST-001")
    sc.create_event(2, 4.0, 10.0, 500.0, 500.0, datetime(2026, 6, 1, 9, 0, 0), "EST-001")
    assert sc.get_event(2).reference_event_id is None
    sc.get_event(2).reference_event_id = 1

    audit = sc.run_audit()
    assert audit["is_valid"] is False
    assert any("distancia" in e for e in audit["errors"])


def test_audit_detects_two_event_cycle():
    sc = _make_scenario()
    sc.create_event(1, 5.0, 10.0, 100.0, 100.0, datetime(2026, 6, 1, 8, 0, 0), "EST-001")
    sc.create_event(2, 6.0, 10.0, 100.0, 100.0, datetime(2026, 6, 1, 9, 0, 0), "EST-001")
    sc.get_event(1).reference_event_id = 2
    sc.get_event(2).reference_event_id = 1

    audit = sc.run_audit()
    assert audit["is_valid"] is False
    assert any(e.startswith("Ciclo de referencias") for e in audit["errors"])


def test_audit_detects_self_reference_cycle():
    sc = _make_scenario()
    sc.create_event(1, 5.0, 10.0, 100.0, 100.0, datetime(2026, 6, 1, 8, 0, 0), "EST-001")
    sc.get_event(1).reference_event_id = 1

    audit = sc.run_audit()
    assert audit["is_valid"] is False
    assert any(e.startswith("Ciclo de referencias") for e in audit["errors"])


def test_parameter_shrink_recalculates_and_audit_stays_clean():
    """Section 7: changing W or R must recalculate associations. If it does,
    the reference that falls outside the new R disappears on its own and the
    audit finds nothing -- proving the recalculation, not a symptom fix in
    the audit itself, is what keeps the graph valid."""
    sc = _make_scenario()
    sc.update_parameters(w_hours=48.0, r_km=100.0)
    sc.create_event(1, 6.0, 10.0, 100.0, 100.0, datetime(2026, 6, 1, 8, 0, 0), "EST-001")
    sc.create_event(2, 4.0, 10.0, 150.0, 100.0, datetime(2026, 6, 1, 9, 0, 0), "EST-001")
    assert sc.get_event(2).reference_event_id == 1  # 50km, within R=100km

    sc.update_parameters(r_km=10.0)  # 50km is now outside R=10km
    assert sc.get_event(2).reference_event_id is None

    audit = sc.run_audit()
    assert audit["is_valid"] is True
    assert audit["errors"] == []
