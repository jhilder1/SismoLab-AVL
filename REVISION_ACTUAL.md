# REVISIÓN ACTUAL — SismoLab AVL

Revisión de solo lectura del checkout actual (`main`, HEAD `8c277ce`, sincronizado con `origin/main`). No se modificó código fuente. Los scripts de prueba se escribieron en un directorio temporal y se borraron.

- Arquitectura vigente: Python + Eel, en `core/`, `domain/`, `web/` y `main.py`. `backend/` y `frontend/` ya no existen (el `.gitignore:16-17` los ignora).
- Enunciado leído primero: `~/Descargas/Proyecto Estructuras de Datos SismoLab AVL.pdf` (10 páginas). Las secciones se citan como §n.
- Convención: `archivo:línea`. Donde algo no existe, dice "no encontrado".
- `INFORME_ESTADO.md` (del turno anterior, sin versionar) describe el estado previo al `git pull`; su "Sección 0" ya no aplica.

**`pytest`, resumen pegado tal cual:**

```
$ python3 -m pytest -q
92 passed, 13 subtests passed in 0.19s
```

Por archivo: `test_loading` 20, `test_new_structure` 24, `test_section16_persistence` 7, `test_storage` 15, `test_undo` 17, `test_versions` 9. Ninguna prueba importa `eel` ni abre la interfaz.

---

## 1. Mapa del código que existe hoy

| Archivo | Líneas | Responsabilidad |
|---|---:|---|
| `main.py` | 384 | Puente Eel: 27 funciones `@eel.expose`, explorador de archivos con tkinter y arranque de la ventana. |
| `core/avl_tree.py` | 661 | `TreeKey` K=(P,M,I), `AVLNode`/`AVLTree` (rotaciones, modo estrés, recuperación), `BSTTree`, `compare_trees`. |
| `core/linear.py` | 71 | `UndoStack` (pila con tope de 100) y `ReportQueue` (cola FIFO sobre `deque`). |
| `core/__init__.py` | 2 | Reexporta las clases de `core`. |
| `domain/models.py` | 396 | Enums, `Epicenter`, `Zone`, `Station`, `Report`, `Association`, `SeismicEvent` (prioridad, clave, validación) y formato ISO 8601 con `Z`. |
| `domain/scenario.py` | 895 | `Scenario`: estado central y una operación por acción (alta, corrección, baja, cola, asociaciones, archivo, deshacer, auditoría, estrés, reloj, parámetros, persistencia, versiones, consultas §11). |
| `domain/storage.py` | 347 | Estado ↔ JSON con topología exacta (todo o nada); lo usan guardar, versiones y deshacer. |
| `domain/loader.py` | 428 | Carga por topología con validaciones y carga por inserciones (AVL + BST). |
| `domain/validation.py` | 182 | Validaciones compartidas: rangos, decimales, orden global por K, alturas y factores. |
| `domain/versions.py` | 134 | Versiones con nombre, un JSON por versión en `data/versions/`. |
| `domain/__init__.py` | 5 | Reexporta `Scenario` y los modelos. |
| `web/index.html` | 187 | Pantalla única: cabecera, barra de indicadores, formularios, pestañas AVL/BST, lista de eventos, barra de log. |
| `web/app.js` | 462 | Lógica de la interfaz: llamadas `eel.*`, dibujo SVG del árbol, listas y mensajes. |
| `web/style.css` | 346 | Estilos. |
| `README.md` | 109 | Instrucciones, arquitectura y descripción de los archivos de prueba. |
| `requirements.txt` | 1 | `eel>=0.18`. |
| `.gitignore` | 17 | Ignora `versions/`, `backend/`, `frontend/`, cachés y entornos. |

Fuera de alcance de esta tabla (por indicación): `tests/` (6 archivos, 92 pruebas) y `data/` (9 JSON de prueba, generados por `tools/make_data.py`).

---

## 2. Separación de capas

**`core/` o `domain/` importan `eel` o tocan el DOM: ninguno.** `grep -n -i -E "import eel|from eel|\beel\b|document\.|window\.|tkinter|innerHTML|getElementById" core/*.py domain/*.py` no devolvió coincidencias. Las dependencias van hacia abajo: `domain` → `core`, y `domain/models.py:309` importa `core.avl_tree` dentro de `build_key`. `tkinter` solo aparece en el puente (`main.py:276-277`).

**`web/` contiene reglas de negocio: solo menores y de presentación. No hay cálculo de prioridad, comparación de claves ni rotaciones.**

| Ubicación | Qué hace | Gravedad |
|---|---|---|
| `web/app.js:198`, `:209` | `Math.abs(n.bf) > 1` decide qué nodo se pinta como desbalanceado (umbral AVL). | Baja: debería venir del servidor. |
| `web/app.js:85` | Ordena la lista de eventos por prioridad y magnitud (sin desempate por id): copia parcial de K. | Baja: es solo el orden de presentación. |
| `web/index.html:51`, `:55`, `:56`, `:59`, `:60`, `:98` | `min`/`max` de id (1–999999), M (−2–10), H (0–700), x/y (0–1000) y revisión ≥ 1: rangos del §3 repetidos en el HTML. | Baja: son ayudas del formulario; el servidor valida la alta manual, no los reportes (§5). |
| `web/app.js:88`, `:190-192` | Traducen prioridad a nombre y color. | Presentación pura. |

En `main.py` hay un poco de lógica en el puente: `search_event` calcula profundidad y costo (`main.py:106-108`) y las zonas y estaciones de ejemplo están fijas (`main.py:29-40`).

---

## 3. Estado de cada requisito

