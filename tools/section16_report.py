"""
Section 16 evidence: every mandatory case, run on its files in
data/test_cases_section16/ (persistence uses data/topologies/), printing the
declared initial state, each step, and the expected and obtained results.
The Section 8 report bursts of data/bursts/ are included as well.

Run from the project root:   python tools/section16_report.py
tests/test_section16_cases.py runs the same cases and fails on any mismatch.

Each case loads its files with the same Scenario methods the interface calls
(load_scenario_file, load_insertions_file, load_burst_file), so what this
prints is what the user sees by following data/test_cases_section16/README.md.
"""

import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from domain.scenario import Scenario  # noqa: E402
from domain.storage import StateError, scenario_to_dict  # noqa: E402
from domain.validation import check_tree  # noqa: E402
from domain.versions import VersionStore  # noqa: E402

DATA = os.path.join(ROOT, "data")
CASES_DIR = os.path.join(DATA, "test_cases_section16")
PRIORITY = {1: "BAJA", 2: "MEDIA", 3: "ALTA"}


def case_file(folder, name):
    return os.path.join(CASES_DIR, folder, name)


class Evidence:
    """Collects (expected, obtained) checks; prints them when `out` is given."""

    def __init__(self, out=None):
        self.out = out
        self.title = ""
        self.checks = []

    def _print(self, text):
        if self.out:
            self.out(text)

    def case(self, title, initial):
        self.title = title
        self._print(f"\n=== {title} ===\nEstado inicial: {initial}")

    def step(self, text):
        self._print(f"  > {text}")

    def check(self, label, expected, obtained):
        ok = expected == obtained
        self.checks.append({"case": self.title, "label": label, "expected": expected,
                            "obtained": obtained, "ok": ok})
        self._print(f"    [{'OK' if ok else 'FALLA'}] {label}: esperado {expected} | obtenido {obtained}")

    @property
    def failures(self):
        return [c for c in self.checks if not c["ok"]]


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def priority(sc, event_id):
    return PRIORITY[int(sc.event_index[event_id].priority)]


def references(sc):
    every = {**sc.archived, **sc.event_index}
    return {i: e.reference_event_id for i, e in sorted(every.items())}


def candidates(sc, event_id):
    assoc = sc.associations.get(event_id)
    return list(assoc.candidate_ids) if assoc else []


def max_abs_balance(sc):
    return max((abs(bf) for _, bf in check_tree(sc.avl)["unbalanced"]), default=1)


def inorder_ids(sc):
    return [k.event_id for k in sc.avl.inorder()]


def run_queue(sc):
    """Process every queued report; returns (event id, revision, station, decision)."""
    steps = []
    while not sc.report_queue.is_empty():
        head = sc.report_queue.peek()
        steps.append((head.event_id, head.revision, head.station_id,
                      sc.process_next_report()["result"]))
    return steps


# ---------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------

def case1_limits_and_ties(ev):
    path = case_file("caso1-limites-empates", "inserciones.json")
    ev.case("Caso 1: limites y empates",
            "Escenario vacio + caso1-limites-empates/inserciones.json (Cargar por inserciones)")
    sc = Scenario()
    sc.load_insertions_file(path)
    ev.step("Prioridad calculada de cada caso limite")
    for event_id, text, expected in [
        (101, "M 4.5, H 30.0, zona poblada", "ALTA"),
        (102, "M 4.5, H 30.1, zona poblada", "MEDIA"),
        (103, "M 4.4, H 10.0, zona poblada", "BAJA"),
        (104, "M 6.0, H 300.0, zona no poblada", "ALTA"),
        (105, "M 5.9, H 300.0, zona no poblada", "MEDIA"),
        (106, "M 4.8, H 20.0, epicentro (500, 100) en el borde Sur/Costa", "ALTA"),
        (107, "M 4.8, H 20.0, epicentro (499.9, 100) solo en Sur", "MEDIA"),
    ]:
        ev.check(f"Evento {event_id} ({text})", expected, priority(sc, event_id))
    ev.check("El borde x = 500 cuenta como zona poblada (106)", True,
             sc.event_index[106].in_populated_zone)
    ev.step("Empate: 110, 108 y 109 tienen P = 1 y M = 3.2 y se insertaron en ese orden")
    ties = [i for i in inorder_ids(sc) if i in (108, 109, 110)]
    ev.check("Orden inorden de los empatados (decide el ID)", [108, 109, 110], ties)
    ev.check("Auditoria del AVL", True, sc.run_audit()["is_valid"])


