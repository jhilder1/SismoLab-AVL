# INFORME DE ESTADO — SismoLab AVL

Generado el 2026-09-26. Solo lectura: no se modificó ningún archivo de código fuente.

## 0. Advertencia previa: hay dos estados distintos del proyecto

El checkout local **no es** el estado más reciente del equipo. Todas las cifras de este informe indican a cuál de los dos se refieren.

| | Commit | Arquitectura | Estado |
|---|---|---|---|
| **A. `origin/main`** (remoto) | `8c277ce` (2026-09-26) | Eel + HTML/JS puro. Carpetas `core/`, `domain/`, `web/` | Es el estado vigente del equipo. Todas las referencias `archivo:línea` de las secciones 1–5 sin otra indicación son de **A**. |
| **B. Checkout local** (`main`) | `05ab8a9` (2026-09-15) + cambios sin commitear | FastAPI + React. Carpetas `backend/`, `frontend/` | Está **9 commits detrás** de A (`git status`: "detrás de 'origin/main' por 9 commits"). Es la arquitectura que el commit `e1b7724` (jhilder1, 2026-09-21) reemplazó. |

Para leer A sin tocar el árbol de trabajo se extrajo con `git archive origin/main` a una carpeta temporal. Para ver cualquier línea citada: `git show origin/main:<ruta>`.

El enunciado (PDF) **no está en el repo** (`find -iname "*.pdf"` dentro de `SismoLab-AVL/`: no encontrado). Se leyó desde `~/Descargas/Proyecto Estructuras de Datos SismoLab AVL.pdf`. `docs/` solo contiene `.gitkeep`.

---

## 1. Stack e infraestructura

### 1.1 Lenguajes, librerías y versiones

**A. `origin/main`**

| Elemento | Valor | Fuente |
|---|---|---|
| Lenguaje backend | Python 3.12 ("probado con 3.12.10") | `README.md` §Requisitos |
| Dependencias | `eel>=0.18` (única línea) | `requirements.txt:1` |
| Instalado al verificar | Eel 0.18.2, bottle 0.13.4, gevent 26.9.0 | `pip list` en venv temporal |
| Stdlib usada | `tkinter` (explorador de archivos), `json`, `unittest`, `datetime`, `re`, `collections.deque` | `main.py:276-277`, `domain/storage.py:23`, `core/linear.py:5` |
| Frontend | HTML + JS + SVG sin framework ni build | `web/index.html`, `web/app.js` |
| Recursos externos | Google Fonts por CDN (`web/index.html:8`) y `/eel.js` (`web/index.html:9`) | — |
| Navegador | Edge (ruta fija) con retroceso a Chrome/por defecto | `main.py:377-384` |

**B. Checkout local**

| Elemento | Valor | Fuente |
|---|---|---|
| Backend | Python 3.12; `fastapi>=0.115.0`, `uvicorn[standard]>=0.30.0`, `pydantic>=2.0.0`, `python-multipart>=0.0.9`, `pytest>=8.0.0`, `pytest-asyncio>=0.23.0` | `backend/requirements.txt:3-12` |
| Instalado al verificar | fastapi 0.141.1, pydantic 2.13.5, pytest 9.1.1 | `pip install -r` en venv temporal |
| Frontend | React `^19.2.8`, Vite `^8.3.0`, `@vitejs/plugin-react ^6.1.1`, oxlint `^1.81.0` | `frontend/package.json` |

### 1.2 Cómo se arranca

**A. `origin/main`** (`README.md` §Ejecutar; `main.py:371-384`):

```
pip install -r requirements.txt
python main.py
```

Verificado en este equipo: `pip install -r requirements.txt` funciona y `import main` termina sin error (27 funciones `@eel.expose` registradas, estado inicial con 0 eventos activos). **No se abrió la ventana** (no hay entorno gráfico). Limitaciones observadas:
- `tkinter` **no está instalado** en el Python de este equipo (`ModuleNotFoundError`), así que los botones de guardar/cargar (`main.py:274-291`) no se pudieron ejercitar aquí. El README dice que "viene con Python": es cierto en Windows, no en Debian/Ubuntu (requiere `python3-tk`).
- `main.py:377` usa la ruta fija `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`; en Linux cae al `except` (`main.py:379`).

**B. Checkout local** (`README.md` local): `cd backend && uvicorn main:app --reload --port 8000` y `cd frontend && npm run dev`.
- **El comando del README falla.** Ejecutado tal cual: `ModuleNotFoundError: No module named 'backend'` en `backend/main.py:11` (`from backend.services.scenario import scenario`). Solo funciona desde la raíz del repo (`from backend.main import app` importa bien y expone `/health` y `/state`).
- Frontend: `npm run lint` limpio y `npm run build` compila (verificado en el turno anterior).

### 1.3 Árbol de directorios (3 niveles) con líneas por archivo `.py/.js`

**A. `origin/main` @ `8c277ce`**