Los números `B*`, `M*` y `E*` remiten a las pruebas ejecutadas (§5).

| Requisito | Lógica | Interfaz | Archivo:línea | Notas |
|---|:-:|:-:|---|---|
| Clave K=(P,M,I), comparación lexicográfica | Sí | Parcial | `core/avl_tree.py:20-87`; `domain/models.py:308-310`; UI `web/app.js:204-205` | La comparación va por tupla (`avl_tree.py:34-62`). Los nodos muestran id y M, pero no la clave completa. La raíz se muestra como cadena (`app.js:113`). |
| Prioridad P=3/2/1, límites inclusivos, zona poblada por borde | Sí | Parcial | `domain/models.py:286-299`, `:84-86`, `:127-129` | Comprobado con script: M=4.5/H=30.0 poblada→3, no poblada→2, H=30.1→2, M=6.0→3, borde Sur/Costa (x=500)→poblada. La UI muestra P (`app.js:87-88`), pero no si la zona es poblada. |
| AVL: insert, delete, search, rotaciones LL/RR/LR/RL, altura (vacío −1, hoja 0) | Sí, con límite de profundidad | Sí | `avl_tree.py:162-223` (insert, balanceo, rotaciones), `:227-252` (delete con `adopt`, `:118-122`), `:262-271` (search), `:105`, `:151` (alturas) | `insert`, `delete` y `recover_balance` son recursivos: `RecursionError` a ~1000 nodos degenerados (B8). UI: `app.js:221-260`. |
| BST comparativo sin balanceo | Sí | Parcial | `avl_tree.py:461-604`; UI pestaña `app.js:101-114` | La pestaña dibuja el BST del catálogo actual. La tabla AVL vs BST solo aparece tras "Cargar por inserciones" (`app.js:370-391`). `compare_trees_view` (`main.py:244-251`) no tiene botón. `BSTTree.insert` también es recursivo (`avl_tree.py:490-498`). |
| Pila de deshacer explícita (las 10 acciones del §13) | Sí, con defecto | Parcial | `core/linear.py:8-38`; acciones registradas en `scenario.py:203`, `:244`, `:270`, `:282`, `:405`, `:511`, `:627`, `:639`, `:672`, `:720` | Las 10 acciones del §13 se registran, más `TOGGLE_STRESS` (`:619`) y `RESTORE_VERSION`. Cada acción guarda una foto completa (`:63-75`). Tope de 100 acciones: descarta la más antigua sin avisar (`linear.py:11`, `:16-17`). Defecto B4b: deshacer pierde los reportes encolados después. UI: botón Deshacer (`index.html:122`, `app.js:282`); `mark_reviewed` y `update_parameters` no tienen botón. |
| Cola FIFO: orden visible, paso a paso y continuo | Parcial | Parcial | `linear.py:40-71`; `scenario.py:288-291`; UI `app.js:262-280` | FIFO y un paso por llamada: sí. Continuo con pausa: no encontrado. Orden visible: no; `queued_reports` viaja en `get_state` (`scenario.py:163`) pero la UI solo muestra el conteo (`app.js:51`). |
| Los 5 casos de reportes del §6 | Parcial | Parcial | `scenario.py:291-407` (ID eliminado `:300`; archivado `:306-343`; activo `:346-381`; nuevo `:384-402`) | Están los casos, incluidos eliminado y archivado. Fallos: no valida datos (B1); tras crear un evento desde la cola no recalcula asociaciones ajenas (B5, `:398`); el resultado no trae estación ni rotaciones (`:302`, `:326`, `:373`). La UI muestra solo el texto del resultado (`app.js:275-278`). |
| Validación de entrada (M, H, epicentro, fecha ≤ reloj, estación) | Parcial | Parcial | `models.py:378-396`; `scenario.py:177-188`; carga `validation.py:57-84` | Alta manual: valida todo (M1). Reportes: no valida nada (`scenario.py:288-289`, `:385-402`). Corrección manual: no valida nada (`scenario.py:211-248`, `models.py:314-332`). |
| Asociaciones: candidatos por W/R/magnitud/tiempo + desempate | Parcial | No | `scenario.py:411-461` | Candidatos correctos (M estrictamente mayor, estrictamente antes, ≤W, ≤R; `:440-457`). Desempate determinista `(-M, distancia, id)` (`:424-428`). Se recalculan en alta, corrección, baja, parámetros y reporte de rev. mayor, no tras crear desde la cola (B5). Solo se recalculan las activas (`:460`): un archivado conserva referencias a eventos eliminados (B6b). Sin pantalla: `query_event_associations` no se usa. |
| Modo estrés, recuperación global, bloqueo de salida si la auditoría no confirma | Parcial | Parcial | `avl_tree.py:178-179`, `:250-251`, `:283-312`; `scenario.py:615-629` | Estrés y recuperación funcionan: 200 árboles aleatorios recuperados sin fallos (B7). No existe el bloqueo: `toggle_stress` sale sin auditar (B2) y `recover_balance` no audita. No pausa la cola. UI: insignia (`index.html:20`, `app.js:63-72`), botones (`index.html:126-127`), nodo rojo si |bf|>1 (`app.js:198-201`). |
| Marca de acceso costoso (P=3 y prof. > L), distinguible de la prioridad | Sí | No | `scenario.py:90-92`, `:861-886` | Lógica correcta (consulta y conteo en `counts.costly_access`). No hay marca en el árbol (`app.js:183-212`), ni indicador, ni botón para la consulta, ni forma de cambiar L (`update_parameters` sin uso). |
| Eliminación individual | Sí | Parcial | `scenario.py:252-272`; UI `app.js:239-243` | Usa el borrado del AVL, registra el id eliminado y guarda la acción. Falta la vista previa del evento afectado que pide el §6: el botón elimina directo. |
| Archivo de rama: elegibilidad (P=1 y antigüedad estrictamente > T) y 3 desempates | Parcial | Parcial | `scenario.py:465-521` | P=1 correcto (`:487`). Antigüedad: `age < T` (`:490`), así que antigüedad == T resulta elegible (B3). Desempates: solo ordena por cantidad (`:468`); faltan mayor profundidad de raíz y mayor id (B3b). Sin vista previa (`main.py:196-199`, `app.js:321-329`). Deshacer sí. |
| Las 5 consultas del §11, con nodos examinados | Parcial | No | `scenario.py:726-886` | Top-k (`:726-760`): recorrido inverso con poda, reporta nodos. Intervalos (`:762-800`): fusiona las dos consultas en una y recorre todo el árbol. Asociaciones (`:802-859`): no reporta nodos y recorre diccionarios. Costosos (`:861-886`): reporta nodos por evento, pero itera sobre `event_index`, no sobre el AVL. Ninguna se llama desde la UI (§4). |
| Carga por inserciones / por topología / guardado, con explorador de archivos | Sí | Sí | `scenario.py:678-696`; `loader.py:36-90`, `:313-386`; `storage.py:99-124`; `main.py:274-331` | Rechazo total con lista de problemas (`app.js:341-345`). Explorador tkinter (`main.py:274-291`): en este equipo `tkinter` no está instalado y las tres funciones lanzan `ModuleNotFoundError` sin capturar (M2). Con 1500 nodos ascendentes la carga por inserciones lanza `RecursionError` sin capturar (B8). |
| Versiones con nombre persistentes | Sí | Sí | `domain/versions.py:27-134`; `scenario.py:700-714`; UI `app.js:397-440` | Persisten tras reiniciar (`test_versions.py:33`, `test_section16_persistence.py:104`). Una versión dañada se lista como inválida y se rechaza. |
| Auditoría: orden global por K, unicidad, referencias, alturas, factores | Parcial | Parcial | `scenario.py:546-611` | Orden global (`:555-561`), unicidad (`:593-601`), alturas (`:578-591`), factores solo en modo normal (`:563-567`). No revisa referencias de asociaciones. En estrés dice "válido" sin informar el desbalance (B2b). `validation.check_tree` (`validation.py:112-148`) es iterativo y completo, pero solo lo usa el cargador (`loader.py:58`). La UI muestra solo el primer error (`app.js:311`). |
| Indicadores del §14 (incl. LL/RR/LR/RL y giros simples) | Sí | Parcial | `scenario.py:77-166`; UI `index.html:26-39`, `app.js:47-61` | Todo viaja en `get_state`. La UI muestra: activos, archivados, eliminados, cola, undo, altura, hojas, balance, LL, RR, LR y RL. No muestra: 4 recorridos, giros simples, correcciones/descartados/conflictos/archivos masivos, eventos por prioridad, pendientes ni costosos. Contadores restaurables: `storage.py:172-176`. |
| Vista del AVL | Sí | Sí | `app.js:120-215` | SVG escrito a mano, con factor de balance sobre el nodo. |
| Vista del BST | Sí | Sí | `app.js:101-114`; `scenario.py:124-129` | Pestaña "BST comparativo". |
| Plano geográfico 0–1000 km | Sí (datos) | No | zonas en `scenario.py:164`; epicentros en `:161` | Los datos llegan a la interfaz, pero no hay dibujo: `grep -i "mapa\|plano\|geogr"` en `web/` no encontró nada. |

