import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.models.epicenter import Epicenter
from backend.models.report import Report
from backend.models.zone import Zone
from backend.models.station import Station
from backend.models.enums import Priority, AttentionState
from backend.services.scenario import Scenario
from backend.services.event_service import EventService
from backend.services.report_service import ReportService
from backend.services.association_service import AssociationService
from backend.services.archive_service import ArchiveService
from backend.services.undo_service import UndoService
from backend.services.audit_service import AuditService


def _make_scenario() -> tuple:
    """Crea un escenario de prueba con zonas y estaciones."""
    sc = Scenario()
    sc.zones = [
        Zone("Capital", 100, 300, 200, 400, True),
        Zone("Desierto", 500, 700, 500, 700, False),
    ]
    sc.stations = {
        "EST-001": Station("EST-001", "Estación Norte"),
        "EST-002": Station("EST-002", "Estación Sur"),
    }
    sc.clock = datetime(2026, 9, 10, 12, 0, 0)

    event_svc = EventService(sc)
    assoc_svc = AssociationService(sc)
    report_svc = ReportService(sc, event_svc, assoc_svc)
    archive_svc = ArchiveService(sc)
    undo_svc = UndoService(sc)
    audit_svc = AuditService(sc)

    return sc, event_svc, report_svc, assoc_svc, archive_svc, undo_svc, audit_svc


# ===== TESTS =====

def test_create_event():
    sc, event_svc, *_ = _make_scenario()

    event = event_svc.create_event(
        event_id=1, magnitude=5.5, depth_km=25.0,
        epicenter_x=200.0, epicenter_y=300.0,
        occurrence_time=datetime(2026, 9, 10, 10, 0, 0),
        station_id="EST-001",
    )
    assert event.priority == Priority.HIGH  # M=5.5, H=25, zona poblada
    assert sc.avl.size == 1
    assert sc.bst.size == 1
    assert 1 in sc.event_index


def test_create_multiple_and_audit():
    sc, event_svc, _, _, _, _, audit_svc = _make_scenario()

    event_svc.create_event(1, 6.5, 100.0, 600.0, 600.0,
                           datetime(2026, 9, 10, 8, 0), "EST-001")
    event_svc.create_event(2, 4.0, 50.0, 200.0, 300.0,
                           datetime(2026, 9, 10, 9, 0), "EST-002")
    event_svc.create_event(3, 5.0, 40.0, 150.0, 250.0,
                           datetime(2026, 9, 10, 10, 0), "EST-001")

    assert sc.avl.size == 3
    report = audit_svc.run_full_audit()
    assert report["is_valid"] is True


def test_correct_event_changes_priority():
    sc, event_svc, *_ = _make_scenario()

    event = event_svc.create_event(42, 4.8, 70.0, 600.0, 600.0,
                                   datetime(2026, 9, 10, 10, 0), "EST-001")
    assert event.priority == Priority.MEDIUM

    event = event_svc.correct_event(42, magnitude=6.2, depth_km=15.0)
    assert event.priority == Priority.HIGH
    assert event.revision == 2


def test_delete_event():
    sc, event_svc, *_ = _make_scenario()

    event_svc.create_event(1, 5.0, 50.0, 500.0, 500.0,
                           datetime(2026, 9, 10, 10, 0), "EST-001")
    event_svc.delete_event(1)

    assert sc.avl.size == 0
    assert 1 not in sc.event_index
    assert 1 in sc.deleted_ids


def test_undo_create():
    sc, event_svc, _, _, _, undo_svc, _ = _make_scenario()

    event_svc.create_event(1, 5.0, 50.0, 500.0, 500.0,
                           datetime(2026, 9, 10, 10, 0), "EST-001")
    assert sc.avl.size == 1

    result = undo_svc.undo()
    assert result["result"] == "UNDONE"
    assert sc.avl.size == 0
    assert 1 not in sc.event_index


def test_undo_delete():
    sc, event_svc, _, _, _, undo_svc, _ = _make_scenario()

    event_svc.create_event(1, 5.0, 50.0, 500.0, 500.0,
                           datetime(2026, 9, 10, 10, 0), "EST-001")
    event_svc.delete_event(1)
    assert 1 not in sc.event_index

    undo_svc.undo()  # Deshacer delete
    assert 1 in sc.event_index
    assert sc.avl.size == 1


def test_report_creates_new_event():
    sc, event_svc, report_svc, *_ = _make_scenario()

    report = Report(
        event_id=10, revision=1, station_id="EST-001",
        magnitude=5.0, depth_km=50.0,
        epicenter=Epicenter(500.0, 500.0),
        occurrence_time=datetime(2026, 9, 10, 10, 0, 0),
    )
    report_svc.enqueue(report)
    result = report_svc.process_next()

    assert result["result"] == "CREATED"
    assert 10 in sc.event_index


