"""
Test para verificar que la nueva estructura core/ y domain/ funciona.
Replica los tests clave de las estructuras y servicios originales.
"""

import sys
import os
from datetime import datetime, timedelta

# Agregar la raíz del proyecto al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.avl_tree import TreeKey, AVLTree, BSTTree
from core.linear import UndoStack, ReportQueue
from domain.models import (
    Priority, AttentionState, EventStatus,
    Epicenter, Zone, Station, Report, Association, SeismicEvent,
)
from domain.scenario import Scenario


# =====================================================================
# Tests de TreeKey
# =====================================================================

def test_treekey_comparison():
    k1 = TreeKey(1, 3.0, 10)
    k2 = TreeKey(2, 3.0, 10)
    assert k1 < k2
    k3 = TreeKey(2, 4.0, 10)
    assert k2 < k3
    k4 = TreeKey(2, 4.0, 20)
    assert k3 < k4

def test_treekey_equality():
    k1 = TreeKey(2, 5.0, 42)
    k2 = TreeKey(2, 5.0, 42)
    assert k1 == k2
    assert hash(k1) == hash(k2)

def test_treekey_serialization():
    k = TreeKey(3, 7.5, 100)
    d = k.to_dict()
    k2 = TreeKey.from_dict(d)
    assert k == k2


# =====================================================================
# Tests de AVLTree
# =====================================================================

class FakeEvent:
    """Evento falso para tests del árbol."""
    def __init__(self, eid, priority=2, magnitude=5.0):
        self.event_id = eid
        self.priority = priority
        self.magnitude = magnitude

    def build_key(self):
        return TreeKey(self.priority, self.magnitude, self.event_id)

def test_avl_insert_and_balance():
    tree = AVLTree()
    for i in range(1, 8):
        tree.insert(FakeEvent(i, 2, float(i)))
    assert tree.is_balanced()
    assert tree.size == 7

def test_avl_delete():
    tree = AVLTree()
    events = [FakeEvent(i, 2, float(i)) for i in range(1, 6)]
    for e in events:
        tree.insert(e)
    tree.delete(events[2].build_key())
    assert tree.size == 4
    assert tree.is_balanced()

def test_avl_search():
    tree = AVLTree()
    e = FakeEvent(42, 3, 7.5)
    tree.insert(e)
    node, visited = tree.search(e.build_key())
    assert node is not None
    assert node.event_id == 42

def test_avl_stress_and_recover():
    tree = AVLTree()
    tree.stress_mode = True
    for i in range(1, 20):
        tree.insert(FakeEvent(i, 2, float(i)))
    assert not tree.is_balanced() or tree.size < 4
    cost = tree.recover_balance()
    assert tree.is_balanced()
    assert tree.stress_mode is False

def test_avl_inorder():
    tree = AVLTree()
    for i in [5, 3, 7, 1, 4]:
        tree.insert(FakeEvent(i, 2, float(i)))
    keys = tree.inorder()
    ids = [k.event_id for k in keys]
    assert ids == sorted(ids)

def test_avl_to_dict():
    tree = AVLTree()
    tree.insert(FakeEvent(1, 2, 5.0))
    tree.insert(FakeEvent(2, 2, 3.0))
    d = tree.to_dict()
    assert d is not None
    assert "event_id" in d


# =====================================================================
# Tests de UndoStack y ReportQueue
# =====================================================================

def test_undo_stack():
    stack = UndoStack()
    stack.push({"type": "A"})
    stack.push({"type": "B"})
    assert stack.size() == 2
    assert stack.pop()["type"] == "B"
    assert stack.pop()["type"] == "A"
    assert stack.is_empty()

def test_report_queue():
    q = ReportQueue()
    q.enqueue("r1")
    q.enqueue("r2")
    assert q.size() == 2
    assert q.dequeue() == "r1"
    assert q.dequeue() == "r2"
    assert q.is_empty()


# =====================================================================
# Tests de Scenario (integración)
# =====================================================================