Requisitos del §3/§6/§7 que no estaban en la lista:

| Requisito | Lógica | Interfaz | Archivo:línea | Notas |
|---|:-:|:-:|---|---|
| Alta manual (rev. 1, prioridad, clave, pendiente, una acción) | Sí | Sí | `scenario.py:174-207`; `app.js:221-229` | Valida y no muta ante error (M1). |
| Corrección manual (rev+1, retira con clave anterior, reinserta) | Parcial | Parcial | `scenario.py:211-248` | Sin validación (B1b). La UI solo corrige M y H (`main.py:76-85`). |
| Marcar revisado | Sí | No | `scenario.py:276-284`; `main.py:170-177` | No existe botón (§4). |
| Consulta de un evento (activo/archivado/eliminado y todos sus datos) | Parcial | Parcial | `main.py:98-116` | Solo busca activos. Archivado o eliminado devuelve "no encontrado" (M4). Muestra id, M, P, prof., rev., profundidad y costo (`app.js:250-252`). Faltan clave, altura, factor de balance, estaciones, zona y asociaciones. |
| Reloj de simulación explícito, solo avanza | Sí | Parcial | `scenario.py:633-641` | La UI solo tiene "+1h" fijo (`index.html:21`, `app.js:315-319`). |
| Parámetros W, R, L, T | Sí | No | `scenario.py:643-674`; `main.py:254-266` | `update_parameters` no tiene control en pantalla. |

---

## 4. Qué se ve en la ventana

Pantalla única (`web/index.html`); no hay navegación entre vistas.