def test_report_confirms_event():
    sc, event_svc, report_svc, *_ = _make_scenario()

    event_svc.create_event(10, 5.0, 50.0, 500.0, 500.0,
                           datetime(2026, 9, 10, 10, 0), "EST-001")

    report = Report(
        event_id=10, revision=1, station_id="EST-002",
        magnitude=5.0, depth_km=50.0,
        epicenter=Epicenter(500.0, 500.0),
        occurrence_time=datetime(2026, 9, 10, 10, 0, 0),
    )
    report_svc.enqueue(report)
    result = report_svc.process_next()

    assert result["result"] == "CONFIRMED"
    assert "EST-002" in sc.event_index[10].reporting_stations


def test_report_corrects_event():
    sc, event_svc, report_svc, *_ = _make_scenario()

    event_svc.create_event(10, 5.0, 50.0, 500.0, 500.0,
                           datetime(2026, 9, 10, 10, 0), "EST-001")

    report = Report(
        event_id=10, revision=2, station_id="EST-002",
        magnitude=6.5, depth_km=30.0,
        epicenter=Epicenter(500.0, 500.0),
        occurrence_time=datetime(2026, 9, 10, 10, 0, 0),
    )
    report_svc.enqueue(report)
    result = report_svc.process_next()

    assert result["result"] == "CORRECTED"
    assert sc.event_index[10].magnitude == 6.5


def test_report_conflict():
    sc, event_svc, report_svc, *_ = _make_scenario()

    event_svc.create_event(10, 5.0, 50.0, 500.0, 500.0,
                           datetime(2026, 9, 10, 10, 0), "EST-001")

    report = Report(
        event_id=10, revision=1, station_id="EST-002",
        magnitude=5.5, depth_km=60.0,  # Datos diferentes!
        epicenter=Epicenter(500.0, 500.0),
        occurrence_time=datetime(2026, 9, 10, 10, 0, 0),
    )
    report_svc.enqueue(report)
    result = report_svc.process_next()

    assert result["result"] == "CONFLICT"


def test_report_outdated():
    sc, event_svc, report_svc, *_ = _make_scenario()

    event_svc.create_event(10, 5.0, 50.0, 500.0, 500.0,
                           datetime(2026, 9, 10, 10, 0), "EST-001")
    # Corregir a rev 2
    event_svc.correct_event(10, magnitude=5.5)

    # Llega reporte con rev 1 (antigua)
    report = Report(
        event_id=10, revision=1, station_id="EST-002",
        magnitude=5.0, depth_km=50.0,
        epicenter=Epicenter(500.0, 500.0),
        occurrence_time=datetime(2026, 9, 10, 10, 0, 0),
    )
    report_svc.enqueue(report)
    result = report_svc.process_next()

    assert result["result"] == "OUTDATED"


def test_association():
    sc, event_svc, _, assoc_svc, *_ = _make_scenario()

    # Evento principal grande (posible mainshock)
    event_svc.create_event(1, 6.5, 50.0, 200.0, 300.0,
                           datetime(2026, 9, 10, 8, 0), "EST-001")

    # Evento menor (posible réplica), cerca y después
    event_svc.create_event(2, 4.0, 40.0, 210.0, 310.0,
                           datetime(2026, 9, 10, 9, 0), "EST-002")

    assoc = assoc_svc.calculate_for_event(2)
    assert assoc.reference_id == 1  # Debe asociarse al evento 1


def test_stress_mode_and_recovery():
    sc, event_svc, _, _, _, _, audit_svc = _make_scenario()

    sc.avl.stress_mode = True

    # Insertar muchos eventos en orden que cause desbalance
    for i in range(1, 8):
        event_svc.create_event(i, float(i), 50.0, 500.0, 500.0,
                               datetime(2026, 9, 10, 10, 0), "EST-001")

    assert not sc.avl.is_balanced()

    sc.avl.recover_balance()
    assert sc.avl.is_balanced()

    report = audit_svc.run_full_audit()
    assert report["is_valid"] is True


def test_full_audit_after_operations():
    sc, event_svc, report_svc, assoc_svc, _, undo_svc, audit_svc = _make_scenario()

    # Crear 5 eventos
    for i in range(1, 6):
        event_svc.create_event(i, 3.0 + i, 50.0, 200.0, 300.0,
                               datetime(2026, 9, 10, i, 0), "EST-001")

    # Corregir uno
    event_svc.correct_event(3, magnitude=7.0)

    # Eliminar uno
    event_svc.delete_event(1)

    # Deshacer
    undo_svc.undo()

    # Auditar
    report = audit_svc.run_full_audit()
    assert report["is_valid"] is True
    assert 1 in sc.event_index  # Se deshizo la eliminación
