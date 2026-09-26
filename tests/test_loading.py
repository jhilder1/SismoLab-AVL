"""
Tests for Section 12: structural save, topology load and insertion load.

Uses the files in data/ (regenerate them with: python tools/make_data.py).
Run with: python -m unittest tests.test_loading -v
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from domain.models import Priority
from domain.scenario import Scenario
from domain.storage import StateError, read_json_file, scenario_to_dict
from domain.validation import check_tree
from tests.test_storage import T0, make_scenario, preorder_ids, rich_scenario

TOPOLOGIES = os.path.join(ROOT, "data", "topologies")
INSERTIONS = os.path.join(ROOT, "data", "insertions")


def topology(name):
    return os.path.join(TOPOLOGIES, name)


def insertions(name):
    return os.path.join(INSERTIONS, name)


class TempDirTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def write(self, name, data):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(data if isinstance(data, str) else json.dumps(data))
        return path

    def assert_rejected(self, sc, loader, path):
        """The load fails, the state and the undo stack stay exactly the same."""
        before = scenario_to_dict(sc)
        depth = sc.undo_stack.size()
        with self.assertRaises(StateError) as ctx:
            loader(path)
        self.assertEqual(scenario_to_dict(sc), before)
        self.assertEqual(sc.undo_stack.size(), depth)
        return ctx.exception.problems


class SaveAndTopologyLoadTest(TempDirTest):

    def test_save_then_load_gives_the_same_scenario(self):
        original = rich_scenario()
        path = os.path.join(self.tmp, "escenario.json")
        original.save_to_file(path)
        loaded = make_scenario()
        info = loaded.load_scenario_file(path)
        self.assertEqual(scenario_to_dict(loaded), scenario_to_dict(original))
        self.assertEqual(info["mode"], "stress")
        self.assertFalse(info["balanced"])
        self.assertEqual(preorder_ids(loaded.avl), preorder_ids(original.avl))

    def test_saved_file_uses_iso_dates_with_z(self):
        path = os.path.join(self.tmp, "escenario.json")
        rich_scenario().save_to_file(path)
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        self.assertEqual(data["format"], "sismolab-scenario")
        self.assertTrue(data["clock"].endswith("Z"))

    def test_load_is_one_undoable_action(self):
        sc = rich_scenario()
        before = scenario_to_dict(sc)
        sc.load_scenario_file(topology("normal.json"))
        self.assertNotEqual(scenario_to_dict(sc), before)
        self.assertEqual(sc.undo()["action_type"], "LOAD_TOPOLOGY")
        self.assertEqual(scenario_to_dict(sc), before)

    def test_normal_file_keeps_history_queue_and_balance(self):
        sc = Scenario()
        info = sc.load_scenario_file(topology("normal.json"))
        self.assertEqual(info["mode"], "normal")
        self.assertTrue(sc.avl.is_balanced())
        self.assertGreater(len(sc.archived), 0)
        self.assertEqual(sc.deleted_ids, {181})
        self.assertEqual(sc.event_index[180].attention_state.value, "reviewed")
        self.assertEqual(sc.report_queue.size(), 2)
        report = check_tree(sc.avl)
        self.assertEqual(report["order"] + report["metadata"] + report["unbalanced"], [])

    def test_correction_then_old_report_creates_no_node(self):
        # Section 16: 170 went from M=4.8/H=70 (P2) to M=6.2/H=15 (P3);
        # the queued revision 1 must be discarded without undoing the correction.
        sc = Scenario()
        sc.load_scenario_file(topology("normal.json"))
        event = sc.event_index[170]
        self.assertEqual((event.magnitude, event.depth_km, event.priority),
                         (6.2, 15.0, Priority.HIGH))
        size = sc.avl.size
        result = sc.process_next_report()
        self.assertEqual(result["result"], "OUTDATED")
        self.assertEqual(sc.avl.size, size)
        self.assertEqual(sc.event_index[170].magnitude, 6.2)

    def test_stress_file_loads_unbalanced_and_flagged(self):
        sc = Scenario()
        info = sc.load_scenario_file(topology("estres.json"))
        self.assertTrue(sc.avl.stress_mode)
        self.assertFalse(info["balanced"])
        self.assertTrue(any(abs(n["balance_factor"]) > 2 for n in info["unbalanced_nodes"]))
        self.assertEqual(check_tree(sc.avl)["order"], [])

    def test_unbalanced_file_needs_stress_mode(self):
        sc = rich_scenario()
        sc.toggle_stress()  # back to normal mode
        problems = self.assert_rejected(sc, sc.load_scenario_file,
                                        topology("desbalanceado-modo-normal.json"))
        self.assertIn("stress mode active", problems[-1])

        sc.toggle_stress()  # stress mode on: now it loads, flagged as stress
        info = sc.load_scenario_file(topology("desbalanceado-modo-normal.json"))
        self.assertEqual(info["mode"], "stress")
        self.assertFalse(info["balanced"])

    def test_wrong_order_is_rejected(self):
        sc = rich_scenario()
        problems = self.assert_rejected(sc, sc.load_scenario_file,
                                        topology("inconsistente-orden.json"))
        self.assertTrue(any("breaks the global order" in p for p in problems))

    def test_wrong_metadata_is_rejected(self):
        sc = rich_scenario()
        problems = self.assert_rejected(sc, sc.load_scenario_file,
                                        topology("inconsistente-metadatos.json"))
        text = "\n".join(problems)
        self.assertIn("stored height", text)
        self.assertIn("stored balance factor", text)
        self.assertIn("stored priority", text)

    def test_invalid_references_are_rejected(self):
        sc = rich_scenario()
        problems = self.assert_rejected(sc, sc.load_scenario_file,
                                        topology("invalido-referencias.json"))
        text = "\n".join(problems)
        self.assertIn("unknown id 999999", text)
        self.assertIn("more than one position", text)

    def test_minimal_hand_written_topology_uses_defaults(self):
        def node(event_id, left, right, height, bf, magnitude):
            return {"event_id": event_id, "left": left, "right": right,
                    "height": height, "balance_factor": bf,
                    "event": {"event_id": event_id, "magnitude": magnitude,
                              "depth_km": 10.0, "epicenter": {"x": 900, "y": 900},
                              "occurrence_time": "2026-09-07T10:00:00Z",
                              "reporting_stations": ["EST-001"]}}
        path = self.write("minimo.json", {
            "format": "sismolab-scenario",
            "clock": "2026-09-12T00:00:00Z",
            "active_tree": {"root": 2, "nodes": [
                node(2, 1, 3, 1, 0, 2.0), node(1, None, None, 0, 0, 1.0),
                node(3, None, None, 0, 0, 3.0)]},
        })
        sc = make_scenario()
        sc.load_scenario_file(path)
        self.assertEqual(preorder_ids(sc.avl), [2, 1, 3])
        self.assertEqual(preorder_ids(sc.bst), [2, 1, 3])  # BST cloned from the AVL
        self.assertEqual(sc.event_index[2].revision, 1)
        self.assertEqual(sc.W_hours, 48.0)

    def test_bad_values_are_all_reported(self):
        data = read_json_file(topology("normal.json"))
        event = data["active_tree"]["nodes"][0]["event"]
        event["magnitude"] = 4.46
        event["depth_km"] = 900.0
        event["occurrence_time"] = "2030-01-01T00:00:00Z"
        event["reporting_stations"] = ["NO-EXISTE"]
        data["parameters"]["L_depth"] = -1
        sc = rich_scenario()
        problems = self.assert_rejected(sc, sc.load_scenario_file, self.write("malo.json", data))
        text = "\n".join(problems)
        for fragment in ("at most one decimal", "depth_km", "after the simulation clock",
                         "unknown station", "L_depth"):
            self.assertIn(fragment, text)

    def test_not_json_and_wrong_format(self):
        sc = rich_scenario()
        self.assert_rejected(sc, sc.load_scenario_file, self.write("roto.json", "{ no es json"))
        problems = self.assert_rejected(sc, sc.load_scenario_file, insertions("mezclado.json"))
        self.assertIn("Cargar por inserciones", problems[0])
        problems = self.assert_rejected(sc, sc.load_insertions_file, topology("normal.json"))
        self.assertIn("Cargar escenario", problems[0])


class InsertionLoadTest(TempDirTest):

    def test_same_sequence_in_avl_and_bst(self):
        sc = Scenario()
        comparison = sc.load_insertions_file(insertions("ascendente.json"))
        n = comparison["events"]
        self.assertEqual(n, 16)
        self.assertEqual([str(k) for k in sc.avl.inorder()], [str(k) for k in sc.bst.inorder()])
        # Ascending keys: the BST becomes a list, the AVL stays logarithmic.
        self.assertEqual(comparison["bst"]["height"], n - 1)
        self.assertEqual(comparison["bst"]["leaves"], 1)
        self.assertLessEqual(comparison["avl"]["height"], 5)
        self.assertLess(comparison["avl"]["total_comparisons"],
                        comparison["bst"]["total_comparisons"])
        self.assertTrue(sc.avl.is_balanced())
        self.assertFalse(sc.avl.stress_mode)

    def test_orders_change_bst_not_the_content(self):
        a, b = Scenario(), Scenario()
        a.load_insertions_file(insertions("ascendente.json"))
        b.load_insertions_file(insertions("mezclado.json"))
        self.assertEqual([str(k) for k in a.avl.inorder()], [str(k) for k in b.avl.inorder()])
        self.assertNotEqual(a.bst.height, b.bst.height)

    def test_limit_cases_of_section_16(self):
        sc = Scenario()
        sc.load_insertions_file(insertions("mezclado.json"))
        self.assertEqual(sc.event_index[120].priority, Priority.HIGH)    # M=4.5, H=30, populated
        self.assertEqual(sc.event_index[115].priority, Priority.MEDIUM)  # same, not populated
        self.assertEqual(sc.event_index[130].priority, Priority.HIGH)    # M=6.0
        self.assertEqual(sc.event_index[118].priority, Priority.HIGH)    # on a zone border
        ties = [k.event_id for k in sc.avl.inorder() if (k.priority, k.magnitude) == (1, 3.2)]
        self.assertEqual(ties, [140, 141, 142])                          # tie broken by id

    def test_insertion_load_is_undoable_and_runs_even_in_stress(self):
        sc = rich_scenario()  # in stress mode
        before = scenario_to_dict(sc)
        sc.load_insertions_file(insertions("mezclado.json"))
        self.assertTrue(sc.avl.is_balanced())
        self.assertEqual(sc.undo()["action_type"], "LOAD_INSERTIONS")
        self.assertEqual(scenario_to_dict(sc), before)

    def test_repeated_id_invalidates_the_file(self):
        sc = rich_scenario()
        problems = self.assert_rejected(sc, sc.load_insertions_file,
                                        insertions("invalido-id-repetido.json"))
        self.assertTrue(any("is repeated" in p for p in problems))

    def test_bad_entry_rejects_the_whole_file(self):
        data = read_json_file(insertions("mezclado.json"))
        data["events"][5]["magnitude"] = 4.46
        data["events"][6]["station_id"] = "NO-EXISTE"
        sc = rich_scenario()
        problems = self.assert_rejected(sc, sc.load_insertions_file,
                                        self.write("malo.json", data))
        self.assertEqual(len(problems), 2)


class OneDecimalRuleTest(unittest.TestCase):

    def test_manual_creation_rejects_two_decimals(self):
        sc = make_scenario()
        with self.assertRaises(ValueError):
            sc.create_event(1, 4.46, 30.0, 100, 100, T0, "EST-001")
        sc.create_event(1, 4.5, 30.0, 100, 100, T0, "EST-001")
        self.assertEqual(sc.event_index[1].magnitude, 4.5)


if __name__ == "__main__":
    unittest.main()
