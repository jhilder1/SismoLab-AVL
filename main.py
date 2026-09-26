"""
SismoLab AVL — Punto de entrada.

Ejecutar con: python main.py
Se abre una ventana con la interfaz gráfica.
Todas las funciones expuestas con @eel.expose se llaman
directamente desde JavaScript: eel.nombre_funcion(args)
"""

import os
import eel
from datetime import datetime
from domain.scenario import Scenario
from domain.models import Epicenter, Report, Zone, Station
from domain.storage import StateError
from domain.versions import VersionStore

# Carpeta donde abre el explorador de archivos (solo el punto de partida:
# el usuario elige el archivo, no hay rutas de entrada fijas - Sección 12).
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# Versiones con nombre: persisten en disco al cerrar el programa (Sección 13).
versions = VersionStore(os.path.join(DATA_DIR, "versions"))

# Estado global del simulador
sc = Scenario()

# Zonas y estaciones de ejemplo
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

# Inicializar Eel apuntando a la carpeta web/
eel.init("web")


# =================================================================
# Funciones expuestas al frontend
# =================================================================

@eel.expose
def get_state():
    """Retorna el estado completo del simulador."""
    return sc.summary()


@eel.expose
def create_event(event_id, magnitude, depth_km, epicenter_x, epicenter_y,
                 occurrence_time_str, station_id):
    """Crea un evento sísmico nuevo."""
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
    """Corrige magnitud y/o profundidad de un evento."""
    try:
        mag = float(magnitude) if magnitude not in (None, "", "null") else None
        dep = float(depth_km) if depth_km not in (None, "", "null") else None
        event = sc.correct_event(int(event_id), magnitude=mag, depth_km=dep)
        return {"ok": True, "message": f"Evento {event.format_id()} corregido a M={event.magnitude} (rev={event.revision})"}
    except Exception as e:
        return {"ok": False, "message": str(e)}


@eel.expose
def delete_event(event_id):
    """Elimina un evento del catálogo activo."""
    try:
        event = sc.delete_event(int(event_id))
        return {"ok": True, "message": f"Evento {event.format_id()} eliminado"}
    except Exception as e:
        return {"ok": False, "message": str(e)}


@eel.expose
def search_event(event_id):
    """Busca un evento por ID. Retorna datos y costo de acceso."""
    try:
        eid = int(event_id)
        event = sc.get_event(eid)
        if not event:
            return {"ok": False, "message": f"Evento {eid} no encontrado"}
        key = event.build_key()
        node, visited = sc.avl.search(key)
        depth = visited - 1 if node else None
        return {
            "ok": True,
            "event": event.to_dict(),
            "depth": depth,
            "access_cost": visited,
        }
    except Exception as e:
        return {"ok": False, "message": str(e)}


@eel.expose
def enqueue_report(event_id, revision, station_id, magnitude, depth_km,
                   epicenter_x, epicenter_y, occurrence_time_str):
    """Encola un reporte de estación."""
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
    """Procesa el siguiente reporte de la cola."""
    result = sc.process_next_report()
    return result


@eel.expose
def undo_action():
    """Deshace la última acción."""
    return sc.undo()


@eel.expose
def toggle_stress():
    """Activa/desactiva modo estrés."""
    return sc.toggle_stress()


@eel.expose
def recover_balance():
    """Recupera el balance del árbol (sale del modo estrés)."""
    return sc.recover_balance()


@eel.expose
def run_audit():
    """Ejecuta auditoría completa del sistema."""
    return sc.run_audit()


@eel.expose
def mark_reviewed(event_id):
    """Marca un evento como revisado."""
    try:
        event = sc.mark_reviewed(int(event_id))
        return {"ok": True, "message": f"Evento {event.format_id()} marcado como revisado"}
    except Exception as e:
        return {"ok": False, "message": str(e)}


@eel.expose
def advance_clock(hours):
    """Avanza el reloj de simulación (acción que se puede deshacer)."""
    try:
        clock = sc.advance_clock(float(hours))
        return {"ok": True, "clock": clock.isoformat()}
    except Exception as e:
        return {"ok": False, "message": str(e), "clock": sc.clock.isoformat()}


@eel.expose
def get_stations():
    """Retorna la lista de estaciones disponibles."""
    return [s.to_dict() for s in sc.stations.values()]


@eel.expose
def archive_eligible():
    """Archiva la rama elegible más grande."""
    return sc.archive_largest_eligible()


