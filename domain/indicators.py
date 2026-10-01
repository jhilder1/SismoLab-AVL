"""
Section 14 indicators as one flat set of named values.

The action log stores, for every action, which of these values changed and
from what to what, so each metric on screen can be explained by the actions
that produced it. Two readers return the same names:

- indicators_of(sc): the live scenario (also what the stats bar shows).
- indicators_from_state(state): a snapshot in the format of domain/storage.py,
  which is how the state before an action is kept.

tests/test_indicators.py checks that both agree on the same scenario.
"""

from domain.models import AttentionState, Priority
from domain.storage import metrics_to_dict

# Display order, grouped as the Indicadores tab shows them.
STRUCTURE = ("active", "archived", "deleted", "queue", "height", "leaves")
PRIORITY = ("priority_high", "priority_medium", "priority_low", "pending", "costly")
OPERATIONS = ("events_created", "reports_processed", "corrections", "reports_discarded",
              "conflicts", "confirmations", "archive_operations", "archives")
ROTATIONS = ("ll", "rr", "lr", "rl", "simple_left", "simple_right")
INDICATOR_NAMES = STRUCTURE + PRIORITY + OPERATIONS + ROTATIONS


def _flat_metrics(metrics: dict) -> dict:
    values = {name: metrics[name] for name in OPERATIONS}
    values.update({name: metrics["rotations"][name] for name in ROTATIONS})
    return values


def indicators_of(sc) -> dict:
    """Current values, from one O(n) walk of the active AVL.

    The walk carries each node's depth, so the costly-access count (high
    priority and depth > L, Section 9) needs no extra search per event.
    """
    by_priority = {1: 0, 2: 0, 3: 0}
    pending = costly = leaves = 0
    stack = [(sc.avl.root, 0)] if sc.avl.root else []
    while stack:
        node, depth = stack.pop()
        event = node.event
        by_priority[int(event.priority)] += 1
        if event.attention_state == AttentionState.PENDING:
            pending += 1
        if event.priority == Priority.HIGH and depth > sc.L_depth:
            costly += 1
        if not node.left and not node.right:
            leaves += 1
        for child in (node.left, node.right):
            if child:
                stack.append((child, depth + 1))
    return {
        "active": sc.avl.size,
        "archived": len(sc.archived),
        "deleted": len(sc.deleted_ids),
        "queue": sc.report_queue.size(),
        "height": sc.avl.height,
        "leaves": leaves,
        "priority_high": by_priority[3],
        "priority_medium": by_priority[2],
        "priority_low": by_priority[1],
        "pending": pending,
        "costly": costly,
        **_flat_metrics(metrics_to_dict(sc)),
    }


def indicators_from_state(state: dict) -> dict:
    """Same values read from a saved state (scenario_to_dict format)."""
    tree = state["active_tree"]
    nodes = {n["event_id"]: n for n in tree["nodes"]}
    limit = state["parameters"]["L_depth"]
    by_priority = {1: 0, 2: 0, 3: 0}
    pending = costly = leaves = 0
    stack = [(tree["root"], 0)] if tree["root"] is not None else []
    while stack:
        event_id, depth = stack.pop()
        node = nodes[event_id]
        priority = node["key"][0]
        by_priority[priority] += 1
        if node["event"]["attention_state"] == AttentionState.PENDING.value:
            pending += 1
        if priority == Priority.HIGH and depth > limit:
            costly += 1
        if node["left"] is None and node["right"] is None:
            leaves += 1
        for child in (node["left"], node["right"]):
            if child is not None:
                stack.append((child, depth + 1))
    return {
        "active": len(nodes),
        "archived": len(state["archived"]),
        "deleted": len(state["deleted_ids"]),
        "queue": len(state["queue"]["reports"]),
        "height": nodes[tree["root"]]["height"] if tree["root"] is not None else -1,
        "leaves": leaves,
        "priority_high": by_priority[3],
        "priority_medium": by_priority[2],
        "priority_low": by_priority[1],
        "pending": pending,
        "costly": costly,
        **_flat_metrics(state["metrics"]),
    }


def indicator_changes(before: dict, after: dict) -> list[dict]:
    """The indicators an action changed, in display order."""
    return [{"name": name, "before": before[name], "after": after[name]}
            for name in INDICATOR_NAMES if before[name] != after[name]]
