"""
SismoLab AVL — Punto de entrada.

Ejecutar con: python main.py
Se abre una ventana con la interfaz gráfica.
Todas las funciones expuestas con @eel.expose se llaman
directamente desde JavaScript: eel.nombre_funcion(args)
"""

import eel
from datetime import datetime
from domain.scenario import Scenario
from domain.models import Epicenter, Report, Zone, Station

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
    """Avanza el reloj de simulación."""
    from datetime import timedelta
    sc.clock += timedelta(hours=float(hours))
    return {"ok": True, "clock": sc.clock.isoformat()}


@eel.expose
def get_stations():
    """Retorna la lista de estaciones disponibles."""
    return [s.to_dict() for s in sc.stations.values()]


@eel.expose
def archive_eligible():
    """Archiva la rama elegible más grande."""
    return sc.archive_largest_eligible()


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