def case2_correction_and_older_report(ev):
    folder = "caso2-correccion-reporte-antiguo"
    ev.case("Caso 2: correccion y reporte antiguo", f"{folder}/escenario.json (Cargar escenario)")
    sc = Scenario()
    sc.load_scenario_file(case_file(folder, "escenario.json"))
    event = sc.event_index[200]
    ev.check("Evento 200 antes: prioridad, clave y revision", ("MEDIA", "(2, 4.8, 200)", 1),
             (priority(sc, 200), str(event.build_key()), event.revision))
    nodes = sc.avl.size

    ev.step("Corregir 200 a M = 6.2 y H = 15.0 (Corregir Evento)")
    sc.correct_event(200, magnitude=6.2, depth_km=15.0)
    ev.check("Prioridad, clave y revision despues de corregir", ("ALTA", "(3, 6.2, 200)", 2),
             (priority(sc, 200), str(event.build_key()), event.revision))
    ev.check("Cantidad de nodos (se reubica, no se duplica)", nodes, sc.avl.size)

    ev.step("Cargar rafaga-revision-antigua.json y procesar el reporte (revision 1)")
    sc.load_burst_file(case_file(folder, "rafaga-revision-antigua.json"))
    ev.check("Decision del paso de la cola", "OUTDATED", sc.process_next_report()["result"])
    ev.check("Cantidad de nodos (no se crea otro)", nodes, sc.avl.size)
    ev.check("Nodos con ID 200 en el AVL", 1, inorder_ids(sc).count(200))
    ev.check("Datos de 200 (la correccion no se revierte)", (6.2, 15.0, 2, "ALTA"),
             (event.magnitude, event.depth_km, event.revision, priority(sc, 200)))


def case3_late_report(ev):
    folder = "caso3-reporte-tardio"
    ev.case("Caso 3: reporte tardio", f"{folder}/escenario.json (Cargar escenario)")
    sc = Scenario()
    sc.load_scenario_file(case_file(folder, "escenario.json"))
    ev.check("Antes: candidatos de 301 y de 302", ([], [301]),
             (candidates(sc, 301), candidates(sc, 302)))
    ev.check("Antes: referencia de 302", 301, references(sc)[302])

    ev.step("Cargar rafaga-reporte-tardio.json: 303, M 6.1, ocurrido a las 09:55, y procesarlo")
    sc.load_burst_file(case_file(folder, "rafaga-reporte-tardio.json"))
    ev.check("Decision del paso de la cola", "CREATED", sc.process_next_report()["result"])
    ev.check("Candidatos de 303 (nada es mayor y anterior)", [], candidates(sc, 303))
    ev.check("Candidatos nuevos de 301", [303], candidates(sc, 301))
    ev.check("Candidatos de 302 en el orden de la politica (mayor M primero)", [303, 301],
             candidates(sc, 302))
    refs = references(sc)
    ev.check("Referencia elegida: 301 y 302 pasan a 303; 303 queda sin referencia",
             (303, 303, None), (refs[301], refs[302], refs[303]))