```
SismoLab-AVL/
├── main.py                              384
├── requirements.txt                       1
├── README.md                            109
├── .gitignore
├── core/
│   ├── __init__.py                        2
│   ├── avl_tree.py                      661   TreeKey, AVLNode, AVLTree, BSTNode, BSTTree, compare_trees
│   └── linear.py                         71   UndoStack, ReportQueue
├── domain/
│   ├── __init__.py                        5
│   ├── models.py                        396   enums, Epicenter, Zone, Station, Report, Association, SeismicEvent
│   ├── scenario.py                      895   estado + una operación por acción + consultas §11
│   ├── storage.py                       347   estado <-> JSON, apply_state todo-o-nada
│   ├── loader.py                        428   carga por topología / por inserciones
│   ├── validation.py                    182   orden global, alturas, balance (iterativo)
│   └── versions.py                      134   versiones con nombre en disco
├── web/
│   ├── app.js                           462
│   ├── index.html                       187
│   └── style.css                        346
├── tests/                                     (unittest)
│   ├── __init__.py                        1
│   ├── test_new_structure.py            358
│   ├── test_storage.py                  200
│   ├── test_undo.py                     160
│   ├── test_loading.py                  274
│   ├── test_versions.py                 144
│   └── test_section16_persistence.py    187
├── tools/make_data.py                   185
├── data/
│   ├── insertions/   (3 .json)
│   ├── topologies/   (6 .json)
│   └── test_cases_section16/            (solo .gitkeep)
└── docs/                                (solo .gitkeep)
```

Totales en A: Python 5 014 líneas (código 3 505, tests 1 324, `tools` 185), JS 462, HTML 187, CSS 346. Coincide con las 6 009 líneas contadas por `git blame`.

**B. Checkout local (HEAD `05ab8a9` + cambios sin commitear)**

```
SismoLab-AVL/
├── backend/                                   (tiene su PROPIO .git anidado, ver §6)
│   ├── main.py                           43
│   ├── requirements.txt                  15
│   ├── api/__init__.py                    1   (vacío: solo un comentario)
│   ├── schemas/__init__.py                1   (vacío: solo un comentario)
│   ├── models/    association 80, enums 49, epicenter 82, event 368, report 114, station 50, zone 85, __init__ 8
│   ├── services/  archive 104, association 80, audit 83, event 173, report 103, scenario 133, undo 95, __init__ 7,
│   │              _scenario_service_DESCARTADO 205   (archivo muerto)
│   ├── structures/ avl_node 66, avl_tree 361, bst_node 11, bst_tree 55, report_queue 36, tree_key 125, undo_stack 28, __init__ 2
│   └── tests/     test_arbol_avl_completo 612, test_avl_tree 75, test_priority 261, test_services 274, test_tree_key 99
├── frontend/src/  (27 archivos; sin commitear, ver §6)
│   ├── App.jsx 152, main.jsx 10, datosDePrueba.js 443
│   ├── utilidades/  arbol.js 170, formato.js 42
│   ├── componentes/ ArbolSvg 100, CampoDato 12, DetalleEvento 84, InsigniaModo 17, InsigniaPrioridad 13,
│   │                LeyendaArbol 30, NodosExaminados 12, Panel 17, TablaSimple 35   (.jsx)
│   └── vistas/      Arbol 208, Auditoria 106, Cola 141, Comparacion 58, Consultas 211, Historico 58, Mapa 104   (.jsx)
├── data/ y docs/                              (solo .gitkeep)
└── README.md, .gitignore
```

En B, `git ls-files` lista 14 archivos `.pyc` rastreados (`backend/**/__pycache__/`), pese a que `.gitignore` ignora `__pycache__/`.

---

## 2. Separación GUI / lógica de negocio

### 2.1 Lógica de negocio que importa la capa de presentación

**A. `origin/main`: ninguno.** Verificado con `grep -rnE "eel|tkinter|document\.|window\.|innerHTML" core domain` → sin coincidencias. La dependencia va en un solo sentido, como declara el README (`web → main.py → domain → core`).

Los únicos imports de presentación en Python están en `main.py`, que es el puente Eel (no lógica de negocio): `import eel` (`main.py:11`), `import tkinter as tk` y `from tkinter import filedialog` (`main.py:276-277`, dentro de `_ask_path`).

Detalle menor: `main.py:29-40` define las zonas y estaciones del escenario de ejemplo (datos de configuración de negocio) dentro del puente, no en `domain/`.

**B. Checkout local:** ninguno en `backend/` (los servicios importan solo modelos y estructuras).

### 2.2 Capa de presentación que contiene reglas de negocio

**A. `origin/main`** (`web/app.js`, `web/index.html`):

| Ubicación | Regla | Gravedad |
|---|---|---|
| `web/app.js:198`, `web/app.js:209` | Umbral de desbalance `abs(bf) > 1` para resaltar nodos (regla AVL de §14) | Baja: solo colorea |
| `web/app.js:85` | Ordena la lista de eventos por `b.priority - a.priority \|\| b.magnitude - a.magnitude` (reimplementa parcialmente la comparación de K, sin el id) | Baja: solo ordena la lista de la derecha; no afecta al árbol |
| `web/app.js:88`, `web/app.js:189-192` | Traducción prioridad→nombre y color | Presentación legítima |
| `web/index.html:51,55,56,59,60` | Atributos `min`/`max` que duplican los rangos de §3 (id 1–999999, M −2..10, H 0..700, x/y 0..1000) | Baja: el dominio los vuelve a validar (`domain/models.py:378-396`) |
| `web/app.js:453` | Fecha por defecto `"2026-01-01T00:00"` = literal duplicado del reloj inicial (`domain/scenario.py:44`) | Baja |

No se encontró en `web/` cálculo de prioridad, rotaciones ni elegibilidad de archivo.

**B. Checkout local** (`frontend/src`, maqueta con datos falsos, sin commitear). Aquí sí hay reglas de negocio en presentación, escritas durante la maqueta:

