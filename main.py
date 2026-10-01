"""
SismoLab AVL — entry point.

Run with: python main.py
A window opens with the graphical interface. Every function exposed with
@eel.expose is called directly from JavaScript: eel.function_name(args)
"""

import os
import eel
from datetime import datetime
from domain.scenario import Scenario
from domain.models import Epicenter, Report, Zone, Station, parse_time
from domain.storage import StateError
from domain.versions import VersionStore

# Folder where the file explorer opens (only the starting point: the user
# picks the file, there are no fixed input paths - Section 12).
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# Named versions: kept on disk after the program closes (Section 13).
versions = VersionStore(os.path.join(DATA_DIR, "versions"))

# Global simulator state
sc = Scenario()

# Sample zones and stations
sc.zones = [
    Zone("Norte", 0, 500, 500, 1000, True),
    Zone("Centro", 200, 800, 200, 800, True),
    Zone("Sur", 0, 500, 0, 500, False),
    Zone("Costa", 500, 1000, 0, 500, True),
]
sc.stations = {
    "EST-001": Station("EST-001", "Estacion Norte"),
    "EST-002": Station("EST-002", "Estacion Centro"),
    "EST-003": Station("EST-003", "Estacion Sur"),
    "EST-004": Station("EST-004", "Estacion Costa"),
}

# Start Eel on the web/ folder
eel.init("web")


# =================================================================
# Functions exposed to the front end
# =================================================================

@eel.expose
def get_state():
    """Returns the whole simulator state."""
    return sc.summary()


@eel.expose
def create_event(event_id, magnitude, depth_km, epicenter_x, epicenter_y,
                 occurrence_time_str, station_id):
    """Creates a new seismic event."""
    try:
        occ = datetime.fromisoformat(occurrence_time_str)
        event = sc.create_event(
            event_id=int(event_id),
            magnitude=float(magnitude),
            depth_km=float(depth_km),
            epicenter_x=float(epicenter_x),
            epicenter_y=float(epicenter_y),
            occurrence_time=occ,
            station_id=station_id,
        )
        return {"ok": True, "message": f"Evento {event.format_id()} creado (P={event.priority.name})"}
    except Exception as e:
        return {"ok": False, "message": str(e)}


@eel.expose
def correct_event(event_id, magnitude=None, depth_km=None):
    """Corrects the magnitude and/or depth of an event."""
    try:
        mag = float(magnitude) if magnitude not in (None, "", "null") else None
        dep = float(depth_km) if depth_km not in (None, "", "null") else None
        event = sc.correct_event(int(event_id), magnitude=mag, depth_km=dep)
        return {"ok": True, "message": f"Evento {event.format_id()} corregido a M={event.magnitude} (rev={event.revision})"}
    except Exception as e:
        return {"ok": False, "message": str(e)}


@eel.expose
def preview_delete(event_id):
    """Shows the affected event before deleting it (Section 6)."""
    try:
        return {"ok": True, **sc.preview_delete(int(event_id))}
    except (TypeError, ValueError) as e:
        return {"ok": False, "message": str(e)}


@eel.expose
def delete_event(event_id):
    """Deletes an event from the active catalogue."""
    try:
        event = sc.delete_event(int(event_id))
        return {"ok": True, "message": f"Evento {event.format_id()} eliminado"}
    except Exception as e:
        return {"ok": False, "message": str(e)}


@eel.expose
def search_event(event_id):
    """Looks up an event by id: says whether it is active, archived or deleted."""
    try:
        info = sc.lookup_event(int(event_id))
        if info["status"] == "unknown":
            return {"ok": False, "message": f"El ID {info['event_id']} no existe en el escenario"}
        return {"ok": True, **info}
    except (TypeError, ValueError):
        return {"ok": False, "message": f"ID inválido: {event_id!r}"}


@eel.expose
def enqueue_report(event_id, revision, station_id, magnitude, depth_km,
                   epicenter_x, epicenter_y, occurrence_time_str):
    """Enqueues a station report."""
    try:
        report = Report(
            event_id=int(event_id),
            revision=int(revision),
            station_id=station_id,
            magnitude=float(magnitude),
            depth_km=float(depth_km),
            epicenter=Epicenter(float(epicenter_x), float(epicenter_y)),
            occurrence_time=datetime.fromisoformat(occurrence_time_str),
        )
        sc.enqueue_report(report)
        return {"ok": True, "message": f"Reporte encolado (evento {event_id}, rev {revision})"}
    except Exception as e:
        return {"ok": False, "message": str(e)}


