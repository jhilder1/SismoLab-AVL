"""
Tests for the Section 11 queries and the Section 14 indicators:

  - query_by_magnitude prunes by K and still returns exactly the events a
    full scan would find.
  - query_by_depth_and_dates is its own query (no magnitude filter) and
    examines every node, since neither H nor the date is part of K.
  - query_costly_high_priority skips subtrees that cannot hold a HIGH key.
  - The action log records which indicators each action changed, also for
    undo and redo, so every metric on screen can be explained.

Run with: python -m unittest tests.test_queries_indicators -v
"""

import os
import random
import sys
import unittest
from datetime import timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from domain.indicators import INDICATOR_NAMES, indicators_from_state, indicators_of
from domain.models import Epicenter, Priority, Report, SeismicEvent
from domain.scenario import ACTION_LOG_SIZE, Scenario
from domain.storage import StateError
from tests.test_storage import T0, make_scenario


def random_scenario(seed: int, n: int = 120, stress: bool = False) -> Scenario:
    """n events with magnitudes across the three priority bands, half of them
    in the populated zone (x < 500) so 4.5 <= M < 6.0 gives HIGH or MEDIUM.

    Inserted straight into the trees, with the associations computed once at
    the end: create_event recalculates them after every insertion, which
    makes building a few hundred events take seconds."""
    rng = random.Random(seed)
    sc = make_scenario()
    sc.avl.stress_mode = stress
    for event_id in rng.sample(range(1, 5000), n):
        x = rng.choice([rng.randint(10, 490), rng.randint(510, 990)])
        event = SeismicEvent(event_id=event_id, magnitude=rng.randint(-20, 99) / 10,
                             depth_km=rng.randint(0, 600) / 10,
                             epicenter=Epicenter(x, rng.randint(10, 490)),
                             occurrence_time=T0 - timedelta(hours=rng.randint(0, 200)),
                             station_id="EST-001", zones=sc.zones)
        sc.avl.insert(event)
        sc.bst.insert(event.build_key())
        sc.event_index[event_id] = event
    sc.recalculate_all_associations()
    return sc


def ids(results) -> list[int]:
    return [r["event_id"] for r in results]


def depth_of(sc: Scenario, event) -> int:
    node, visited = sc.avl.search(event.build_key())
    return visited - 1


class MagnitudeQueryTest(unittest.TestCase):
    """Section 11: events in an inclusive magnitude interval, pruned by K."""

    INTERVALS = [(-2.0, 10.0), (4.5, 4.5), (6.0, 6.0), (4.4, 4.6), (5.9, 6.1),
                 (1.0, 3.0), (5.0, 5.5), (6.0, 9.9), (4.5, 5.9), (-2.0, 4.4), (7.3, 8.1)]

    def brute_force(self, sc, low, high):
        events = [e for e in sc.event_index.values() if low <= e.magnitude <= high]
        events.sort(key=lambda e: e.build_key().to_tuple(), reverse=True)
        return [e.event_id for e in events]

    def test_same_result_as_a_full_scan(self):
        for seed in range(4):
            for stress in (False, True):
                sc = random_scenario(seed, stress=stress)
                for low, high in self.INTERVALS:
                    with self.subTest(seed=seed, stress=stress, interval=(low, high)):
                        res = sc.query_by_magnitude(low, high)
                        self.assertEqual(ids(res["results"]), self.brute_force(sc, low, high))
                        self.assertEqual(res["count"], len(res["results"]))
                        self.assertLessEqual(res["nodes_examined"], sc.avl.size)

    def test_whole_subtrees_are_skipped(self):
        """With one run, only the matches and the two paths to the run's
        ends are visited: at most r + 2 (h + 1) nodes."""
        sc = random_scenario(7, n=300)
        for low, high in [(6.0, 9.9), (7.0, 7.5), (1.0, 1.0)]:
            with self.subTest(interval=(low, high)):
                res = sc.query_by_magnitude(low, high)
                self.assertEqual(sum(r["searched"] for r in res["runs"]), 1)
                self.assertLessEqual(res["nodes_examined"], res["count"] + 2 * (sc.avl.height + 1))
                self.assertLess(res["nodes_examined"], sc.avl.size)
                self.assertGreater(res["pruned_subtrees"], 0)

    def test_runs_say_which_priorities_are_searched(self):
        def searched(low, high):
            runs = Scenario().query_by_magnitude(low, high)["runs"]
            return {r["name"]: r.get("text") for r in runs if r["searched"]}

        self.assertEqual(searched(5.0, 5.5), {"MEDIUM": "(2, 5.0, *) a (2, 5.5, *)",
                                              "HIGH": "(3, 5.0, *) a (3, 5.5, *)"})
        self.assertEqual(searched(1.0, 4.4), {"LOW": "(1, 1.0, *) a (1, 4.4, *)"})
        self.assertEqual(searched(6.0, 7.0), {"HIGH": "(3, 6.0, *) a (3, 7.0, *)"})
        self.assertEqual(searched(4.0, 6.5), {"LOW": "(1, 4.0, *) a (1, 4.5, *)",
                                              "MEDIUM": "(2, 4.5, *) a (2, 6.0, *)",
                                              "HIGH": "(3, 4.5, *) a (3, 6.5, *)"})
        runs = Scenario().query_by_magnitude(6.0, 7.0)["runs"]
        self.assertEqual([r["rule"] for r in runs if not r["searched"]],
                         ["M < 4.5", "4.5 <= M < 6.0"])

    def test_inverted_interval_is_rejected(self):
        with self.assertRaises(ValueError):
            random_scenario(1, n=10).query_by_magnitude(6.0, 5.0)

    def test_empty_tree(self):
        res = Scenario().query_by_magnitude(1.0, 2.0)
        self.assertEqual((res["count"], res["nodes_examined"]), (0, 0))


