"""
Persistence — files and named versions (Sections 12 and 13).

The parsing and validation live in domain.loader / domain.storage; this
module only turns their results into undoable actions on the scenario.
"""

from __future__ import annotations

import os

from domain.loader import load_burst, load_insertions, load_topology
from domain.storage import read_json_file, write_json_file


class PersistenceMixin:
    """Save/load scenario files and save/restore named versions."""

    # --- Files (Section 12) ---

    def save_to_file(self, path: str) -> dict:
        """Structural save: topology, history, queue, clock, parameters, mode, metrics."""
        write_json_file(path, self.snapshot())
        return {"path": path, "active": self.avl.size, "archived": len(self.archived)}

    def load_scenario_file(self, path: str) -> dict:
        """Topology load. Raises StateError with every problem and keeps the state."""
        state, info = load_topology(self, read_json_file(path))
        self._replace_state(state, "LOAD_TOPOLOGY",
                            f"Cargar escenario {os.path.basename(path)}")
        return info

    def load_insertions_file(self, path: str) -> dict:
        """Insertion load into a balanced AVL and a plain BST; returns their comparison."""
        state, comparison = load_insertions(self, read_json_file(path))
        self._replace_state(state, "LOAD_INSERTIONS",
                            f"Cargar {comparison['events']} eventos por inserción "
                            f"desde {os.path.basename(path)}")
        return comparison

    def load_burst_file(self, path: str) -> dict:
        """Report burst (Section 8): every report enters the queue, in file
        order, as one undoable action (a load, Section 13). None is applied
        until its queue step runs. Raises StateError and keeps the queue when
        any report is invalid."""
        data = read_json_file(path)
        reports = load_burst(self, data)
        first_position = self.report_queue.size() + 1
        stations = sorted({r.station_id for r in reports})
        before = self.snapshot()
        for report in reports:
            self.report_queue.enqueue(report)
        self._record("LOAD_BURST", before,
                     f"Cargar ráfaga {os.path.basename(path)}: {len(reports)} reportes "
                     f"de {len(stations)} estación(es)")
        description = data.get("description")
        return {
            "count": len(reports),
            "stations": stations,
            "first_position": first_position,
            "queue_size": self.report_queue.size(),
            "description": description if isinstance(description, str) else None,
        }

    # --- Named versions (Section 13) ---

    def save_version(self, store, name: str) -> dict:
        """Store the current operational state under a name. Not an action:
        the scenario does not change, so there is nothing to undo."""
        return store.save(name, self.snapshot())

    def restore_version(self, store, version_id: str) -> dict:
        """Replace the state with a saved version as one undoable action.

        The stored state is validated like a topology file, so an edited or
        damaged version raises StateError and the scenario stays untouched.
        """
        name, stored = store.load_state(version_id)
        state, info = load_topology(self, stored)
        self._replace_state(state, "RESTORE_VERSION", f"Restaurar versión '{name}'")
        return {"name": name, **info}
