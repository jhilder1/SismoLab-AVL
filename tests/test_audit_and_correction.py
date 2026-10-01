"""
Tests for four interface requirements:

  - Section 14: "Verificar estructura" gives one report per inconsistent event.
  - Section 6: a manual correction can replace the epicenter and the time too.
  - Section 3: the clock moves forward by the hours the user asks for.
  - Section 15: tree nodes can be inspected (key and links), checked in the
    browser code by tests/js/tree_audit_ui.js.

The correction and clock tests call main.py's endpoints, the same functions
the interface calls.

Run with: python -m unittest tests.test_audit_and_correction -v
"""

import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import warnings
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.avl_tree import TreeKey
from domain.models import Priority
from domain.scenario import Scenario
from domain.storage import scenario_to_dict

NORMAL = os.path.join(ROOT, "data", "topologies", "normal.json")
DEGRADED = os.path.join(ROOT, "data", "test_cases_section16", "caso4-rotaciones-recuperacion",
                        "estres-degradado.json")


def load(path) -> Scenario:
    sc = Scenario()
    sc.load_scenario_file(path)
    return sc


def node_of(sc, event_id):
    return sc.avl.search(sc.event_index[event_id].build_key())[0]


def broken_scenario() -> Scenario:
    """normal.json with three defects on different events:
    a wrong stored height (leaf 115), a key that breaks the global order
    (leftmost node gets the largest key) and an active reference to a
    smaller event (151 -> 182), plus an archived event with a reference to a
    deleted id (141 -> 181)."""
    sc = load(NORMAL)
    node_of(sc, 115).height = 5
    leftmost = sc.avl.root
    while leftmost.left:
        leftmost = leftmost.left
    leftmost.key = TreeKey(3, 9.9, leftmost.event_id)
    sc.event_index[151].reference_event_id = 182
    sc.archived[141].reference_event_id = 181
    return sc


def import_main():
    """main.py runs eel.init("web") on import, a path relative to the project root."""
    cwd = os.getcwd()
    os.chdir(ROOT)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")   # pyparsing deprecations inside the eel package
            return importlib.import_module("main")
    finally:
        os.chdir(cwd)


class AuditReportTest(unittest.TestCase):
    """Section 14: "generará un reporte por evento inconsistente"."""

    def test_clean_tree_has_an_empty_report(self):
        audit = load(NORMAL).run_audit()
        self.assertEqual((audit["is_valid"], audit["report"], audit["errors"]), (True, [], []))

    def test_one_entry_per_inconsistent_event_with_all_its_problems(self):
        sc = broken_scenario()
        audit = sc.run_audit()
        self.assertFalse(audit["is_valid"])
        report = {entry["event_id"]: entry for entry in audit["report"]}
        self.assertEqual([e["event_id"] for e in audit["report"]], sorted(report))
        self.assertIn("stored height 5", " ".join(report[115]["problems"]))
        self.assertTrue(any("breaks the global order" in p for e in audit["report"] for p in e["problems"]))
        self.assertTrue(any("magnitud mayor" in p for p in report[151]["problems"]))
        self.assertEqual(report[141]["status"], "archived")
        self.assertTrue(any("inexistente/eliminado: 181" in p for p in report[141]["problems"]))
        self.assertEqual(report[151]["status"], "active")
        # The flat list keeps every problem exactly once.
        self.assertEqual(sorted(audit["errors"]),
                         sorted(p for entry in audit["report"] for p in entry["problems"]))

    def test_a_reference_cycle_is_reported_once_under_its_smallest_id(self):
        sc = load(NORMAL)
        sc.event_index[150].reference_event_id = 180
        sc.event_index[180].reference_event_id = 150
        audit = sc.run_audit()
        cycles = [(e["event_id"], p) for e in audit["report"] for p in e["problems"]
                  if p.startswith("Ciclo de referencias")]
        self.assertEqual(len(cycles), 1)
        self.assertEqual(cycles[0][0], 150)

    def test_stress_imbalance_is_not_in_the_report_but_normal_mode_imbalance_is(self):
        sc = load(DEGRADED)
        audit = sc.run_audit()
        self.assertEqual((audit["is_valid"], audit["is_avl"], audit["report"]), (True, False, []))
        self.assertTrue(audit["unbalanced_nodes"])

        sc.avl.stress_mode = False   # same tree, now judged as a normal-mode AVL
        audit = sc.run_audit()
        unbalanced = {n["event_id"] for n in audit["unbalanced_nodes"]}
        reported = {e["event_id"] for e in audit["report"]
                    if any("factor de balance" in p for p in e["problems"])}
        self.assertEqual(reported, unbalanced)