class DepthAndDatesQueryTest(unittest.TestCase):
    """Section 11: depth <= limit inside a date interval, separate from magnitude."""

    def test_same_result_as_a_full_scan_and_every_node_examined(self):
        for stress in (False, True):
            sc = random_scenario(3, stress=stress)
            start, end = T0 - timedelta(hours=150), T0 - timedelta(hours=40)
            res = sc.query_by_depth_and_dates(25.0, start, end)
            expected = sorted((e for e in sc.event_index.values()
                               if e.depth_km <= 25.0 and start <= e.occurrence_time <= end),
                              key=lambda e: (e.occurrence_time, e.event_id))
            self.assertEqual(ids(res["results"]), [e.event_id for e in expected])
            self.assertEqual(res["nodes_examined"], sc.avl.size)

    def test_magnitude_does_not_filter_and_bounds_are_inclusive(self):
        sc = make_scenario()
        sc.create_event(1, 9.5, 30.0, 100, 100, T0, "EST-001")                         # depth == limit, at end
        sc.create_event(2, -1.0, 5.0, 700, 700, T0 - timedelta(hours=5), "EST-001")    # at start
        sc.create_event(3, 5.0, 30.1, 100, 100, T0 - timedelta(hours=2), "EST-001")    # too deep
        sc.create_event(4, 5.0, 10.0, 100, 100, T0 - timedelta(hours=6), "EST-001")    # too early
        res = sc.query_by_depth_and_dates(30.0, T0 - timedelta(hours=5), T0)
        self.assertEqual(ids(res["results"]), [2, 1])

    def test_invalid_arguments(self):
        sc = make_scenario()
        with self.assertRaises(ValueError):
            sc.query_by_depth_and_dates(10.0, T0, T0 - timedelta(hours=1))
        with self.assertRaises(ValueError):
            sc.query_by_depth_and_dates(-1.0, T0 - timedelta(hours=1), T0)


class CostlyQueryTest(unittest.TestCase):
    """Sections 9 and 11: HIGH events deeper than L, skipping non-HIGH left subtrees."""

    def test_same_result_as_searching_every_high_event(self):
        for stress in (False, True):
            for limit in (0, 2, 3):
                sc = random_scenario(5, stress=stress)
                sc.L_depth = limit
                with self.subTest(stress=stress, L=limit):
                    res = sc.query_costly_high_priority()
                    expected = {e.event_id for e in sc.event_index.values()
                                if e.priority == Priority.HIGH and depth_of(sc, e) > limit}
                    self.assertEqual(set(ids(res["costly_events"])), expected)
                    self.assertEqual(res["count"], sc.summary()["counts"]["costly_access"])
                    for c in res["costly_events"]:
                        node, visited = sc.avl.search(sc.event_index[c["event_id"]].build_key())
                        self.assertEqual(c["nodes_visited"], visited)
                        self.assertEqual(c["depth"], visited - 1)
                    self.assertLess(res["nodes_examined"], sc.avl.size)

    def test_without_high_events_only_the_right_spine_is_examined(self):
        sc = make_scenario()
        for i in range(1, 32):
            sc.create_event(i, 2.0, 10.0, 700, 700, T0, "EST-001")
        res = sc.query_costly_high_priority()
        self.assertEqual(res["count"], 0)
        self.assertEqual(res["nodes_examined"], sc.avl.height + 1)


