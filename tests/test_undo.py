"""
Tests for undo (Section 13): every action returns to the exact previous state.

Run with: python -m unittest tests.test_undo -v
"""

import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.models import Epicenter, Report
from domain.storage import scenario_to_dict
from tests.test_storage import T0, make_scenario, preorder_ids, rich_scenario


class UndoRestoresExactStateTest(unittest.TestCase):

    def assert_undo_restores(self, sc, action):
        """Run `action`, undo it and check the state is identical to before."""
        before = scenario_to_dict(sc)
        depth = sc.undo_stack.size()
        action(sc)
        self.assertEqual(sc.undo_stack.size(), depth + 1, "action was not recorded")
        self.assertNotEqual(scenario_to_dict(sc), before, "action changed nothing")
        result = sc.undo()
        self.assertEqual(result["result"], "UNDONE")
        self.assertEqual(scenario_to_dict(sc), before)

    def test_create(self):
        self.assert_undo_restores(rich_scenario(), lambda sc: sc.create_event(
            500, 4.5, 30.0, 250, 250, T0, "EST-001"))

    def test_correct(self):
        self.assert_undo_restores(rich_scenario(), lambda sc: sc.correct_event(
            30, magnitude=2.0))

    def test_delete(self):
        self.assert_undo_restores(rich_scenario(), lambda sc: sc.delete_event(40))

    def test_mark_reviewed(self):
        self.assert_undo_restores(rich_scenario(), lambda sc: sc.mark_reviewed(30))

    def test_archive(self):
        self.assert_undo_restores(rich_scenario(), lambda sc: sc.archive_largest_eligible())

    def test_process_report(self):
        self.assert_undo_restores(rich_scenario(), lambda sc: sc.process_next_report())

    def test_advance_clock(self):
        self.assert_undo_restores(rich_scenario(), lambda sc: sc.advance_clock(5))

    def test_update_parameters(self):
        self.assert_undo_restores(rich_scenario(), lambda sc: sc.update_parameters(
            w_hours=10, r_km=5, l_depth=0, t_archive_hours=1))

    def test_toggle_stress(self):
        self.assert_undo_restores(rich_scenario(), lambda sc: sc.toggle_stress())

    def test_recover_balance(self):
        sc = rich_scenario()
        self.assertFalse(sc.avl.is_balanced())
        self.assert_undo_restores(sc, lambda sc: sc.recover_balance())
        self.assertFalse(sc.avl.is_balanced())
        self.assertTrue(sc.avl.stress_mode)


class UndoDetailsTest(unittest.TestCase):

    def test_topology_after_key_change(self):
        # The old undo re-inserted keys and moved the root from 50 to 40.
        sc = make_scenario()
        sc.toggle_stress()
        for i in [40, 20, 60, 10, 30, 50, 70]:
            sc.create_event(i, 1.0, 10, 900, 900, T0, "EST-001")
        sc.correct_event(40, magnitude=3.0)
        shape = preorder_ids(sc.avl)
        sc.mark_reviewed(10)
        sc.undo()
        self.assertEqual(preorder_ids(sc.avl), shape)
        self.assertEqual(sc.avl.root.event_id, 50)

    def test_rotation_counters_are_restored(self):
        sc = make_scenario()
        for i in range(1, 8):
            sc.create_event(i, 1.0, 10, 900, 900, T0, "EST-001")
        counters = (sc.avl.rotations_rr, sc.avl.simple_turns_left)
        self.assertGreater(counters[0], 0)
        sc.mark_reviewed(1)
        sc.undo()
        self.assertEqual((sc.avl.rotations_rr, sc.avl.simple_turns_left), counters)

    def test_discarded_report_returns_to_its_queue_position(self):
        sc = make_scenario()
        sc.create_event(1, 5.0, 10, 100, 100, T0, "EST-001")
        sc.correct_event(1, magnitude=5.5)  # revision 2
        old = Report(1, 1, "EST-002", 5.0, 10, Epicenter(100, 100), T0)
        new = Report(2, 1, "EST-002", 3.0, 10, Epicenter(100, 100), T0)
        sc.enqueue_report(old)
        sc.enqueue_report(new)

        result = sc.process_next_report()
        self.assertEqual(result["result"], "OUTDATED")
        self.assertEqual(sc.total_reports_discarded, 1)

        sc.undo()
        self.assertEqual([(r.event_id, r.revision) for r in sc.report_queue.get_all()],
                         [(1, 1), (2, 1)])
        self.assertEqual(sc.total_reports_discarded, 0)
        self.assertEqual(sc.total_reports_processed, 0)

    def test_several_actions_undo_in_reverse_order(self):
        sc = make_scenario()
        states = [scenario_to_dict(sc)]
        sc.create_event(1, 5.0, 10, 100, 100, T0, "EST-001")
        states.append(scenario_to_dict(sc))
        sc.advance_clock(2)
        states.append(scenario_to_dict(sc))
        sc.correct_event(1, magnitude=6.3)
        states.append(scenario_to_dict(sc))
        sc.delete_event(1)
        for expected in reversed(states):
            sc.undo()
            self.assertEqual(scenario_to_dict(sc), expected)
        self.assertEqual(sc.undo()["result"], "EMPTY")

    def test_undo_keeps_event_identity_between_index_and_tree(self):
        sc = rich_scenario()
        sc.delete_event(40)
        sc.undo()
        node, _ = sc.avl.search(sc.event_index[40].build_key())
        self.assertIs(node.event, sc.event_index[40])

    def test_invalid_clock_and_parameters_change_nothing(self):
        sc = rich_scenario()
        before = scenario_to_dict(sc)
        depth = sc.undo_stack.size()
        for bad in (0, -3):
            with self.assertRaises(ValueError):
                sc.advance_clock(bad)
        with self.assertRaises(ValueError):
            sc.update_parameters(w_hours=5, r_km=-1)
        with self.assertRaises(ValueError):
            sc.update_parameters(l_depth=1.5)
        self.assertEqual(scenario_to_dict(sc), before)
        self.assertEqual(sc.undo_stack.size(), depth)

    def test_clock_undo_restores_time(self):
        sc = make_scenario()
        start = sc.clock
        sc.advance_clock(1.5)
        self.assertEqual(sc.clock, start + timedelta(hours=1.5))
        sc.undo()
        self.assertEqual(sc.clock, start)


if __name__ == "__main__":
    unittest.main()
