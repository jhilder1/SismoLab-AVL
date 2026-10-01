# 🏔️ SismoLab AVL

Aplicación de escritorio para gestionar un observatorio sísmico simulado.
El catálogo de eventos activos es un **árbol AVL de implementación propia**,
ordenado por la clave **K = (P, M, I)**: prioridad, magnitud e identificador.

## Requisitos

- **Python 3.12** (probado con 3.12.10).
- **Eel** para la ventana: `pip install -r requirements.txt`
- **Microsoft Edge** (viene con Windows) o Chrome para mostrar la interfaz.

`tkinter` (explorador de archivos), `json` y `unittest` vienen con Python.

## Ejecutar

```
pip install -r requirements.txt
python main.py
```

Se abre una ventana con la interfaz. Cerrar la ventana detiene el programa.

## Pruebas

Todas las pruebas, solo con Python (174 pruebas):

```
python -m unittest discover -s tests
```

También corren con `pytest` (`pip install -r requirements-dev.txt` y
`python -m pytest tests/`). Los archivos escritos con funciones sueltas
`def test_algo():` (`test_new_structure.py`, `test_iterative_tree_queries.py`
y `test_audit_associations.py`) tienen un `load_tests` que las registra para
que `unittest` no se las salte. Las pruebas de la interfaz
(`tests/js/*.js`) necesitan Node.js; sin él aparecen como omitidas.

La evidencia de la sección 16 (resultados esperados y obtenidos) se imprime con
`python tools/section16_report.py`.

| Archivo | Qué prueba |
|---|---|
| `tests/test_new_structure.py` | AVL, BST, pila, cola, operaciones básicas del escenario |
| `tests/test_storage.py` | Foto completa del estado y reconstrucción con la topología exacta |
| `tests/test_undo.py` | Deshacer cada acción devuelve el estado exacto anterior (sección 13) |
| `tests/test_loading.py` | Guardado, carga por topología y por inserciones, validaciones (sección 12) |
| `tests/test_versions.py` | Versiones con nombre que persisten al cerrar el programa (sección 13) |
| `tests/test_section16_persistence.py` | Caso "Persistencia y consistencia" de la sección 16, paso a paso, y reproducibilidad de `data/` |
| `tests/test_iterative_tree_queries.py` | `query_top_k_pending`, `query_by_magnitude` y `find_eligible_branches` sobre un árbol degenerado (sin RecursionError) y equivalencia exacta con la versión recursiva anterior en un árbol chico |
| `tests/test_review_fixes.py` | Fallas de la revisión: decimales, comparativa AVL/BST, consulta completa del evento, vista previa al eliminar, regla de archivo y pausa de la cola (secciones 3, 6, 8, 10, 11, 14) |
| `tests/test_section16_cases.py` | Los casos de la sección 16 con los archivos de `data/test_cases_section16/`, ráfagas de reportes y el cargador de ráfagas (sección 8) |
| `tests/test_queries_indicators.py` | Consultas de la sección 11 (poda por K, profundidad y fechas, acceso costoso) contra un recorrido completo, e indicadores y registro de acciones de la sección 14 |
| `tests/test_audit_associations.py` | `run_audit` detecta una referencia que existe pero viola magnitud/tiempo/W/R, y ciclos en la cadena de referencias (sección 14 sobre sección 7) |

## Arquitectura

Tres capas; las dependencias solo van hacia abajo (`web → main.py → domain → core`).
La interfaz nunca toca un nodo: pide la operación a `Scenario` y dibuja el resultado.

