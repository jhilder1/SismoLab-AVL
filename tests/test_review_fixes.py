"""
Regression tests for the defects found in the project review:

  1. Reports with more than one decimal were rounded instead of rejected (Section 3).
  3. The AVL/BST comparison described a rebuilt BST, not the scenario's own (Section 11).
  4. Looking up an archived or deleted id answered "not found" (Section 6).
  6. Deleting did not show the affected event first (Section 6).
  7. There was no counter of mass-archive operations (Section 14).

Run with: python -m unittest tests.test_review_fixes -v
"""

import copy
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from domain.models import Epicenter, Report
from domain.scenario import Scenario
from domain.storage import StateError, read_json_file, scenario_to_dict, write_json_file
from tests.test_storage import T0, make_scenario

DATA = os.path.join(ROOT, "data")


def ascending_scenario(ids=range(1, 8)) -> Scenario:
    """Balanced AVL built from ascending keys: 1..7 gives root 4, children 2 and 6."""
    sc = make_scenario()
    for i in ids:
        sc.create_event(i, 1.0, 10.0, 900, 900, T0, "EST-001")
    return sc


class ReportDecimalsTest(unittest.TestCase):
    """Defect 1: a report is validated with the values it was sent with."""

    def test_two_decimals_are_rejected_not_rounded(self):
        sc = make_scenario()
        before, depth = scenario_to_dict(sc), sc.undo_stack.size()
        cases = {
            "magnitude": (4.46, 30.0, 10.0, 10.0),
            "depth_km": (4.5, 30.04, 10.0, 10.0),
            "epicenter.x": (4.5, 30.0, 10.06, 10.0),
            "epicenter.y": (4.5, 30.0, 10.0, 10.06),
        }
        for field, (mag, dep, x, y) in cases.items():
            with self.subTest(field=field):
                with self.assertRaises(ValueError) as ctx:
                    sc.enqueue_report(Report(5, 1, "EST-001", mag, dep, Epicenter(x, y), T0))
                self.assertIn(f"{field} must have at most one decimal", str(ctx.exception))
        self.assertEqual(scenario_to_dict(sc), before)
        self.assertEqual(sc.undo_stack.size(), depth)

    def test_rounding_would_have_changed_the_priority(self):
        # 4.46 rounded to 4.5 in a populated zone with H <= 30 is priority 3;
        # the report must be rejected instead of creating that event.
        sc = make_scenario()
        with self.assertRaises(ValueError):
            sc.enqueue_report(Report(5, 1, "EST-001", 4.46, 30.0, Epicenter(100, 100), T0))
        self.assertEqual(sc.report_queue.size(), 0)

    def test_float_noise_is_still_normalized(self):
        sc = make_scenario()
        sc.enqueue_report(Report(5, 1, "EST-001", 0.1 + 0.2, 30.0, Epicenter(0.1 + 0.2, 10), T0))
        report = sc.report_queue.peek()
        self.assertEqual((report.magnitude, report.epicenter.x), (0.3, 0.3))

    def test_queued_report_in_a_file_is_validated(self):
        data = read_json_file(os.path.join(DATA, "topologies", "normal.json"))
        data["queue"]["reports"][0]["magnitude"] = 4.46
        data["queue"]["reports"][1]["station_id"] = "NO-EXISTE"
        tmp = tempfile.mkdtemp()
        try:
            path = os.path.join(tmp, "cola-mala.json")
            write_json_file(path, data)
            sc = make_scenario()
            before = scenario_to_dict(sc)
            with self.assertRaises(StateError) as ctx:
                sc.load_scenario_file(path)
            text = "\n".join(ctx.exception.problems)
            self.assertIn("Queued report #1: magnitude must have at most one decimal", text)
            self.assertIn("Queued report #2: unknown station 'NO-EXISTE'", text)
            self.assertEqual(scenario_to_dict(sc), before)
        finally:
            shutil.rmtree(tmp)


class CurrentTreesComparisonTest(unittest.TestCase):
    """Defect 3: the comparison describes the trees the user sees."""

    def test_comparison_matches_the_scenario_bst(self):
        sc = Scenario()
        sc.load_insertions_file(os.path.join(DATA, "insertions", "mezclado.json"))
        comparison = sc.compare_current_trees()

        self.assertEqual(comparison["size"], 16)
        self.assertEqual(comparison["bst"]["height"], sc.bst.height)
        self.assertEqual(comparison["avl"]["height"], sc.avl.height)
        self.assertEqual(comparison["bst"]["root_id"], sc.bst.root.event_id)
        self.assertEqual(comparison["avl"]["root_id"], sc.avl.root.event_id)
        # Mixed order: not the chain a rebuild from sorted keys would give.
        self.assertLess(comparison["bst"]["height"], 15)

    def test_comparisons_are_real_search_costs(self):
        sc = ascending_scenario()
        comparison = sc.compare_current_trees()
        keys = sc.avl.inorder()
        for name, tree in (("avl", sc.avl), ("bst", sc.bst)):
            costs = [tree.search(k)[1] for k in keys]
            self.assertEqual(comparison[name]["total_comparisons"], sum(costs))
            self.assertEqual(comparison[name]["max_comparisons"], max(costs))
            self.assertEqual(comparison[name]["avg_comparisons"], round(sum(costs) / len(keys), 2))

    def test_empty_scenario(self):
        comparison = make_scenario().compare_current_trees()
        self.assertEqual(comparison["size"], 0)
        self.assertEqual(comparison["avl"]["avg_comparisons"], 0.0)


