# AUDITORÍA FINAL — SismoLab AVL

**Commit auditado: `34d42e3`** ("se corrigio el sistema de mas de mil inserciones y se agrego un archivo de ejemplo"), `origin/main`, sincronizado hoy con `git fetch` + `git merge --ff-only` (el checkout local estaba 7 commits atrás; no había cambios propios sin commitear, así que el fast-forward no descartó nada). No se modificó ningún archivo del repositorio en esta auditoría.

**Regla de verificación aplicada:** cada fila de las tablas dice cómo se comprobó. "Verificado en ejecución" significa que corrí un script real y pego su salida. "Solo lectura" significa que no lo ejecuté y lo digo explícitamente. Los scripts se escribieron en un directorio temporal fuera del repo y se borraron al terminar, junto con los entornos virtuales y los procesos de Chrome/Eel que levanté.

---

## 1. Estado general

**Últimos 20 commits, con autor:**

```
34d42e3 2026-09-29 jhilder1        se corrigio el sistema de mas de mil inserciones y se agrego un archivo de ejemplo
1529130 2026-09-29 jhilder1         se corigio un pequeño error q no enconlaba bien por conflicto de fechas
558cf7e 2026-09-29 jhilder1         se agrego el endo y se mejoror un problema q no mostraba el historico de ramas archivadas
e9c472c 2026-09-29 jhilder1         se agrego las graficas de comparacion en el arbol avl y bts y no solo informacion
c1db927 2026-09-29 jhilder1        se organizo el boton de archibar para entender mejor lo que se esta guardando
e2ffbe8 2026-09-27 jhilder1        codigo duplicado
3384b53 2026-09-27 jhilder1        fix(core): corregidas validaciones, desempates en rama y recursión en avl
aed463b 2026-09-27 Alejandro       se agregó cola y procexsamiento con historial de decisiones
5572f96 2026-09-27 Alejandro       se agr egó el panel de ocnsultas individuales para los sismos
61b4d62 2026-09-27 Alejandro       modo estres completamente funcionando
d731c93 2026-09-27 Alejandro       marcador de acceso costosos y panel del párametro w/r/l/t funcionando
3610236 2026-09-26 Alejandro       correcion de boton crear evento
33eb716 2026-09-26 Alejandro       eliminar la ruta de Edge codificada directamente en el código...
8c277ce 2026-09-26 AndresTrejo38711 test: caso de persistencia de la seccion 16 y README actualizado
1dcb518 2026-09-26 AndresTrejo38711 feat(versiones): guardar y restaurar versiones con nombre
1d9fb66 2026-09-25 AndresTrejo38711 feat(persistencia): guardar y cargar escenarios por topologia e inserciones
97f78a5 2026-09-25 AndresTrejo38711 fix(undo): restaurar estado exacto con topologia y metricas
1e6d98e 2026-09-25 AndresTrejo38711 feat(storage): serializar y reconstruir el estado completo con topologia exacta
e65fe45 2026-09-21 jhilder1         se reorganizo los calculos del bst y el avl, y organizacion de estos metodos
e1b7724 2026-09-21 jhilder1         refactor: simplificar arquitectura - Eel + HTML/JS puro...
```

**`git shortlog -sn --no-merges` no imprimió nada** (salida vacía, código de retorno 0, probé también con `GIT_PAGER=cat` y sin `--no-merges`; no encontré la causa). Lo sustituí por el equivalente verificado:

```
$ git log --format="%an" --no-merges | sort | uniq -c | sort -rn
     15 jhilder1
     10 Alejandro
      5 AndresTrejo38711
```
(32 commits totales, 2 son merges, 30 no-merge → 15+10+5=30, cuadra.)