```
main.py                 Puente Eel: cada botón llama una función @eel.expose;
                        explorador de archivos (tkinter)
web/                    Interfaz HTML + JS + SVG (árbol AVL y BST comparativo)
domain/
  models.py             Evento, reporte, zona, estación, epicentro, asociación;
                        cálculo de prioridad y formato de fechas ISO 8601 (Z)
  scenario.py           Estado completo y un método por acción; pila de deshacer
  storage.py            Estado <-> JSON con topología exacta (todo o nada)
  loader.py             Carga por topología y por inserciones (sección 12) y
                        ráfagas de reportes para la cola (sección 8)
  validation.py         Validaciones de datos, orden global por K, alturas y balance
  versions.py           Versiones con nombre en data/versions/ (sección 13)
core/
  avl_tree.py           TreeKey, AVLTree (rotaciones, modo estrés, recuperación), BSTTree
  linear.py             Pila de deshacer y cola FIFO de reportes
tools/make_data.py      Regenera los archivos de prueba de data/
tools/section16_report.py  Evidencia de la sección 16: resultados esperados y obtenidos
```

## Persistencia

- **Guardar escenario:** un JSON con la topología real del AVL y del BST (raíz y
  enlaces izquierdo/derecho por identificador), alturas, factores de balance,
  datos vigentes, histórico, identificadores eliminados, asociaciones, cola en
  su orden, reloj, zonas, estaciones, parámetros W, R, L y T, modo y métricas.
- **Cargar escenario (topología):** reconstruye los enlaces sin reinsertar. Antes
  de sustituir el escenario valida datos, unicidad, referencias, ciclos, orden
  global, alturas, factores y prioridades. Si algo falla muestra todos los
  problemas y conserva el escenario actual.
- **Cargar por inserciones:** inserta la secuencia en un AVL balanceado y en un
  BST y compara raíz, altura, hojas y comparaciones de búsqueda.
- **Versiones:** se guardan en `data/versions/` (no se suben al repositorio) y
  se restauran como una acción que se puede deshacer.

## Archivos de prueba (`data/`)

Se generan con `python tools/make_data.py`; una prueba comprueba que al
regenerarlos se obtiene el mismo contenido.

| Archivo | Resultado esperado |
|---|---|
| `insertions/ascendente.json` | 16 eventos en orden ascendente de K: BST de altura 15 frente a AVL de altura 4 |
| `insertions/mezclado.json` | Los mismos 16 eventos en otro orden: mismo contenido, otro BST |
| `insertions/invalido-id-repetido.json` | Rechazado: un identificador repetido invalida el archivo |
| `topologies/normal.json` | Carga en modo normal: árbol balanceado, histórico, un eliminado y 2 reportes en cola |
| `topologies/estres.json` | Carga en modo estrés, desbalanceado (factores hasta -6) |
| `topologies/desbalanceado-modo-normal.json` | Rechazado en modo normal; se carga si el modo estrés está activo |
| `topologies/inconsistente-orden.json` | Rechazado: orden global por K roto |
| `topologies/inconsistente-metadatos.json` | Rechazado: altura, factor de balance y prioridad guardados no coinciden |
| `topologies/invalido-referencias.json` | Rechazado: enlace a un identificador inexistente y nodo en dos posiciones |
| `bursts/rafaga-mixta.json` | Para `normal.json`: 12 reportes de 4 estaciones con altas, confirmaciones, correcciones que cambian la clave, un reporte antiguo, un conflicto, un ID eliminado y una reactivación |
| `bursts/rafaga-altas-concurrentes.json` | Para `normal.json`: 8 altas de 4 estaciones con sus confirmaciones; la cola respeta el orden de recepción |
| `bursts/rafaga-invalida.json` | Rechazada completa: la cola no cambia |
| `test_cases_section16/` | Un archivo por caso de la sección 16, con pasos y resultados esperados en su `README.md` |

Los 16 eventos incluyen los casos límite de la sección 16: M = 4.5 con H = 30.0
en zona poblada (prioridad 3) y fuera de ella (prioridad 2), M = 6.0, un
epicentro en el borde de dos zonas y empates de prioridad y magnitud resueltos
por identificador.

## Equipo

- Integrante A — Estructuras de datos (AVL, BST, recuperación)
- Integrante B — Backend (servicios, persistencia, API)
- Integrante C — Frontend (interfaz, visualización)

## Licencia

Proyecto académico — Universidad