class AssociationQueryCostTest(unittest.TestCase):

    def test_reports_no_avl_nodes_and_the_events_scanned(self):
        sc = random_scenario(2, n=30)
        some_id = next(iter(sc.event_index))
        res = sc.query_event_associations(some_id)
        self.assertEqual(res["nodes_examined"], 0)
        self.assertEqual(res["events_scanned"], 2 * (len(sc.event_index) + len(sc.archived)))


class IndicatorsTest(unittest.TestCase):
    """Section 14: the live values and the values read from a snapshot agree."""

    def busy_scenario(self, seed, stress):
        sc = random_scenario(seed, n=60, stress=stress)
        ids_ = sorted(sc.event_index)
        sc.mark_reviewed(ids_[0])
        sc.delete_event(ids_[1])
        sc.clock += timedelta(days=30)
        sc.archive_largest_eligible()
        sc.enqueue_report(Report(ids_[2], 1, "EST-002", 1.0, 10.0, Epicenter(700, 700), T0))
        sc.L_depth = 1
        return sc

    def test_live_and_snapshot_readers_agree(self):
        for seed in range(3):
            for stress in (False, True):
                sc = self.busy_scenario(seed, stress)
                with self.subTest(seed=seed, stress=stress):
                    live = indicators_of(sc)
                    self.assertEqual(indicators_from_state(sc.snapshot()), live)
                    self.assertEqual(set(live), set(INDICATOR_NAMES))
                    self.assertGreater(live["archived"], 0)
                    self.assertEqual(live["deleted"], 1)
                    self.assertEqual(live["queue"], 1)

    def test_summary_traversals_are_key_lists(self):
        sc = random_scenario(4, n=25)
        traversals = sc.summary()["traversals"]
        inorder = [tuple(k) for k in traversals["inorder"]]
        self.assertEqual(inorder, sorted(inorder))
        self.assertEqual(len(traversals["level_order"]), 25)
        self.assertEqual(traversals["level_order"][0], sc.avl.root.key.to_list())
        self.assertEqual(traversals["postorder"][-1], sc.avl.root.key.to_list())