def case4_rotations_and_recovery(ev):
    folder = "caso4-rotaciones-recuperacion"
    ev.case("Caso 4: rotaciones y recuperacion",
            f"Escenario vacio + {folder}/rotacion-*.json (Cargar por inserciones)")
    expected = {"ll": (1, 0, 0, 0, 0, 1), "rr": (0, 1, 0, 0, 1, 0),
                "lr": (0, 0, 1, 0, 1, 1), "rl": (0, 0, 0, 1, 1, 1)}
    for name, counts in expected.items():
        sc = Scenario()
        r = sc.load_insertions_file(case_file(folder, f"rotacion-{name}.json"))["rotations"]
        ev.check(f"rotacion-{name}.json: LL, RR, LR, RL, giros izq, giros der", counts,
                 (r["ll"], r["rr"], r["lr"], r["rl"], r["simple_left"], r["simple_right"]))
    sc = Scenario()
    c = sc.load_insertions_file(case_file(folder, "rotaciones-cuatro-casos.json"))
    r = c["rotations"]
    ev.check("rotaciones-cuatro-casos.json: un caso de cada tipo, 3 giros por lado",
             (1, 1, 1, 1, 3, 3),
             (r["ll"], r["rr"], r["lr"], r["rl"], r["simple_left"], r["simple_right"]))
    ev.check("Altura AVL frente a BST con el mismo orden", (2, 5),
             (c["avl"]["height"], c["bst"]["height"]))

    ev.step(f"Cargar {folder}/base.json, activar Modo Estres, cargar rafaga-ascendente.json "
            "y procesar la cola completa")
    sc = Scenario()
    sc.load_scenario_file(case_file(folder, "base.json"))
    sc.toggle_stress()
    sc.load_burst_file(case_file(folder, "rafaga-ascendente.json"))
    decisions = [step[3] for step in run_queue(sc)]
    ev.check("Altas creadas por la cola", 8, decisions.count("CREATED"))
    ev.check("Altura y mayor |factor de balance| en estres (desbalance mayor que 2)", (9, 7),
             (sc.avl.height, max_abs_balance(sc)))
    audit = sc.run_audit()
    ev.check("Auditoria en estres: sin errores de orden ni metadatos, pero no es AVL",
             (True, False), (audit["is_valid"], audit["is_avl"]))
    degraded = Scenario()
    degraded.load_scenario_file(case_file(folder, "estres-degradado.json"))
    ev.check("estres-degradado.json guarda este mismo arbol", inorder_ids(sc), inorder_ids(degraded))

    ids, order, refs = set(sc.event_index), inorder_ids(sc), references(sc)
    ev.step("Recuperar Balance")
    cost = sc.recover_balance()["cost"]
    ev.check("Costo: LL, RR, LR, RL y altura final", (0, 8, 0, 2, 4),
             (cost["ll"], cost["rr"], cost["lr"], cost["rl"], cost["final_height"]))
    ev.check("Mayor |factor de balance| despues", 1, max_abs_balance(sc))
    ev.check("Conserva las identidades", sorted(ids), sorted(sc.event_index))
    ev.check("Conserva el orden (inorden)", order, inorder_ids(sc))
    ev.check("Conserva las asociaciones", refs, references(sc))
    ev.step("Modo Estres otra vez: salir solo si la auditoria confirma el equilibrio")
    ev.check("Modo despues de salir", False, sc.toggle_stress()["stress_mode"])


