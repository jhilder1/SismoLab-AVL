"""
Validation — checks shared by file loading (Section 12) and the audit (Section 14).

Every function appends human-readable problems to a list instead of stopping at
the first one, so the user sees every cause of a rejected file at once.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Optional

from domain.models import has_max_one_decimal, parse_time


# =====================================================================
# Scalar checks
# =====================================================================

def is_int(value) -> bool:
    """True for real integers only (JSON true/false are not ids or counters)."""
    return isinstance(value, int) and not isinstance(value, bool)


def is_number(value) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def check_decimal(value, name: str, low: float, high: float,
                  where: str, problems: list[str]) -> None:
    """Section 3: finite number inside [low, high] with at most one decimal."""
    if not is_number(value):
        problems.append(f"{where}: {name} must be a number, got {value!r}")
    elif not low <= value <= high:
        problems.append(f"{where}: {name} must be between {low} and {high}, got {value}")
    elif not has_max_one_decimal(value):
        problems.append(f"{where}: {name} must have at most one decimal, got {value}")


def check_time(value, name: str, where: str, problems: list[str]) -> Optional[datetime]:
    if not isinstance(value, str):
        problems.append(f"{where}: {name} must be an ISO 8601 text, got {value!r}")
        return None
    try:
        return parse_time(value)
    except ValueError:
        problems.append(f"{where}: {name} is not a valid ISO 8601 date: {value!r}")
        return None


# =====================================================================
# Event data (Section 3)
# =====================================================================

def check_event_data(data, clock: Optional[datetime], where: str,
                     problems: list[str]) -> None:
    """Physical data shared by stored events and insertion entries."""
    if not isinstance(data, dict):
        problems.append(f"{where}: must be an object")
        return
    event_id = data.get("event_id")
    if not is_int(event_id) or not 1 <= event_id <= 999999:
        problems.append(f"{where}: event_id must be an integer between 1 and 999999, "
                        f"got {event_id!r}")
    check_decimal(data.get("magnitude"), "magnitude", -2.0, 10.0, where, problems)
    check_decimal(data.get("depth_km"), "depth_km", 0.0, 700.0, where, problems)

    epicenter = data.get("epicenter")
    if not isinstance(epicenter, dict):
        problems.append(f"{where}: epicenter must be an object with x and y")
    else:
        check_decimal(epicenter.get("x"), "epicenter.x", 0.0, 1000.0, where, problems)
        check_decimal(epicenter.get("y"), "epicenter.y", 0.0, 1000.0, where, problems)

    occurred = check_time(data.get("occurrence_time"), "occurrence_time", where, problems)
    if occurred and clock and occurred > clock:
        problems.append(f"{where}: occurrence_time {data['occurrence_time']} is after "
                        f"the simulation clock")

    revision = data.get("revision", 1)
    if not is_int(revision) or revision < 1:
        problems.append(f"{where}: revision must be a positive integer, got {revision!r}")


def check_stored_event(data, clock: Optional[datetime], station_ids: set[str],
                       expected_status: str, where: str, problems: list[str]) -> None:
    """A saved event: physical data plus provenance, attention state and status."""
    check_event_data(data, clock, where, problems)
    if not isinstance(data, dict):
        return
    stations = data.get("reporting_stations")
    if not isinstance(stations, list) or not stations:
        problems.append(f"{where}: reporting_stations must be a non-empty list")
    else:
        for station in stations:
            if station not in station_ids:
                problems.append(f"{where}: unknown station {station!r}")
    if data.get("attention_state", "pending") not in ("pending", "reviewed"):
        problems.append(f"{where}: attention_state must be 'pending' or 'reviewed'")
    status = data.get("status", expected_status)
    if status != expected_status:
        problems.append(f"{where}: status is {status!r} but the event is stored "
                        f"as {expected_status}")


# =====================================================================
# Tree checks (Sections 12 and 14)
# =====================================================================

def check_tree(tree, stored: Optional[dict[int, dict]] = None) -> dict:
    """Check global order by K, heights and balance factors of an AVL.

    `stored` maps event_id -> node data read from a file; when given, the
    stored height and balance_factor are compared with recalculated ones.
    Without it the heights kept in the nodes are compared (audit).
    Iterative walks, so a degenerate tree of any size cannot overflow the stack.

    Returns {"order": [...], "metadata": [...], "unbalanced": [(event_id, bf)]}.
    """
    metadata_problems: list[str] = []
    unbalanced: list[tuple[int, int]] = []

    order_problems = check_order(tree.root)

    # Heights bottom-up (empty tree = -1, leaf = 0) and balance factors.
    heights: dict[int, int] = {}
    for node in _postorder(tree.root):
        left = heights[node.left.event_id] if node.left else -1
        right = heights[node.right.event_id] if node.right else -1
        height = 1 + max(left, right)
        balance = left - right
        heights[node.event_id] = height

        saved = stored.get(node.event_id, {}) if stored is not None else None
        saved_height = saved.get("height") if saved is not None else node.height
        if saved_height != height:
            metadata_problems.append(f"Event {node.event_id}: stored height "
                                     f"{saved_height}, recalculated {height}")
        if saved is not None and saved.get("balance_factor") != balance:
            metadata_problems.append(f"Event {node.event_id}: stored balance factor "
                                     f"{saved.get('balance_factor')}, recalculated {balance}")
        if abs(balance) > 1:
            unbalanced.append((node.event_id, balance))

    return {"order": order_problems, "metadata": metadata_problems,
            "unbalanced": unbalanced}


def check_order(root) -> list[str]:
    """Global order: the in-order sequence must be strictly ascending by K.

    Checking each child against its parent is not enough (Section 14): a key
    can sit on the correct side of its parent and the wrong side of an ancestor.
    """
    problems: list[str] = []
    previous = None
    stack, node = [], root
    while stack or node:
        while node:
            stack.append(node)
            node = node.left
        node = stack.pop()
        if previous is not None and not previous.key < node.key:
            problems.append(
                f"Event {node.event_id} with key {node.key} breaks the global order: "
                f"it follows event {previous.event_id} with key {previous.key}")
        previous = node
        node = node.right
    return problems


def _postorder(root) -> list:
    """Nodes in postorder without recursion."""
    result, stack = [], [root] if root else []
    while stack:
        node = stack.pop()
        result.append(node)
        stack.extend(child for child in (node.left, node.right) if child)
    result.reverse()  # root-right-left reversed = left-right-root
    return result