class CorrectionEndpointTest(unittest.TestCase):
    """Section 6: "Una corrección reemplaza uno o varios datos de un evento activo"."""

    def setUp(self):
        self.main = import_main()
        self.main.sc = load(NORMAL)
        self.sc = self.main.sc

    def test_epicenter_correction_recalculates_zone_priority_and_key(self):
        event = self.sc.event_index[115]           # M 4.5, H 30.0 at (100, 100): Sur, unpopulated
        self.assertEqual((event.priority, event.revision), (Priority.MEDIUM, 1))
        res = self.main.correct_event("115", None, None, "300", "300", None)   # into Centro
        self.assertTrue(res["ok"], res)
        self.assertEqual((event.epicenter.x, event.epicenter.y, event.priority, event.revision),
                         (300, 300, Priority.HIGH, 2))
        self.assertEqual(str(event.build_key()), "(3, 4.5, 115)")
        self.assertEqual(node_of(self.sc, 115).event, event)
        self.assertIn("prioridad HIGH", res["message"])
        self.assertTrue(self.sc.run_audit()["is_valid"])

    def test_one_coordinate_keeps_the_other(self):
        event = self.sc.event_index[115]
        self.assertTrue(self.main.correct_event("115", None, None, None, "120", None)["ok"])
        self.assertEqual((event.epicenter.x, event.epicenter.y), (100, 120))

    def test_time_correction_updates_the_associations(self):
        self.assertEqual(self.sc.event_index[151].reference_event_id, 150)
        res = self.main.correct_event("151", None, None, None, None, "2026-09-08T09:00:30")
        self.assertTrue(res["ok"], res)
        event = self.sc.event_index[151]
        self.assertEqual(event.occurrence_time, datetime(2026, 9, 8, 9, 0, 30))
        self.assertIsNone(event.reference_event_id)   # 150 (10:00) is no longer earlier

    def test_invalid_corrections_change_nothing(self):
        before, depth = scenario_to_dict(self.sc), self.sc.undo_stack.size()
        for args, expected in [
            (("151", None, None, None, None, "2026-09-13T00:00:00"), "simulation clock"),
            (("151", None, None, "1000.5", None, None), "epicenter.x"),
            (("151", None, None, None, None, None), "al menos un dato"),
            (("151", "abc", None, None, None, None), "could not convert"),
        ]:
            with self.subTest(args=args):
                res = self.main.correct_event(*args)
                self.assertFalse(res["ok"])
                self.assertIn(expected, res["message"])
                self.assertEqual(scenario_to_dict(self.sc), before)
                self.assertEqual(self.sc.undo_stack.size(), depth)

    def test_correction_is_one_undoable_action(self):
        before = scenario_to_dict(self.sc)
        self.main.correct_event("115", "5.0", "12.0", "300", "300", "2026-09-07T10:00:00")
        self.sc.undo()
        self.assertEqual(scenario_to_dict(self.sc), before)


class ClockEndpointTest(unittest.TestCase):
    """Section 3: the clock moves forward by a user action, any number of hours."""

    def setUp(self):
        self.main = import_main()
        self.main.sc = load(NORMAL)

    def test_advances_by_the_hours_given(self):
        start = self.main.sc.clock
        res = self.main.advance_clock("2.5")
        self.assertTrue(res["ok"])
        self.assertEqual(self.main.sc.clock, start + timedelta(hours=2.5))
        self.main.sc.undo()
        self.assertEqual(self.main.sc.clock, start)

    def test_rejects_hours_that_are_not_positive_numbers(self):
        start = self.main.sc.clock
        for hours, expected in [("abc", "deben ser un número"), ("0", "positivas"),
                                ("-3", "positivas"), ("", "deben ser un número")]:
            with self.subTest(hours=hours):
                res = self.main.advance_clock(hours)
                self.assertFalse(res["ok"])
                self.assertIn(expected, res["message"])
                self.assertEqual(self.main.sc.clock, start)


class TreeAndAuditUiTest(unittest.TestCase):
    """web/app.js: node tooltips, the Auditoria tab, the correction form and the
    clock field, with real answers. Runs tests/js/tree_audit_ui.js; skipped
    without Node.js."""

    def test_interface(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is not installed")
        sc = load(NORMAL)
        sc.update_parameters(l_depth=0)    # every HIGH node below the root is costly
        data = {"state": sc.summary(), "audit_broken": broken_scenario().run_audit(),
                "audit_stress": load(DEGRADED).run_audit()}
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "ui_data.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(data, handle)
            result = subprocess.run(
                [node, os.path.join(ROOT, "tests", "js", "tree_audit_ui.js"),
                 os.path.join(ROOT, "web", "app.js"), path],
                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