**`pytest` completo:**
```
$ python3 -m pytest -q          # sin acotar a tests/
ERROR backend/tests/test_arbolAVL_completo.py
ERROR backend/tests/test_arbol_avl_completo.py
2 errors in 0.17s
```
Esto NO es un defecto del commit auditado: hay una carpeta `backend/` en este disco, **sin rastrear por git** (`git ls-files backend/` da 0 archivos) e ignorada por `.gitignore:16`. Es un residuo de un trabajo mío anterior con la arquitectura vieja (FastAPI+React), ajeno al repositorio del equipo. La dejé intacta (esta auditoría no modifica nada) y corrí las pruebas acotadas, tal como indica el propio README (`README.md:29`):
```
$ python -m unittest discover -s tests -v      # el comando exacto del README
Ran 98 tests in 0.117s
FAILED (failures=1)

$ python3 -m pytest -q tests/
1 failed, 97 passed, 4 subtests passed in 0.26s
FAILED tests/test_section16_persistence.py::ReproducibleDataTest::test_regenerated_files_match_data_folder
```
**El fallo es real y reproducible**, no relacionado con `backend/`: `tools/make_data.py` no genera `data/insertions/prueba_carga_masiva_1500.json` (ese archivo lo crea un script aparte, `tools/generate_massive_data.py`, añadido en el commit `34d42e3` y nunca invocado desde `make_data.py`). El test compara el contenido de `data/` con lo que `make_data.main()` regenera y encuentra un archivo de más. Detalle en `tests/test_section16_persistence.py:172-177`.

**`node --check web/app.js`:** sin errores.

**`python main.py` sin error:** sí, verificado con Eel real en un venv temporal (`eel==0.18.2`, instalado desde `requirements.txt`). El servidor sirvió `index.html` y `app.js` con `200`, el log no mostró ninguna traza de error, y el proceso terminó limpio. La ventana no se abrió automáticamente (no hay entorno gráfico en esta sesión), pero el bucle nuevo de `main.py:411-419` (intenta chrome → edge → default, y si nada funciona imprime la URL) reemplazó al que fallaba en Linux; no lo puedo confirmar abriendo una ventana real, solo que el bucle no lanzó ninguna excepción y el puerto quedó servido.

---

## 2. Los bugs conocidos: ¿siguen ahí?

Todo lo de esta sección se verificó ejecutando scripts contra `domain.scenario.Scenario` directamente (no contra la interfaz), salvo donde digo lo contrario.

### 1. Reportes y correcciones con datos fuera de rango

**Corregido.** `domain/scenario.py:308-319` (`enqueue_report`) ahora valida antes de encolar, y `domain/scenario.py:232-238` (`correct_event`) valida antes de aplicar. Ejecuté:
```
M=99 (fuera de rango)     -> RECHAZADO: magnitude must be between -2.0 and 10.0, got 99
H=900 (fuera de rango)    -> RECHAZADO: depth_km must be between 0.0 and 700.0, got 900
estacion inexistente 'XXX'-> RECHAZADO: Estación 'XXX' no existe en el escenario
fecha futura (2030)       -> RECHAZADO: occurrence_time (...) cannot be after simulation clock (...)

correct_event(magnitude=99.0)  -> RECHAZADA
correct_event(depth_km=-5.0)   -> RECHAZADA
correct_event(magnitude=4.46)  -> RECHAZADA (mas de un decimal)
correct_event(depth_km=9999.0) -> RECHAZADA
estado final del evento: sin cambios (M=4.8, H=70.0, rev=1)
```

### 2. Elegibilidad de archivo con antigüedad EXACTAMENTE igual a T

**Corregido.** `domain/scenario.py:536` ahora usa `age <= timedelta(hours=T)` para descartar (antes usaba `<`). Verificado:
```
edad = 72h exactas   -> no elegible (correcto)
edad = 72h00m01s     -> ELEGIBLE (correcto)
edad = 71h59m59s     -> no elegible (correcto)
```

### 3. Desempates de archivo de rama (§10)

