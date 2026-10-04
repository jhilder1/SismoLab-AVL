"""
Balance — stress mode and global recovery of the AVL (Section 8).
"""

from __future__ import annotations

from domain.storage import apply_state


class BalanceMixin:
    """Enter/leave stress mode and rebalance the tree."""

    def _run_recovery(self) -> dict:
        """Rebalance the AVL, with the report queue paused meanwhile (Section 8).

        core.avl_tree.AVLTree.recover_balance always turns its own
        stress_mode off as part of rebalancing; the two callers below
        restore it afterwards when the scenario's declared mode should not
        change by itself (see recover_balance and toggle_stress).

        The engine is single-threaded and synchronous (Section 8 does not
        require threads), so no report can actually be dequeued while this
        call is on the stack. The flag is still real, not decorative: it is
        what process_next_report checks, so a recovery started from inside
        report processing (or a future asynchronous caller) is guarded too,
        not just this call's immediate synchronous extent.
        """
        self._recovery_in_progress = True
        try:
            return self.avl.recover_balance()
        finally:
            self._recovery_in_progress = False

    def toggle_stress(self) -> dict:
        """Enter or leave stress mode (Section 8).

        Entering is unconditional: deferred balancing can start at any time.
        Leaving runs a global recovery first and only completes when the
        audit that follows confirms the tree is an AVL again ("El retorno al
        modo normal solo se completa cuando la auditoría confirma el
        equilibrio"). If the audit still finds a problem, stress mode stays
        on, the attempted recovery is rolled back and nothing is recorded.
        """
        if not self.avl.stress_mode:
            before = self.snapshot()
            self.avl.stress_mode = True
            self._record("TOGGLE_STRESS", before, "Entrar en modo estrés")
            return {"stress_mode": True, "message": "Modo estrés activado"}

        before = self.snapshot()
        cost = self._run_recovery()          # also turns avl.stress_mode off
        audit = self.run_audit()             # mode is already normal: balance counts as error
        if not audit["is_valid"]:
            apply_state(self, before)        # undo the attempt: tree and stress mode as they were
            return {
                "stress_mode": True,
                "message": "La auditoría no confirma el equilibrio: el árbol sigue en modo estrés",
                "errors": audit["errors"],
            }

        self._record("TOGGLE_STRESS", before,
                     f"Salir de modo estrés: recuperación global, {_cost_text(cost)}")
        return {"stress_mode": False,
                "message": f"Modo normal: la auditoría confirma el equilibrio ({_cost_text(cost)})",
                "cost": cost}

    def recover_balance(self) -> dict:
        """Global recovery (Section 8): can run in either mode.

        Rebalancing the structure is independent of the mode switch itself,
        which only toggle_stress decides, with its audit gate: the mode is
        restored to whatever it was before this call, so running this while
        in stress mode fixes the tree without granting an unaudited exit. In
        normal mode the tree should already be an AVL, so a call that finds
        nothing to rotate is not recorded as an action (same reasoning as
        save_version: nothing changed, so there is nothing to undo); if it
        were unbalanced anyway, it gets repaired the same way.
        """
        stress_before = self.avl.stress_mode
        before = self.snapshot()
        cost = self._run_recovery()
        self.avl.stress_mode = stress_before

        rotated = any(cost[k] for k in ("ll", "rr", "lr", "rl"))
        if not rotated:
            message = "El árbol ya cumplía la propiedad AVL: no hubo rotaciones que aplicar"
            return {"result": "ALREADY_BALANCED", "message": message,
                    "cost": cost, "stress_mode": self.avl.stress_mode}

        message = f"Recuperación global aplicada: {_cost_text(cost)}"
        self._record("RECOVER", before, message)
        return {"result": "RECOVERED", "message": message,
                "cost": cost, "stress_mode": self.avl.stress_mode}


def _cost_text(cost: dict) -> str:
    """One line with what a recovery found and changed (Section 8)."""
    cases = sum(cost[k] for k in ("ll", "rr", "lr", "rl"))
    turns = cost["simple_turns_left"] + cost["simple_turns_right"]
    return (f"{len(cost['unbalanced_before'])} nodo(s) desbalanceado(s) detectado(s), "
            f"altura {cost['height_before']} -> {cost['final_height']}, "
            f"{cases} caso(s) de rotación con {turns} giro(s) elemental(es)")