class LookupStatusTest(unittest.TestCase):
    """Defect 4: an id lookup says whether the event is active, archived or deleted."""

    def test_active_event_with_changed_key(self):
        sc = ascending_scenario()
        sc.correct_event(3, magnitude=6.5)  # priority and magnitude change: new key
        info = sc.lookup_event(3)
        self.assertEqual(info["status"], "active")
        self.assertEqual(info["key"], str(sc.event_index[3].build_key()))
        node, visited = sc.avl.search(sc.event_index[3].build_key())
        self.assertEqual(info["access_cost"], visited)
        self.assertEqual(info["depth"], visited - 1)
        self.assertEqual(info["height"], node.height)

    def test_archived_deleted_and_unknown(self):
        sc = make_scenario()
        old = sc.clock - timedelta(days=10)
        sc.create_event(1, 1.0, 10.0, 900, 900, old, "EST-001")
        sc.create_event(2, 5.0, 10.0, 900, 900, T0, "EST-001")
        sc._archive_ids([1])  # fixture: archive directly, no branch is eligible here
        sc.delete_event(2)

        archived = sc.lookup_event(1)
        self.assertEqual(archived["status"], "archived")
        self.assertEqual(archived["event"]["magnitude"], 1.0)
        self.assertEqual(sc.lookup_event(2), {"event_id": 2, "status": "deleted", "event": None})
        self.assertEqual(sc.lookup_event(3)["status"], "unknown")

    def test_undo_of_deletion_makes_it_active_again(self):
        sc = ascending_scenario()
        sc.delete_event(5)
        self.assertEqual(sc.lookup_event(5)["status"], "deleted")
        sc.undo()
        self.assertEqual(sc.lookup_event(5)["status"], "active")


class DeletePreviewTest(unittest.TestCase):
    """Defect 6: the event and the effects of deleting it are shown first."""

    def test_preview_lists_descendants_that_stay_active(self):
        sc = ascending_scenario()           # root 4, children 2 and 6
        preview = sc.preview_delete(2)
        self.assertEqual(preview["event"]["event_id"], 2)
        self.assertEqual(preview["depth"], 1)
        self.assertEqual(sorted(preview["descendants"]), [1, 3])

        sc.delete_event(2)
        for event_id in preview["descendants"]:
            self.assertEqual(sc.lookup_event(event_id)["status"], "active")

    def test_preview_lists_events_that_use_it_as_reference(self):
        sc = make_scenario()
        sc.create_event(10, 5.6, 20.0, 100, 100, T0, "EST-001")
        sc.create_event(11, 4.2, 20.0, 110, 105, T0 + timedelta(minutes=20), "EST-001")
        self.assertEqual(sc.event_index[11].reference_event_id, 10)
        self.assertEqual(sc.preview_delete(10)["dependents"], [11])
        sc.delete_event(10)
        self.assertIsNone(sc.event_index[11].reference_event_id)

    def test_preview_changes_nothing(self):
        sc = ascending_scenario()
        before, depth = scenario_to_dict(sc), sc.undo_stack.size()
        sc.preview_delete(4)
        self.assertEqual(scenario_to_dict(sc), before)
        self.assertEqual(sc.undo_stack.size(), depth)
        with self.assertRaises(ValueError):
            sc.preview_delete(999)