**Corregido**, los tres niveles. `domain/scenario.py:508` ordena por `(count, root_depth, root_id)` con `reverse=True`. Los primeros dos casos que armé a mano dieron resultados sorprendentes por rotaciones reales del AVL que no anticipé (un nodo de prioridad alta insertado antes que sus hijos de baja prioridad terminó siendo hoja, no raíz, tras una rotación LR) — no es un bug, es que mi construcción inicial del árbol estaba mal pensada. Rehice los tres casos construyendo el árbol en modo estrés (sin rotaciones automáticas) para controlar la topología exacta y verificar cada criterio por separado:
```
Caso 1 (mismo conteo=1, misma profundidad=1): raíz recién anfitriona con dos hojas viejas de baja
  prioridad, ids 5 y 900 -> ganó [900] (mayor id). Correcto.
Caso 2 (mismo conteo=1, profundidad 2 vs 3): dos hojas elegibles a distinta profundidad
  -> ganó la de profundidad 3. Correcto.
Caso 3 (conteo 2 vs conteo 1): una rama de 2 nodos contra una hoja sola
  -> ganó la de 2 nodos, sin importar profundidad ni id. Correcto.
```

### 4. Recalculo de asociaciones de OTROS eventos al procesar por la cola

**Corregido.** `domain/scenario.py:435` ahora llama `self.recalculate_all_associations()` en el caso "ID nuevo desconocido" (antes solo llamaba `_calculate_association` para el evento propio). Reproduje el caso §16 "reporte tardío" (5.6 a las 10:00, 4.2 a las 10:20, luego 6.1 a las 09:55) por la cola y comparé contra crearlo a mano:
```
Por la cola:  ref(151)=152  ref(150)=152
A mano:       ref(151)=152  ref(150)=152    (idénticos)
```
También confirmé el caso relacionado que había reportado antes (un evento eliminado deja de ser referencia de un archivado): `domain/scenario.py:559` ahora hace que `archive_branch` también llame `recalculate_all_associations`, y `recalculate_all_associations` (línea 496-500) ahora recorre también `self.archived`. Con event 1 (M=6.0, más temprano) referenciado por event 2 (M=3.0, archivado después): al eliminar el evento 1, `sc.archived[2].reference_event_id` pasó de `1` a `None` correctamente.

### 5. Undo de un paso de cola: ¿se pierden los reportes encolados después?

**Corregido**, y de forma más profunda de lo que pedía el hallazgo original: `enqueue_report` ahora también registra su propia acción deshacible (`domain/scenario.py:308-323`, tipo `ENQUEUE_REPORT`). Antes encolar no dejaba rastro en la pila, así que un `undo()` posterior "saltaba" directo al snapshot de antes del último paso de cola y se comía cualquier reporte encolado en el medio. Ahora cada encolado y cada procesamiento son acciones independientes en orden cronológico estricto, así que nada se pierde silenciosamente — se necesitan más `undo()` para llegar más atrás, pero cada uno es exacto. Verificado:
```
encolar(1); encolar(2); procesar(1) [CREATED]; encolar(3)
cola antes de deshacer: [2, 3]
undo() -> ENQUEUE_REPORT   | cola: [2]
undo() -> PROCESS_REPORT   | cola: [1, 2]   (vuelve el evento 1 a la cola Y se deshace su creación)
undo() -> ENQUEUE_REPORT   | cola: [1]
```
Nota: el enunciado (§13) no menciona "encolar" como una de las acciones deshacibles explícitas; el equipo añadió una no listada, pero es la que corrige el defecto y no contradice nada del enunciado.

### 6. RecursionError con ~1000-1500 nodos degenerados

**Parcialmente corregido — este es el hallazgo más importante de la auditoría.**

`core/avl_tree.py` fue reescrito por completo a versión iterativa: `insert`, `delete`, `search` (ya lo era), `recover_balance`, los cuatro recorridos, `is_balanced`, `count_leaves`, `to_dict`, `get_all_event_ids`, y lo mismo en `BSTTree`. Probé con una cadena degenerada real de 1000 y 1500 nodos (cargada por topología en modo estrés, altura = n-1):
```
get_state() / summary()   -> OK, sin RecursionError (antes fallaba)
run_audit()                -> OK, sin RecursionError (antes fallaba)
recover_balance()           -> OK, RECOVERED, altura final 12-13 (antes fallaba)
```
Estas tres eran exactamente las que yo había reportado rotas. Están resueltas.