| Ubicación | Regla |
|---|---|
| `frontend/src/utilidades/arbol.js:19` | `compararClaves`: comparación lexicográfica de K |
| `frontend/src/utilidades/arbol.js:27`, `:154` | Altura, factor de balance y umbral `> 1` |
| `frontend/src/utilidades/arbol.js:135` | `verificarEstructura` (auditoría global) |
| `frontend/src/vistas/Consultas.jsx:14` | `primerosKPendientes` (consulta top-k con poda) |
| `frontend/src/vistas/Consultas.jsx:73`, `frontend/src/componentes/ArbolSvg.jsx:74` | Acceso costoso: `prioridad === 3 && profundidad > L` |
| `frontend/src/vistas/Arbol.jsx:23` | `validarFormulario` (rangos de §3) |

---

## 3. Inventario de lo implementado

Base: **A. `origin/main`** (estado vigente). Las rutas son de A.

| Requisito | Estado | Archivo:línea | Notas |
|---|---|---|---|
| Clave K=(P,M,I) y comparación lexicográfica | **Completo** | `core/avl_tree.py:20-87` (`TreeKey`; `__lt__` :34, `__hash__` :64) | Comparación por tupla `(priority, magnitude, event_id)`; magnitud redondeada a 1 decimal (:28). Test: `tests/test_new_structure.py:26-50`. |
| Cálculo de prioridad (P=3/2/1), límites inclusivos, zona poblada por borde | **Completo** | `domain/models.py:286-293` (regla), `:295-299` (zona poblada), `:127-129` (`Zone.contains` inclusivo) | M≥6.0 → 3; M≥4.5 y H≤30.0 y zona poblada → 3; M≥4.5 → 2; resto → 1. En borde de dos zonas cuenta "poblada" si alguna lo es (`for zone…` :296-298). Test: `tests/test_loading.py:229-237`. |
| AVL: insert, delete, search, rotaciones LL/RR/LR/RL, altura (vacío=-1, hoja=0) | **Completo** | `core/avl_tree.py`: `insert` :162, `_balance` :184 (LL :189, LR :191, RR :197, RL :199), rotaciones :205/:215, `delete` :227, `search` :262, altura :150-158 | `search` devuelve `(nodo, visitados)`. Contadores `simple_turns_*` (:145-146). Cobertura de tests **parcial**: `tests/test_new_structure.py:62-94` solo afirma `is_balanced()`/tamaño; no prueba cada caso LL/RR/LR/RL ni sus contadores. |
| BST comparativo sin balanceo, mismo comparador | **Completo** | `core/avl_tree.py:461-604` (`BSTTree`); `compare_trees` :622; alimentado en `domain/scenario.py:199` (alta), `:239-240` (corrección) | Misma `TreeKey`. `web/app.js:101-114` muestra la pestaña BST. |
| Pila de deshacer explícita | **Completo** | `core/linear.py:8-37` (`UndoStack`); uso `domain/scenario.py:71-75`, `:525-539` | Pila con tope de 100 (`max_size`, :11). Cada acción guarda un snapshot completo (`domain/storage.py:99`). Tests: `tests/test_undo.py` (17). |
| Cola FIFO de reportes explícita | **Completo** | `core/linear.py:40-71` (`ReportQueue`) | `deque`; orden preservado al deshacer (`tests/test_undo.py:95`). |
| Procesamiento de reportes: los 5 casos | **Parcial** | `domain/scenario.py:291-407`: desconocido :384; rev. mayor :347; igual+iguales :366-373; igual+distintos :374-377; menor :378-381 (+ eliminado :300, archivado :306) | Los 5 casos existen y se distinguen. **Defecto verificado**: no se validan los datos del reporte. Un reporte con M=99, H=900, x=5000, y=−3, fecha 2030 y estación inexistente devolvió `CREATED` (el `try/except ValueError` de :385-402 nunca se activa porque `SeismicEvent.__init__` no valida). `correct_event` tampoco valida (`correct_event(1, magnitude=99.0)` dejó M=99.0, `scenario.py:211-248`). Tests: OUTDATED (`test_loading.py:112`, `test_undo.py:105`), CREATED (`test_new_structure.py:180`), REACTIVATED (:261). **No se encontró test de CONFIRMED ni de CONFLICT.** |
| Asociaciones (candidatos por W, R, magnitud y tiempo) y desempate | **Completo** | `domain/scenario.py:411-461`; desempate :424-426 | Candidato: M estrictamente mayor (:446), estrictamente anterior (:448), Δt≤W (:451), dist≤R (:454); considera activos y archivados (:442), no eliminados. Desempate: mayor M → menor distancia → menor id. Se recalcula tras alta/corrección/eliminación/cambio de W-R (:206,:247,:268,:671). Un solo test positivo: `test_new_structure.py:308`. |
| Modo estrés (balanceo diferido) y recuperación global | **Parcial** | `core/avl_tree.py:178,250` (aplaza rotaciones), `:283-312` (recuperación); `domain/scenario.py:615-629` | La recuperación es correcta para desbalances >2 (re-recursión tras cada rotación, :309-310) y pone `stress_mode=False` al final (:290). **Defectos verificados**: (1) `toggle_stress` (`scenario.py:617`) permite volver a modo normal sin recuperar: tras 7 inserciones ascendentes en estrés y un toggle, el modo quedó `False` con `is_balanced()==False` y auditoría inválida. (2) No se pausa el procesamiento de la cola durante la recuperación (§8): no encontrado. Test: `test_new_structure.py:86-94` (no verifica |FB|>2 ni identidades). |
| Marca de acceso costoso (profundidad > L, solo P=3) | **Parcial** | `domain/scenario.py:88-92` (conteo en `summary`), `:861-886` (consulta) | Regla correcta (P=3 y profundidad > L). **No hay marca visual**: `web/` no contiene "costoso"/"costly" (0 coincidencias en `app.js` e `index.html`), así que no se distingue de la prioridad como exige §9. Sin test dedicado. |
| Eliminación individual vs. archivo de rama (elegibilidad, desempates) | **Parcial** | Eliminación: `domain/scenario.py:252-272` (**Completo**). Archivo: `:465-521` | **Defectos verificados**: (1) elegibilidad usa `age < T` → falso (`scenario.py:490`), por lo que una antigüedad exactamente igual a T sí es elegible; §10 exige "estrictamente mayor". Con antigüedad = 72 h exactas el evento resultó elegible. (2) Desempates de §10 (mayor profundidad de la raíz, luego mayor id) **no implementados**: solo `sort(key=count)` (:468). (3) La UI ejecuta el archivo sin mostrar antes ids, cantidad y justificación (`web/app.js:321-329`, `main.py:196-199`). Tests: `test_new_structure.py:261` (1 evento), `test_undo.py:46`. |
| Las 5 consultas del §11, cada una reportando nodos examinados | **Parcial** | `domain/scenario.py`: top-k :726; intervalo :762; asociaciones :802; costosos :861. Expuestas en `main.py:203-241` | (1) Top-k con poda inversa: reporta `nodes_examined` (:756-760). (2) Magnitud y (3) profundidad+fechas están **fusionadas** en una sola función con AND (:762-800); §11 las lista como consultas distintas. Reporta `nodes_examined` (:797). (4) Asociaciones (:802-859): **sin** `nodes_examined`. (5) Costosos (:861-886): devuelve `nodes_visited` por evento, **sin** total de nodos examinados. **Ninguna consulta es alcanzable desde la interfaz**: `web/app.js` y `web/index.html` tienen 0 coincidencias de `query_`/"consulta". Test: `test_new_structure.py:308`. |
| Carga por inserciones / por topología / guardado estructural | **Completo** | `domain/loader.py:36` (topología), `:313` (inserciones); `domain/storage.py:99` (guardar), `:183` (`apply_state` todo-o-nada); `main.py:274-331` | Sin rutas de entrada fijas: explorador `tkinter` (`main.py:274-291`). Validaciones: datos, unicidad, referencias, ciclos, orden global, alturas, factores, prioridad almacenada (`loader.py:231-251`). Rechaza y conserva el escenario. Modo estrés obligatorio para topología desbalanceada (`loader.py:65-70`). UI en `web/app.js:335-391`. Tests: `test_loading.py`, `test_storage.py`, `test_section16_persistence.py`. 9 archivos `data/*.json`. |
| Versiones con nombre persistentes | **Completo** | `domain/versions.py:27-134`; `domain/scenario.py:700-720`; `main.py:338-364`; UI `web/app.js:397-440`, `web/index.html:144-153` | Persisten en `data/versions/` (ignorada por `.gitignore:13`). Restaurar = una acción deshacible (`scenario.py:716-720`). Valida al restaurar. Tests: `tests/test_versions.py` (9). |
| Auditoría de estructura (orden GLOBAL por K) | **Parcial** | `domain/scenario.py:546-611` (`run_audit`) y `domain/validation.py:112-171` (`check_tree`, `check_order`) | El orden global se verifica bien en ambos (inorden estrictamente creciente, `scenario.py:555-561`; `validation.py:151-171`, iterativo). Pero hay **dos implementaciones distintas**: `run_audit` (recursiva, sin reporte por evento, en estrés omite el balance en silencio, :565) y `check_tree` (usada solo al cargar archivos). §14 pide un reporte por evento inconsistente y distinguir el desbalance esperado de estrés de los errores de orden/metadatos. La UI solo muestra una línea de log (`web/app.js:306-313`). |
| Métricas e indicadores del §14 | **Parcial** | `domain/scenario.py:46-53` (contadores), `:77-166` (`summary`) | Existen: activos/archivados/eliminados, altura, hojas, 4 recorridos, correcciones, descartados, conflictos, archivados, LL/RR/LR/RL, giros simples, eventos por prioridad, pendientes, costosos. **Falta el contador de "archivos masivos"** (solo `total_archives` cuenta eventos, :510). **La UI muestra un subconjunto**: `web/index.html:26-39` (activos, archivados, eliminados, cola, undo, altura, hojas, balance, LL/RR/LR/RL). No se muestran prioridades, pendientes, costosos, descartados/conflictos ni los recorridos (`traversals`: 0 coincidencias en la UI). Los giros simples aparecen solo en la tabla de "carga por inserciones" (`web/app.js:388`), no en la barra permanente. |
| Vista del AVL, vista del BST y plano geográfico 0–1000 km | **Parcial** | AVL y BST: `web/app.js:101-215`, `web/index.html:157-169` | AVL y BST se dibujan en SVG con posición por inorden/profundidad. **Plano geográfico: no encontrado** (`web/` no dibuja zonas ni epicentros). Tampoco hay vista de cola (solo su cantidad), de histórico/eliminados, ni detalle completo del evento de §6 (`searchEvent`, `web/app.js:245-260`, no muestra estaciones, zona, clave, atención, altura, FB ni asociaciones). No hay botón de "marcar revisado" (`mark_reviewed` está en `main.py:170` pero `app.js` no lo llama), ni formulario de W/R/L/T (`update_parameters`, `main.py:255`, sin uso en la UI), ni ráfagas de N estaciones ni procesamiento continuo. |

