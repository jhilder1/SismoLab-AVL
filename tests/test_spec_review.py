"""
Regression tests for the gaps found when checking the project against the spec:

  1. The interface bridge crashed on ISO times with 'Z' and kept sub-second
     precision when creating an event or enqueuing a report (Section 3).
  2. Marking an already reviewed event recorded an action that changed nothing (Section 6).
  3. The global recovery only reported rotation counts; it now also reports the
     imbalances it detected, each rotation it applied and the height before
     and after (Section 8: "Se muestran los cambios y su costo").
  4. The bundled insertion files overwrote the L the user set before loading (Section 9).

Run with: python -m unittest tests.test_spec_review -v
"""

import os
import sys
import unittest
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import main
from core.avl_tree import AVLTree, TreeKey
from core.tree_compare import _DummyEvent
from tests.test_storage import T0, make_scenario

DATA = os.path.join(ROOT, "data")


class BridgeTimesTest(unittest.TestCase):
    """main.py parses times like every other entry point (Section 3)."""

    def setUp(self):
        self.original = main.sc
        main.sc = make_scenario()

    def tearDown(self):
        main.sc = self.original

    def test_create_event_accepts_z_suffix_and_keeps_seconds_only(self):
        res = main.create_event(1, 5.0, 10.0, 100.0, 100.0, "2026-09-07T10:00:00.700Z", "EST-001")
        self.assertTrue(res["ok"], res["message"])
        self.assertEqual(main.sc.get_event(1).occurrence_time, datetime(2026, 9, 7, 10, 0, 0))

    def test_enqueue_report_accepts_z_suffix(self):
        res = main.enqueue_report(2, 1, "EST-001", 5.0, 10.0, 100.0, 100.0, "2026-09-07T10:00:00Z")
        self.assertTrue(res["ok"], res["message"])
        self.assertEqual(main.sc.report_queue.peek().occurrence_time, datetime(2026, 9, 7, 10))

    def test_interface_datetime_local_text_still_works(self):
        res = main.create_event(3, 5.0, 10.0, 100.0, 100.0, "2026-09-07T10:00", "EST-001")
        self.assertTrue(res["ok"], res["message"])


class MarkReviewedTwiceTest(unittest.TestCase):

    def test_second_mark_is_refused_and_records_nothing(self):
        sc = make_scenario()
        sc.create_event(10, 3.0, 10.0, 100.0, 100.0, T0, "EST-001")
        sc.mark_reviewed(10)
        depth = sc.undo_stack.size()
        with self.assertRaises(ValueError):
            sc.mark_reviewed(10)
        self.assertEqual(sc.undo_stack.size(), depth)

    def test_a_correction_makes_it_markable_again(self):
        sc = make_scenario()
        sc.create_event(10, 3.0, 10.0, 100.0, 100.0, T0, "EST-001")
        sc.mark_reviewed(10)
        sc.correct_event(10, depth_km=20.0)
        sc.mark_reviewed(10)
        self.assertEqual(sc.get_event(10).attention_state.value, "reviewed")


class RecoveryReportTest(unittest.TestCase):
    """Section 8: the recovery shows what it detected, what it changed and its cost."""

    def degenerate_tree(self, n=12):
        tree = AVLTree()
        tree.stress_mode = True
        for i in range(1, n + 1):
            tree.insert(_DummyEvent(TreeKey(1, 1.0, i)))   # ascending: a right chain
        return tree

    def test_report_lists_imbalances_steps_and_heights(self):
        tree = self.degenerate_tree()
        expected_unbalanced = [n.event_id for n in _preorder(tree.root) if abs(n.balance_factor) > 1]
        cost = tree.recover_balance()

        self.assertEqual(cost["height_before"], 11)
        self.assertEqual([u["event_id"] for u in cost["unbalanced_before"]], expected_unbalanced)
        self.assertTrue(any(abs(u["balance_factor"]) > 2 for u in cost["unbalanced_before"]))
        cases = sum(cost[k] for k in ("ll", "rr", "lr", "rl"))
        self.assertEqual(len(cost["steps"]), cases)
        for step in cost["steps"]:
            self.assertIn(step["case"], ("LL", "RR", "LR", "RL"))
            self.assertGreater(abs(step["balance_factor"]), 1)
        self.assertTrue(tree.is_balanced())
        self.assertLess(cost["final_height"], cost["height_before"])

    def test_normal_insertions_do_not_collect_steps(self):
        tree = AVLTree()
        for i in range(1, 30):
            tree.insert(_DummyEvent(TreeKey(1, 1.0, i)))
        self.assertIsNone(tree._rotation_log)

    def test_scenario_message_explains_the_recovery(self):
        sc = make_scenario()
        sc.toggle_stress()
        for i in range(1, 9):
            sc.create_event(i, 1.0, 10.0, 900.0, 900.0, T0, "EST-001")
        res = sc.recover_balance()
        self.assertEqual(res["result"], "RECOVERED")
        self.assertIn("desbalanceado", res["message"])
        self.assertIn(f"altura {res['cost']['height_before']} -> {res['cost']['final_height']}",
                      res["message"])
        self.assertIn(res["message"], sc.get_action_log(1)[0]["description"])


class LimitSetBeforeLoadingTest(unittest.TestCase):
    """Section 9: L is configured "antes de cargar los datos" and the load keeps it."""

    def test_bundled_insertion_files_keep_the_users_parameters(self):
        for name in ("prueba_carga_inserciones.json", "ascendente.json", "mezclado.json"):
            with self.subTest(name):
                sc = make_scenario()
                sc.update_parameters(w_hours=24, r_km=15, l_depth=1, t_archive_hours=100)
                sc.load_insertions_file(os.path.join(DATA, "insertions", name))
                self.assertEqual((sc.W_hours, sc.R_km, sc.L_depth, sc.T_archive_hours),
                                 (24.0, 15.0, 1, 100.0))


def _preorder(node):
    stack = [node] if node else []
    while stack:
        current = stack.pop()
        yield current
        stack.extend(c for c in (current.right, current.left) if c)


if __name__ == "__main__":
    unittest.main()