**Pero quedan tres funciones recursivas sin corregir en `domain/scenario.py`, y las tres SÍ truenan con el mismo árbol degenerado de 1000 nodos:**
```
query_top_k_pending(5)   -> RecursionError   (domain/scenario.py:890, traverse_reverse)
query_by_interval(0,10)  -> RecursionError   (domain/scenario.py:925, traverse)
find_eligible_branches() -> RecursionError   (domain/scenario.py:511-524 y 527-540, _find_eligible / _is_subtree_eligible)
```
Con el archivo de 1500 eventos aleatorios que sí trae el commit (`data/insertions/prueba_carga_masiva_1500.json`), estas mismas tres funciones NO fallan, porque esa carga produce un árbol AVL balanceado (altura 11): la recursión de estas funciones depende de la **altura**, no de la cantidad de nodos, así que solo se manifiesta con un árbol genuinamente degenerado (estrés + inserción ascendente, o una topología cargada así). El archivo de prueba que trae el commit no ejercita este caso — por eso pasó desapercibido.

### 7. `query_event_associations`: ¿reporta `nodes_examined`?

**Parcial: sí en el backend, no en la interfaz.** `domain/scenario.py:1010` ahora incluye `"nodes_examined": len(self.event_index) + len(self.archived)` en el resultado — lo confirmé llamándolo directamente (`nodes_examined = 2` con 2 eventos en el escenario). Pero es un conteo de eventos recorridos, no de "nodos del AVL": esta consulta nunca toca el árbol (recorre diccionarios de eventos activos y archivados), así que "nodos del AVL examinados" no puede aplicarse literalmente aquí; el número que devuelve es la interpretación más razonable disponible dado ese diseño.

`web/app.js:811-813` **no cambió** y sigue mostrando textualmente "no hay nodos examinados que reportar", ignorando el campo `nodes_examined` que el backend ya manda. Lo confirmé en el navegador: la consulta de asociaciones real muestra ese mismo texto fijo en vez del número.

### 8. ¿La auditoría verifica las asociaciones entre eventos?

**Parcial, y por diseño incompleto.** `domain/scenario.py:685-697` (`_audit_associations`, nuevo) comprueba que toda referencia (`reference_event_id`) apunte a un evento activo o archivado que exista. Lo verifiqué:
```
referencia a un ID inexistente (9999) -> detectado: "Evento activo 2 referencia a ID inexistente/eliminado: 9999"
```
Pero **no verifica la validez semántica de la referencia** (que el enunciado exige en la §7: mayor magnitud y estrictamente anterior), ni detecta ciclos. Construí una referencia hacia un ID que sí existe pero que la viola (evento 2, M=3.0, apuntando a evento 3, M=1.0 y posterior — ni mayor magnitud ni anterior):
```
run_audit() con esa referencia inválida (pero a un ID existente): is_valid=True, errors=[]
```
La auditoría no lo detectó. Solo comprueba existencia, no las reglas de asociación del enunciado.

---

## 3. Requisitos del enunciado

"Verificado en ejecución" = corrí código. "Solo lectura" = leí el código sin ejecutarlo, se indica explícitamente.