Leyenda: la lista de 17 puntos es la del encargo. "Parcial" = existe pero con defecto verificado o sin alcanzar la UI.

---

## 4. Deuda técnica y riesgos

### 4.1 TODO, FIXME, `pass`, funciones vacías, `NotImplementedError`

- **A. `origin/main`: ninguno.** `grep` de `TODO|FIXME|XXX|HACK|NotImplementedError|^\s*pass\s*$` en `.py/.js/.html/.css` → sin resultados. Un barrido AST de funciones cuyo cuerpo es solo docstring o `pass` → sin resultados.
- **B. Checkout local:** sin TODO/FIXME/`NotImplementedError`. Barrido AST: sin funciones vacías. Un `pass` intencional en `backend/tests/test_arbol_avl_completo.py:459`. Paquetes vacíos (solo un comentario): `backend/api/__init__.py:1`, `backend/schemas/__init__.py:1`. Archivo muerto: `backend/services/_scenario_service_DESCARTADO.py` (205 líneas).

### 4.2 Duplicación de lógica (A. `origin/main`)

| Regla duplicada | Sitios |
|---|---|
| Auditoría de orden/alturas/balance | `domain/scenario.py:546-611` **y** `domain/validation.py:112-171` (esta última iterativa y más completa) |
| Comparativa AVL vs BST | `core/avl_tree.py:622` (`compare_trees`), `domain/loader.py:389` (`compare_loaded_trees`), `domain/scenario.py:888` (`compare_current_trees`) |
| Aplicar una corrección a un evento | `domain/scenario.py:230-240` (manual), `:350-362` (reporte a evento activo), `:308-326` (reactivación de archivado) |
| Comparar datos de reporte contra evento (confirmar/conflicto) | `domain/scenario.py:327-339` (archivado) y `:366-377` (activo) |
| Recorridos, `count_leaves` y `to_dict` | `AVLTree` (`core/avl_tree.py:316-376,414-440`) y `BSTTree` (`:477-485,540-604`) |
| Rangos de validación de §3 | `domain/models.py:385-392`, `domain/validation.py:64-75`, `web/index.html:51-60` |
| Reloj inicial 2026-01-01 | `domain/scenario.py:44` y `web/app.js:453` |
| Cálculo de asociaciones tras cada operación | Se recalcula **todo** en cada alta/corrección/eliminación (`scenario.py:206,247,268`), O(n²) por operación; no es duplicación pero sí riesgo de rendimiento |