@eel.expose
def process_report():
    """Processes the next report in the queue."""
    result = sc.process_next_report()
    return result


@eel.expose
def undo_action():
    """Undoes the last action."""
    return sc.undo()

@eel.expose
def redo_action():
    """Redoes the action just undone."""
    return sc.redo()


@eel.expose
def toggle_stress():
    """Turns stress mode on or off."""
    return sc.toggle_stress()


@eel.expose
def recover_balance():
    """Restores the balance of the tree (global recovery)."""
    return sc.recover_balance()


@eel.expose
def run_audit():
    """Runs the full structure audit."""
    return sc.run_audit()


@eel.expose
def mark_reviewed(event_id):
    """Marks an event as reviewed."""
    try:
        event = sc.mark_reviewed(int(event_id))
        return {"ok": True, "message": f"Evento {event.format_id()} marcado como revisado"}
    except Exception as e:
        return {"ok": False, "message": str(e)}


@eel.expose
def advance_clock(hours):
    """Moves the simulation clock forward (an undoable action)."""
    try:
        clock = sc.advance_clock(float(hours))
        return {"ok": True, "clock": clock.isoformat()}
    except Exception as e:
        return {"ok": False, "message": str(e), "clock": sc.clock.isoformat()}


@eel.expose
def get_stations():
    """Returns the available stations."""
    return [s.to_dict() for s in sc.stations.values()]


@eel.expose
def preview_archive():
    """Archive preview (Section 10): the branch the rule selects, its ids,
    its size and the justification, before running it."""
    return {"ok": True, **sc.preview_archive()}


@eel.expose
def archive_selected_branch(event_ids):
    """Archives the previewed branch. If the rule no longer selects it (the
    scenario changed), it is refused and nothing is archived."""
    try:
        count = sc.archive_branch([int(i) for i in event_ids])
        return {"ok": True, "count": count, "event_ids": event_ids}
    except (TypeError, ValueError) as e:
        return {"ok": False, "message": str(e)}


@eel.expose
def query_top_k_pending(k=5):
    """Returns the first k pending events in descending order of K."""
    try:
        return {"ok": True, "data": sc.query_top_k_pending(int(k))}
    except Exception as e:
        return {"ok": False, "message": str(e)}


@eel.expose
def query_by_magnitude(min_mag, max_mag):
    """Events with magnitude in an inclusive interval, pruned by K (Section 11)."""
    try:
        return {"ok": True, "data": sc.query_by_magnitude(float(min_mag), float(max_mag))}
    except (TypeError, ValueError) as e:
        return {"ok": False, "message": str(e)}


@eel.expose
def query_by_depth_and_dates(max_depth, start_date_str, end_date_str):
    """Events with depth <= a limit inside an inclusive date interval."""
    if max_depth in (None, "") or not start_date_str or not end_date_str:
        return {"ok": False, "message": "La profundidad máxima y las fechas desde y hasta son obligatorias"}
    try:
        res = sc.query_by_depth_and_dates(float(max_depth), parse_time(start_date_str),
                                          parse_time(end_date_str))
        return {"ok": True, "data": res}
    except (TypeError, ValueError) as e:
        return {"ok": False, "message": str(e)}


@eel.expose
def get_action_log(limit=100):
    """Action log with the indicators each action changed (Section 14)."""
    return sc.get_action_log(int(limit))


@eel.expose
def query_event_associations(event_id):
    """Candidates, reference and replicas of an event."""
    try:
        res = sc.query_event_associations(int(event_id))
        return {"ok": True, "data": res}
    except Exception as e:
        return {"ok": False, "message": str(e)}


@eel.expose
def query_costly_high_priority():
    """High-priority events with costly access (depth > L)."""
    try:
        res = sc.query_costly_high_priority()
        return {"ok": True, "data": res}
    except Exception as e:
        return {"ok": False, "message": str(e)}


@eel.expose
def compare_trees_view():
    """Structural comparison between the AVL and the BST."""
    try:
        res = sc.compare_current_trees()
        return {"ok": True, "data": res}
    except Exception as e:
        return {"ok": False, "message": str(e)}