| Requisito | Lógica | Interfaz | Cómo lo verifiqué | Archivo:línea |
|---|:-:|:-:|---|---|
| Clave K=(P,M,I) lexicográfica | Sí | Sí | Lectura (sin cambios respecto a mi auditoría anterior, que sí ejecutó comparaciones) | `core/avl_tree.py:21-84` |
| Prioridad P=3/2/1, límites inclusivos, borde de dos zonas → poblada | Sí | Parcial | Solo lectura esta vez (`Priority`/`_calculate_priority` y `Epicenter.is_inside` sin cambios; lo ejecuté en la auditoría anterior con los mismos resultados) | `domain/models.py:284-299` |
| AVL: insert, delete, search, LL/RR/LR/RL, altura (vacío=-1, hoja=0) | Sí | Sí | **Verificado en ejecución**: inserciones/eliminaciones iterativas probadas con 1000-1500 nodos (sección 2.6); las pruebas de `pytest` cubren rotaciones en árboles chicos | `core/avl_tree.py:152-303` |
| BST comparativo | Sí | Sí | Verificado en ejecución (`compare_current_trees()` corrido sobre 1500 eventos, sección 2.6) | `core/avl_tree.py:574-844` |
| Pila de deshacer y cola FIFO explícitas | Sí | Sí | Verificado en ejecución: undo/redo y cola probados a fondo (secciones 2.5 y 1) | `core/linear.py`; `domain/scenario.py:76-81,574-619` |
| Los 5 casos de procesamiento de reportes (§6) | Sí | Sí | Verificado en ejecución en la §2 de esta auditoría y en la sesión anterior (CREATED/CORRECTED/CONFIRMED/CONFLICT/OUTDATED/REJECTED, los 6 resultados incluido el de id eliminado) | `domain/scenario.py:325-444` |
| Marcar evento como revisado, deshacible | Sí | Sí | **Mejoró**: ahora hay botón real (`web/app.js:124,129-133`). Verificado en ejecución que el botón llama a `eel.mark_reviewed` y refresca | `domain/scenario.py:296-304`; `web/app.js:124` |
| Asociaciones: W, R, magnitud, tiempo, desempate determinista | Sí | Parcial | Verificado en ejecución (sección 2.4); la consulta de asociaciones sí tiene pantalla, pero no hay forma de ver el criterio W/R en la vista de eventos | `domain/scenario.py:448-500` |
| Modo estrés, recuperación global, salida bloqueada si la auditoría no confirma | Sí | Sí | No re-ejecuté (ya lo había verificado a fondo en la sesión anterior, sin cambios en este commit: `toggle_stress`/`recover_balance`/`_run_recovery` idénticos a como los dejé) | `domain/scenario.py:701-780` |
| Marca de acceso costoso (P=3, prof>L), distinguible de prioridad | Sí | Sí | No re-ejecuté (sin cambios desde mi implementación previa) | `domain/scenario.py:83-98`; `web/app.js:57-68,247-254` |
| Eliminación individual vs. archivo de rama | Sí | Sí | **Mejoró**: ahora hay vista previa de ramas elegibles con selección manual (`get_eligible_branches`/`archive_selected_branch`), antes solo existía "archivar la más grande" a ciegas. Verificado en ejecución en el navegador (sección de Chrome headless): el panel muestra "Sin ramas elegibles..." correctamente cuando no hay ninguna | `domain/scenario.py:504-570`; `main.py:207-233`; `web/app.js:654-720` |
| Las 5 consultas del §11, cada una reportando nodos examinados | Parcial | Parcial | Verificado en ejecución: top-k, intervalo y costosos sí reportan nodos/costo real; comparativa reporta su propio costo; asociaciones tiene el campo en el backend pero no en pantalla (sección 2.7); y **top-k e intervalo son recursivas y truenan en árboles degenerados grandes** (sección 2.6) | `domain/scenario.py:877-1046` |
| Carga por inserciones, por topología (atómica, validaciones completas), guardado estructural | Sí | Sí | No re-ejecuté directamente (código sin cambios: `domain/loader.py`, `domain/validation.py`, `domain/storage.py` no aparecen en el diff de este commit); lo doy por verificado porque **corrí `pytest tests/`**, que ejercita ciclos, orden global, alturas, FB, prioridad e IDs duplicados, y esos 20 tests de `test_loading.py` pasan | `domain/loader.py`; `domain/validation.py` |
| Versiones con nombre persistentes tras cerrar | Sí | Sí | No re-ejecuté (código sin cambios); verificado indirectamente vía `pytest tests/test_versions.py` (9 tests, todos pasan) | `domain/versions.py` |
| Auditoría: orden GLOBAL por K, no solo hijos inmediatos | Sí | Sí | Verificado en ejecución (sección 2.8: detectó una referencia rota; y el orden global lo prueba `tests/test_loading.py` con `check_tree`, que reutiliza `run_audit`) | `domain/scenario.py:626-663`; `domain/validation.py:151-171` |
| Indicadores del §14, incl. conteos LL/RR/LR/RL y giros simples | Sí | Sí | Solo lectura esta vez, sin cambios desde la revisión previa | `domain/scenario.py:142-149`; `web/index.html:44-47` |
| Vista del AVL, del BST, plano geográfico, cola, histórico, versiones | Sí | Sí | **Mejoró**: se agregó la pestaña "Histórico" (`web/index.html:192`, `web/app.js:135-151,190-192`) que antes no existía — cubre el hueco que reporté ("Vista de histórico… no encontrado en web/"). Verificado en el navegador: las 6 pestañas cargan sin error de consola | `web/index.html:184-278` |

