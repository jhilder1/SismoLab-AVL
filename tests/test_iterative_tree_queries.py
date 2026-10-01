"""
Regression tests for the iterative conversion of the three tree walks that
used to be recursive: Scenario.query_top_k_pending, Scenario.query_by_magnitude
(formerly query_by_interval) and Scenario.find_eligible_branches (with its
_is_subtree_eligible helper).

Two kinds of test per function:
  - "no_recursion_error": run it over a genuinely degenerate tree (a straight
    chain built under stress mode, so no rotation balances it) of a size well
    past Python's default recursion limit, and check it still returns a
    sane result instead of raising RecursionError.
  - "matches_expected": run it over a small, hand-built tree (also built
    under stress mode, so its BST shape is fully predictable) and check the
    exact result, including nodes_examined, against values worked out by
    hand from the same pruning rules the old recursive version used. This is
    the semantic-equivalence check: the conversion must not change what the
    query reports, only how it walks the tree.
"""

import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.models import Epicenter, SeismicEvent, Station, Zone
from domain.scenario import Scenario


def _make_scenario():
    sc = Scenario()
    sc.stations = {"EST-001": Station("EST-001", "Estacion 1")}
    sc.zones = [Zone("Centro", 0, 500, 0, 500, True)]
    sc.clock = datetime(2026, 6, 1, 12, 0, 0)
    return sc


def _degenerate_chain(sc, count):
    """A straight chain of `count` nodes: ascending ids, same LOW magnitude
    and same occurrence_time, inserted directly into the AVL under stress
    mode (no rotation) so the shape is a genuine chain, not a balanced tree.

    Built by calling AVLTree.insert directly instead of Scenario.create_event:
    create_event also takes a full O(n) undo snapshot and an O(n) candidate
    scan per call for association recalculation, which makes building a tree
    of this size that way O(n^3) overall (irrelevant, pre-existing overhead
    unrelated to the tree walks under test here, so it is bypassed)."""
    sc.avl.stress_mode = True
    for i in range(1, count + 1):
        event = SeismicEvent(i, 3.0, 10.0, Epicenter(100.0, 100.0),
                             datetime(2026, 1, 1, 0, 0, 0), "EST-001", sc.zones)
        sc.avl.insert(event)
        sc.event_index[i] = event


def _small_bst(sc):
    """7 LOW-priority events (magnitude < 4.5, so priority is constant and the
    BST shape only depends on magnitude), inserted under stress mode in an
    order that produces a known, perfectly balanced BST:

                        id1 (M=2.0)
                 id2 (M=1.0)      id3 (M=3.0)
            id4(M=0.5) id5(M=1.5) id6(M=2.5) id7(M=3.5)

    Insertion order must be 2.0, 1.0, 3.0, 0.5, 1.5, 2.5, 3.5 for stress-mode
    (plain BST, no rotation) insertion to produce exactly this shape.
    """
    sc.toggle_stress()
    order = [(1, 2.0), (2, 1.0), (3, 3.0), (4, 0.5), (5, 1.5), (6, 2.5), (7, 3.5)]
    for event_id, magnitude in order:
        sc.create_event(event_id, magnitude, 10.0, 100.0, 100.0,
                        datetime(2026, 1, 1, 0, 0, 0), "EST-001")
    return sc


# =====================================================================
# query_top_k_pending
# =====================================================================

def test_query_top_k_pending_degenerate_tree_no_recursion_error():
    sc = _make_scenario()
    _degenerate_chain(sc, 1500)
    assert sc.avl.get_height(sc.avl.root) == 1499  # genuinely degenerate, not balanced

    result = sc.query_top_k_pending(k=5)
    assert result["count"] == 5
    assert len(result["results"]) == 5
    # Descending key order: the 5 largest ids (same magnitude for all, so id
    # is the tie-breaker) come first.
    assert [r["event_id"] for r in result["results"]] == [1500, 1499, 1498, 1497, 1496]
    assert result["nodes_examined"] == 5