def case5_mass_archive(ev):
    folder = "caso5-archivo-masivo"
    ev.case("Caso 5: archivo masivo", f"{folder}/escenario.json (Cargar escenario), T = 72 h")
    sc = Scenario()
    sc.load_scenario_file(case_file(folder, "escenario.json"))
    initial = scenario_to_dict(sc)

    ev.step("Archivar rama de eventos antiguos: vista previa")
    p = sc.preview_archive()
    ev.check("Rama seleccionada (raiz y eventos)", (606, [605, 606, 607]),
             (p["selected"]["root_id"], sorted(p["selected"]["event_ids"])))
    ev.check("Otras ramas elegibles: raiz, nodos y motivo", [
        (602, 3, "empata en nodos y profundidad, y el ID de su raíz es menor (602 frente a 606)"),
        (609, 1, "tiene menos nodos (1 frente a 3)"),
    ], [(o["root_id"], o["count"], o["why_not"]) for o in p["others"]])
    ev.check("Raices de prioridad baja no elegibles", [
        (610, 611, "prioridad MEDIUM"),
        (608, 604, "antigüedad 24.0 h, no supera T"),
    ], [(r["root_id"], r["offender_id"], r["reason"]) for r in p["rejected_low_roots"]])

    ev.step("Archivar esta rama")
    ev.check("Eventos archivados", 3, sc.archive_branch(p["selected"]["event_ids"]))
    ev.check("Activos e historicos", (12, 3), (sc.avl.size, len(sc.archived)))
    ev.check("Auditoria (el AVL se rebalancea)", True, sc.run_audit()["is_valid"])

    ev.step("Deshacer")
    sc.undo()
    ev.check("Un solo Deshacer devuelve el estado inicial completo", True,
             scenario_to_dict(sc) == initial)

    ev.step("Parametros: T = 1000 h, y Archivar rama otra vez")
    sc.update_parameters(t_archive_hours=1000)
    before = scenario_to_dict(sc)
    p = sc.preview_archive()
    ev.check("Sin ramas elegibles", (None, "No hay ramas elegibles: no se archivará nada."),
             (p["selected"], p["justification"][0]))
    try:
        sc.archive_branch([605, 606, 607])
        refused = False
    except ValueError:
        refused = True
    ev.check("Archivar se rechaza y el estado se conserva", (True, True),
             (refused, scenario_to_dict(sc) == before))


def case6_persistence(ev):
    ev.case("Caso 6: persistencia y consistencia",
            "topologies/normal.json y topologies/estres.json (Cargar escenario)")
    folder = tempfile.mkdtemp()
    try:
        for name, mode in (("normal.json", "normal"), ("estres.json", "stress")):
            ev.step(f"Cargar {name}, Guardar escenario y cargar lo guardado en un programa nuevo")
            first = Scenario()
            first.load_scenario_file(os.path.join(DATA, "topologies", name))
            path = os.path.join(folder, name)
            first.save_to_file(path)
            second = Scenario()
            info = second.load_scenario_file(path)
            ev.check(f"{name}: modo y mismo estado completo (topologia incluida)", (mode, True),
                     (info["mode"], scenario_to_dict(second) == scenario_to_dict(first)))

        ev.step("Con normal.json cargado, intentar cargar cada archivo inconsistente")
        sc = Scenario()
        sc.load_scenario_file(os.path.join(DATA, "topologies", "normal.json"))
        before = scenario_to_dict(sc)
        for name in ("inconsistente-orden.json", "inconsistente-metadatos.json",
                     "invalido-referencias.json"):
            try:
                sc.load_scenario_file(os.path.join(DATA, "topologies", name))
                rejected = False
            except StateError:
                rejected = True
            ev.check(f"{name}: rechazado y el estado no cambia", (True, True),
                     (rejected, scenario_to_dict(sc) == before))

        ev.step("Guardar la version 'Base', cambiar el escenario, cerrar y restaurarla")
        store_dir = os.path.join(folder, "versions")
        sc.save_version(VersionStore(store_dir), "Base")
        sc.delete_event(180)
        restarted = Scenario()
        store = VersionStore(store_dir)
        restarted.restore_version(store, store.list()[0]["id"])
        ev.check("La version restaurada es el estado guardado", True,
                 scenario_to_dict(restarted) == before)

        ev.step("Corregir 150 a M = 4.0 y deshacer")
        restarted.correct_event(150, magnitude=4.0)
        restarted.undo()
        ev.check("Estado igual al de antes de corregir", True, scenario_to_dict(restarted) == before)
        ev.step("Procesar un paso de la cola (170 rev 1, antiguo) y deshacer")
        decision = restarted.process_next_report()["result"]
        restarted.undo()
        ev.check("Decision y estado despues de deshacer (reporte de vuelta en la cola)",
                 ("OUTDATED", True), (decision, scenario_to_dict(restarted) == before))
    finally:
        shutil.rmtree(folder)