---

## 4. Interfaz

**Paneles y botones**, sin cambios de fondo respecto a mi inventario anterior salvo lo que menciono explícitamente: Crear Evento, Corregir Evento, Eliminar/Buscar, Encolar Reporte + Procesar Siguiente, **Parámetros W/R/L/T** (turno anterior), Acciones (Deshacer, **Rehacer — nuevo**, Auditar, Modo Estrés, Recuperar Balance, **"Consultar ramas elegibles" — nuevo**, reemplaza al archivado directo), Archivo (guardar/cargar), Versiones; y en el panel central: pestañas Árbol AVL, BST, Plano, Consultas (5 sub-consultas), Cola, **Histórico (nueva)**.

**Funciones `@eel.expose` que ninguna parte de la interfaz invoca:** de 30 funciones expuestas (antes eran 27), solo **1 queda huérfana**:

| Función | Línea | Por qué quedó huérfana |
|---|---:|---|
| `archive_eligible` | `main.py:202` | Reemplazada por el flujo nuevo `get_eligible_branches` + `archive_selected_branch` (vista previa + selección manual), que sí se usa. Es código muerto, no una carencia. |

(Verificado por conteo automático de `eel.<nombre>(` en `web/app.js` contra cada `@eel.expose` de `main.py`.)

---

## 5. Los 6 casos del §16

Sin cambios respecto a mi auditoría anterior (ningún archivo de `tests/` ni `data/test_cases_section16/` cambió en este commit, salvo el nuevo `prueba_carga_masiva_1500.json`/`prueba_carga_inserciones.json`/`prueba_carga_topologia.json`, que son datos de carga masiva, no casos del §16):

| Caso | ¿Test automatizado? | ¿JSON de datos? |
|---|---|---|
| Límites y empates | Sí (`test_loading.py:229-237`) | Sí (`data/insertions/mezclado.json`, `ascendente.json`) |
| Corrección y reporte antiguo | Sí (`test_loading.py:102-114`) | Sí (`data/topologies/normal.json`) |
| Reporte tardío | **No** | **No** |
| Rotaciones y recuperación | Parcial (`test_new_structure.py`, sin los 4 casos por separado) | Parcial (`data/topologies/estres.json`) |
| Archivo masivo | Parcial (ningún test con varios eventos y desempates reales) | Parcial |
| Persistencia y consistencia | Sí (`test_section16_persistence.py`, 7 tests) | Sí (9 archivos en `data/topologies/`) |

---

## 6. Entregables del §17

- **Manual de usuario:** no encontrado.
- **Manual técnico:** no encontrado.
- **Reporte de uso de IA:** no encontrado. (El enunciado dice que estos tres van adjuntos al correo, no en Git/Drive/Dropbox — no puedo verificar el correo desde aquí.)
- **Comentarios que no están en inglés:** siguen siendo mayoría en los archivos de lógica. Recuento fresco de los archivos que cambiaron en este commit: `core/avl_tree.py` 7 de 16 comentarios en español (líneas 34,150,238,305,326,791,817); `domain/scenario.py` 15 de 37 (líneas 39,45,48,85,175,306,335,341,507,557,624,699,782,874,992); `main.py` 11 de 13 (líneas 18-19,22,25,28,304,314,368,401,409-410). No conté el resto del repo de nuevo (sin cambios desde mi auditoría previa, donde el total era ≈151 de 383 comentarios sin contar tests).
- **Rutas de archivo fijas:** ya no encontré ninguna (`main.py:377` con la ruta de Edge para Windows fue eliminada en el commit `33eb716`, confirmado por `grep` sobre todo el árbol de `.py/.js/.html`).
- **README con instrucciones que funcionan:** sí, con una salvedad. `pip install -r requirements.txt && python main.py` corre sin error (verificado). `python -m unittest discover -s tests -v` (el comando exacto del README) corre pero termina en `FAILED (failures=1)` por el motivo de la sección 1 — el README no lo advierte.
- **¿El repo evidencia aportes de cada integrante?** Sí en el historial de Git: 3 autores distintos con nombres reales de usuario de GitHub (`jhilder1`, `Alejandro`, `AndresTrejo38711`) y commits repartidos a lo largo de 9 días. Pero el `README.md:101-105` todavía dice "Integrante A/B/C" con roles genéricos en vez de nombrar a quien corresponde.

