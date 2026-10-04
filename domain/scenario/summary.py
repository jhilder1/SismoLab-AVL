"""
Summary — the whole visible state in one dict, for the interface
(Sections 14 and 15). Read only.
"""

from __future__ import annotations

from domain.indicators import indicators_of


def _tree_view(tree) -> dict:
    return {
        "height": tree.height,
        "leaves": tree.count_leaves(),
        "root": str(tree.root.key) if tree.root else None,
        "nodes": tree.to_dict(),
    }


class SummaryMixin:
    """`summary()`: what the front end draws after every action."""

    def summary(self) -> dict:
        """Visible indicators (Section 14) and the current parameters."""
        values = indicators_of(self)
        avl_view = _tree_view(self.avl)
        avl_view = {"height": avl_view["height"], "leaves": avl_view["leaves"],
                    "root": avl_view["root"], "balanced": self.avl.is_balanced(),
                    "nodes": avl_view["nodes"]}
        return {
            "counts": {
                "active": values["active"],
                "archived": values["archived"],
                "deleted": values["deleted"],
                "queued_reports": values["queue"],
                "undo_depth": self.undo_stack.size(),
                "priority_high": values["priority_high"],
                "priority_medium": values["priority_medium"],
                "priority_low": values["priority_low"],
                "pending": values["pending"],
                "reviewed": values["active"] - values["pending"],
                "costly_access": values["costly"],
            },
            # Every Section 14 indicator under the names the action log uses.
            "indicators": values,
            "tree": avl_view,
            "bst": _tree_view(self.bst),
            # Keys as [P, M, I] so the interface can show either the id or K.
            "traversals": {
                "inorder": [k.to_list() for k in self.avl.inorder()],
                "preorder": [k.to_list() for k in self.avl.preorder()],
                "postorder": [k.to_list() for k in self.avl.postorder()],
                "level_order": [k.to_list() for k in self.avl.level_order()],
            },
            "rotations": {
                "ll": self.avl.rotations_ll,
                "rr": self.avl.rotations_rr,
                "lr": self.avl.rotations_lr,
                "rl": self.avl.rotations_rl,
                "simple_left": self.avl.simple_turns_left,
                "simple_right": self.avl.simple_turns_right,
            },
            "metrics": {
                "events_created": self.total_events_created,
                "reports_processed": self.total_reports_processed,
                "corrections": self.total_corrections,
                "archives": self.total_archives,
                "archive_operations": self.total_archive_operations,
                "reports_discarded": self.total_reports_discarded,
                "conflicts": self.total_conflicts,
                "confirmations": self.total_confirmations,
            },
            "parameters": {
                "W_hours": self.W_hours,
                "R_km": self.R_km,
                "L_depth": self.L_depth,
                "T_archive_hours": self.T_archive_hours,
            },
            "clock": self.clock.isoformat(),
            "stress_mode": self.avl.stress_mode,
            "events": [e.to_dict() for e in self.event_index.values()],
            "archived_events": [e.to_dict() for e in self.archived.values()],
            "queued_reports": [r.to_dict() for r in self.report_queue.get_all()],
            "zones": [z.to_dict() for z in self.zones],
            "stations": [s.to_dict() for s in self.stations.values()],
        }