class ArchiveOperationsCounterTest(unittest.TestCase):
    """Defect 7: mass-archive operations and archived events are counted apart."""

    def old_low_scenario(self):
        sc = make_scenario()
        old = sc.clock - timedelta(days=10)
        for i in (1, 2, 3):
            sc.create_event(i, 1.0, 10.0, 900, 900, old, "EST-001")
        sc.create_event(9, 7.0, 10.0, 900, 900, T0, "EST-001")  # keeps part of the tree active
        return sc

    def test_one_operation_several_events(self):
        sc = self.old_low_scenario()
        result = sc.archive_largest_eligible()
        self.assertEqual(result["result"], "ARCHIVED")
        self.assertEqual(sc.total_archive_operations, 1)
        self.assertEqual(sc.total_archives, result["count"])
        self.assertEqual(sc.summary()["metrics"]["archive_operations"], 1)

    def test_counter_is_restored_by_undo_and_saved(self):
        sc = self.old_low_scenario()
        sc.archive_largest_eligible()
        saved = scenario_to_dict(sc)
        self.assertEqual(saved["metrics"]["archive_operations"], 1)

        restored = make_scenario()
        state = copy.deepcopy(saved)
        from domain.storage import apply_state
        apply_state(restored, state)
        self.assertEqual(restored.total_archive_operations, 1)

        sc.undo()
        self.assertEqual((sc.total_archive_operations, sc.total_archives), (0, 0))

    def test_old_files_without_the_counter_still_load(self):
        data = read_json_file(os.path.join(DATA, "topologies", "normal.json"))
        del data["metrics"]["archive_operations"]
        tmp = tempfile.mkdtemp()
        try:
            path = os.path.join(tmp, "sin-contador.json")
            write_json_file(path, data)
            sc = Scenario()
            sc.load_scenario_file(path)
            self.assertEqual(sc.total_archive_operations, 0)
        finally:
            shutil.rmtree(tmp)


class ArchiveRuleTest(unittest.TestCase):
    """Defect 2: only the branch selected by Section 10 can be archived."""

    OLD = timedelta(days=10)

    def three_low_and_four_high(self, young_low=None):
        """Ascending keys build a perfect tree: root 10 (high), left subtree
        2 -> (1, 3) all LOW, right subtree all HIGH. `young_low` is a LOW id
        that occurs recently, so it is not old enough to archive."""
        sc = make_scenario()
        for i, magnitude in ((1, 1.0), (2, 1.1), (3, 1.2)):
            when = sc.clock - timedelta(hours=1) if i == young_low else sc.clock - self.OLD
            sc.create_event(i, magnitude, 10.0, 900, 900, when, "EST-001")
        for i, magnitude in ((10, 7.0), (11, 7.1), (12, 7.2), (13, 7.3)):
            sc.create_event(i, magnitude, 10.0, 900, 900, T0, "EST-001")
        return sc

    def test_preview_shows_the_selected_branch_and_why(self):
        sc = self.three_low_and_four_high()
        before = scenario_to_dict(sc)
        preview = sc.preview_archive()
        selected = preview["selected"]
        self.assertEqual((selected["root_id"], sorted(selected["event_ids"])), (2, [1, 2, 3]))
        self.assertEqual(selected["root_depth"], 1)
        self.assertIn("prioridad BAJA", preview["justification"][0])
        self.assertIn("única rama elegible", preview["justification"][1])
        self.assertEqual(scenario_to_dict(sc), before)   # a preview changes nothing

    def test_low_root_with_a_non_eligible_descendant_is_reported(self):
        # Section 16: a LOW root is not eligible when a descendant fails the rule.
        sc = self.three_low_and_four_high(young_low=3)
        preview = sc.preview_archive()
        self.assertEqual([b["root_id"] for b in [preview["selected"]] + preview["others"]], [1])
        self.assertEqual(preview["rejected_low_roots"],
                         [{"root_id": 2, "offender_id": 3, "reason": preview["rejected_low_roots"][0]["reason"]}])
        self.assertIn("no supera T", preview["rejected_low_roots"][0]["reason"])

        sc = make_scenario()  # LOW root 2 whose right child is HIGH
        sc.create_event(2, 1.1, 10.0, 900, 900, sc.clock - self.OLD, "EST-001")
        sc.create_event(1, 1.0, 10.0, 900, 900, sc.clock - self.OLD, "EST-001")
        sc.create_event(10, 7.0, 10.0, 900, 900, T0, "EST-001")
        rejected = sc.preview_archive()["rejected_low_roots"]
        self.assertEqual([(r["root_id"], r["offender_id"], r["reason"]) for r in rejected],
                         [(2, 10, "prioridad HIGH")])

    def test_only_the_selected_set_is_accepted(self):
        sc = self.three_low_and_four_high()
        before, depth = scenario_to_dict(sc), sc.undo_stack.size()
        for wrong in ([10], [1], [1, 2], [1, 2, 3, 10]):
            with self.subTest(ids=wrong):
                with self.assertRaises(ValueError):
                    sc.archive_branch(wrong)
        self.assertEqual(scenario_to_dict(sc), before)
        self.assertEqual(sc.undo_stack.size(), depth)

        self.assertEqual(sc.archive_branch([3, 1, 2]), 3)   # order does not matter
        self.assertEqual(sorted(sc.archived), [1, 2, 3])

    def test_stale_preview_is_refused(self):
        sc = self.three_low_and_four_high()
        seen = sc.preview_archive()["selected"]["event_ids"]
        sc.correct_event(3, magnitude=7.5)   # 3 becomes HIGH: the branch changes
        before = scenario_to_dict(sc)
        with self.assertRaises(ValueError):
            sc.archive_branch(seen)
        self.assertEqual(scenario_to_dict(sc), before)

    def test_nothing_eligible(self):
        sc = ascending_scenario()            # all LOW, about 110 h old
        sc.update_parameters(t_archive_hours=1000)   # none is older than T
        preview = sc.preview_archive()
        self.assertIsNone(preview["selected"])
        with self.assertRaises(ValueError):
            sc.archive_branch([1])

    def test_tie_break_explanations(self):
        best = {"count": 3, "root_depth": 2, "root_id": 50}
        lost = Scenario._lost_tie_break
        self.assertIn("menos nodos", lost(best, {"count": 2, "root_depth": 4, "root_id": 90}))
        self.assertIn("menos profunda", lost(best, {"count": 3, "root_depth": 1, "root_id": 90}))
        self.assertIn("ID de su raíz es menor", lost(best, {"count": 3, "root_depth": 2, "root_id": 7}))