def bursts_section8(ev):
    ev.case("Rafagas de reportes (seccion 8)",
            "topologies/normal.json (cola: 170 rev 1, 190 rev 1) + bursts/rafaga-mixta.json")
    sc = Scenario()
    sc.load_scenario_file(os.path.join(DATA, "topologies", "normal.json"))
    info = sc.load_burst_file(os.path.join(DATA, "bursts", "rafaga-mixta.json"))
    ev.check("Reportes encolados, estaciones y posicion del primero", (12, 4, 3),
             (info["count"], len(info["stations"]), info["first_position"]))
    ev.step("Procesar la cola completa, un reporte por paso, en orden de recepcion")
    expected = [
        (170, 1, "EST-002", "OUTDATED", "revision menor que la vigente (2)"),
        (190, 1, "EST-001", "CREATED", "ID desconocido"),
        (300, 1, "EST-003", "CREATED", "ID desconocido"),
        (150, 1, "EST-004", "CONFIRMED", "misma revision y mismos datos"),
        (300, 1, "EST-001", "CONFIRMED", "confirma la alta anterior"),
        (150, 2, "EST-002", "CORRECTED", "revision mayor: M 5.6 -> 4.4, prioridad 3 -> 1"),
        (150, 1, "EST-003", "OUTDATED", "revision menor que la vigente (2)"),
        (300, 1, "EST-001", "CONFIRMED", "la misma confirmacion repetida"),
        (301, 3, "EST-004", "CREATED", "primera revision recibida 3"),
        (120, 1, "EST-002", "CONFLICT", "misma revision, otra magnitud"),
        (118, 2, "EST-001", "CORRECTED", "revision mayor: M 4.8 -> 6.4, misma prioridad"),
        (181, 2, "EST-003", "REJECTED", "ID eliminado"),
        (141, 2, "EST-004", "REACTIVATED", "revision mayor sobre un archivado"),
        (142, 1, "EST-002", "CONFIRMED_ARCHIVED", "confirma un archivado sin reactivarlo"),
    ]
    steps = run_queue(sc)
    ev.check("Pasos procesados", len(expected), len(steps))
    for n, ((event_id, revision, station, decision, why), obtained) in enumerate(
            zip(expected, steps), start=1):
        ev.check(f"Paso {n}: {station} -> evento {event_id} rev {revision} ({why})",
                 decision, obtained[3] if obtained[:3] == (event_id, revision, station) else obtained)
    ev.check("150: la correccion cambio su clave", "(1, 4.4, 150)", str(sc.event_index[150].build_key()))
    ev.check("300: confirmacion repetida sin duplicar estaciones", ["EST-001", "EST-003"],
             sorted(sc.event_index[300].reporting_stations))
    ev.check("141 vuelve al AVL; 142 sigue en el historico", (True, True),
             (141 in sc.event_index, 142 in sc.archived))

    ev.step("Cargar bursts/rafaga-invalida.json")
    before = scenario_to_dict(sc)
    try:
        sc.load_burst_file(os.path.join(DATA, "bursts", "rafaga-invalida.json"))
        problems = []
    except StateError as e:
        problems = e.problems
    ev.check("Problemas informados y estado sin cambios", (3, True),
             (len(problems), scenario_to_dict(sc) == before))


CASES = [case1_limits_and_ties, case2_correction_and_older_report, case3_late_report,
         case4_rotations_and_recovery, case5_mass_archive, case6_persistence, bursts_section8]


def main():
    ev = Evidence(out=print)
    for case in CASES:
        case(ev)
    failed = ev.failures
    print(f"\n{len(ev.checks) - len(failed)} de {len(ev.checks)} comprobaciones coinciden con lo esperado.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
