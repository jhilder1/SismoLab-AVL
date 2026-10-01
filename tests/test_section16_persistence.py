"""
Section 16, case "Persistencia y consistencia", followed step by step:

  1. Save and recover a normal topology and a stress topology.
  2. Reject an inconsistent file without altering the current state.
  3. Restore a version after restarting.
  4. Undo a correction and a queue step.

Each test states its initial state, the expected result and checks the
obtained one, as Section 16 asks. The last class proves that the files in
data/ are reproducible: regenerating them gives the same content.

Run with: python -m unittest tests.test_section16_persistence -v
"""

import importlib.util
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
from domain.versions import VersionStore

DATA = os.path.join(ROOT, "data")


def data_file(*parts):
    return os.path.join(DATA, *parts)


def preorder(tree):
    return [key.event_id for key in tree.preorder()]


class Section16PersistenceTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_1a_save_and_recover_normal_topology(self):
        """Initial: data/topologies/normal.json (balanced, history, queue).
        Expected: after save + load in a new scenario, identical state and shape."""
        first = Scenario()
        first.load_scenario_file(data_file("topologies", "normal.json"))
        path = os.path.join(self.tmp, "normal-guardado.json")
        first.save_to_file(path)

        second = Scenario()
        info = second.load_scenario_file(path)

        self.assertEqual(info["mode"], "normal")
        self.assertTrue(info["balanced"])
        self.assertEqual(preorder(second.avl), preorder(first.avl))
        self.assertEqual(scenario_to_dict(second), scenario_to_dict(first))

    def test_1b_save_and_recover_stress_topology(self):
        """Initial: data/topologies/estres.json (|bf| up to 6, stress mode).
        Expected: recovered unbalanced, flagged as stress, order intact."""
        first = Scenario()
        first.load_scenario_file(data_file("topologies", "estres.json"))
        path = os.path.join(self.tmp, "estres-guardado.json")
        first.save_to_file(path)

        second = Scenario()
        info = second.load_scenario_file(path)

        self.assertEqual(info["mode"], "stress")
        self.assertFalse(info["balanced"])
        self.assertGreater(max(abs(n["balance_factor"]) for n in info["unbalanced_nodes"]), 2)
        self.assertEqual(check_tree(second.avl)["order"], [])
        self.assertEqual(scenario_to_dict(second), scenario_to_dict(first))

    def test_2_inconsistent_files_do_not_alter_the_current_state(self):
        """Initial: normal.json loaded. Expected: each damaged file is rejected
        with its cause, and the state and the undo stack stay exactly the same."""
        sc = Scenario()
        sc.load_scenario_file(data_file("topologies", "normal.json"))
        before, depth = scenario_to_dict(sc), sc.undo_stack.size()
        expected_cause = {
            "inconsistente-orden.json": "breaks the global order",
            "inconsistente-metadatos.json": "stored height",
            "invalido-referencias.json": "unknown id",
            "desbalanceado-modo-normal.json": "stress mode active",
        }
        for name, cause in expected_cause.items():
            with self.subTest(file=name):
                with self.assertRaises(StateError) as ctx:
                    sc.load_scenario_file(data_file("topologies", name))
                self.assertTrue(any(cause in p for p in ctx.exception.problems))
                self.assertEqual(scenario_to_dict(sc), before)
                self.assertEqual(sc.undo_stack.size(), depth)

    def test_3_restore_a_version_after_restarting(self):
        """Initial: normal.json saved as version "Base", then the scenario is
        changed and the program "closes". Expected: a fresh program lists
        "Base" and restores exactly the saved state."""
        folder = os.path.join(self.tmp, "versions")
        sc = Scenario()
        sc.load_scenario_file(data_file("topologies", "normal.json"))
        sc.save_version(VersionStore(folder), "Base")
        saved = scenario_to_dict(sc)
        sc.delete_event(180)
        del sc  # program closed

        restarted = Scenario()
        store = VersionStore(folder)
        versions = store.list()
        self.assertEqual([v["name"] for v in versions], ["Base"])
        restarted.restore_version(store, versions[0]["id"])
        self.assertEqual(scenario_to_dict(restarted), saved)

    def test_4a_undo_a_correction(self):
        """Initial: normal.json; event 150 has M=5.6, P3, revision 1.
        Action: correct it to M=4.0 (P1, revision 2, key changes).
        Expected: undo returns data, key, revision and tree shape."""
        sc = Scenario()
        sc.load_scenario_file(data_file("topologies", "normal.json"))
        before, shape = scenario_to_dict(sc), preorder(sc.avl)

        sc.correct_event(150, magnitude=4.0)
        self.assertEqual((sc.event_index[150].priority, sc.event_index[150].revision),
                         (Priority.LOW, 2))
        sc.undo()

        event = sc.event_index[150]
        self.assertEqual((event.magnitude, event.priority, event.revision),
                         (5.6, Priority.HIGH, 1))
        self.assertEqual(preorder(sc.avl), shape)
        self.assertEqual(scenario_to_dict(sc), before)

    def test_4b_undo_a_queue_step_that_discarded_a_report(self):
        """Initial: normal.json; queue = [170 rev 1 (older), 190 rev 1 (new)].
        Action: process one step -> 170 rev 1 is OUTDATED (170 is at rev 2).
        Expected: undo puts the report back first in the queue, counters return."""
        sc = Scenario()
        sc.load_scenario_file(data_file("topologies", "normal.json"))
        before = scenario_to_dict(sc)
        queue = [(r.event_id, r.revision) for r in sc.report_queue.get_all()]
        self.assertEqual(queue, [(170, 1), (190, 1)])

        result = sc.process_next_report()
        self.assertEqual(result["result"], "OUTDATED")
        self.assertEqual(sc.report_queue.size(), 1)
        sc.undo()

        self.assertEqual([(r.event_id, r.revision) for r in sc.report_queue.get_all()], queue)
        self.assertEqual(scenario_to_dict(sc), before)