def _make_scenario():
    sc = Scenario()
    sc.stations = {"EST-001": Station("EST-001", "Estación 1")}
    sc.zones = [Zone("Centro", 0, 500, 0, 500, True)]
    sc.clock = datetime(2026, 6, 1, 12, 0, 0)
    return sc

def test_scenario_create_event():
    sc = _make_scenario()
    event = sc.create_event(1, 5.0, 50.0, 100.0, 100.0,
                            datetime(2026, 6, 1, 10, 0, 0), "EST-001")
    assert event.event_id == 1
    assert sc.avl.size == 1
    assert 1 in sc.event_index

def test_scenario_correct_event():
    sc = _make_scenario()
    sc.create_event(1, 5.0, 50.0, 100.0, 100.0,
                    datetime(2026, 6, 1, 10, 0, 0), "EST-001")
    event = sc.correct_event(1, magnitude=7.0)
    assert event.magnitude == 7.0
    assert event.revision == 2

def test_scenario_delete_event():
    sc = _make_scenario()
    sc.create_event(1, 5.0, 50.0, 100.0, 100.0,
                    datetime(2026, 6, 1, 10, 0, 0), "EST-001")
    sc.delete_event(1)
    assert sc.avl.size == 0
    assert 1 in sc.deleted_ids

def test_scenario_undo():
    sc = _make_scenario()
    sc.create_event(1, 5.0, 50.0, 100.0, 100.0,
                    datetime(2026, 6, 1, 10, 0, 0), "EST-001")
    assert sc.avl.size == 1
    result = sc.undo()
    assert result["result"] == "UNDONE"
    assert sc.avl.size == 0

def test_scenario_report_creates_event():
    sc = _make_scenario()
    report = Report(
        event_id=42, revision=1, station_id="EST-001",
        magnitude=4.0, depth_km=100.0,
        epicenter=Epicenter(200.0, 200.0),
        occurrence_time=datetime(2026, 6, 1, 8, 0, 0),
    )
    sc.enqueue_report(report)
    result = sc.process_next_report()
    assert result["result"] == "CREATED"
    assert 42 in sc.event_index

def test_scenario_audit():
    sc = _make_scenario()
    for i in range(1, 6):
        sc.create_event(i, 3.0 + i, 50.0, 100.0, 100.0,
                        datetime(2026, 6, 1, 10, 0, 0), "EST-001")
    audit = sc.run_audit()
    assert audit["is_valid"]

def test_scenario_stress_toggle():
    sc = _make_scenario()
    result = sc.toggle_stress()
    assert result["stress_mode"] is True
    result = sc.toggle_stress()
    assert result["stress_mode"] is False

def test_scenario_summary():
    sc = _make_scenario()
    sc.create_event(1, 5.0, 50.0, 100.0, 100.0,
                    datetime(2026, 6, 1, 10, 0, 0), "EST-001")
    s = sc.summary()
    assert s["counts"]["active"] == 1
    assert "tree" in s
    assert "rotations" in s


# =====================================================================
# Tests de Fase 1: Recorridos, BST, Reactivación, Consultas y Undo
# =====================================================================

def test_avl_all_traversals():
    tree = AVLTree()
    for i in [4, 2, 6, 1, 3, 5, 7]:
        tree.insert(FakeEvent(i, 2, float(i)))

    inorder_ids = [k.event_id for k in tree.inorder()]
    assert inorder_ids == [1, 2, 3, 4, 5, 6, 7]

    preorder_ids = [k.event_id for k in tree.preorder()]
    assert len(preorder_ids) == 7
    assert preorder_ids[0] == 4  # raíz

    postorder_ids = [k.event_id for k in tree.postorder()]
    assert len(postorder_ids) == 7
    assert postorder_ids[-1] == 4  # raíz al final

    level_ids = [k.event_id for k in tree.level_order()]
    assert level_ids == [4, 2, 6, 1, 3, 5, 7]