class LookupDetailsTest(unittest.TestCase):
    """Defect 5: the consultation shows every field Section 6 lists."""

    def test_active_event_has_every_field(self):
        sc = ascending_scenario()
        info = sc.lookup_event(2)
        event = info["event"]
        for field in ("magnitude", "depth_km", "epicenter", "occurrence_time", "revision",
                      "reporting_stations", "in_populated_zone", "priority", "attention_state"):
            self.assertIn(field, event)
        for field in ("key", "depth", "height", "balance_factor", "access_cost", "associations"):
            self.assertIn(field, info)
        self.assertEqual(event["reporting_stations"], ["EST-001"])

    def test_costly_flag_only_for_deep_high_priority(self):
        sc = make_scenario()
        for i, magnitude in ((1, 7.0), (2, 7.1), (3, 7.2)):   # root 2, children 1 and 3
            sc.create_event(i, magnitude, 10.0, 900, 900, T0, "EST-001")
        sc.update_parameters(l_depth=0)
        self.assertFalse(sc.lookup_event(2)["costly"])          # depth 0, not > L
        self.assertTrue(sc.lookup_event(1)["costly"])           # depth 1 > L = 0
        sc.update_parameters(l_depth=3)
        self.assertFalse(sc.lookup_event(1)["costly"])

    def test_associations_of_the_late_report_case(self):
        # Section 16 "Reporte tardío": 5.6 at 10:00 and 4.2 at 10:20, then 6.1 at 09:55.
        sc = make_scenario()
        sc.create_event(10, 5.6, 20.0, 100, 100, T0, "EST-001")
        sc.create_event(11, 4.2, 20.0, 110, 105, T0 + timedelta(minutes=20), "EST-001")
        sc.create_event(12, 6.1, 20.0, 105, 100, T0 - timedelta(minutes=5), "EST-001")

        late = sc.lookup_event(11)["associations"]
        self.assertEqual(late["reference"]["event_id"], 12)     # policy: largest magnitude
        self.assertEqual([c["event_id"] for c in late["candidates"]], [12, 10])
        main_shock = sc.lookup_event(12)["associations"]
        self.assertIsNone(main_shock["reference"])
        self.assertEqual([r["event_id"] for r in main_shock["replicas"]], [10, 11])

    def test_archived_event_keeps_its_associations(self):
        sc = make_scenario()
        old = sc.clock - timedelta(days=10)
        sc.create_event(10, 5.6, 20.0, 100, 100, old, "EST-001")
        sc.create_event(11, 4.2, 20.0, 110, 105, old + timedelta(minutes=20), "EST-001")
        sc._archive_ids([11])  # fixture
        info = sc.lookup_event(11)
        self.assertEqual(info["status"], "archived")
        self.assertEqual(info["associations"]["reference"],
                         {"event_id": 10, "magnitude": 5.6, "status": "active"})


class QueuePauseUiTest(unittest.TestCase):
    """Defect 8: web/js pauses continuous processing during a recovery.

    Runs tests/js/queue_pause.js, which loads the web/js scripts with a fake DOM and a
    fake eel. Skipped when Node.js is not installed.
    """

    def test_recovery_pauses_continuous_processing(self):
        import shutil as _shutil
        import subprocess
        node = _shutil.which("node")
        if not node:
            self.skipTest("Node.js is not installed")
        result = subprocess.run(
            [node, os.path.join(ROOT, "tests", "js", "queue_pause.js"),
             os.path.join(ROOT, "web", "js")],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