---

## 7. Veredicto

**No está terminado.** Es un salto real desde mi auditoría anterior — 6 de 8 defectos conocidos quedaron completamente corregidos y verificados en ejecución, se agregaron dos flujos de interfaz que antes faltaban del todo (histórico, selección manual de rama a archivar) y una función más quedó alcanzable (`mark_reviewed`). Pero quedan pendientes que si incumplen el enunciado, y uno de ellos (recursión) es el mismo tipo de defecto que ya se había "arreglado" a medias antes: se corrigieron las tres funciones que yo había señalado, pero otras tres con el mismo problema, en el mismo archivo, se quedaron sin tocar.

**Ninguna de las correcciones de esta ronda trae un test automatizado nuevo** (`git diff --stat -- tests/` entre el commit anterior y este solo muestra las 80 líneas que yo mismo agregué para el modo estrés en un turno previo). Todo lo que reporto arriba como "corregido" lo verifiqué con scripts que escribí y borré en este turno; si algo de esto se rompe en el próximo commit, `pytest` no lo va a notar.

**Pendientes, lo que incumple el enunciado primero:**

| # | Pendiente | Evidencia | Esfuerzo |
|--:|---|---|---|
| 1 | `pytest tests/` no está en verde: falta regenerar `prueba_carga_masiva_1500.json` desde `make_data.py`, o excluirlo de la comparación de reproducibilidad. | Sección 1 | Bajo |
| 2 | `query_top_k_pending`, `query_by_interval` y `find_eligible_branches`/`_is_subtree_eligible` siguen recursivas: truenan con `RecursionError` en un árbol degenerado de 1000 nodos, verificado. | Sección 2.6 | Medio |
| 3 | La auditoría no verifica la validez semántica de las asociaciones (mayor magnitud + anterioridad) ni detecta ciclos, solo que el ID exista. | Sección 2.8 | Medio |
| 4 | `query_event_associations` calcula `nodes_examined` en el backend pero la interfaz sigue sin mostrarlo (mensaje fijo desactualizado). | Sección 2.7 | Bajo |
| 5 | Consultar un evento eliminado sigue devolviendo "no encontrado" genérico, sin decir que existió y fue eliminado (pendiente ya señalado en mi auditoría previa, sin cambios). | `main.py:99-116`, verificado en el navegador esta vez | Bajo |
| 6 | Sin test automatizado para ninguna corrección de esta ronda (validación de reportes, desempate de 3 niveles, recálculo de asociaciones por cola, undo/redo de la cola, `_audit_associations`, selección manual de rama). | `git diff --stat -- tests/` | Medio-Alto |
| 7 | Caso §16 "reporte tardío": sigue sin test ni archivo de datos dedicado. | Sección 5 | Bajo |
| 8 | Manual de usuario, manual técnico y reporte de uso de IA: no encontrados en el repo (pueden estar en el correo, no lo puedo verificar). | Sección 6 | Alto si no existen |
| 9 | README: el comando de pruebas documentado termina en 1 fallo sin advertirlo; sección "Equipo" con marcadores genéricos en vez de los 3 nombres reales. | Sección 6 | Bajo |
| 10 | `archive_eligible` quedó huérfana (código muerto tras el cambio de flujo); no rompe nada, pero es limpieza pendiente. | Sección 4 | Bajo |

No suavizo el resultado: los defectos 1, 2 y 3 son cosas que un `pytest` completo o una prueba manual con datos grandes deberían haber atrapado antes de decir "terminado", y los tres estaban al alcance de la mano dado que la mitad del mismo problema (recursión) ya se había identificado y corregido a medias.