def test_query_top_k_pending_matches_expected_small_tree():
    sc = _make_scenario()
    _small_bst(sc)
    # id3 (magnitude 3.0) is reviewed: it must still be visited (and counted)
    # by the reverse in-order walk, just not included in the results.
    sc.mark_reviewed(3)

    result = sc.query_top_k_pending(k=3)
    # Descending order is 3.5(id7), 3.0(id3, reviewed->skip), 2.5(id6), 2.0(id1), ...
    # so the walk must visit id7, id3, id6, id1 (4 nodes) to collect 3 pending
    # results, and stop there without touching id5/id2/id4.
    assert [r["event_id"] for r in result["results"]] == [7, 6, 1]
    assert result["nodes_examined"] == 4
    assert result["count"] == 3


def test_query_top_k_pending_k_larger_than_pending_events():
    sc = _make_scenario()
    _small_bst(sc)
    result = sc.query_top_k_pending(k=100)
    assert result["count"] == 7
    assert result["nodes_examined"] == 7


# =====================================================================
# query_by_magnitude
# =====================================================================

def test_query_by_magnitude_degenerate_tree_no_recursion_error():
    sc = _make_scenario()
    _degenerate_chain(sc, 1500)

    result = sc.query_by_magnitude(min_mag=0.0, max_mag=10.0)
    assert result["count"] == 1500
    assert result["nodes_examined"] == 1500


def test_query_by_magnitude_matches_expected_small_tree():
    sc = _make_scenario()
    _small_bst(sc)

    result = sc.query_by_magnitude(min_mag=1.0, max_mag=3.0)
    # Pruning by K skips nothing here: every subtree could still hold a key of
    # the run (1, 1.0, *) to (1, 3.0, *). id4 (M=0.5) is visited because a key
    # (1, 1.0, 1) would sit under it, and id7 (M=3.5) because (1, 3.0, 4)
    # would. tests/test_queries_indicators.py covers trees where it does skip.
    assert result["nodes_examined"] == 7
    matched_ids = {r["event_id"] for r in result["results"]}
    # magnitudes in [1.0, 3.0]: id2(1.0), id5(1.5), id1(2.0), id6(2.5), id3(3.0)
    assert matched_ids == {1, 2, 3, 5, 6}
    assert result["count"] == 5


# =====================================================================
# find_eligible_branches
# =====================================================================

def test_find_eligible_branches_degenerate_tree_no_recursion_error():
    sc = _make_scenario()
    _degenerate_chain(sc, 1500)
    # Age every event past T_archive_hours (all LOW priority already, since
    # magnitude 3.0 < 4.5).
    sc.clock = datetime(2026, 1, 1, 0, 0, 0) + timedelta(hours=sc.T_archive_hours + 1)

    branches = sc.find_eligible_branches()
    assert len(branches) == 1
    assert branches[0]["count"] == 1500
    assert branches[0]["root_depth"] == 0


def test_find_eligible_branches_tie_break_by_root_id():
    sc = _make_scenario()
    _small_bst(sc)
    # Every event starts 100h before the clock (old enough: T_archive_hours
    # default is 72h), except the root (id1), which is recent (10h old) and
    # therefore ineligible by age alone -- its priority stays LOW like every
    # other node here, so this is purely an age-based split, not a
    # priority-based one.
    sc.clock = datetime(2026, 1, 1, 0, 0, 0) + timedelta(hours=100)
    sc.get_event(1).occurrence_time = sc.clock - timedelta(hours=10)

    branches = sc.find_eligible_branches()
    # The root subtree is not eligible (id1 too recent), so the search
    # splits into id1's two children, each a fully old, fully LOW subtree of
    # 3 nodes at depth 1: {2,4,5} rooted at id2 and {3,6,7} rooted at id3.
    assert len(branches) == 2
    assert {b["root_id"] for b in branches} == {2, 3}
    for b in branches:
        assert b["count"] == 3
        assert b["root_depth"] == 1
    # Same count, same depth on both sides: the third tie-break level (higher
    # root id wins) must still decide the order, as it did before conversion.
    assert branches[0]["root_id"] == 3
    assert branches[1]["root_id"] == 2
    assert set(branches[0]["event_ids"]) == {3, 6, 7}
    assert set(branches[1]["event_ids"]) == {2, 4, 5}