@eel.expose
def update_parameters(w_hours=None, r_km=None, l_depth=None, t_archive_hours=None):
    """Updates the scenario parameters (W, R, L, T) as one undoable action."""
    try:
        sc.update_parameters(
            w_hours=float(w_hours) if w_hours is not None else None,
            r_km=float(r_km) if r_km is not None else None,
            l_depth=float(l_depth) if l_depth is not None else None,
            t_archive_hours=float(t_archive_hours) if t_archive_hours is not None else None,
        )
        return {"ok": True, "message": "Parámetros actualizados exitosamente"}
    except Exception as e:
        return {"ok": False, "message": str(e)}


# =================================================================
# Persistence (Section 12): file explorer + load/save
# =================================================================

def _ask_path(title, save=False):
    """Opens the native file explorer and returns the chosen path (or None)."""
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)  # keep the dialog above the app window
    try:
        options = {"parent": root, "title": title, "initialdir": DATA_DIR,
                   "filetypes": [("JSON", "*.json"), ("Todos", "*.*")]}
        if save:
            path = filedialog.asksaveasfilename(defaultextension=".json", **options)
        else:
            path = filedialog.askopenfilename(**options)
    finally:
        root.destroy()
    return path or None


def _load(title, load_method):
    path = _ask_path(title)
    if not path:
        return {"ok": False, "cancelled": True, "message": "Carga cancelada"}
    try:
        info = load_method(path)
        return {"ok": True, "file": os.path.basename(path), "info": info}
    except StateError as e:
        return {"ok": False, "file": os.path.basename(path),
                "message": f"Archivo rechazado: {len(e.problems)} problema(s). "
                           f"El escenario actual no cambió.",
                "problems": e.problems}


@eel.expose
def save_scenario():
    """Saves the whole scenario (topology included) to a JSON file."""
    path = _ask_path("Guardar escenario", save=True)
    if not path:
        return {"ok": False, "cancelled": True, "message": "Guardado cancelado"}
    try:
        info = sc.save_to_file(path)
        return {"ok": True, "message": f"Escenario guardado en {os.path.basename(path)} "
                                       f"({info['active']} activos, {info['archived']} en histórico)"}
    except OSError as e:
        return {"ok": False, "message": f"No se pudo guardar: {e}"}


@eel.expose
def load_scenario():
    """Topology load: rebuilds the exact tree of the file."""
    return _load("Cargar escenario (topología)", sc.load_scenario_file)


@eel.expose
def load_insertions():
    """Insertion load: the same sequence into a balanced AVL and a BST."""
    return _load("Cargar eventos por inserciones", sc.load_insertions_file)


@eel.expose
def load_burst():
    """Report burst (Section 8): enqueues the reports in order, without applying them."""
    return _load("Cargar ráfaga de reportes", sc.load_burst_file)


# =================================================================
# Named versions (Section 13)
# =================================================================

@eel.expose
def list_versions():
    """Lists the saved versions, oldest first."""
    return versions.list()


@eel.expose
def save_version(name):
    """Saves the current state under a name."""
    try:
        info = sc.save_version(versions, name)
        return {"ok": True, "message": f"Versión '{info['name']}' guardada"}
    except (ValueError, OSError) as e:
        return {"ok": False, "message": str(e)}


@eel.expose
def restore_version(version_id):
    """Restores a version (an undoable action)."""
    try:
        info = sc.restore_version(versions, version_id)
        return {"ok": True, "message": f"Versión '{info['name']}' restaurada "
                                       f"({info['active']} activos, modo {info['mode']})"}
    except StateError as e:
        return {"ok": False,
                "message": "La versión no se pudo restaurar. El escenario actual no cambió.",
                "problems": e.problems}


# =================================================================
# Start the application
# =================================================================

if __name__ == "__main__":
    print("SismoLab AVL - Iniciando...")
    print("Cerrando la ventana se detiene el servidor.")

    PORT = 8080
    # Try Chrome, Edge or the default browser; if none works, start only the
    # server and print the URL to open by hand.
    for mode in ("chrome", "edge", "default"):
        try:
            eel.start("index.html", size=(1400, 850), port=PORT, mode=mode)
            break
        except (OSError, EnvironmentError, RuntimeError):
            continue
    else:
        print(f"No se detecto navegador. Abre http://localhost:{PORT} manualmente.")
        eel.start("index.html", port=PORT, mode=None)