**B. Checkout local:** toda la arquitectura nueva (`core/`+`domain/`) duplica la vieja (`backend/`): mismas clases de modelos, estructuras y servicios. Además `backend/services/scenario.py` conserva un `snapshot()` propio que quedó desfasado del `AVLTree` actual (ver 5.2).

### 4.3 Rutas de archivo escritas en el código (§12 prohíbe rutas de *entrada* fijas)

| Ubicación | Ruta | ¿Viola §12? |
|---|---|---|
| `main.py:20` | `DATA_DIR = <carpeta de main.py>/data` | No: solo punto de partida del explorador (`main.py:283`) |
| `main.py:23` | `data/versions` para versiones | No es entrada de usuario; carpeta de salida fija |
| `main.py:377` | `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe` | No es un archivo de datos, pero es una ruta fija de Windows; en Linux cae al `except` |
| `main.py:378,381,384` | Puerto 8080 fijo | No es ruta |
| `tools/make_data.py:23`, `tests/*.py` | Rutas relativas a la raíz del repo | No (herramientas y pruebas) |

No se encontraron rutas de entrada fijas para cargar escenarios: la carga siempre pasa por el diálogo.

### 4.4 Comentarios de código que no están en inglés (§17 exige inglés)

Verificado con dos criterios: comentarios/docstrings con tildes o ñ (líneas citadas, exactas) y una heurística por palabras comunes (cifras aproximadas: puede contar de más).

**A. `origin/main`: hay comentarios y docstrings en español en:**

| Archivo | Ejemplos exactos (línea) |
|---|---|
| `main.py` | docstring módulo :1-8; comentarios :18-19, :22, :271, :335, :368; casi todos los docstrings de `@eel.expose` (28 de 29 con español, heurística) |
| `domain/scenario.py` | docstring módulo :1-6; comentarios :37, :43, :46, :79, :299, :305, :544, :613, :723, :841; docstrings de consultas :727-732, :763-767, :803-806 |
| `core/avl_tree.py` | docstring módulo :1-9; comentarios :33, :74, :140, :160, :225, :260, :281, :608, :634 |
| `domain/models.py` | docstring módulo :2; comentarios :284, :343, :376 y docstrings de clases (:114, :150, :182, :227, :260) |
| `core/linear.py` | docstrings :2, :9, :41 |
| `tests/test_new_structure.py` | comentarios :10, :137, :219 |
| `web/app.js` | comentarios :14, :21, :26, :143-145, :194, :394, :461 |

En inglés: `domain/loader.py`, `domain/storage.py`, `domain/validation.py`, `domain/versions.py`, `tools/make_data.py` y el resto de `tests/` (0 comentarios en español por tildes).

**B. Checkout local:** comentarios y docstrings en español en `backend/services/*.py` (p. ej. `event_service.py:12` "Gestiona crear, corregir…", `scenario.py:20`) y en `backend/main.py:41`. El archivo `backend/tests/test_arbol_avl_completo.py` está en español a propósito (excepción pedida).

### 4.5 Otros riesgos verificados en `origin/main`

