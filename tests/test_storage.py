"""
Tests for domain/storage.py: full state capture and exact rebuild.

Run with: python -m unittest tests.test_storage -v
"""

import copy
import json
import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.models import Epicenter, Report, Station, Zone, format_time, parse_time
from domain.scenario import Scenario
from domain.storage import StateError, apply_state, scenario_to_dict

T0 = datetime(2026, 9, 7, 10, 0, 0)


def make_scenario() -> Scenario:
    sc = Scenario()
    sc.zones = [Zone("Poblada", 0, 500, 0, 500, True),
                Zone("Vacia", 500, 1000, 0, 1000, False)]
    sc.stations = {"EST-001": Station("EST-001", "Norte"),
                   "EST-002": Station("EST-002", "Sur")}
    sc.clock = datetime(2026, 9, 12, 0, 0, 0)
    return sc


def rich_scenario() -> Scenario:
    """A scenario that touches every part of the state."""
    sc = make_scenario()
    for i, (mag, x) in enumerate([(5.6, 100), (4.2, 110), (6.1, 105), (3.0, 700),
                                  (2.1, 710), (4.8, 120), (1.5, 720)], start=1):
        sc.create_event(i * 10, mag, 20.0, x, 100, T0 + timedelta(minutes=5 * i), "EST-001")
    sc.mark_reviewed(10)
    sc.correct_event(60, magnitude=6.2, depth_km=15.0)
    sc.delete_event(20)
    sc.archive_branch([50])
    sc.enqueue_report(Report(30, 2, "EST-002", 6.1, 20.0, Epicenter(105, 100), T0))
    sc.enqueue_report(Report(99, 1, "EST-001", 4.0, 5.0, Epicenter(10, 10), T0))
    sc.W_hours, sc.R_km, sc.L_depth, sc.T_archive_hours = 24.0, 30.0, 2, 48.0

    # Stress mode with an ascending run leaves an unbalanced tree (|bf| > 2).
    sc.toggle_stress()
    for i in range(100, 106):
        sc.create_event(i, 7.0, 10.0, 900, 900, T0, "EST-002")
    return sc


def preorder_ids(tree) -> list[int]:
    return [key.event_id for key in tree.preorder()]


def json_round_trip(data: dict) -> dict:
    return json.loads(json.dumps(data))


class TimeFormatTest(unittest.TestCase):

    def test_format_uses_z_suffix(self):
        self.assertEqual(format_time(T0), "2026-09-07T10:00:00Z")

    def test_parse_accepts_z_offset_and_plain(self):
        self.assertEqual(parse_time("2026-09-07T10:00:00Z"), T0)
        self.assertEqual(parse_time("2026-09-07T05:00:00-05:00"), T0)
        self.assertEqual(parse_time("2026-09-07T10:00:00"), T0)
        self.assertIsNone(parse_time("2026-09-07T10:00:00Z").tzinfo)


