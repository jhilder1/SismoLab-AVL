"""
Section 16 cases on the files of data/test_cases_section16/, and the Section 8
report bursts of data/bursts/.

The cases, their steps and their expected results are written once, in
tools/section16_report.py, which prints them as evidence (expected vs
obtained). This test runs the same cases and fails when any obtained result
differs. BurstLoadTest covers the burst loader itself.

Run with: python -m unittest tests.test_section16_cases -v
"""

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from domain.scenario import Scenario
from domain.storage import StateError, scenario_to_dict

_spec = importlib.util.spec_from_file_location(
    "section16_report", os.path.join(ROOT, "tools", "section16_report.py"))
report = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(report)

NORMAL = os.path.join(ROOT, "data", "topologies", "normal.json")
BURSTS = os.path.join(ROOT, "data", "bursts")


class Section16CasesTest(unittest.TestCase):

    def run_case(self, case):
        evidence = report.Evidence()
        case(evidence)
        self.assertTrue(evidence.checks)
        for check in evidence.checks:
            with self.subTest(check=check["label"]):
                self.assertEqual(check["obtained"], check["expected"])

    def test_case1_limits_and_ties(self):
        self.run_case(report.case1_limits_and_ties)

    def test_case2_correction_and_older_report(self):
        self.run_case(report.case2_correction_and_older_report)

    def test_case3_late_report(self):
        self.run_case(report.case3_late_report)

    def test_case4_rotations_and_recovery(self):
        self.run_case(report.case4_rotations_and_recovery)

    def test_case5_mass_archive(self):
        self.run_case(report.case5_mass_archive)

    def test_case6_persistence(self):
        self.run_case(report.case6_persistence)

    def test_section8_bursts(self):
        self.run_case(report.bursts_section8)


class BurstLoadTest(unittest.TestCase):
    """Section 8: a burst enters the queue in order, as one action, or not at all."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.sc = Scenario()
        self.sc.load_scenario_file(NORMAL)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def write(self, data) -> str:
        path = os.path.join(self.tmp, "burst.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        return path

    @staticmethod
    def report(event_id, station="EST-001", **changes):
        data = {"event_id": event_id, "revision": 1, "station_id": station, "magnitude": 4.0,
                "depth_km": 10.0, "epicenter": {"x": 100, "y": 100},
                "occurrence_time": "2026-09-11T08:00:00Z"}
        data.update(changes)
        return data

    def test_reports_are_queued_in_file_order_without_being_applied(self):
        queue_before = [(r.event_id, r.revision) for r in self.sc.report_queue.get_all()]
        active_before = set(self.sc.event_index)
        info = self.sc.load_burst_file(self.write({
            "format": "sismolab-burst", "description": "prueba",
            "reports": [self.report(500, "EST-002"), self.report(501), self.report(500, "EST-003")],
        }))
        self.assertEqual((info["count"], info["stations"], info["first_position"], info["queue_size"]),
                         (3, ["EST-001", "EST-002", "EST-003"], 3, 5))
        self.assertEqual(info["description"], "prueba")
        self.assertEqual([(r.event_id, r.station_id) for r in self.sc.report_queue.get_all()][2:],
                         [(500, "EST-002"), (501, "EST-001"), (500, "EST-003")])
        self.assertEqual([(r.event_id, r.revision) for r in self.sc.report_queue.get_all()][:2],
                         queue_before)
        self.assertEqual(set(self.sc.event_index), active_before)

    def test_load_is_one_undoable_action_and_is_logged(self):
        before, depth = scenario_to_dict(self.sc), self.sc.undo_stack.size()
        self.sc.load_burst_file(os.path.join(BURSTS, "rafaga-mixta.json"))
        self.assertEqual(self.sc.undo_stack.size(), depth + 1)
        entry = self.sc.get_action_log()[0]
        self.assertEqual(entry["type"], "LOAD_BURST")
        self.assertEqual(entry["changes"], [{"name": "queue", "before": 2, "after": 14}])
        self.sc.undo()
        self.assertEqual(scenario_to_dict(self.sc), before)

    def test_one_bad_report_rejects_the_whole_burst(self):
        before, depth = scenario_to_dict(self.sc), self.sc.undo_stack.size()
        bad = {"format": "sismolab-burst", "reports": [
            self.report(500),
            self.report(501, "EST-999"),
            self.report(502, magnitude=4.25),
            self.report(503, occurrence_time="2026-09-13T00:00:00Z"),
            {k: v for k, v in self.report(504).items() if k != "revision"},
            self.report(505, revision=0),
        ]}
        with self.assertRaises(StateError) as ctx:
            self.sc.load_burst_file(self.write(bad))
        problems = ctx.exception.problems
        for expected in ("Report #2 (id 501): unknown station", "Report #3 (id 502): magnitude",
                         "Report #4 (id 503): occurrence_time", "Report #5 (id 504): missing revision",
                         "Report #6 (id 505): revision must be a positive integer"):
            self.assertTrue(any(p.startswith(expected) for p in problems), (expected, problems))
        self.assertFalse(any("Report #1" in p for p in problems))
        self.assertEqual(scenario_to_dict(self.sc), before)
        self.assertEqual(self.sc.undo_stack.size(), depth)

    def test_wrong_files_point_to_the_right_button(self):
        with self.assertRaises(StateError) as ctx:
            self.sc.load_burst_file(NORMAL)
        self.assertIn("Cargar escenario", ctx.exception.problems[0])
        with self.assertRaises(StateError) as ctx:
            self.sc.load_scenario_file(os.path.join(BURSTS, "rafaga-mixta.json"))
        self.assertIn("Cargar rafaga", ctx.exception.problems[0])
        with self.assertRaises(StateError) as ctx:
            self.sc.load_burst_file(self.write({"format": "sismolab-burst", "reports": []}))
        self.assertEqual(ctx.exception.problems, ["reports must be a non-empty list"])

    def test_concurrent_burst_keeps_receipt_order_not_priority(self):
        self.sc.load_burst_file(os.path.join(BURSTS, "rafaga-altas-concurrentes.json"))
        steps = report.run_queue(self.sc)[2:]        # after the 2 reports already queued
        created = [event_id for event_id, _, _, decision in steps if decision == "CREATED"]
        self.assertEqual(created, list(range(310, 318)))
        self.assertEqual(sum(1 for s in steps if s[3] == "CONFIRMED"), 14)
        priorities = [int(self.sc.event_index[i].priority) for i in created]
        self.assertNotEqual(priorities, sorted(priorities, reverse=True))
        for event_id in created[:-1]:
            self.assertEqual(len(self.sc.event_index[event_id].reporting_stations), 3)
        self.assertTrue(self.sc.run_audit()["is_valid"])


if __name__ == "__main__":
    unittest.main()