| Riesgo | Evidencia |
|---|---|
| `RecursionError` con árboles degenerados | Insertando 1 500 claves ascendentes en modo estrés, el AVL falló con `RecursionError` en 996 nodos. `core/avl_tree.py` usa recursión en `_insert`/`_delete`/inorden/altura, mientras que `domain/validation.py:118` ya evita recursión "so a degenerate tree of any size cannot overflow the stack". §16 pide desbalances degenerados. |
| Excepciones genéricas en el puente | 13 bloques `except Exception` en `main.py` (:72, :84, :94, :115, :135, :176, :186, :207, :220, :230, :240, :250, :265) devuelven `{"ok": False, "message": str(e)}`: esconden errores de programación como si fueran errores de usuario. |
| `.gitignore` de A ignora `backend/` y `frontend/` | `.gitignore` de `origin/main` (líneas "Carpetas viejas"). Ver §7. |

---

## 5. Pruebas

### 5.1 `origin/main` (A): suite y resultado

Comando (README): `python -m unittest discover -s tests -v`. Ejecutado en una copia extraída de `origin/main`:

```
Ran 92 tests in 0.108s
OK
```

| Archivo | Tests | Qué cubre |
|---|---|---|
| `tests/test_new_structure.py` | 24 | `TreeKey`, AVL (inserción/borrado/búsqueda/estrés/recorridos), pila, cola, operaciones básicas de `Scenario`, reactivación de archivado, consultas §11, undo de cola |
| `tests/test_storage.py` | 15 | Serialización/reconstrucción con topología exacta, formato `Z`, enlaces inválidos, ciclos, doble padre |
| `tests/test_undo.py` | 17 | Deshacer cada acción (crear, corregir, eliminar, revisar, archivar, reporte, reloj, parámetros, estrés, recuperación) |
| `tests/test_loading.py` | 20 | Guardar/cargar, topología normal/estrés/desbalanceada/inconsistente, inserciones, id repetido |
| `tests/test_versions.py` | 9 | Versiones con nombre que sobreviven al reinicio, archivos dañados |
| `tests/test_section16_persistence.py` | 7 | Caso de persistencia de §16 paso a paso y reproducibilidad de `data/` |
| **Total** | **92** | (24+15+17+20+9+7) |

Ausentes en A (existían en el `backend/` viejo, ver 5.2): `test_priority.py` (24 tests de prioridad), `test_tree_key.py` (11), `test_arbol_avl_completo.py` (115: las 4 rotaciones, estrés/recuperación aleatoria, búsqueda/costo). No fueron migrados a `core/`.

### 5.2 Checkout local (B): suite y resultado

Ejecutado desde la raíz: `pytest backend/tests -q` → **`20 failed, 150 passed`** (170 recolectados: `test_arbol_avl_completo.py` 115, `test_priority.py` 24, `test_tree_key.py` 11, `test_services.py` 14, `test_avl_tree.py` 6).

Fallan todos los de `backend/tests/test_avl_tree.py` (6) y `backend/tests/test_services.py` (14), con `AttributeError: 'TreeKey' object has no attribute 'build_key'` en `backend/structures/avl_tree.py:73`. Causa: `AVLTree.insert` ahora recibe un evento (`avl_tree.py:65`), pero `backend/services/event_service.py:60` y `:115`, `backend/services/undo_service.py:58` y esos dos archivos de tests siguen pasando un `TreeKey`. Los 150 que pasan son los de `test_arbol_avl_completo.py` (115), `test_priority.py` (24) y `test_tree_key.py` (11).

### 5.3 Casos obligatorios del §16 (sobre A)

| # | Caso §16 | Estado | Evidencia |
|---|---|---|---|
| 1 | Límites y empates (M=4.5, M=6.0, H=30.0, borde de zona, empate por id) | **Cubierto** | `tests/test_loading.py:229-237`: prioridad 3 vs 2 para M=4.5/H=30 dentro/fuera de zona poblada, M=6.0, borde de zona, empate `(1, 3.2)` resuelto `[140, 141, 142]`. Datos: `data/insertions/mezclado.json`. |
| 2 | Corrección y reporte antiguo (4.8/70 → 6.2/15, P 2→3; revisión menor no crea nodo ni revierte) | **Parcial** | `tests/test_loading.py:102-113` y `tests/test_section16_persistence.py:123-160` prueban el descarte `OUTDATED` sobre un evento 170 **ya corregido** en el JSON de prueba y que no se crea nodo. La corrección viva 4.8→6.2 que cambia P 2→3 no se ejecuta en un test (`test_new_structure.py:155-161` solo comprueba M=7.0 y revisión 2, sin prioridad). |
| 3 | Reporte tardío (5.6 a las 10:00, 4.2 a las 10:20, luego 6.1 a las 09:55; candidatos nuevos y política) | **No encontrado** | Sin coincidencias de esos valores/horas en `tests/`, `data/` ni `tools/`. |
| 4 | Rotaciones y recuperación (4 casos, degradar en estrés, reparar, identidades/orden/asociaciones, desbalances >2) | **Parcial** | `tests/test_new_structure.py:62-94` solo afirma `is_balanced()`; no prueba cada caso ni preserva identidades/asociaciones ni verifica |FB|>2. La cobertura fina existe solo en el checkout viejo (`backend/tests/test_arbol_avl_completo.py`). `data/topologies/estres.json` declara factores hasta −6 (README) y se carga en `test_loading.py:116`. |
| 5 | Archivo masivo (rama elegible, desempates, sin ramas elegibles, raíz baja con descendiente alto no elegible, deshacer) | **Parcial** | `tests/test_new_structure.py:261` (un solo evento archivado y reactivado) y `tests/test_undo.py:46` (deshacer archivo). Sin test de desempate, sin "sin ramas elegibles", sin raíz baja con descendiente alto. |
| 6 | Persistencia y consistencia (guardar/recuperar normal y estrés, rechazar inconsistente sin alterar, restaurar versión tras reinicio, deshacer corrección y paso de cola) | **Cubierto** | `tests/test_section16_persistence.py:51` (1a), `:67` (1b), `:84` (2), `:104` (3), `:123` (4a), `:142` (4b), `:163` (regeneración de `data/`). |

