"""
Tests for named versions (Section 13).

A "restart" is simulated with a brand-new VersionStore and Scenario that only
share the folder on disk with the ones that saved the version.
Run with: python -m unittest tests.test_versions -v
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.scenario import Scenario
from domain.storage import StateError, scenario_to_dict
from domain.versions import VersionStore
from tests.test_storage import T0, make_scenario, preorder_ids, rich_scenario


class VersionsTest(unittest.TestCase):

    def setUp(self):
        self.folder = os.path.join(tempfile.mkdtemp(), "versions")
        self.store = VersionStore(self.folder)

    def tearDown(self):
        shutil.rmtree(os.path.dirname(self.folder))

    def test_version_survives_a_restart(self):
        original = rich_scenario()
        original.save_version(self.store, "Antes de la corrección")
        expected = scenario_to_dict(original)
        del original

        # "Restart": new objects, same folder.
        store = VersionStore(self.folder)
        versions = store.list()
        self.assertEqual([v["name"] for v in versions], ["Antes de la corrección"])
        self.assertEqual(versions[0]["id"], "antes-de-la-correccion")

        restored = Scenario()
        info = restored.restore_version(store, versions[0]["id"])
        self.assertEqual(scenario_to_dict(restored), expected)
        self.assertEqual(info["mode"], "stress")
        self.assertFalse(restored.avl.is_balanced())

    def test_version_keeps_the_exact_topology(self):
        sc = make_scenario()
        sc.toggle_stress()
        for i in [40, 20, 60, 10, 30, 50, 70]:
            sc.create_event(i, 1.0, 10, 900, 900, T0, "EST-001")
        sc.correct_event(40, magnitude=3.0)
        shape = preorder_ids(sc.avl)
        sc.save_version(self.store, "forma")
        restored = Scenario()
        restored.restore_version(VersionStore(self.folder), "forma")
        self.assertEqual(preorder_ids(restored.avl), shape)
        self.assertEqual(restored.avl.root.event_id, 50)

    def test_saving_is_not_an_action_and_later_changes_do_not_alter_it(self):
        sc = rich_scenario()
        depth = sc.undo_stack.size()
        sc.save_version(self.store, "v1")
        saved = scenario_to_dict(sc)
        self.assertEqual(sc.undo_stack.size(), depth)

        sc.correct_event(30, magnitude=2.0)
        sc.advance_clock(3)
        sc.restore_version(self.store, "v1")
        self.assertEqual(scenario_to_dict(sc), saved)

    def test_restore_is_one_undoable_action(self):
        sc = rich_scenario()
        sc.save_version(self.store, "v1")
        sc.delete_event(40)
        sc.process_next_report()
        before = scenario_to_dict(sc)
        sc.restore_version(self.store, "v1")
        self.assertEqual(sc.undo()["action_type"], "RESTORE_VERSION")
        self.assertEqual(scenario_to_dict(sc), before)

    def test_version_file_has_no_undo_stack(self):
        sc = rich_scenario()
        self.assertGreater(sc.undo_stack.size(), 0)
        sc.save_version(self.store, "v1")
        with open(os.path.join(self.folder, "v1.json"), encoding="utf-8") as handle:
            data = json.load(handle)
        self.assertEqual(set(data), {"format", "name", "saved_at", "state"})
        self.assertNotIn("undo", json.dumps(data["state"]).lower())

    def test_list_is_ordered_and_names_are_unique(self):
        sc = make_scenario()
        # Reverse alphabetical names: the order must come from saving time.
        for name in ("Zeta", "Omega", "Alfa"):
            sc.save_version(self.store, name)
        self.assertEqual([v["name"] for v in self.store.list()], ["Zeta", "Omega", "Alfa"])
        with self.assertRaises(ValueError):
            sc.save_version(self.store, "  zeta ")  # same name, other case/spaces
        with self.assertRaises(ValueError):
            sc.save_version(self.store, "   ")
        with self.assertRaises(ValueError):
            sc.save_version(self.store, "x" * 61)
        self.assertEqual(len(self.store.list()), 3)

    def test_names_with_the_same_slug_get_different_files(self):
        sc = make_scenario()
        a = sc.save_version(self.store, "Prueba #1")
        b = sc.save_version(self.store, "Prueba 1")
        self.assertEqual((a["id"], b["id"]), ("prueba-1", "prueba-1-2"))

    def test_damaged_version_is_listed_and_rejected_without_changes(self):
        sc = rich_scenario()
        sc.save_version(self.store, "buena")
        path = os.path.join(self.folder, "buena.json")
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        data["state"]["active_tree"]["nodes"][0]["height"] = 99
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        with open(os.path.join(self.folder, "rota.json"), "w", encoding="utf-8") as handle:
            handle.write("{ no es json")

        listed = {v["id"]: v for v in self.store.list()}
        self.assertTrue(listed["buena"]["valid"])   # readable, fails on restore
        self.assertFalse(listed["rota"]["valid"])

        target = make_scenario()
        before = scenario_to_dict(target)
        for version_id in ("buena", "rota", "no-existe", "../fuera"):
            with self.assertRaises(StateError):
                target.restore_version(self.store, version_id)
        self.assertEqual(scenario_to_dict(target), before)
        self.assertEqual(target.undo_stack.size(), 0)

    def test_empty_folder(self):
        self.assertEqual(VersionStore(os.path.join(self.folder, "nada")).list(), [])


if __name__ == "__main__":
    unittest.main()
