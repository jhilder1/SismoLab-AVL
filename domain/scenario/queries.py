"""
Queries — read-only queries and performance analysis (Section 11).

Every query reports how many AVL nodes it examined, and uses K = (P, M, I)
to skip whole subtrees whenever the key allows it.
"""

from __future__ import annotations

from datetime import datetime

from domain.loader import compare_loaded_trees
from domain.models import AttentionState, Priority


def _status_label(sc, event_id: int) -> str:
    return "ACTIVO" if event_id in sc.event_index else "ARCHIVADO"


class QueriesMixin:
    """Top-k pending, magnitude range, depth+dates, associations, costly access."""

    def query_top_k_pending(self, k: int) -> dict:
        """
        The first k events pending attention, in descending order of K.
        Walks the tree in reverse order (right to left) and stops as soon as
        it has k results. Reports how many nodes it examined.

        Iterative reverse in-order walk (explicit stack: push the right spine,
        pop, then descend left), so a degenerate tree of any size cannot
        overflow the recursion stack. The pruning happens at the same point as
        the old recursive version: a node is only counted once its whole right
        subtree has been explored, and the walk stops the instant results
        reach k, so nodes_examined matches the recursive version exactly.
        """
        if k <= 0:
            return {"results": [], "nodes_examined": 0, "k": k, "count": 0}

        results = []
        nodes_examined = 0
        stack = []
        node = self.avl.root
        while (stack or node) and len(results) < k:
            while node:
                stack.append(node)
                node = node.right
            node = stack.pop()
            nodes_examined += 1
            event = node.event
            if event and event.attention_state == AttentionState.PENDING:
                results.append(event.to_dict())
            if len(results) >= k:
                break
            node = node.left

        return {
            "results": results,
            "nodes_examined": nodes_examined,
            "k": k,
            "count": len(results),
        }

    # Section 4 bounds the priority by the magnitude: M < 4.5 is always LOW,
    # M >= 6.0 always HIGH, and 4.5 <= M < 6.0 is MEDIUM or HIGH (depth and
    # zone decide). Each band: (priority, lowest M, M it must stay below, rule).
    _MAGNITUDE_BANDS = (
        (Priority.LOW, None, 4.5, "M < 4.5"),
        (Priority.MEDIUM, 4.5, 6.0, "4.5 <= M < 6.0"),
        (Priority.HIGH, 4.5, None, "M >= 4.5"),
    )

    @classmethod
    def _magnitude_runs(cls, min_mag: float, max_mag: float) -> list[dict]:
        """The key runs that can hold an event with min_mag <= M <= max_mag.

        K = (P, M, I) orders by priority first, so those events are not one
        contiguous run of keys but up to three, one per priority the interval
        allows: from (P, lowest M, any id) to (P, highest M, any id). Every key
        inside a run has M in the interval, and no matching key is outside.
        """
        runs = []
        for priority, band_low, band_below, rule in cls._MAGNITUDE_BANDS:
            low = min_mag if band_low is None else max(min_mag, band_low)
            high = max_mag if band_below is None else min(max_mag, band_below)
            possible = (band_low is None or max_mag >= band_low) and \
                       (band_below is None or min_mag < band_below)
            run = {"priority": int(priority), "name": priority.name, "rule": rule,
                   "searched": possible}
            if possible:
                run["low"] = (int(priority), low, float("-inf"))
                run["high"] = (int(priority), high, float("inf"))
                run["text"] = f"({int(priority)}, {float(low)}, *) a ({int(priority)}, {float(high)}, *)"
            runs.append(run)
        return runs

    def query_by_magnitude(self, min_mag: float, max_mag: float) -> dict:
        """Active events with min_mag <= M <= max_mag (Section 11), pruned by K.

        Each subtree's keys lie strictly between bounds set by its ancestors
        (left of a node: below its key; right: above it). A subtree whose
        bounds miss every run of _magnitude_runs cannot hold a match, so it
        is skipped without visiting it. The walk visits the matches plus the
        nodes on the paths to each run's two ends: O(h + r) per run, with h
        the tree height and r the results (h is O(log n) in normal mode and
        up to n in stress mode).
        """
        if min_mag > max_mag:
            raise ValueError(f"La magnitud mínima ({min_mag}) no puede ser mayor que la máxima ({max_mag})")
        runs = [r for r in self._magnitude_runs(min_mag, max_mag) if r["searched"]]

        def can_hold_match(low, high):
            # None = unbounded on that side.
            return any((low is None or low < r["high"]) and (high is None or r["low"] < high)
                       for r in runs)

        matched = []
        nodes_examined = 0
        pruned_subtrees = 0
        stack = [(self.avl.root, None, None)] if self.avl.root and runs else []
        while stack:
            node, low, high = stack.pop()
            nodes_examined += 1
            if min_mag <= node.event.magnitude <= max_mag:
                matched.append(node.event)
            key = node.key.to_tuple()
            for child, child_low, child_high in ((node.right, key, high), (node.left, low, key)):
                if child is None:
                    continue
                if can_hold_match(child_low, child_high):
                    stack.append((child, child_low, child_high))
                else:
                    pruned_subtrees += 1

        matched.sort(key=lambda e: e.build_key().to_tuple(), reverse=True)
        return {
            "results": [e.to_dict() for e in matched],
            "count": len(matched),
            "nodes_examined": nodes_examined,
            "active": self.avl.size,
            "pruned_subtrees": pruned_subtrees,
            "runs": [{k: v for k, v in r.items() if k not in ("low", "high")}
                     for r in self._magnitude_runs(min_mag, max_mag)],
        }

    def query_by_depth_and_dates(self, max_depth_km: float,
                                 start: datetime, end: datetime) -> dict:
        """Active events with H <= max_depth_km that occurred between start
        and end, both inclusive (Section 11).

        Neither the hypocenter depth nor the date is part of K, so no branch
        can be ruled out by its position: every node is examined, O(n) even
        in a balanced AVL. Avoiding that would need an auxiliary index by
        date, which this project does not keep.
        """
        if max_depth_km < 0:
            raise ValueError(f"La profundidad máxima no puede ser negativa, se recibió {max_depth_km}")
        if start > end:
            raise ValueError("La fecha inicial no puede ser posterior a la final")

        matched = []
        nodes_examined = 0
        stack = [self.avl.root] if self.avl.root else []
        while stack:
            node = stack.pop()
            nodes_examined += 1
            event = node.event
            if event.depth_km <= max_depth_km and start <= event.occurrence_time <= end:
                matched.append(event)
            if node.right:
                stack.append(node.right)
            if node.left:
                stack.append(node.left)

        matched.sort(key=lambda e: (e.occurrence_time, e.event_id))
        return {
            "results": [e.to_dict() for e in matched],
            "count": len(matched),
            "nodes_examined": nodes_examined,
            "active": self.avl.size,
        }

    def query_event_associations(self, event_id: int) -> dict:
        """
        Candidates and chosen reference of an event, and the events that use
        it as their reference. Says whether each result is active or archived.
        """
        event = self._find_any(event_id)
        if not event:
            raise ValueError(f"Evento {event_id} no encontrado")

        candidates_info = []
        for c in self._find_candidates(event):
            candidates_info.append({
                "event_id": c.event_id,
                "magnitude": c.magnitude,
                "depth_km": c.depth_km,
                "distance_km": round(event.epicenter.distance_to(c.epicenter), 1),
                "time_delta_hours": round(abs((event.occurrence_time - c.occurrence_time)
                                              .total_seconds() / 3600), 1),
                "status": _status_label(self, c.event_id),
            })

        ref_info = None
        if event.reference_event_id:
            ref_event = self._find_any(event.reference_event_id)
            if ref_event:
                ref_info = {
                    "event_id": ref_event.event_id,
                    "magnitude": ref_event.magnitude,
                    "status": _status_label(self, ref_event.event_id),
                }

        # Events that use this one as their reference (replicas)
        replicas = [{"event_id": other.event_id, "magnitude": other.magnitude,
                     "status": _status_label(self, other.event_id)}
                    for other in self._all_events() if other.reference_event_id == event_id]

        # The AVL is not used here: the event comes from the id indexes, and
        # candidates and replicas come from two passes over the active and
        # archived events (the AVL does not hold the archived ones).
        return {
            "event_id": event_id,
            "status": _status_label(self, event_id),
            "reference": ref_info,
            "candidates": candidates_info,
            "replicas": replicas,
            "nodes_examined": 0,
            "events_scanned": 2 * (len(self.event_index) + len(self.archived)),
        }

    def query_costly_high_priority(self) -> dict:
        """High-priority events whose node depth exceeds L (Sections 9 and 11).

        HIGH is the largest P, so every HIGH key is greater than every other
        key. The left subtree of a node with lower priority only has smaller
        keys, hence no HIGH event: it is skipped. The walk carries each
        node's depth, and a key search visits exactly the path from the root
        to the node, so its cost is depth + 1 nodes.
        """
        results = []
        nodes_examined = 0
        pruned_subtrees = 0
        stack = [(self.avl.root, 0)] if self.avl.root else []
        while stack:
            node, depth = stack.pop()
            nodes_examined += 1
            event = node.event
            if event.priority == Priority.HIGH and depth > self.L_depth:
                results.append({
                    "event_id": event.event_id,
                    "key": str(node.key),
                    "depth": depth,
                    "limit_L": self.L_depth,
                    "nodes_visited": depth + 1,
                    "event": event.to_dict(),
                })
            if node.right:
                stack.append((node.right, depth + 1))
            if node.left:
                if node.key.priority == Priority.HIGH:
                    stack.append((node.left, depth + 1))
                else:
                    pruned_subtrees += 1

        results.sort(key=lambda r: (-r["depth"], r["event_id"]))
        return {
            "limit_L": self.L_depth,
            "costly_events": results,
            "count": len(results),
            "nodes_examined": nodes_examined,
            "active": self.avl.size,
            "pruned_subtrees": pruned_subtrees,
        }

    def compare_current_trees(self) -> dict:
        """Compare the scenario's own AVL and BST (Sections 11 and 15).

        Both trees hold the same keys and received the same operations in the
        same order, so they are compared as they are. Rebuilding them from the
        sorted keys would always describe the worst-case BST (a chain), not
        the one the user sees in the BST tab.
        """
        comparison = compare_loaded_trees(self)
        comparison["size"] = comparison["events"]
        return comparison