Resumen: 2 cubiertos, 3 parciales, 1 sin cobertura.

---

## 6. Historial Git

### 6.1 Estructura de repositorios

- `Proyecto_Sismo/` (carpeta padre): **no es un repositorio** (`git status` → "no es un repositorio git").
- `SismoLab-AVL/.git`: remoto `origin = https://github.com/jhilder1/SismoLab-AVL`, rama `main`, en `05ab8a9`, **9 commits detrás** de `origin/main` (`git rev-list --left-right --count`: `0 9`).
- `SismoLab-AVL/backend/.git`: **repositorio anidado propio**, sin remoto, 2 commits (`f740035`, `4fd29c4`, ambos de Alejandro, 2026-09-14). Su `git status` muestra `D config.py`, `D services/scenario_service.py` y varios `M` sin commitear.
- Cambios sin commitear en `SismoLab-AVL/` (repo externo): `frontend/src/App.css`, `App.jsx`, `index.css` modificados; sin seguimiento: `frontend/src/componentes/`, `datosDePrueba.js`, `estilos/`, `utilidades/`, `vistas/`. Este informe (`INFORME_ESTADO.md`) también queda sin seguimiento.

### 6.2 Últimos 20 commits (`origin/main` tiene 19 en total —17 sin merges y 2 merges—, así que se listan todos)

| Commit | Autor | Fecha | Mensaje |
|---|---|---|---|
| `8c277ce` | AndresTrejo38711 | 2026-09-26 13:49 | test: caso de persistencia de la seccion 16 y README actualizado |
| `1dcb518` | AndresTrejo38711 | 2026-09-26 13:34 | feat(versiones): guardar y restaurar versiones con nombre |
| `1d9fb66` | AndresTrejo38711 | 2026-09-25 20:44 | feat(persistencia): guardar y cargar escenarios por topologia e inserciones |
| `97f78a5` | AndresTrejo38711 | 2026-09-25 16:37 | fix(undo): restaurar estado exacto con topologia y metricas |
| `1e6d98e` | AndresTrejo38711 | 2026-09-25 16:18 | feat(storage): serializar y reconstruir el estado completo con topologia exacta |
| `e65fe45` | jhilder1 | 2026-09-21 18:15 | se reorganizo los calculos del bst y el avl, y organizacion de estos metodos |
| `e1b7724` | jhilder1 | 2026-09-21 12:41 | refactor: simplificar arquitectura - Eel + HTML/JS puro, sin APIs ni React… |
| `4c483b4` | jhilder1 | 2026-09-20 21:29 | se comenso la reestructuracion del proyecto… core y domain |
| `c0ec745` | jhilder1 | 2026-09-20 21:06 | chore: eliminar cache pycache rastreado en git |
| `05ab8a9` | Alejandro | 2026-09-15 16:57 | frontend con react conectado, enpoint, Get devuelve la sesión 14 |
| `7836011` | Alejandro | 2026-09-14 22:03 | proyecto Frontend y Backend conectado |
| `73ad2b0` | Alejandro | 2026-09-14 21:43 | Merge branch 'main' of https://github.com/jhilder1/SismoLab-AVL |
| `1e683ef` | Alejandro | 2026-09-14 21:24 | estado de los escenarios, fastapi, cors para el frontend, se corrigió la recuperacion global… |
| `bc50a5a` | jhilder1 | 2026-09-14 20:50 | correcion |
| `71a2cc7` | jhilder1 | 2026-09-14 20:49 | Merge branch 'main' of https://github.com/jhilder1/SismoLab-AVL |
| `1fb1dda` | jhilder1 | 2026-09-14 20:45 | se creo la logica de los servicios para el uso de las apis… |
| `5c4a8c2` | Alejandro | 2026-09-14 19:47 | el nodo referencia un evento, metricas de costo y recuperación global |
| `316234d` | jhilder1 | 2026-09-12 15:46 | se creo la estructura de las clases mas importante como el bst avls y test de manejo… |
| `8d518fe` | jhilder1 | 2026-09-12 12:58 | se definio la estructura del backend y se creo la clase de sismoevent… |

`73ad2b0` y `71a2cc7` son los dos merges. Verificado con `git rev-list --count origin/main` = 19.

### 6.3 Aportes por autor (`git shortlog -sn --no-merges origin/main`)

```
     8  jhilder1
     5  AndresTrejo38711
     4  Alejandro
```

Líneas añadidas/borradas por autor (`git log --numstat`, sin merges, excluyendo `data/` y `package-lock.json`; incluye código que luego se borró en refactors):

| Autor | Añadidas | Borradas |
|---|---|---|
| jhilder1 | 6 474 | 4 363 |
| AndresTrejo38711 | 2 867 | 251 |
| Alejandro | 1 617 | 181 |

