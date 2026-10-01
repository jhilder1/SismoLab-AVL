# Casos mínimos de la sección 16

Cada carpeta declara el estado inicial de un caso con archivos que se cargan
desde la interfaz. Abajo están los pasos y el resultado esperado.

Para ver los resultados esperados y obtenidos de todos los casos en una sola
salida:

```bash
python tools/section16_report.py
```

`tests/test_section16_cases.py` ejecuta los mismos casos y falla si algún
resultado obtenido cambia. Los archivos se regeneran con
`python tools/make_data.py`.

Todos los escenarios usan las zonas y estaciones de `main.py`, el reloj en
2026-09-12 00:00 UTC y los parámetros iniciales (W = 48 h, R = 40 km, L = 3,
T = 72 h).

## Caso 1: límites y empates (`caso1-limites-empates/`)

**Estado inicial:** escenario vacío. **Cargar por inserciones** →
`inserciones.json`.

| Evento | Datos | Prioridad esperada |
|---|---|---|
| 101 | M 4.5, H 30.0, zona poblada | ALTA (ambos límites son inclusivos) |
| 102 | M 4.5, H 30.1, zona poblada | MEDIA |
| 103 | M 4.4, H 10.0, zona poblada | BAJA |
| 104 | M 6.0, H 300.0, zona no poblada | ALTA |
| 105 | M 5.9, H 300.0, zona no poblada | MEDIA |
| 106 | M 4.8, H 20.0, epicentro (500, 100) | ALTA: el borde entre Sur y Costa cuenta como zona poblada |
| 107 | M 4.8, H 20.0, epicentro (499.9, 100) | MEDIA: solo Sur, no poblada |

**Empate:** 110, 108 y 109 tienen P = 1 y M = 3.2 y se insertan en ese orden.
El recorrido inorden (pestaña Indicadores, formato "Clave K") los muestra como
108, 109, 110: el ID decide.

## Caso 2: corrección y reporte antiguo (`caso2-correccion-reporte-antiguo/`)

**Estado inicial:** **Cargar escenario** → `escenario.json`. El evento 200
tiene M 4.8 y H 70.0, prioridad 2, clave (2, 4.8, 200) y revisión 1.

1. **Corregir Evento** 200 con magnitud 6.2 y profundidad 15.0. Resultado:
   prioridad 3, clave (3, 6.2, 200) y revisión 2. El nodo cambia de lugar y
   sigue habiendo 5 nodos.
2. Pestaña **Cola** → **Cargar ráfaga (JSON)** → `rafaga-revision-antigua.json`.
   El archivo trae la revisión 1 con los datos originales.
3. **Procesar un paso**. Resultado: **Desactualizado** (reporte rev 1 frente a
   la rev 2 vigente). Siguen 5 nodos y el evento 200 conserva M 6.2, H 15.0 y
   revisión 2.

## Caso 3: reporte tardío (`caso3-reporte-tardio/`)

**Estado inicial:** **Cargar escenario** → `escenario.json`.
- 301: M 5.6 a las 10:00.
- 302: M 4.2 a las 10:20, a 11 km de 301.
- 302 tiene como candidato y referencia a 301; 301 no tiene candidatos.

1. Pestaña **Cola** → **Cargar ráfaga** → `rafaga-reporte-tardio.json`. Llega
   el evento 303: M 6.1, ocurrido a las 09:55, cerca de ambos.
2. **Procesar un paso**. Resultado: **Creado**.
3. En **Consultas → Asociaciones** (o al buscar cada ID):
   - 301 tiene un candidato nuevo, 303, que es su referencia.
   - 302 tiene como candidatos a 303 y 301, en ese orden por la política
     (mayor magnitud, luego menor distancia, luego menor ID). Su referencia
     pasa de 301 a 303.
   - 303 no tiene candidatos: ningún evento es mayor y anterior.

## Caso 4: rotaciones y recuperación (`caso4-rotaciones-recuperacion/`)

**Los cuatro casos de balanceo.** En un escenario vacío, **Cargar por
inserciones** con cada archivo. El recuadro de resultado y el registro de
acciones (pestaña Indicadores) muestran:

| Archivo | Orden de M | Resultado |
|---|---|---|
| `rotacion-ll.json` | 3.0, 2.0, 1.0 | LL = 1, 1 giro a la derecha |
| `rotacion-rr.json` | 1.0, 2.0, 3.0 | RR = 1, 1 giro a la izquierda |
| `rotacion-lr.json` | 3.0, 1.0, 2.0 | LR = 1, un giro a cada lado (caso doble) |
| `rotacion-rl.json` | 1.0, 3.0, 2.0 | RL = 1, un giro a cada lado (caso doble) |
| `rotaciones-cuatro-casos.json` | 7 inserciones | RR, LL, RL y LR una vez cada uno; AVL de altura 2 frente a BST de altura 5 |

**Degradación en estrés y recuperación:**
1. **Cargar escenario** → `base.json`: 5 eventos cercanos con asociaciones.
2. **Modo Estrés**.
3. Pestaña **Cola** → **Cargar ráfaga** → `rafaga-ascendente.json`: 8 altas con
   claves ascendentes.
4. **Procesar continuo**. El árbol se degrada en una cadena a la derecha, con
   altura 9 y factores de balance de hasta -7 (desbalance mayor que 2).
   **Verificar estructura** (pestaña Auditoría) informa 0 errores de orden y
   metadatos, y aparte el desbalance esperado del modo estrés.
   `estres-degradado.json` guarda este mismo estado, por si se quiere cargar
   directamente.
5. **Recuperar Balance**: RR = 8 y RL = 2, altura final 4. Se conservan los 13
   identificadores, el recorrido inorden y todas las referencias.
6. **Modo Estrés** otra vez: vuelve a modo normal porque la auditoría confirma
   el equilibrio.

## Caso 5: archivo masivo (`caso5-archivo-masivo/`)

**Estado inicial:** **Cargar escenario** → `escenario.json`. Es un AVL perfecto
de 15 nodos:
- 601 a 610 tienen prioridad baja y más de 72 h, salvo 604, que tiene 24 h;
- 611 a 615 tienen prioridad media o alta.

1. **Archivar rama de eventos antiguos** muestra la vista previa:
   - **Seleccionada:** raíz 606 con 605, 606 y 607. Empata en nodos (3) y
     profundidad (2) con la raíz 602, y gana por tener el mayor ID.
   - **Otras elegibles:** 602 (3 nodos, ID menor) y 609 (1 nodo, menos nodos).
   - **Raíces de prioridad baja no elegibles:** 610, porque contiene a 611, de
     prioridad MEDIUM; y 608, porque contiene a 604, de 24 h.
2. **Archivar esta rama**: 3 eventos pasan al histórico, quedan 12 activos y el
   AVL se rebalancea.
3. **Deshacer**: vuelve el estado inicial completo en una sola acción.
4. **Parámetros** con T = 1000 → **Archivar rama** otra vez: "No hay ramas
   elegibles"; nada cambia.

## Caso 6: persistencia y consistencia (`../topologies/`)

Usa los archivos de `data/topologies/`:
1. Cargar `normal.json` y `estres.json`, **Guardar escenario** y volver a
   cargar lo guardado: mismo estado y misma topología. `estres.json` se carga
   en modo estrés y desbalanceado.
2. Con `normal.json` cargado, cargar `inconsistente-orden.json`,
   `inconsistente-metadatos.json` e `invalido-referencias.json`: cada uno se
   rechaza con su causa y el escenario actual no cambia.
3. **Versiones**: guardar "Base", cerrar el programa, abrirlo y restaurarla.
4. Corregir el evento 150 y **Deshacer**. Procesar un paso de la cola (170
   rev 1, desactualizado) y **Deshacer**: el reporte vuelve al inicio de la
   cola.

## Ráfagas de reportes, sección 8 (`../bursts/`)

Todas son para `topologies/normal.json`: su estado decide cada resultado.
Se cargan desde la pestaña **Cola**.

- `rafaga-mixta.json`: 12 reportes de 4 estaciones. Contiene:
  - altas: 300, y 301 con revisión inicial 3;
  - confirmaciones, incluida una repetida que no duplica la estación;
  - una corrección que cambia la prioridad (150: de 3 a 1) y otra que solo
    cambia la magnitud (118);
  - un reporte antiguo, un conflicto (120) y un ID eliminado (181);
  - una reactivación del histórico (141) y una confirmación de un archivado
    (142).
- `rafaga-altas-concurrentes.json`: 8 eventos nuevos de 4 estaciones, cada uno
  confirmado después por otras 2. El orden de la cola es el de recepción, no
  el de prioridad.
- `rafaga-invalida.json`: se rechaza completa por una estación desconocida,
  una magnitud con dos decimales y una ocurrencia posterior al reloj. La cola
  no cambia.