| Elemento | Ubicación | Llama a (`eel.expose`) |
|---|---|---|
| Reloj de simulación | `index.html:17` | `get_state` (`app.js:31`, `:37`) |
| Insignia Normal/ESTRÉS | `index.html:20` | `get_state.stress_mode` (`app.js:36`) |
| Botón "Avanzar Reloj +1h" | `index.html:21` | `advance_clock(1)` (`app.js:316`) |
| Barra de indicadores (12 valores) | `index.html:26-39` | `get_state` (`app.js:47-61`) |
| Formulario "Crear Evento" | `index.html:48-64` | `create_event` (`app.js:223`) |
| Formulario "Corregir Evento" (id, M, H) | `index.html:67-77` | `correct_event` (`app.js:234`) |
| "Eliminar" | `index.html:84` | `delete_event` (`app.js:240`) |
| "Buscar" y cuadro de resultado | `index.html:86-90` | `search_event` (`app.js:246`) |
| Formulario "Encolar Reporte" + "Encolar" | `index.html:94-113` | `enqueue_report` (`app.js:264`) |
| "Procesar Siguiente" | `index.html:114` | `process_report` (`app.js:274`) |
| "Deshacer" | `index.html:122` | `undo_action` (`app.js:283`) |
| "Auditar" | `index.html:123` | `run_audit` (`app.js:307`) |
| "Modo Estres" | `index.html:126` | `toggle_stress` (`app.js:290`) |
| "Recuperar Balance" | `index.html:127` | `recover_balance` (`app.js:296`) |
| "Archivar Elegibles" | `index.html:130` | `archive_eligible` (`app.js:322`) |
| "Guardar escenario" | `index.html:137` | `save_scenario` (`app.js:348`) |
| "Cargar escenario (topología)" | `index.html:138` | `load_scenario` (`app.js:353`) |
| "Cargar por inserciones" + tabla de comparación | `index.html:139-140` | `load_insertions` (`app.js:371`) |
| Versiones: nombre + "Guardar" + lista con "Restaurar" | `index.html:144-153` | `save_version` (`app.js:423`), `list_versions` (`:398`), `restore_version` (`:432`) |
| Selectores de estación | `index.html:52`, `:110` | `get_stations` (`app.js:448`) |
| Pestañas "Arbol AVL" / "BST comparativo" y SVG | `index.html:160-166` | Ninguna (dibujan el último `get_state`, `app.js:101-114`) |
| Lista "Eventos Activos" | `index.html:172-177` | `get_state.events` (`app.js:35`) |
| Barra de log | `index.html:181-183` | (mensajes de todas las acciones) |

**Funciones expuestas que ninguna parte de la interfaz invoca (huérfanas): 7 de 27.** Comprobado con `grep "eel\.<función>(" web/app.js`: 0 coincidencias.

| Función | Línea en `main.py` | Qué falta en pantalla |
|---|---:|---|
| `mark_reviewed` | 170 | Botón de marcar revisado. |
| `query_top_k_pending` | 202 | Consulta 1 del §11. |
| `query_by_interval` | 211 | Consultas 2 y 3 del §11. |
| `query_event_associations` | 224 | Consulta 4 del §11 (candidatos, referencia y réplicas). |
| `query_costly_high_priority` | 234 | Consulta 5 del §11 y marca de acceso costoso. |
| `compare_trees_view` | 244 | Comparativa AVL vs BST del catálogo actual. |
| `update_parameters` | 254 | Edición de W, R, L y T. |

No encontrado en `web/`: vista de histórico (`archived_events` no se dibuja), cola con su orden, plano geográfico, pila de deshacer visible, recorridos.

---

## 5. Bugs confirmados ejecutando código

Scripts temporales en el directorio temporal de la sesión; borrados al terminar. Estado de partida: reloj `2026-01-01` (o el indicado), zonas y estaciones como `main.py:29-40`.

### B1. Reportes con datos inválidos: se aceptan todos (§3, §6)

`Scenario.enqueue_report` + `process_next_report`, un reporte por caso:

```
M=99 (fuera de rango)                  -> CREATED   evento_creado=True M=99 rev=1
H=900 (fuera de rango)                 -> CREATED   evento_creado=True M=5 rev=1
estacion inexistente 'XXX'             -> CREATED   evento_creado=True M=5 rev=1
epicentro x=5000                       -> CREATED   evento_creado=True M=5 rev=1
id=0 (fuera de 1..999999)              -> CREATED   evento_creado=True M=5 rev=1
id=5000000                             -> CREATED   evento_creado=True M=5 rev=1
fecha 2030 > reloj 2026-01-01          -> CREATED   evento_creado=True M=5 rev=1
M=4.46 (dos decimales)                 -> CREATED   evento_creado=True M=4.5 rev=1
revision=0                             -> CREATED   evento_creado=True M=5 rev=0
revision=-3                            -> CREATED   evento_creado=True M=5 rev=-3
```

Por la ruta de la interfaz (`main.py`, con Eel simulado): `enqueue_report(50, 1, "XXX", 99, 900, 5000, 100, "2030-01-01T00:00")` → `{'ok': True, ...}`; `process_report()` → `{'result': 'CREATED', 'event_id': 50}` y el evento 50 quedó activo. En cambio la alta manual sí valida:

```
create_event M=99          -> {'ok': False, 'message': 'magnitude must be between -2.0 and 10.0, got 99.0'}
create_event estación XXX  -> {'ok': False, 'message': "Estación 'XXX' no existe en el escenario"}
create_event año 2027      -> {'ok': False, 'message': 'occurrence_time (2027-01-01T00:00:00) cannot be after simulation clock (2026-01-01T00:00:00)'}
```

Causa: `scenario.py:288-289` (encolar sin validar) y `:385-402` (el `try/except ValueError` no puede saltar porque el constructor no valida).

**B1b. Corrección manual sin validación** (`scenario.py:211-248`):