Líneas que **sobreviven** en el árbol de `origin/main` (`git blame` sobre `.py/.js/.html/.css`, 6 009 líneas): jhilder1 **3 253**, AndresTrejo38711 **2 756**, Alejandro **0**. El código de Alejandro (backend FastAPI y frontend React) está en el historial pero no en el árbol actual de `origin/main`, porque el commit `e1b7724` lo eliminó. §17 exige un repositorio que "permita evidenciar los aportes de cada integrante": el historial lo evidencia, el árbol vigente no.

---

## 7. Qué falta para entregar

Fecha de entrega del enunciado: **7 de octubre** (§17). Hoy es 2026-09-26: quedan 11 días. Esfuerzo: **bajo** (≤ ½ día), **medio** (~1–2 días), **alto** (> 2 días).

### Prioridad 1 — Decisiones y bloqueos de integridad

| # | Pendiente | Esfuerzo | Referencia |
|---|---|---|---|
| 1 | **Reconciliar el repo.** El checkout está 9 commits detrás y `origin/main` eliminó `backend/` y `frontend/` (y su `.gitignore` los ignora). Un `git pull` probablemente chocará con los cambios sin commitear en `frontend/src/{App.jsx,App.css,index.css}` (archivos rastreados que el remoto borró); no se probó el pull para no tocar el árbol de trabajo. Decidir cuál es la entrega (Eel vs. React) y cómo conservar el trabajo de Alejandro en el historial/árbol. | bajo–medio (es una decisión de equipo) | §0, §6.1, §6.3 |
| 2 | Impedir salir de modo estrés sin recuperar balance (`domain/scenario.py:617`) y pausar la cola durante la recuperación (§8). | bajo | §3 fila "Modo estrés" |
| 3 | Validar datos de reportes y de correcciones antes de aplicarlos (`scenario.py:385-402`, `:230`). Hoy un reporte con M=99 crea el evento. | bajo | §3 fila "Procesamiento" |
| 4 | Archivo masivo: antigüedad estrictamente mayor que T (`scenario.py:490`), desempates de §10 (profundidad y id de la raíz, `:468`), vista previa de ids/cantidad/justificación antes de ejecutar. | medio | §3 fila "Eliminación vs. archivo" |
| 5 | Quitar la recursión de `AVLTree`/`BSTTree` (falla a ~1 000 nodos en estrés, `core/avl_tree.py`). | medio | §4.5 |

### Prioridad 2 — Requisitos funcionales que faltan (todos son de la interfaz o del reporte de consultas)

| # | Pendiente | Esfuerzo | Referencia |
|---|---|---|---|
| 6 | Interfaz de las consultas de §11 (hoy `main.py:203-241` las expone pero `web/` no las llama). Separar la de magnitud de la de profundidad+fechas; añadir `nodes_examined` a asociaciones y costosos. | medio | §3 fila "Consultas" |
| 7 | Plano geográfico 0–1000 km con zonas y epicentros (§15). Existe una maqueta en `frontend/src/vistas/Mapa.jsx` del checkout local, portable a `web/`. | medio | §3 fila "Vistas" |
| 8 | Marca visual de acceso costoso distinta de la prioridad (§9) y todos los indicadores de §14 en pantalla (giros simples, prioridades, pendientes, costosos, descartados, conflictos, recorridos). | medio | §3 filas "Acceso costoso", "Métricas" |
| 9 | Vistas/controles ausentes: lista de la cola en orden FIFO, ráfagas de N estaciones y procesamiento continuo con pausa, histórico y eliminados, detalle completo del evento de §6, botón "marcar revisado", formulario de W/R/L/T, corrección de epicentro y fecha. | alto | §3 fila "Vistas" |
| 10 | Contador de "archivos masivos" (§14). | bajo | §3 fila "Métricas" |
| 11 | Unificar la auditoría (`run_audit` con `check_tree`), con reporte por evento y distinguiendo el desbalance esperado de estrés. | medio | §3 fila "Auditoría" |

### Prioridad 3 — Pruebas, documentación y entregables

| # | Pendiente | Esfuerzo | Referencia |
|---|---|---|---|
| 12 | Tests de los casos de §16 que faltan: reporte tardío (caso 3, sin cobertura), corrección viva 4.8→6.2, rotaciones LL/RR/LR/RL con contadores y desbalances >2 con identidades/asociaciones, archivo masivo (desempates, sin ramas, raíz baja). Recuperar los 150 tests que pasan en el `backend/` viejo (`test_priority` 24, `test_tree_key` 11, `test_arbol_avl_completo` 115) adaptándolos a `core/`. Tests de CONFIRMED y CONFLICT. | medio | §5.3 |
| 13 | Manual de usuario, manual técnico (modelo de dominio, esquema JSON, invariantes, costos) y reporte del uso de IA: `docs/` está vacío. Se envían por correo, no por Git/Drive/Dropbox. | alto | §17 |
| 14 | Video de explicación en un segundo idioma, con todos los integrantes y demostración en ejecución. | alto | §17 |
| 15 | Comentarios en inglés en `main.py`, `domain/scenario.py`, `core/avl_tree.py`, `domain/models.py`, `core/linear.py`, `web/app.js`, `tests/test_new_structure.py` (líneas en §4.4). | bajo | §4.4 |
| 16 | Portabilidad: ruta fija de Edge (`main.py:377`) y dependencia de `tkinter` (no está en Debian/Ubuntu por defecto). Documentarlo o degradar con gracia. | bajo | §1.2, §4.3 |
| 17 | Limpieza: consolidar las tres comparativas AVL/BST y las tres rutas de corrección duplicadas; en el checkout local, 14 `.pyc` rastreados, el repo `backend/.git` anidado y `_scenario_service_DESCARTADO.py`. | bajo–medio | §4.2, §1.3 |