@eel.expose
def query_top_k_pending(k=5):
    """Retorna los primeros k eventos pendientes en orden descendente de K."""
    try:
        return {"ok": True, "data": sc.query_top_k_pending(int(k))}
    except Exception as e:
        return {"ok": False, "message": str(e)}


@eel.expose
def query_by_interval(min_mag, max_mag, max_depth=None, start_date_str=None, end_date_str=None):
    """Consulta eventos por rango de magnitud, profundidad y fechas."""
    try:
        s_date = datetime.fromisoformat(start_date_str) if start_date_str else None
        e_date = datetime.fromisoformat(end_date_str) if end_date_str else None
        m_depth = float(max_depth) if max_depth not in (None, "", "null") else None
        res = sc.query_by_interval(float(min_mag), float(max_mag), m_depth, s_date, e_date)
        return {"ok": True, "data": res}
    except Exception as e:
        return {"ok": False, "message": str(e)}


@eel.expose
def query_event_associations(event_id):
    """Consulta candidatos, referencia y réplicas de un evento."""
    try:
        res = sc.query_event_associations(int(event_id))
        return {"ok": True, "data": res}
    except Exception as e:
        return {"ok": False, "message": str(e)}


@eel.expose
def query_costly_high_priority():
    """Consulta eventos de prioridad alta con acceso costoso (profundidad > L)."""
    try:
        res = sc.query_costly_high_priority()
        return {"ok": True, "data": res}
    except Exception as e:
        return {"ok": False, "message": str(e)}


@eel.expose
def compare_trees_view():
    """Retorna comparativa estructural entre AVL y BST."""
    try:
        res = sc.compare_current_trees()
        return {"ok": True, "data": res}
    except Exception as e:
        return {"ok": False, "message": str(e)}


@eel.expose
def update_parameters(w_hours=None, r_km=None, l_depth=None, t_archive_hours=None):
    """Actualiza parámetros del escenario (W, R, L, T). Registra acción en undo."""
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
# Persistencia (Sección 12): explorador de archivos + carga/guardado
# =================================================================

def _ask_path(title, save=False):
    """Abre el explorador de archivos nativo y devuelve la ruta elegida (o None)."""
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)  # que el diálogo quede encima de la ventana
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
    """Guarda el escenario completo (topología incluida) en un JSON."""
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
    """Carga por topología: reconstruye el árbol exacto del archivo."""
    return _load("Cargar escenario (topología)", sc.load_scenario_file)


@eel.expose
def load_insertions():
    """Carga por inserciones: misma secuencia en un AVL balanceado y un BST."""
    return _load("Cargar eventos por inserciones", sc.load_insertions_file)


# =================================================================
# Versiones con nombre (Sección 13)
# =================================================================

@eel.expose
def list_versions():
    """Lista las versiones guardadas, de la más antigua a la más reciente."""
    return versions.list()


@eel.expose
def save_version(name):
    """Guarda el estado actual con un nombre."""
    try:
        info = sc.save_version(versions, name)
        return {"ok": True, "message": f"Versión '{info['name']}' guardada"}
    except (ValueError, OSError) as e:
        return {"ok": False, "message": str(e)}


@eel.expose
def restore_version(version_id):
    """Restaura una versión (acción que se puede deshacer)."""
    try:
        info = sc.restore_version(versions, version_id)
        return {"ok": True, "message": f"Versión '{info['name']}' restaurada "
                                       f"({info['active']} activos, modo {info['mode']})"}
    except StateError as e:
        return {"ok": False,
                "message": "La versión no se pudo restaurar. El escenario actual no cambió.",
                "problems": e.problems}


# =================================================================
# Arrancar la aplicación
# =================================================================

if __name__ == "__main__":
    print("SismoLab AVL - Iniciando...")
    print("Cerrando la ventana se detiene el servidor.")

    # Intentar con Edge (viene con Windows), si no con el navegador por defecto
    try:
        eel.browsers.set_path("edge", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
        eel.start("index.html", size=(1400, 850), port=8080, mode="edge")
    except Exception:
        try:
            eel.start("index.html", size=(1400, 850), port=8080, mode="edge")
        except Exception:
            print("No se encontro Edge ni Chrome. Abriendo en el navegador por defecto...")
            eel.start("index.html", size=(1400, 850), port=8080, mode="default")