class RoundTripTest(unittest.TestCase):

    def test_state_is_plain_json(self):
        data = scenario_to_dict(rich_scenario())
        self.assertEqual(json_round_trip(data), data)

    def test_rebuild_gives_identical_state(self):
        original = scenario_to_dict(rich_scenario())
        restored = Scenario()
        apply_state(restored, json_round_trip(original))
        self.assertEqual(scenario_to_dict(restored), original)

    def test_exact_topology_in_stress_mode(self):
        sc = rich_scenario()
        self.assertFalse(sc.avl.is_balanced())
        restored = Scenario()
        apply_state(restored, scenario_to_dict(sc))
        self.assertTrue(restored.avl.stress_mode)
        self.assertFalse(restored.avl.is_balanced())
        self.assertEqual(preorder_ids(restored.avl), preorder_ids(sc.avl))
        self.assertEqual(preorder_ids(restored.bst), preorder_ids(sc.bst))

    def test_topology_after_key_change_is_not_rebuilt_by_insertion(self):
        # Reinserting keys (the old undo) moved the root from 50 to 40 here.
        sc = make_scenario()
        sc.toggle_stress()
        for i in [40, 20, 60, 10, 30, 50, 70]:
            sc.create_event(i, 1.0, 10, 900, 900, T0, "EST-001")
        sc.correct_event(40, magnitude=3.0)
        restored = Scenario()
        apply_state(restored, scenario_to_dict(sc))
        self.assertEqual(preorder_ids(restored.avl), preorder_ids(sc.avl))
        self.assertEqual(restored.avl.root.event_id, 50)

    def test_nodes_reference_the_indexed_event_objects(self):
        restored = Scenario()
        apply_state(restored, scenario_to_dict(rich_scenario()))
        stack = [restored.avl.root]
        while stack:
            node = stack.pop()
            self.assertIs(node.event, restored.event_index[node.event_id])
            stack.extend(c for c in (node.left, node.right) if c)
        self.assertEqual(restored.avl.size, len(restored.event_index))

    def test_counters_parameters_queue_and_history(self):
        sc = rich_scenario()
        restored = Scenario()
        apply_state(restored, scenario_to_dict(sc))
        self.assertEqual(restored.avl.simple_turns_left, sc.avl.simple_turns_left)
        self.assertEqual(restored.avl.rotations_rr, sc.avl.rotations_rr)
        self.assertEqual(restored.total_corrections, 1)
        self.assertEqual((restored.W_hours, restored.R_km, restored.L_depth,
                          restored.T_archive_hours), (24.0, 30.0, 2, 48.0))
        self.assertEqual([r.event_id for r in restored.report_queue.get_all()], [30, 99])
        self.assertEqual(set(restored.archived), {50})
        self.assertEqual(restored.deleted_ids, {20})
        self.assertEqual(restored.event_index[10].attention_state.value, "reviewed")
        self.assertEqual(restored.event_index[60].revision, 2)
        self.assertEqual(restored.clock, sc.clock)

    def test_saved_state_does_not_change_afterwards(self):
        sc = rich_scenario()
        data = scenario_to_dict(sc)
        frozen = copy.deepcopy(data)
        sc.correct_event(30, magnitude=2.0)
        sc.report_queue.dequeue()
        sc.W_hours = 1.0
        self.assertEqual(data, frozen)


class AllOrNothingTest(unittest.TestCase):

    def assert_rejected_without_changes(self, corrupt):
        target = rich_scenario()
        before = scenario_to_dict(target)
        data = copy.deepcopy(before)
        corrupt(data)
        with self.assertRaises(StateError) as ctx:
            apply_state(target, data)
        self.assertEqual(scenario_to_dict(target), before)
        self.assertTrue(ctx.exception.problems)
        return ctx.exception.problems

    def test_link_to_unknown_id(self):
        def corrupt(data):
            data["active_tree"]["nodes"][0]["left"] = 424242
        problems = self.assert_rejected_without_changes(corrupt)
        self.assertTrue(any("unknown id 424242" in p for p in problems))

    def test_cycle_outside_the_root(self):
        def corrupt(data):
            nodes = data["active_tree"]["nodes"]
            leaf = next(n for n in nodes if n["left"] is None and n["right"] is None)
            parent = next(n for n in nodes if leaf["event_id"] in (n["left"], n["right"]))
            side = "left" if parent["left"] == leaf["event_id"] else "right"
            parent[side] = None          # detach the leaf ...
            leaf["left"] = leaf["event_id"]  # ... and make it point to itself
        problems = self.assert_rejected_without_changes(corrupt)
        self.assertTrue(any("not reachable" in p for p in problems))

    def test_node_with_two_parents(self):
        def corrupt(data):
            nodes = data["active_tree"]["nodes"]
            root = data["active_tree"]["root"]
            child = next(n["left"] for n in nodes if n["event_id"] == root)
            other = next(n for n in nodes if n["event_id"] not in (root, child)
                         and n["right"] is None)
            other["right"] = child
        problems = self.assert_rejected_without_changes(corrupt)
        self.assertTrue(any("more than one position" in p for p in problems))

    def test_duplicate_between_active_and_archived(self):
        def corrupt(data):
            data["archived"].append(copy.deepcopy(data["active_tree"]["nodes"][0]["event"]))
        self.assert_rejected_without_changes(corrupt)

    def test_missing_field(self):
        self.assert_rejected_without_changes(lambda data: data.pop("queue"))

    def test_wrong_schema_version(self):
        def corrupt(data):
            data["schema_version"] = 99
        self.assert_rejected_without_changes(corrupt)


if __name__ == "__main__":
    unittest.main()