def test_bst_features():
    from core.avl_tree import compare_trees
    bst = BSTTree()
    keys = [TreeKey(2, float(i), i) for i in [4, 2, 6, 1, 3]]
    for k in keys:
        bst.insert(k)
    assert bst.size == 5
    assert bst.height >= 2
    assert bst.count_leaves() >= 2
    node, comps = bst.search(keys[0])
    assert node is not None
    assert comps == 1  # raíz encontrada en 1 comparación

    comp_result = compare_trees(keys)
    assert "avl" in comp_result
    assert "bst" in comp_result
    assert comp_result["avl"]["total_comparisons"] > 0


def test_reactivate_archived_event():
    sc = _make_scenario()
    e = sc.create_event(10, 3.0, 50.0, 100.0, 100.0,
                        datetime(2026, 5, 1, 10, 0, 0), "EST-001")
    sc.clock = datetime(2026, 5, 10, 10, 0, 0)
    res = sc.archive_largest_eligible()
    assert res["result"] == "ARCHIVED"
    assert 10 in sc.archived
    assert 10 not in sc.event_index
    assert sc.avl.size == 0

    rep = Report(
        event_id=10, revision=2, station_id="EST-001",
        magnitude=5.5, depth_km=20.0,
        epicenter=Epicenter(100.0, 100.0),
        occurrence_time=datetime(2026, 5, 1, 10, 0, 0),
    )
    sc.enqueue_report(rep)
    proc_res = sc.process_next_report()
    assert proc_res["result"] == "REACTIVATED"
    assert 10 in sc.event_index
    assert 10 not in sc.archived
    assert sc.avl.size == 1
    assert sc.get_event(10).magnitude == 5.5
    assert sc.get_event(10).attention_state == AttentionState.PENDING


def test_undo_restores_queue_position():
    sc = _make_scenario()
    rep = Report(
        event_id=99, revision=1, station_id="EST-001",
        magnitude=4.0, depth_km=30.0,
        epicenter=Epicenter(50.0, 50.0),
        occurrence_time=datetime(2026, 6, 1, 9, 0, 0),
    )
    sc.enqueue_report(rep)
    assert sc.report_queue.size() == 1
    sc.process_next_report()
    assert sc.report_queue.size() == 0
    assert 99 in sc.event_index

    sc.undo()
    assert 99 not in sc.event_index
    assert sc.report_queue.size() == 1
    assert sc.report_queue.peek().event_id == 99


def test_queries_section_11():
    sc = _make_scenario()
    sc.create_event(1, 4.0, 20.0, 100.0, 100.0, datetime(2026, 6, 1, 10, 0, 0), "EST-001")
    sc.create_event(2, 6.5, 15.0, 110.0, 100.0, datetime(2026, 6, 1, 9, 0, 0), "EST-001")
    sc.create_event(3, 7.0, 25.0, 105.0, 102.0, datetime(2026, 6, 1, 8, 0, 0), "EST-001")

    top = sc.query_top_k_pending(k=2)
    assert len(top["results"]) == 2
    assert top["nodes_examined"] >= 2
    assert top["results"][0]["magnitude"] >= top["results"][1]["magnitude"]

    interval_res = sc.query_by_interval(min_mag=6.0, max_mag=8.0)
    assert len(interval_res["results"]) == 2
    assert interval_res["nodes_examined"] == 3

    assoc = sc.query_event_associations(1)
    assert assoc["event_id"] == 1
    assert assoc["status"] == "ACTIVO"
    assert len(assoc["candidates"]) > 0
    assert assoc["reference"] is not None


# =====================================================================
# Ejecutar todos los tests
# =====================================================================


def load_tests(loader, standard_tests, pattern):
    """Register the plain test_* functions so `python -m unittest discover` runs them."""
    import unittest
    suite = unittest.TestSuite()
    for name, func in sorted(globals().items()):
        if name.startswith("test_") and callable(func):
            suite.addTest(unittest.FunctionTestCase(func, description=name))
    return suite


if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_")]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL {t.__name__}: {e}")
            failed += 1
    print(f"\n{'='*50}")
    print(f"Resultado: {passed} passed, {failed} failed de {passed+failed}")