class ActionLogTest(unittest.TestCase):
    """Section 14: "El registro de una acción debe permitir explicar cómo se
    obtuvieron sus métricas"."""

    @staticmethod
    def changes(entry) -> dict:
        return {c["name"]: (c["before"], c["after"]) for c in entry["changes"]}

    def test_create_lists_every_indicator_it_changed(self):
        sc = make_scenario()
        sc.create_event(1, 6.5, 10.0, 100, 100, T0, "EST-001")
        entry = sc.get_action_log()[0]
        self.assertEqual(entry["type"], "CREATE")
        self.assertEqual(self.changes(entry), {
            "active": (0, 1), "height": (-1, 0), "leaves": (0, 1),
            "priority_high": (0, 1), "pending": (0, 1), "events_created": (0, 1),
        })

    def test_single_and_double_rotation_cases(self):
        sc = make_scenario()
        for i, mag in enumerate((1.0, 2.0, 3.0), start=1):        # ascending: RR at the root
            sc.create_event(i, mag, 10.0, 700, 700, T0, "EST-001")
        rr = self.changes(sc.get_action_log()[0])
        self.assertEqual((rr["rr"], rr["simple_left"]), ((0, 1), (0, 1)))
        self.assertNotIn("simple_right", rr)

        sc = make_scenario()
        for i, mag in enumerate((3.0, 1.0, 2.0), start=1):        # LR: one case, two turns
            sc.create_event(i, mag, 10.0, 700, 700, T0, "EST-001")
        lr = self.changes(sc.get_action_log()[0])
        self.assertEqual((lr["lr"], lr["simple_left"], lr["simple_right"]),
                         ((0, 1), (0, 1), (0, 1)))

    def test_queue_step_explains_the_discarded_report(self):
        sc = make_scenario()
        sc.create_event(1, 5.0, 10.0, 700, 700, T0, "EST-001")
        sc.process_next_report()                                  # empty queue: not an action
        sc.correct_event(1, magnitude=5.2)                        # revision 2
        sc.enqueue_report(Report(1, 1, "EST-002", 5.0, 10.0, Epicenter(700, 700), T0))
        sc.process_next_report()
        entry = sc.get_action_log()[0]
        self.assertEqual(entry["type"], "PROCESS_REPORT")
        self.assertIn("EST-002", entry["description"])
        self.assertIn("OUTDATED", entry["description"])
        self.assertEqual(self.changes(entry), {"queue": (1, 0), "reports_processed": (0, 1),
                                               "reports_discarded": (0, 1)})

    def test_archive_counts_operation_and_events(self):
        sc = make_scenario()
        for i in range(1, 8):
            sc.create_event(i, 1.0, 10.0, 700, 700, T0, "EST-001")
        sc.clock += timedelta(days=30)
        result = sc.archive_largest_eligible()
        c = self.changes(sc.get_action_log()[0])
        self.assertEqual(c["archive_operations"], (0, 1))
        self.assertEqual(c["archives"], (0, result["count"]))
        self.assertEqual(c["archived"], (0, result["count"]))
        self.assertEqual(c["active"], (7, 7 - result["count"]))

    def test_undo_and_redo_are_logged_with_the_reverse_changes(self):
        sc = make_scenario()
        sc.create_event(1, 6.5, 10.0, 100, 100, T0, "EST-001")
        sc.undo()
        undo = sc.get_action_log()[0]
        self.assertEqual(undo["type"], "UNDO")
        self.assertIn("Crear evento", undo["description"])
        self.assertEqual(self.changes(undo)["events_created"], (1, 0))
        sc.redo()
        redo = sc.get_action_log()[0]
        self.assertEqual(redo["type"], "REDO")
        self.assertEqual(self.changes(redo)["active"], (0, 1))
        self.assertEqual([e["seq"] for e in sc.get_action_log()], [3, 2, 1])

    def test_action_without_metric_changes_has_an_empty_list(self):
        sc = make_scenario()
        sc.advance_clock(2)
        entry = sc.get_action_log()[0]
        self.assertEqual((entry["type"], entry["changes"]), ("ADVANCE_CLOCK", []))

    def test_log_is_bounded_and_not_part_of_the_saved_state(self):
        sc = make_scenario()
        for _ in range(ACTION_LOG_SIZE + 50):
            sc.advance_clock(1)
        log = sc.get_action_log()
        self.assertEqual(len(log), ACTION_LOG_SIZE)
        self.assertEqual((log[0]["seq"], log[-1]["seq"]), (ACTION_LOG_SIZE + 50, 51))
        self.assertEqual(len(sc.get_action_log(5)), 5)
        self.assertNotIn("action_log", sc.snapshot())


class IndicatorsUiTest(unittest.TestCase):
    """web/js renders the Indicadores tab, the queries and the burst loader
    from real answers.

    Runs tests/js/indicators_ui.js with the answers main.py would send for
    data/topologies/normal.json after a few actions. Skipped without Node.js.
    """

    def test_indicators_tab_and_queries_render(self):
        import json
        import shutil
        import subprocess
        import tempfile
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is not installed")

        sc = make_scenario()
        sc.load_scenario_file(os.path.join(ROOT, "data", "topologies", "normal.json"))
        sc.create_event(990001, 6.3, 12.0, 100, 100, sc.clock - timedelta(hours=1), "EST-001")
        sc.correct_event(990001, magnitude=6.8)
        sc.advance_clock(100)
        sc.archive_largest_eligible()
        sc.undo()
        data = {
            "state": sc.summary(),
            "log": sc.get_action_log(100),
            "magnitude": {"ok": True, "data": sc.query_by_magnitude(6.0, 9.9)},
            "magnitude_bad": {"ok": False, "message": "La magnitud mínima no puede ser mayor"},
            "depthdates": {"ok": True, "data": sc.query_by_depth_and_dates(
                20.0, sc.clock - timedelta(days=400), sc.clock)},
            "costly": {"ok": True, "data": sc.query_costly_high_priority()},
            "assoc": {"ok": True, "data": sc.query_event_associations(min(sc.event_index))},
        }
        bursts = os.path.join(ROOT, "data", "bursts")
        data["burst_ok"] = {"ok": True, "file": "rafaga-mixta.json",
                            "info": sc.load_burst_file(os.path.join(bursts, "rafaga-mixta.json"))}
        with self.assertRaises(StateError) as ctx:
            sc.load_burst_file(os.path.join(bursts, "rafaga-invalida.json"))
        data["burst_bad"] = {"ok": False, "file": "rafaga-invalida.json",
                             "message": "Archivo rechazado", "problems": ctx.exception.problems}
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "ui_data.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(data, handle)
            result = subprocess.run(
                [node, os.path.join(ROOT, "tests", "js", "indicators_ui.js"),
                 os.path.join(ROOT, "web", "js"), path],
                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