#: Files present in data/ that make_data.py does not (and should not) regenerate:
#: they come from tools/generate_massive_data.py, which draws from an unseeded
#: random.uniform on every run and is meant for manual load testing (not a
#: Section 12/16 fixture), so it has no single reproducible content to compare
#: against.
NON_REPRODUCIBLE_FILES = {"insertions": {"prueba_carga_masiva_1500.json"}}


class ReproducibleDataTest(unittest.TestCase):

    def test_regenerated_files_match_data_folder(self):
        """tools/make_data.py rebuilds every file of data/ with the same content."""
        spec = importlib.util.spec_from_file_location(
            "make_data", os.path.join(ROOT, "tools", "make_data.py"))
        make_data = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(make_data)

        out = tempfile.mkdtemp()
        try:
            make_data.main(out_dir=out, verbose=False)
            for folder in ("insertions", "topologies", "bursts", "test_cases_section16"):
                excluded = NON_REPRODUCIBLE_FILES.get(folder, set())
                generated = json_files(os.path.join(out, folder))
                self.assertEqual(generated, sorted(
                    f for f in json_files(data_file(folder)) if f not in excluded))
                for name in generated:
                    with self.subTest(file=f"{folder}/{name}"):
                        # Compare parsed JSON: Git may change line endings on checkout.
                        self.assertEqual(read_json_file(os.path.join(out, folder, name)),
                                         read_json_file(data_file(folder, name)))
        finally:
            shutil.rmtree(out)


def json_files(folder):
    """Relative paths of every .json file under folder, subfolders included."""
    found = []
    for current, _, names in os.walk(folder):
        found += [os.path.relpath(os.path.join(current, n), folder)
                  for n in names if n.endswith(".json")]
    return sorted(found)


if __name__ == "__main__":
    unittest.main()