```
{'magnitude': 99.0}   -> ACEPTADA: M=99.0 H=70.0 rev=2 P=HIGH
{'depth_km': -5.0}    -> ACEPTADA: M=99.0 H=-5.0 rev=3 P=HIGH
{'magnitude': 4.46}   -> ACEPTADA: M=4.5 H=-5.0 rev=4 P=MEDIUM
{'depth_km': 9999.0}  -> ACEPTADA: M=4.5 H=9999.0 rev=5 P=MEDIUM
```

**B1c. Consecuencia:** un escenario con un reporte inválido se guarda, pero no se puede volver a cargar:

```
RECARGA RECHAZADA:
  Node 1: magnitude must be between -2.0 and 10.0, got 99
  Node 1: unknown station 'XXX'
```

**B1d. Fechas con `Z`:** `main.py:61`, `:131`, `:215-216` usan `datetime.fromisoformat`, no `parse_time` (`models.py:22`). `create_event(..., "2025-12-31T00:00:00Z", ...)` devuelve `{'ok': False, 'message': "can't compare offset-naive and offset-aware datetimes"}`. `enqueue_report` con `Z` sí encoló y creó el evento sin error. La interfaz nunca envía `Z`, así que es latente.

### B2. Salir de modo estrés con el árbol desbalanceado (§8)

7 altas en estrés (altura 6) y luego `toggle_stress()`, que es lo que llama el botón:

```
en estres: height=6 balanced=False
toggle_stress() -> {'stress_mode': False} | balanced = False | height = 6
run_audit(): is_valid=False errores=5  primero: ['Nodo (1, 1.1, 1) tiene BF=-6']
resumen 'balanced' que ve la interfaz: False | stress_mode: False
recover_balance() en modo normal -> {'result': 'NOT_IN_STRESS', 'message': 'El árbol no está en modo estrés'}
```

El sistema queda en "modo normal" con un árbol que no es AVL, y `recover_balance` ya no puede repararlo (`scenario.py:623-624`). Causa: `scenario.py:615-620` no comprueba nada.

**B2b. Auditoría en estrés:** `run_audit()` con el árbol desbalanceado devuelve `{'is_valid': True, 'errors': [], 'nodes_checked': 7}`. El §14 pide informar el desbalance esperado y distinguirlo de errores de orden o metadatos (`scenario.py:563-567` lo omite).

### B3. Antigüedad exactamente igual a T (§10)

```
antiguedad = 72h exactas, T=72 -> ELEGIBLE (incorrecto: debe ser > T)
antiguedad = 71h59m59s        -> no elegible (correcto)
antiguedad = 72h00m01s        -> ELEGIBLE (correcto)
```

Causa: `scenario.py:490` usa `age < timedelta(...)` para descartar.

**B3b. Desempates del §10** (dos ramas elegibles disjuntas, mismo tamaño):

```
raiz=100 izq=5 der=900
elegibles: [[5], [900]]
§10 exige mayor id de raíz => [900]; archive_largest_eligible() -> {'result': 'ARCHIVED', 'count': 1, 'event_ids': [5]}
elegibles: [([103], 'prof=1'), ([102], 'prof=2')]
§10 exige la raíz más profunda => [102]; archive_largest_eligible() -> {'result': 'ARCHIVED', 'count': 1, 'event_ids': [103]}
```

`find_eligible_branches` solo ordena por cantidad (`scenario.py:468`), así que gana la primera en preorden.

### B4. Deshacer un paso de cola

Ese caso funciona: el reporte vuelve a su posición original, incluso si el paso lo descartó.

```
cola antes : [(1,'EST-001'), (2,'EST-002'), (1,'EST-002')]
paso 1     : {'result': 'CREATED', 'event_id': 1}
cola tras 1: [(2,'EST-002'), (1,'EST-002')]
undo       : PROCESS_REPORT
cola tras undo: [(1,'EST-001'), (2,'EST-002'), (1,'EST-002')] | evento 1 existe: False
--- reporte antiguo descartado
paso: OUTDATED | cola: [8]  ->  tras undo, cola: [7, 8]
```

**B4b. Defecto relacionado:** encolar no es una acción y la foto de deshacer incluye la cola, así que deshacer descarta lo encolado después:

```
cola antes de undo: [2, 3]
cola tras undo    : [1, 2]  (el reporte 3 desapareció)
```

Causa: `scenario.py:288-289` (no registra) y `:295`/`:533` (foto y restauración de la cola completa).

### B5. Caso §16 "reporte tardío" por la cola: las asociaciones ajenas quedan obsoletas

5.6 a las 10:00 (id 150), 4.2 a las 10:20 (id 151), luego 6.1 a las 09:55 (id 152), todos cercanos:

```
-- alta manual (create_event)
 antes  : ref(151)=150 ref(150)=None
 despues: ref(151)=152 ref(150)=152 ref(152)=None | asoc(151).candidatos=[152, 150] asoc(150).candidatos=[152]
-- por la cola (process_next_report, caso 'ID desconocido')
 antes  : ref(151)=150 ref(150)=None
 cola   : {'result': 'CREATED', 'event_id': 152}
 despues: ref(151)=150 ref(150)=None ref(152)=None | asoc(151).candidatos=[150] asoc(150).candidatos=[]
```

Por la cola el 6.1 no aparece como candidato de 4.2 ni de 5.6. Causa: `scenario.py:398` calcula solo la asociación del evento nuevo; los casos de revisión mayor sí llaman a `recalculate_all_associations` (`:325`, `:364`). Viola el §7 ("un alta … debe actualizar las asociaciones afectadas").

**B6b.** Eliminar el evento que es referencia de un archivado deja la referencia colgando:

```
archivar: {'result': 'ARCHIVED', 'count': 1, 'event_ids': [2]}
ref(2 archivado) antes: 1
ref(2 archivado) tras eliminar 1: 1 | 1 en deleted_ids: True
query_event_associations(2): {'reference': None, 'candidates': []}
```

Causa: `recalculate_all_associations` solo recorre `event_index` (`scenario.py:460`).

### B7. Recuperación global (comprobación que resultó correcta)

200 árboles aleatorios en estrés (5–60 nodos, |bf| máximo visto = 11, es decir, diferencias > 2):

```
200 arboles en estres (max |bf| visto = 11): fallos = 0
```

En cada uno se comprobó: balanceado, mismos identificadores, orden estrictamente ascendente, auditoría válida, asociaciones idénticas y `stress_mode` en falso.

### B8. Profundidad grande (>1000 nodos degenerados): sí hay `RecursionError`

`core`, inserciones ascendentes en un `AVLTree` en modo estrés y en un `BSTTree`:

```
-- n = 900   AVL insert OK size=900 height=899 | BST insert OK | to_dict OK | inorder OK | recover_balance OK final_height=12
-- n = 1000  AVLTree.insert -> RecursionError | BSTTree.insert -> RecursionError
-- n = 1200  AVLTree.insert -> RecursionError | BSTTree.insert -> RecursionError
-- n = 5000  AVLTree.insert -> RecursionError (se detuvo con size=997)
```

Un BST se degenera en modo normal con claves ascendentes, que es justo la comparación que pide el §11. Con una cadena de 1500 nodos cargada por topología (archivo válido para el §12, iterativo en la carga):

```
load_scenario_file(cadena de 1500, modo estres)  OK activos=1500 altura=1499
search de la hoja mas profunda (iterativo)       OK 1500
summary() [lo que llama get_state]               RecursionError
json.dumps(summary())                            RecursionError
run_audit()                                      RecursionError
snapshot() [se hace en cada accion]              OK
recover_balance()                                RecursionError
estado tras el fallo: stress_mode=True, is_balanced=False
```

Con esa carga la interfaz no puede refrescar (`get_state`), auditar ni recuperar. Además `load_insertions_file` con 1500 eventos de misma M e ids ascendentes lanza `RecursionError` en el BST. `main._load` solo captura `StateError` (`main.py:301`), así que el error llega sin tratar a la interfaz; el escenario no cambia (activos = 0). Funciones recursivas: `avl_tree.py:165-180`, `:230-252`, `:301-312`, `:321-388`, `:428-440`, `:468-471`, `:490-498`, `:593-604`, y las de auditoría `scenario.py:555-561`, `:569-576`, `:583-591`.

### Otros hallazgos verificados

- **M2. tkinter ausente.** `main.load_scenario()`, `load_insertions()` y `save_scenario()` lanzan `ModuleNotFoundError: No module named 'tkinter'` sin capturar (`main.py:276-277`; solo se captura `StateError` en `:301` y `OSError` en `:318`). Los tres botones del panel "Archivo" quedan inertes.
- **M4. Búsqueda de eliminado.** `search_event(777)` con 777 en `deleted_ids` → `{'ok': False, 'message': 'Evento 777 no encontrado'}`. El §6 pide indicar si está activo, archivado o eliminado.
- **E1. Arranque real con Eel** (venv temporal con `eel>=0.18` → Eel 0.18.2): `python main.py` sirvió `/index.html` (200), `/eel.js` (200) y `/app.js` (200). El log mostró `/bin/sh: 1: start: not found`: en Linux el modo `edge` intenta ejecutar el comando de Windows `start`, no lanza excepción y no abre ventana, y las ramas de respaldo de `main.py:379-384` nunca se activan. La ventana no se abrió; hay que ir a `http://localhost:8080/index.html`. No abrí la ventana ni ejecuté el JavaScript en un navegador: `web/app.js` se validó solo con `node --check` (sintaxis correcta) y lectura.

---

## 6. Casos §16

| Caso | ¿Test automatizado? | ¿JSON de datos? | Evidencia | Qué falta |
|---|---|---|---|---|
| Límites y empates | Sí | Sí | `tests/test_loading.py:229-237`; `data/insertions/mezclado.json` y `ascendente.json` (`tools/make_data.py:44-70`) | Cubre M=4.5/H=30.0 poblada y no poblada, M=6.0, borde x=500 (evento 118) y empates 140/141/142. No prueba H=30.1 (lo comprobé aparte). |
| Corrección y reporte antiguo | Sí | Sí | `test_loading.py:102-114`; `data/topologies/normal.json` (evento 170: 6.2/15.0, rev. 2; cola con el reporte rev. 1); `make_data.py:126-127`, `:129-130`; `test_section16_persistence.py:123` | El test arranca ya corregido: comprueba prioridad final y `OUTDATED`, no la transición P2→P3. |
| Reporte tardío | No | No | no encontrado | Los eventos 150 (5.6) y 151 (4.2) están en `make_data.py:56-57`, pero no existe el 6.1 de las 09:55. `test_storage.py:36` usa esas magnitudes en otro fixture, sin asertar candidatos. Además B5 muestra que la ruta por cola falla. |
| Rotaciones y recuperación | Parcial | Parcial | `test_new_structure.py:62-94` (7 inserciones ascendentes; estrés + recuperación con 19 claves), `test_undo.py:62-67`, `:85-93`; `data/topologies/estres.json` (FB hasta −6; `test_loading.py:116-122`) | Ningún test provoca los cuatro casos por separado (no hay `rotations_lr`/`rotations_rl` en `tests/`). La recuperación solo aserta `is_balanced`; no comprueba identidades, orden ni asociaciones (yo sí, en B7). |
| Archivo masivo | Parcial | Parcial | `test_undo.py:46-47`, `test_new_structure.py:261-285` (un evento archivado y reactivado); `normal.json` contiene un archivado | No hay test de rama con varios eventos, desempates, "sin ramas elegibles" (`NO_ELIGIBLE` no aparece en `tests/`) ni raíz baja con descendiente de mayor prioridad. B3 y B3b muestran defectos. |
| Persistencia y consistencia | Sí | Sí | `test_section16_persistence.py:43-158` (7 tests); 9 JSON en `data/`; regeneración reproducible (`:161-`) | Cubre guardar/cargar normal y estrés, rechazo de inconsistentes sin alterar, restaurar versión tras reiniciar, deshacer corrección y paso de cola. |

Además: `data/test_cases_section16/` solo tiene `.gitkeep`. No hay ráfagas de reportes (§17: "ráfagas de reportes") en `data/`.

---

## 7. Portabilidad

**Rutas fijas.**
- `main.py:377`: `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`. Es una ruta de Windows; no es de entrada de datos, así que el §12 no la prohíbe, pero rompe la portabilidad.
- `main.py:378`, `:381`, `:384`: `port=8080` fijo. Si el puerto está ocupado, falla.
- `DATA_DIR` (`main.py:20`) es relativo al archivo, no fijo. Solo es el directorio inicial del explorador (`:283`). No hay rutas de entrada fijas.
- `web/index.html:8`: carga la fuente Inter desde `fonts.googleapis.com`; sin red, solo cambia la tipografía.

**¿Arranca en Linux?** Parcialmente (E1):
- El servidor y los archivos estáticos responden.
- El modo `edge` no abre ventana (`start: not found`) y no cae al respaldo (`main.py:376-384`, solo reacciona a excepciones).
- Este equipo tiene `google-chrome` y `firefox`, pero el código no los usa.
- El explorador de archivos falla sin `python3-tk` (M2), y el README afirma que `tkinter` "viene con Python" (`README.md:13`), lo cual no ocurre en Debian/Ubuntu.

**Dependencias de `requirements.txt`.**
- `eel>=0.18`: **no instalado** en el Python del sistema (`ModuleNotFoundError: No module named 'eel'`).
- Al instalar en un venv temporal se resolvió: Eel 0.18.2, bottle 0.13.4, bottle-websocket 0.2.9, gevent 26.9.0, gevent-websocket 0.10.1, future 1.0.0, pyparsing 3.3.3.
- Falta declarar `tkinter` (paquete del sistema). `pytest` está instalado (9.1.1) pero no figura en `requirements.txt`. El README usa `unittest`.

**Comentarios que no están en inglés (§17).** Conteo por heurística (acentos y palabras españolas), con revisión manual de los casos dudosos. Cuenta comentarios `#`, `//`, `/* */`, `<!-- -->` y docstrings en líneas no vacías. Es una cuenta aproximada; los números de línea son exactos para lo detectado.

| Archivo | Comentarios | En español | Líneas (español) |
|---|---:|---:|---|
| `main.py` | 45 | 45 | 2, 4-7, 18-19, 22, 25, 28, 42, 47, 52, 59, 78, 90, 100, 122, 141, 148, 154, 160, 166, 172, 182, 192, 198, 204, 213, 226, 236, 246, 256, 271, 275, 281, 310, 324, 330, 335, 340, 346, 356, 368, 375 |
| `core/avl_tree.py` | 35 | 26 | 2, 4-8, 21, 33, 74, 95, 119, 133, 140, 160, 225, 260, 263, 281, 425, 448, 462, 530, 608, 624-625, 634 |
| `core/linear.py` | 3 | 3 | 2, 9, 41 |
| `domain/models.py` | 28 | 11 | 2, 48, 73, 114, 150, 182, 227, 260, 284, 343, 376 |
| `domain/scenario.py` | 62 | 41 | 2, 4-5, 23, 37, 43, 46, 78-79, 169, 172, 209, 250, 274, 286, 299, 305, 345, 383, 409, 423, 463, 544, 613, 631, 723, 728-731, 767-769, 804-805, 813, 829, 841, 863-864, 890 |
| `domain/storage.py`, `loader.py`, `validation.py`, `versions.py` | 119 | 0 | (en inglés) |
| `web/app.js` | 26 | 17 | 14, 21, 26, 84, 138, 143-145, 194, 218, 332, 394, 404, 443, 447, 452, 461 |
| `web/index.html` | 14 | 7 | 47, 66, 79, 93, 118, 134, 143 |
| `web/style.css` | 16 | 1 | 2 |
| `tools/make_data.py` | 35 | 0 | (en inglés) |
| **Total (sin tests)** | **383** | **≈151** | |

En `tests/`, solo `test_new_structure.py` tiene comentarios en español: 13 de 14 (líneas 2-3, 10, 23, 49, 53, 114, 137, 219, 232, 236, 253, 331). Los otros cinco archivos de prueba están en inglés. Los mensajes de la interfaz están en español, lo cual es correcto; solo se cuentan comentarios.

---

## 8. Lista de pendientes, priorizada

Orden: primero lo que incumple el enunciado, luego lo que está a medias, al final lo cosmético. El esfuerzo es una estimación mía.

**A. Incumple el enunciado**

| # | Pendiente | Sección | Esfuerzo | Lógica / Interfaz |
|--:|---|---|:-:|:-:|
| 1 | Validar los reportes antes de crear, corregir o encolar: M, H, epicentro, id, decimales, fecha ≤ reloj, estación y revisión ≥ 1 (B1). | §3, §6 | Bajo | Lógica |
| 2 | Validar la corrección manual antes de aplicar (todo o nada) (B1b). | §6 | Bajo | Lógica |
| 3 | Bloquear la salida de modo estrés si la auditoría no confirma equilibrio; que `toggle_stress` y `recover_balance` no dejen "normal" con árbol desbalanceado (B2). | §8 | Bajo | Lógica |
| 4 | Antigüedad estrictamente > T: `<` → `<=` en `scenario.py:490` (B3). | §10 | Bajo | Lógica |
| 5 | Desempates de archivo: mayor profundidad de raíz, luego mayor id (B3b). | §10 | Bajo | Lógica |
| 6 | Recalcular asociaciones al crear desde la cola, y las de archivados al eliminar (B5, B6b). | §7, §16 | Bajo | Lógica |
| 7 | Deshacer no debe perder reportes encolados después (B4b): registrar el encolado o excluir la cola de la foto. | §13 | Medio | Lógica |
| 8 | Quitar la recursión de insert/delete/recover, BST, `to_dict`, recorridos y auditoría, o fijar y documentar un límite (B8). | §11, §16 | Medio | Lógica |
| 9 | Auditoría: informar el desbalance esperado en estrés, revisar referencias de asociaciones y devolver un reporte por evento (B2b). Reusar `validation.check_tree`. | §14 | Medio | Lógica |
| 10 | Resultado de cada paso de cola con estación y rotaciones producidas. | §8 | Bajo | Lógica + interfaz |
| 11 | Consultas: nodos examinados en la de asociaciones; la de costosos debe usar el AVL; separar las dos consultas por intervalo. | §11 | Medio | Lógica |
| 12 | Plano geográfico 0–1000 km con zonas y epicentros. | §15 | Medio | Interfaz |
| 13 | Marca de acceso costoso visible (canal distinto de la prioridad) y L editable en pantalla. | §9 | Medio | Interfaz |
| 14 | Cola visible en orden de recepción y procesamiento continuo con pausa; la recuperación global debe pausarlo. | §8 | Medio | Interfaz (+ lógica mínima) |
| 15 | Pantallas de las 5 consultas del §11 (todas huérfanas). | §11 | Medio | Interfaz |
| 16 | Vista previa antes de eliminar y de archivar: ids afectados, cantidad y justificación. | §6, §10 | Medio | Interfaz + lógica |
| 17 | Consulta de evento completa: activo/archivado/eliminado, clave, altura, factor de balance, estaciones, zona y asociaciones (M4). | §6 | Medio | Interfaz + lógica |
| 18 | Botón "Marcar revisado", avance de reloj configurable y edición de W, R, T. | §3, §6, §7 | Bajo | Interfaz |
| 19 | Indicadores del §14 faltantes: 4 recorridos, giros simples, correcciones/descartados/conflictos/archivos masivos, eventos por prioridad, pendientes, costosos. | §14 | Bajo | Interfaz |
| 20 | Vista de histórico (archivados) y de la pila de deshacer. | §15 | Bajo | Interfaz |
| 21 | Portabilidad: modo de navegador según el sistema (Chrome/Edge/por defecto), `tkinter` documentado o alternativa, captura de su error (M2). | §12, §17 | Bajo | Interfaz (puente) |
| 22 | Datos y pruebas de los casos §16 que faltan: reporte tardío, cuatro rotaciones y recuperación con verificación, archivo masivo con desempates y sin ramas; ráfagas de reportes en `data/`. | §16, §17 | Medio | Pruebas |
| 23 | Comentarios en español → inglés (≈151 de 383). | §17 | Medio | Ambos |

**B. A medias**

| # | Pendiente | Sección | Esfuerzo | Lógica / Interfaz |
|--:|---|---|:-:|:-:|
| 24 | Comparativa AVL vs BST sobre el catálogo actual con botón (`compare_trees_view` huérfana). | §11, §15 | Bajo | Interfaz |
| 25 | Mostrar todos los errores de la auditoría, no solo el primero (`app.js:311`). | §14 | Bajo | Interfaz |
| 26 | Corrección manual limitada a M y H en el puente y la UI; el §6 permite corregir epicentro y fecha. | §6 | Bajo | Interfaz + puente |
| 27 | Tope de 100 acciones de deshacer, sin aviso (`linear.py:11`); justificarlo o quitarlo. Cada acción guarda una foto completa (memoria O(n) por acción). | §13 | Bajo | Lógica |
| 28 | `main.py` usa `fromisoformat` en vez de `parse_time` (B1d). | §3 | Bajo | Puente |

**C. Cosmético**

| # | Pendiente | Sección | Esfuerzo | Lógica / Interfaz |
|--:|---|---|:-:|:-:|
| 29 | Mover a Python el umbral `|bf| > 1` y el orden de la lista (§2). | — | Bajo | Interfaz |
| 30 | Textos de la interfaz sin tildes ("Arbol", "estres", "Prof."). | — | Bajo | Interfaz |
| 31 | README: sección "Equipo" con marcadores genéricos; la línea de `tkinter` es inexacta en Linux. | §17 | Bajo | — |
| 32 | Fuente de Google externa (`index.html:8`); puerto fijo (`main.py:378`). | — | Bajo | Interfaz |
| 33 | `level_order` usa `pop(0)` (O(n²)) y `BSTTree.to_dict` calcula la altura por nodo (`avl_tree.py:370`, `:601`). | — | Bajo | Lógica |

Entregables del §17 fuera del código (manual de usuario, manual técnico con reporte de uso de IA, videos): no encontrados en el repositorio; `docs/` solo tiene `.gitkeep`. Los manuales deben ir por correo, no en Git, según el §17.
