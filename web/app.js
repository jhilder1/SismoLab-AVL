


function $(id) { return document.getElementById(id); }

function log(msg, type) {
    const el = $("log-msg");
    el.textContent = msg;
    el.className = "log-msg " + (type || "");
}

function val(id) { return $(id).value; }

// Escapa texto antes de meterlo en innerHTML (mensajes que vienen de archivos).
function esc(text) {
    return String(text).replace(/[&<>"']/g, c => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[c]);
}

// Ultimo estado recibido y arbol que se esta mostrando ("avl" o "bst").
let lastState = null;
let treeView = "avl";
let zonesCache = null;
let limitL = 3;                 // access-depth budget L (section 9)
let costlyIds = new Set();      // event ids currently marked as costly access

// =====================================================
// Refresh: trae el estado y actualiza toda la pantalla
// =====================================================

async function refresh() {
    try {
        const state = await eel.get_state()();
        lastState = state;
        limitL = state.parameters.L_depth;
        zonesCache = state.zones;
        computeCostly(state.tree.nodes);
        fillParameters(state.parameters);
        updateStats(state);
        drawCurrentTree();
        updateEvents(state.events);
        renderArchived(state.archived);
        renderQueue(state.queued_reports);
        updateStress(state.stress_mode);
        $("clock").textContent = state.clock.replace("T", " ");
    } catch (e) {
        log("Error al conectar con Python: " + e, "err");
    }
}

// =====================================================
// Costly access (section 9)
// =====================================================

// An active high-priority event is costly when its node depth exceeds L.
// Depth is derived from the tree the backend already sends: the root is 0
// and every child is its parent's depth plus one.
function computeCostly(root) {
    costlyIds = new Set();
    const stack = root ? [[root, 0]] : [];
    while (stack.length) {
        const [node, depth] = stack.pop();
        if (node.priority === 3 && depth > limitL) costlyIds.add(node.event_id);
        if (node.left) stack.push([node.left, depth + 1]);
        if (node.right) stack.push([node.right, depth + 1]);
    }
}

// =====================================================
// Update Stats Bar
// =====================================================

function updateStats(state) {
    $("st-active").textContent = state.counts.active;
    $("st-archived").textContent = state.counts.archived;
    $("st-deleted").textContent = state.counts.deleted;
    $("st-queue").textContent = state.counts.queued_reports;
    $("st-undo").textContent = state.counts.undo_depth;
    $("st-pending").textContent = state.counts.pending;
    $("st-costly").textContent = state.counts.costly_access;
    $("st-costly").style.color = state.counts.costly_access > 0 ? "var(--yellow)" : "";
    $("st-limit").textContent = state.parameters.L_depth;
    $("st-height").textContent = state.tree.height;
    $("st-leaves").textContent = state.tree.leaves;
    $("st-balanced").textContent = state.tree.balanced ? "Si" : "NO";
    $("st-balanced").style.color = state.tree.balanced ? "var(--green)" : "var(--red)";
    $("st-ll").textContent = state.rotations.ll;
    $("st-rr").textContent = state.rotations.rr;
    $("st-lr").textContent = state.rotations.lr;
    $("st-rl").textContent = state.rotations.rl;
}

function updateStress(isStress) {
    const badge = $("stress-badge");
    if (isStress) {
        badge.textContent = "ESTRES";
        badge.className = "badge badge-on";
    } else {
        badge.textContent = "Normal";
        badge.className = "badge badge-off";
    }
}

// =====================================================
// Update Events List (right panel)
// =====================================================

function updateEvents(events) {
    const list = $("events-list");
    if (!events || events.length === 0) {
        list.innerHTML = '<p class="muted">Sin eventos.</p>';
        return;
    }
    // Ordenar por prioridad descendente
    events.sort((a, b) => b.priority - a.priority || b.magnitude - a.magnitude);
    list.innerHTML = events.map(e => {
        const pClass = "p" + e.priority;
        const pName = ["", "LOW", "MED", "HIGH"][e.priority];
        return `<div class="event-card ${pClass}">
            <div class="ev-id">SIS-${String(e.event_id).padStart(6, "0")}</div>
            <div class="ev-detail">M=${e.magnitude} | P=${pName} | Prof=${e.depth_km}km | Rev=${e.revision}</div>
            <div class="ev-detail">Epi=(${e.epicenter.x}, ${e.epicenter.y}) | ${e.attention_state}</div>
            <button class="btn btn-sm" onclick="window.markReviewed(${e.event_id})" style="margin-top: 5px; width: 100%;">Marcar Revisado</button>
        </div>`;
    }).join("");
}

window.markReviewed = async function(id) {
    const res = await eel.mark_reviewed(id)();
    log(res.message, res.ok ? "info" : "error");
    if (res.ok) refresh();
};

function renderArchived(archived) {
    const list = $("archived-list");
    if (!archived || archived.length === 0) {
        list.innerHTML = '<p class="muted">Sin eventos archivados.</p>';
        return;
    }
    // Orden descendente por id
    archived.sort((a, b) => b.event_id - a.event_id);
    list.innerHTML = archived.map(e => {
        const pClass = "p" + e.priority;
        const pName = ["", "LOW", "MED", "HIGH"][e.priority];
        return `<div class="event-card ${pClass}">
            <div class="ev-id">SIS-${String(e.event_id).padStart(6, "0")} (Archivado)</div>
            <div class="ev-detail">M=${e.magnitude} | P=${pName} | Prof=${e.depth_km}km</div>
        </div>`;
    }).join("");
}

// =====================================================
// AVL / BST tabs
// =====================================================

function showTree(view) {
    treeView = view;
    $("tab-avl").classList.toggle("active", view === "avl");
    $("tab-bst").classList.toggle("active", view === "bst");
    $("tab-map").classList.toggle("active", view === "map");
    $("tab-queries").classList.toggle("active", view === "queries");
    $("tab-queue").classList.toggle("active", view === "queue");
    $("tab-history").classList.toggle("active", view === "history");
    drawCurrentTree();
}

function drawCurrentTree() {
    if (!lastState) return;
    const isMap = treeView === "map";
    const isQueries = treeView === "queries";
    const isQueue = treeView === "queue";
    const isHistory = treeView === "history";
    $("tree-svg").style.display = (!isMap && !isQueries && !isQueue && !isHistory) ? "block" : "none";
    $("map-svg").style.display = isMap ? "block" : "none";
    $("map-legend").style.display = isMap ? "flex" : "none";
    $("queries-panel").style.display = isQueries ? "flex" : "none";
    $("queue-panel").style.display = isQueue ? "flex" : "none";
    $("history-panel").style.display = isHistory ? "flex" : "none";
    $("tree-empty").style.display = "none";

    if (isQueue) {
        // The pending list and the history are refreshed by their own
        // functions (renderQueue on every refresh, renderHistory on every
        // processed step); this tab only needs its own header text.
        const n = (lastState.queued_reports || []).length;
        $("tree-root").textContent = `Cola FIFO de reportes | ${n} pendiente(s)`;
        return;
    }
    if (isHistory) {
        $("tree-root").textContent = `Histórico | ${(lastState.archived || []).length} archivados`;
        return;
    }
    if (isQueries) {
        // The queries panel keeps whatever result is already on screen: it
        // does not redraw on every refresh, same as the search result box.
        $("tree-root").textContent = "Consultas del catalogo activo (Seccion 11)";
        return;
    }
    if (isMap) {
        drawMap();
        const n = (lastState.events || []).length;
        $("tree-root").textContent = `Plano 0-1000 km | ${n} eventos activos`;
        return;
    }
    const data = treeView === "bst" ? lastState.bst : lastState.tree;
    const label = treeView === "bst" ? "BST" : "AVL";
    updateTree(data);
    $("tree-root").textContent = `${label} | Raiz: ${data.root || "--"} | Altura: ${data.height} | Hojas: ${data.leaves}`;
}

// =====================================================
// Draw AVL Tree (SVG)
// =====================================================

const NODE_R = 22;
const H_GAP = 16;
const V_GAP = 60;

function updateTree(treeData) {
    const svg = $("tree-svg");
    const emptyMsg = $("tree-empty");

    if (!treeData.nodes) {
        svg.innerHTML = "";
        svg.style.display = "none";
        emptyMsg.style.display = "block";
        return;
    }

    emptyMsg.style.display = "none";
    svg.style.display = "block";

    // Calcular posiciones
    const positions = [];
    const edges = [];
    let minX = Infinity, maxX = -Infinity, maxY = 0;

    // X = posicion del nodo en el recorrido inorden (columna k para el k-esimo
    // nodo), Y = profundidad. El ancho crece con la cantidad de nodos y no con
    // 2^altura, asi que un BST degenerado (una "escalera") tambien se ve.
    let column = 0;
    function layout(node, depth) {
        if (!node) return null;
        const left = layout(node.left, depth + 1);
        const x = column * (NODE_R * 2 + H_GAP);
        column++;
        const y = depth * V_GAP + NODE_R + 10;
        const right = layout(node.right, depth + 1);

        positions.push({ x, y, node });
        if (x < minX) minX = x;
        if (x > maxX) maxX = x;
        if (y > maxY) maxY = y;
        for (const child of [left, right]) {
            if (child) edges.push({ x1: x, y1: y, x2: child.x, y2: child.y });
        }
        return { x, y };
    }

    layout(treeData.nodes, 0);

    const svgW = maxX - minX + NODE_R * 4;
    const svgH = maxY + NODE_R * 2 + 10;
    const offsetX = -minX + NODE_R * 2;

    svg.setAttribute("width", svgW);
    svg.setAttribute("height", svgH);
    svg.setAttribute("viewBox", `0 0 ${svgW} ${svgH}`);

    let html = "";

    // Edges
    for (const e of edges) {
        html += `<line class="tree-edge" x1="${e.x1 + offsetX}" y1="${e.y1}" x2="${e.x2 + offsetX}" y2="${e.y2}"/>`;
    }

    // Nodes
    for (const p of positions) {
        const n = p.node;
        const cx = p.x + offsetX;
        const cy = p.y;

        // Color by priority
        let fill = "#3a4a6b"; // default
        if (n.priority === 3) fill = "#c62828";
        else if (n.priority === 2) fill = "#ef6c00";
        else if (n.priority === 1) fill = "#2e7d32";

        // Highlight unbalanced (el BST no guarda factor de balance)
        const hasBf = typeof n.bf === "number";
        let stroke = "none";
        let strokeW = 0;
        if (hasBf && Math.abs(n.bf) > 1) {
            stroke = "#ff1744";
            strokeW = 3;
        }

        html += `<circle class="node-circle" cx="${cx}" cy="${cy}" r="${NODE_R}" fill="${fill}" stroke="${stroke}" stroke-width="${strokeW}"/>`;

        // Costly access (section 9): high priority AND node depth > L.
        // Shown as a dashed outer ring so it stays distinct from the
        // priority colour, which is the node fill.
        // The BST view has no such mark: costly ids come from the AVL.
        if (treeView === "avl" && costlyIds.has(n.event_id)) {
            html += `<circle class="node-costly" cx="${cx}" cy="${cy}" r="${NODE_R + 5}"/>`;
            html += `<text class="node-costly-mark" x="${cx + NODE_R + 3}" y="${cy - NODE_R + 4}">$</text>`;
        }
        html += `<text class="node-label" x="${cx}" y="${cy + 1}">ID:${n.event_id}</text>`;
        html += `<text class="node-sublabel" x="${cx}" y="${cy + 13}">M${n.magnitude}</text>`;

        // Balance factor above node
        if (hasBf) {
            const bfColor = Math.abs(n.bf) > 1 ? "#ff1744" : "var(--yellow)";
            html += `<text class="node-bf" x="${cx}" y="${cy - NODE_R - 4}" fill="${bfColor}">${n.bf}</text>`;
        }
    }

    svg.innerHTML = html;
}

// =====================================================
// Actions: cada una llama a eel y hace refresh
// =====================================================
// =====================================================
// Geographic map (section 15): 0-1000 km plane
// =====================================================

const MAP_SIZE = 1000;   // km on each axis
const MAP_PAD = 46;      // room for axis labels

const mapX = km => MAP_PAD + km;
const mapY = km => MAP_PAD + (MAP_SIZE - km);   // y grows upward on screen

// Magnitude -2.0..10.0 mapped to a 4..15 px radius.
const magRadius = m => 4 + ((Math.max(-2, Math.min(10, m)) + 2) / 12) * 11;

const PRIORITY_FILL = { 1: "#2e7d32", 2: "#ef6c00", 3: "#c62828" };

function drawMap() {
    const svg = $("map-svg");
    const side = MAP_SIZE + MAP_PAD * 2;
    svg.setAttribute("viewBox", `0 0 ${side} ${side}`);
    svg.setAttribute("width", side);
    svg.setAttribute("height", side);

    let html = "";

    // Plane background
    html += `<rect class="map-plane" x="${MAP_PAD}" y="${MAP_PAD}" width="${MAP_SIZE}" height="${MAP_SIZE}"/>`;
    // Grid and axis labels every 100 km
    for (let k = 0; k <= MAP_SIZE; k += 100) {
        html += `<line class="map-grid" x1="${mapX(k)}" y1="${mapY(0)}" x2="${mapX(k)}" y2="${mapY(MAP_SIZE)}"/>`;
        html += `<line class="map-grid" x1="${mapX(0)}" y1="${mapY(k)}" x2="${mapX(MAP_SIZE)}" y2="${mapY(k)}"/>`;
        html += `<text class="map-axis" x="${mapX(k)}" y="${mapY(0) + 22}">${k}</text>`;
        html += `<text class="map-axis map-axis-y" x="${MAP_PAD - 10}" y="${mapY(k) + 4}">${k}</text>`;
    }

    // Zones: populated ones get a distinct fill, since priority depends on them
    for (const z of (zonesCache || [])) {
        const populated = z.populated ?? z.is_populated;
        const x = mapX(z.x_min);
        const y = mapY(z.y_max);
        const w = z.x_max - z.x_min;
        const h = z.y_max - z.y_min;
        html += `<rect class="map-zone ${populated ? "pop" : "npop"}" x="${x}" y="${y}" width="${w}" height="${h}">
            <title>${esc(z.name || "")} - ${populated ? "poblada" : "no poblada"}</title></rect>`;
        html += `<text class="map-zone-lbl" x="${x + 6}" y="${y + 18}">${esc(z.name || "")}</text>`;
    }

    // Events: colour = priority, radius = magnitude, hollow = already reviewed
    for (const e of (lastState.events || [])) {
        const cx = mapX(e.epicenter.x);
        const cy = mapY(e.epicenter.y);
        const r = magRadius(e.magnitude);
        const reviewed = e.attention_state === "reviewed";
        const stroke = PRIORITY_FILL[e.priority] || "#3a4a6b";
        const fill = reviewed ? "none" : stroke;
        // Costly access (section 9): dashed ring, separate from the priority colour
        if (costlyIds.has(e.event_id)) {
            html += `<circle class="map-costly" cx="${cx}" cy="${cy}" r="${r + 6}"/>`;
        }
        html += `<circle class="map-event" cx="${cx}" cy="${cy}" r="${r}" fill="${fill}" stroke="${stroke}" stroke-width="2.5">
            <title>SIS-${String(e.event_id).padStart(6, "0")} | M=${e.magnitude} | P=${e.priority} | H=${e.depth_km} km | Epi=(${e.epicenter.x}, ${e.epicenter.y}) | ${e.attention_state}</title></circle>`;
        html += `<text class="map-event-lbl" x="${cx}" y="${cy - r - 5}">${e.event_id}</text>`;
    }

    svg.innerHTML = html;
}

async function createEvent() {
    const timeVal = val("ev-time") || new Date().toISOString().slice(0, 19);
    const res = await eel.create_event(
        val("ev-id"), val("ev-mag"), val("ev-depth"),
        val("ev-x"), val("ev-y"), timeVal, val("ev-station")
    )();
    log(res.message, res.ok ? "ok" : "err");
    if (res.ok) refresh();
}

async function correctEvent() {
    const mag = val("cor-mag") || null;
    const dep = val("cor-depth") || null;
    const res = await eel.correct_event(val("cor-id"), mag, dep)();
    log(res.message, res.ok ? "ok" : "err");
    if (res.ok) refresh();
}

async function deleteEvent() {
    const res = await eel.delete_event(val("del-id"))();
    log(res.message, res.ok ? "ok" : "err");
    if (res.ok) refresh();
}

async function searchEvent() {
    const res = await eel.search_event(val("search-id"))();
    const box = $("search-result");
    if (res.ok) {
        const e = res.event;
        box.innerHTML = `<b>SIS-${String(e.event_id).padStart(6,"0")}</b> M=${e.magnitude} P=${e.priority}<br>
            Prof=${e.depth_km}km | Rev=${e.revision}<br>
            Profundidad en arbol: ${res.depth} | Costo acceso: ${res.access_cost}`;
        box.classList.remove("hidden");
        log("Evento encontrado. Costo de acceso: " + res.access_cost, "info");
    } else {
        box.innerHTML = res.message;
        box.classList.remove("hidden");
        log(res.message, "err");
    }
}

async function enqueueReport() {
    const timeVal = val("rp-time") || new Date().toISOString().slice(0, 19);
    const res = await eel.enqueue_report(
        val("rp-evid"), val("rp-rev"), val("rp-station"),
        val("rp-mag"), val("rp-depth"),
        val("rp-x"), val("rp-y"), timeVal
    )();
    log(res.message, res.ok ? "ok" : "err");
    if (res.ok) refresh();
}

// =====================================================
// Report queue and continuous processing (Section 8)
// =====================================================

// Spanish label, colour family and a short generic reason for each decision
// process_next_report can return (domain/scenario.py:295 onward). The family
// picks the CSS class: create/correct the catalogue, only confirm, or reject.
const REPORT_DECISIONS = {
    CREATED:            { label: "Creado",                family: "create",  why: "Identificador desconocido: se registra como evento nuevo" },
    CORRECTED:          { label: "Corregido",              family: "create",  why: "Revision mayor que la vigente: se actualizan los datos" },
    REACTIVATED:        { label: "Reactivado",             family: "create",  why: "Revision mayor sobre un evento archivado: vuelve al AVL" },
    CONFIRMED:          { label: "Confirmado",             family: "confirm", why: "Misma revision y mismos datos: se anade la estacion" },
    CONFIRMED_ARCHIVED: { label: "Confirmado (archivado)", family: "confirm", why: "Misma revision y mismos datos sobre un evento archivado" },
    CONFLICT:           { label: "Conflicto",              family: "reject",  why: "Misma revision pero datos distintos: se rechaza" },
    OUTDATED:           { label: "Desactualizado",         family: "reject",  why: "Revision menor que la vigente: se descarta" },
    REJECTED:           { label: "Rechazado",              family: "reject",  why: "Datos invalidos o evento eliminado: no se aplica" },
};

// The frontend's own record of processed steps. Section 8 asks that each
// step show its decision and rotations, not that the record survive a
// restart (unlike the undo stack or the named versions), so it lives only
// here, most recent first.
let reportHistory = [];
let continuousRunning = false;

function renderQueue(reports) {
    const box = $("queue-pending");
    if (!reports || reports.length === 0) {
        box.innerHTML = '<p class="muted">Cola vacia: no hay reportes pendientes.</p>';
        return;
    }
    // Position in the queue, not the event's priority, decides this order:
    // that is the point being shown here (Section 8).
    const rows = reports.map((r, i) => `<tr class="${i === 0 ? "queue-next" : ""}">
        <td>${i === 0 ? "Siguiente" : i + 1}</td>
        <td>SIS-${String(r.event_id).padStart(6, "0")}</td>
        <td>${esc(r.station_id)}</td>
        <td>${r.revision}</td>
        <td>${r.magnitude}</td>
        <td>${r.depth_km}</td>
        <td>(${r.epicenter.x}, ${r.epicenter.y})</td>
        <td>${esc((r.occurrence_time || "").replace("T", " ").replace("Z", ""))}</td>
    </tr>`).join("");
    box.innerHTML = `<table class="queue-table">
        <tr><th>#</th><th>Evento</th><th>Estacion</th><th>Rev</th><th>M</th><th>H (km)</th><th>Epicentro</th><th>Ocurrencia</th></tr>
        ${rows}
    </table>`;
}

// Extra, decision-specific detail the backend does provide (a rejection's
// reason, or the two revisions compared in an outdated report).
function decisionExtra(result) {
    const parts = [];
    if (result.reason) parts.push(result.reason);
    if (result.report_rev !== undefined && result.current_rev !== undefined) {
        parts.push(`reporte rev ${result.report_rev} vs vigente rev ${result.current_rev}`);
    }
    return parts.join(" — ");
}

function renderHistory() {
    const box = $("queue-history");
    if (!reportHistory.length) {
        box.innerHTML = '<p class="muted">Sin reportes procesados todavia.</p>';
        return;
    }
    box.innerHTML = reportHistory.map(entry => {
        const meta = REPORT_DECISIONS[entry.result] || { label: entry.result, family: "confirm", why: "" };
        const rot = entry.rotations;
        const rotated = rot.ll || rot.rr || rot.lr || rot.rl || rot.simple_left || rot.simple_right;
        const rotText = rotated
            ? `LL=${rot.ll} RR=${rot.rr} LR=${rot.lr} RL=${rot.rl} | giro izq=${rot.simple_left} der=${rot.simple_right}`
            : "sin rotaciones";
        const extra = entry.extra ? ` — ${esc(entry.extra)}` : "";
        return `<div class="history-entry family-${meta.family}">
            <div class="history-head">
                <span class="history-decision">${esc(meta.label)}</span>
                <span class="history-who">${esc(entry.station)} &rarr; SIS-${String(entry.eventId).padStart(6, "0")} rev ${entry.revision}</span>
            </div>
            <div class="history-why">${esc(meta.why)}${extra}</div>
            <div class="history-rot">${rotText}</div>
        </div>`;
    }).join("");
}

// Runs exactly one queue step. The backend's result does not always carry
// the station or the revision (Section 8 still asks for both), so the
// pending report is read here before it is dequeued; the rotations it
// produced are the AVL's rotation counters before this call minus after.
// Nothing is dequeued on EMPTY or PAUSED, so no history entry is added then.
async function processOneReport() {
    const pending = lastState && lastState.queued_reports ? lastState.queued_reports[0] : null;
    const before = lastState ? { ...lastState.rotations } : null;

    const result = await eel.process_report()();
    if (result.result === "EMPTY" || result.result === "PAUSED") {
        return result;
    }

    await refresh();

    const after = lastState.rotations;
    const rotations = before ? {
        ll: after.ll - before.ll, rr: after.rr - before.rr,
        lr: after.lr - before.lr, rl: after.rl - before.rl,
        simple_left: after.simple_left - before.simple_left,
        simple_right: after.simple_right - before.simple_right,
    } : { ll: 0, rr: 0, lr: 0, rl: 0, simple_left: 0, simple_right: 0 };

    reportHistory.unshift({
        station: pending ? pending.station_id : "?",
        eventId: pending ? pending.event_id : result.event_id,
        revision: pending ? pending.revision : (result.revision ?? "?"),
        result: result.result,
        extra: decisionExtra(result),
        rotations,
    });
    renderHistory();

    return result;
}

async function processReport() {
    const result = await processOneReport();
    if (result.result === "EMPTY" || result.result === "PAUSED") {
        log(result.message, "info");
        return;
    }
    const meta = REPORT_DECISIONS[result.result];
    log(meta ? `${meta.label}: ${meta.why}` : `Reporte procesado: ${result.result}`,
        meta && meta.family === "reject" ? "err" : "ok");
}

// One report per step, each fully resolved before the next starts, with a
// visible pause in between (Section 8). continuousRunning guards against two
// loops at once; the loop also stops on an empty queue (via EMPTY), on
// PAUSED (a recovery is running), or when the button is clicked again.
async function processContinuous() {
    const button = $("btn-continuous");
    if (continuousRunning) {
        continuousRunning = false;   // "Pausar": the loop checks this before its next step
        return;
    }

    continuousRunning = true;
    button.textContent = "Pausar";
    button.classList.replace("btn-primary", "btn-danger");

    const delay = Number(val("continuous-delay"));
    try {
        while (continuousRunning) {
            const result = await processOneReport();
            if (result.result === "EMPTY" || result.result === "PAUSED") {
                log(result.message, "info");
                break;
            }
            if (!continuousRunning) break;
            await new Promise(resolve => setTimeout(resolve, delay));
        }
    } finally {
        continuousRunning = false;
        button.textContent = "Procesar continuo";
        button.classList.replace("btn-danger", "btn-primary");
    }
}

async function undoAction() {
    const res = await eel.undo_action()();
    const msg = res.message || `Deshecho: ${res.description}`;
    log(msg, res.result === "UNDONE" ? "ok" : "info");
    refresh();
}

async function toggleStress() {
    const res = await eel.toggle_stress()();
    log("Modo estres: " + (res.stress_mode ? "ACTIVADO" : "desactivado"), res.stress_mode ? "err" : "ok");
    refresh();
}

async function recoverBalance() {
    const res = await eel.recover_balance()();
    if (res.result === "RECOVERED") {
        const c = res.cost;
        log(`Balance recuperado. LL=${c.ll} RR=${c.rr} LR=${c.lr} RL=${c.rl} | Altura final=${c.final_height}`, "ok");
    } else {
        log(res.message, "info");
    }
    refresh();
}

async function runAudit() {
    const res = await eel.run_audit()();
    if (res.is_valid) {
        log(`Auditoria OK: ${res.nodes_checked} nodos verificados, 0 errores`, "ok");
    } else {
        log(`Auditoria FALLO: ${res.errors.length} error(es): ${res.errors[0]}`, "err");
    }
}

async function advanceClock() {
    const res = await eel.advance_clock(1)();
    log("Reloj avanzado a " + res.clock.replace("T", " "), "info");
    refresh();
}

async function archiveEligible() {
    const res = await eel.archive_eligible()();
    if (res.result === "ARCHIVED") {
        log(`Archivados ${res.count} eventos: ${res.event_ids}`, "ok");
    } else {
        log(res.message || "No hay ramas elegibles para archivar", "info");
    }
    refresh();
}

// =====================================================
// Queries and performance analysis (Section 11)
// =====================================================

const PRIORITY_NAME = ["", "BAJA", "MEDIA", "ALTA"];

// Shared body for an event card; eventCardHtml wraps it, costlyCardHtml
// appends one more line without nesting a second .event-card inside it.
function eventCardInner(e) {
    const id = "SIS-" + String(e.event_id).padStart(6, "0");
    const date = (e.occurrence_time || "").replace("T", " ").replace("Z", "");
    return `<div class="ev-id">${id}</div>
        <div class="ev-detail">M=${e.magnitude} | P=${PRIORITY_NAME[e.priority] || e.priority} | Prof=${e.depth_km} km | Rev=${e.revision}</div>
        <div class="ev-detail">Epi=(${e.epicenter.x}, ${e.epicenter.y}) | ${esc(date)} | ${e.attention_state}</div>`;
}

function eventCardHtml(e) {
    return `<div class="event-card p${e.priority}">${eventCardInner(e)}</div>`;
}

function costlyCardHtml(c) {
    return `<div class="event-card p${c.event.priority}">${eventCardInner(c.event)}
        <div class="ev-detail costly-line">Clave=${esc(c.key)} | profundidad del nodo=${c.depth} (L=${c.limit_L}) | nodos visitados=${c.nodes_visited}</div>
    </div>`;
}

// Sub-tab inside the Consultas panel: one form and one set of results shown
// at a time, so switching query never mixes a stale result with a new one.
function showQuery(name) {
    document.querySelectorAll(".qtab").forEach(b => b.classList.toggle("active", b.dataset.q === name));
    document.querySelectorAll(".query-form").forEach(f => f.classList.toggle("hidden", f.id !== `qform-${name}`));
    $("query-cost").classList.add("hidden");
    $("query-results").innerHTML = "";
}

// Section 11: every query reports how many AVL nodes it examined. That cost
// always goes on its own highlighted line, never buried inside the results.
function showQueryCost(text) {
    const box = $("query-cost");
    box.textContent = text;
    box.classList.remove("hidden");
}

function showQueryResults(html) {
    $("query-results").innerHTML = html;
}

function showQueryError(message) {
    $("query-cost").classList.add("hidden");
    $("query-results").innerHTML = `<p class="query-error">${esc(message)}</p>`;
    log(message, "err");
}

async function runQueryTopK() {
    const k = val("q-topk-k") || "5";
    const res = await eel.query_top_k_pending(k)();
    if (!res.ok) { showQueryError(res.message); return; }
    const d = res.data;
    const active = lastState ? lastState.counts.active : "?";
    showQueryCost(`Nodos del AVL examinados: ${d.nodes_examined} de ${active} activos | k solicitado=${d.k} | obtenidos=${d.count}`);
    showQueryResults(d.results.length ? d.results.map(eventCardHtml).join("")
        : '<p class="muted">No hay eventos pendientes.</p>');
}

async function runQueryInterval() {
    const minMag = val("q-int-min"), maxMag = val("q-int-max");
    if (minMag === "" || maxMag === "") { log("Magnitud minima y maxima son obligatorias", "err"); return; }
    const depth = val("q-int-depth") || null;
    // datetime-local gives "YYYY-MM-DDTHH:MM" (no seconds). Checked against
    // this project's Python (3.11+): datetime.fromisoformat accepts that
    // directly, so nothing is appended here, same as createEvent's ev-time.
    const from = val("q-int-from") || null;
    const to = val("q-int-to") || null;
    const res = await eel.query_by_interval(minMag, maxMag, depth, from, to)();
    if (!res.ok) { showQueryError(res.message); return; }
    const d = res.data;
    const active = lastState ? lastState.counts.active : "?";
    showQueryCost(`Nodos del AVL examinados: ${d.nodes_examined} de ${active} activos | resultados=${d.count}`);
    showQueryResults(d.results.length ? d.results.map(eventCardHtml).join("")
        : '<p class="muted">Ningun evento cumple el intervalo.</p>');
}

async function runQueryAssociations() {
    const id = val("q-assoc-id");
    if (!id) { log("Indica un ID de evento", "err"); return; }
    const res = await eel.query_event_associations(id)();
    if (!res.ok) { showQueryError(res.message); return; }
    const d = res.data;

    // This query walks active and archived events, not the AVL, so there is
    // no node-examined count to report here (unlike the other four).
    showQueryCost(`Esta consulta recorre eventos activos y archivados, no el AVL: no hay nodos examinados que reportar `
        + `| candidatos=${d.candidates.length} | referencias entrantes=${d.replicas.length}`);

    const statusBadge = s => `<span class="status-badge ${s === "ACTIVO" ? "active" : "archived"}">${s}</span>`;
    const fmtId = id => "SIS-" + String(id).padStart(6, "0");

    let html = `<div class="assoc-block"><h4>Evento consultado</h4>
        <div>${fmtId(d.event_id)} ${statusBadge(d.status)}</div></div>`;

    html += `<div class="assoc-block"><h4>Referencia elegida</h4>`;
    html += d.reference
        ? `<div class="assoc-row">${fmtId(d.reference.event_id)} M=${d.reference.magnitude} ${statusBadge(d.reference.status)}</div>`
        : `<p class="muted">Sin referencia.</p>`;
    html += `</div>`;

    html += `<div class="assoc-block"><h4>Candidatos (${d.candidates.length})</h4>`;
    html += d.candidates.length
        ? d.candidates.map(c => `<div class="assoc-row">${fmtId(c.event_id)} M=${c.magnitude} | H=${c.depth_km} km `
            + `| distancia=${c.distance_km} km | &Delta;t=${c.time_delta_hours} h ${statusBadge(c.status)}</div>`).join("")
        : `<p class="muted">Sin candidatos.</p>`;
    html += `</div>`;

    html += `<div class="assoc-block"><h4>Eventos que lo usan como referencia (${d.replicas.length})</h4>`;
    html += d.replicas.length
        ? d.replicas.map(r => `<div class="assoc-row">${fmtId(r.event_id)} M=${r.magnitude} ${statusBadge(r.status)}</div>`).join("")
        : `<p class="muted">Ninguno.</p>`;
    html += `</div>`;

    showQueryResults(html);
}

async function runQueryCostly() {
    const res = await eel.query_costly_high_priority()();
    if (!res.ok) { showQueryError(res.message); return; }
    const d = res.data;
    // The relevant cost here is the sum of nodes visited across every
    // individual key search, not one tree walk (Sections 9 and 11).
    const totalVisited = d.costly_events.reduce((sum, c) => sum + c.nodes_visited, 0);
    showQueryCost(`Nodos visitados en total (suma de cada busqueda por clave): ${totalVisited} `
        + `| limite L=${d.limit_L} | eventos costosos=${d.count}`);
    showQueryResults(d.costly_events.length ? d.costly_events.map(costlyCardHtml).join("")
        : '<p class="muted">Ningun evento de prioridad alta supera el limite L.</p>');
}

async function runQueryCompare() {
    const res = await eel.compare_trees_view()();
    if (!res.ok) { showQueryError(res.message); return; }
    const d = res.data;
    showQueryCost(`Comparacion sobre los ${d.size} eventos activos actuales `
        + `(compara dos estructuras completas, no es una busqueda por clave)`);
    const row = (label, key) => `<tr><td>${label}</td><td>${d.avl[key] ?? "--"}</td><td>${d.bst[key] ?? "--"}</td></tr>`;
    showQueryResults(`<table class="query-table">
        <tr><th></th><th>AVL</th><th>BST</th></tr>
        ${row("Raiz", "root")}
        ${row("Altura", "height")}
        ${row("Hojas", "leaves")}
        ${row("Comparaciones totales (buscar todas las claves)", "total_comparisons")}
        ${row("Comparaciones promedio", "avg_comparisons")}
    </table>`);
}

// =====================================================
// Parameters W, R, L, T (sections 7, 9 and 10)
// =====================================================

// Order matches update_parameters(w_hours, r_km, l_depth, t_archive_hours).
const PARAM_FIELDS = [
    ["par-w", "W_hours"],
    ["par-r", "R_km"],
    ["par-l", "L_depth"],
    ["par-t", "T_archive_hours"],
];

// Preload the current values, but never overwrite a field being edited.
function fillParameters(params) {
    for (const [id, key] of PARAM_FIELDS) {
        const input = $(id);
        if (document.activeElement !== input) input.value = params[key];
    }
}

// An empty field is sent as null so a single parameter can be changed.
async function applyParameters() {
    const args = PARAM_FIELDS.map(([id]) => val(id).trim() === "" ? null : Number(val(id)));
    const res = await eel.update_parameters(...args)();
    log(res.message, res.ok ? "ok" : "err");
    refresh();
}

// =====================================================
// Archivo: guardar y cargar (Seccion 12)
// =====================================================

function showFileResult(html) {
    const box = $("file-result");
    box.innerHTML = html;
    box.classList.remove("hidden");
}

function showProblems(res) {
    const items = (res.problems || []).map(p => `<li>${esc(p)}</li>`).join("");
    showFileResult(`<b class="err">${esc(res.file || "")}: rechazado</b>
        <div>El escenario actual se conserva sin cambios.</div><ul>${items}</ul>`);
}

async function saveScenario() {
    const res = await eel.save_scenario()();
    log(res.message, res.ok ? "ok" : (res.cancelled ? "info" : "err"));
}

async function loadScenario() {
    const res = await eel.load_scenario()();
    if (res.cancelled) { log(res.message, "info"); return; }
    if (!res.ok) { log(res.message, "err"); showProblems(res); return; }

    const i = res.info;
    const modeText = i.balanced
        ? `modo ${i.mode === "stress" ? "estres" : "normal"}, arbol balanceado`
        : `<b class="err">modo estres: topologia desbalanceada</b>`;
    const bad = i.unbalanced_nodes.map(n => `ID ${n.event_id} (FB ${n.balance_factor})`).join(", ");
    showFileResult(`<b class="ok">${esc(res.file)} cargado</b><br>
        ${i.active} activos, ${i.archived} en historico | raiz ID ${i.root ?? "--"} | altura ${i.height}<br>
        ${modeText}${bad ? "<br>Nodos desbalanceados: " + esc(bad) : ""}`);
    log(`Escenario ${res.file} cargado (${i.mode})`, i.balanced ? "ok" : "info");
    showTree("avl");
    refresh();
}

async function loadInsertions() {
    const res = await eel.load_insertions()();
    if (res.cancelled) { log(res.message, "info"); return; }
    if (!res.ok) { log(res.message, "err"); showProblems(res); return; }

    const c = res.info;
    const row = (label, key) => `<tr><td>${label}</td><td>${esc(c.avl[key] ?? "--")}</td><td>${esc(c.bst[key] ?? "--")}</td></tr>`;
    const r = c.rotations;
    showFileResult(`<b class="ok">${esc(res.file)}: ${c.events} eventos insertados en el mismo orden</b>
        <table>
            <tr><th></th><th>AVL</th><th>BST</th></tr>
            ${row("Raiz", "root")}
            ${row("Altura", "height")}
            ${row("Prof. maxima", "max_depth")}
            ${row("Hojas", "leaves")}
            ${row("Comparaciones (buscar todas)", "total_comparisons")}
            ${row("Peor busqueda", "max_comparisons")}
        </table>
        Rotaciones AVL: LL=${r.ll} RR=${r.rr} LR=${r.lr} RL=${r.rl} | giros izq=${r.simple_left} der=${r.simple_right}`);
    log(`${c.events} eventos cargados por insercion. Usa las pestanas AVL / BST para comparar.`, "ok");
    refresh();
}

// =====================================================
// Versiones con nombre (Seccion 13)
// =====================================================

async function refreshVersions() {
    const list = await eel.list_versions()();
    const box = $("versions-list");
    if (!list.length) {
        box.innerHTML = '<p class="muted">Sin versiones guardadas.</p>';
        return;
    }
    // Mas reciente arriba.
    box.innerHTML = list.slice().reverse().map(v => {
        if (!v.valid) {
            return `<div class="version-item invalid" title="${esc(v.error)}">
                <div><div class="v-name">${esc(v.name)}</div>
                <div class="v-detail">Archivo danado: no se puede restaurar</div></div></div>`;
        }
        const saved = v.saved_at.replace("T", " ").replace("Z", " UTC");
        const mode = v.mode === "stress" ? " | estres" : "";
        return `<div class="version-item">
            <div><div class="v-name">${esc(v.name)}</div>
            <div class="v-detail">Guardada ${esc(saved)}</div>
            <div class="v-detail">Reloj ${esc(v.clock.replace("T", " ").replace("Z", ""))} | ${v.active} activos, ${v.archived} hist.${mode}</div></div>
            <button class="btn btn-sm" onclick="restoreVersion('${esc(v.id)}')">Restaurar</button>
        </div>`;
    }).join("");
}

async function saveVersion() {
    const res = await eel.save_version(val("version-name"))();
    log(res.message, res.ok ? "ok" : "err");
    if (res.ok) {
        $("version-name").value = "";
        refreshVersions();
    }
}

async function restoreVersion(id) {
    const res = await eel.restore_version(id)();
    log(res.message, res.ok ? "ok" : "err");
    if (!res.ok) {
        showProblems({ file: "Version", problems: res.problems });
        return;
    }
    showTree("avl");
    refresh();
}

// =====================================================
// Init: cargar estaciones y estado inicial
// =====================================================

async function init() {
    // Llenar selects de estaciones
    const stations = await eel.get_stations()();
    for (const sel of [document.getElementById("ev-station"), document.getElementById("rp-station")]) {
        sel.innerHTML = stations.map(s => `<option value="${s.station_id}">${s.station_id}</option>`).join("");
    }
    // Poner fecha default
    const now = "2026-01-01T00:00";
    $("ev-time").value = now;
    $("rp-time").value = now;

    renderHistory();
    refresh();
    refreshVersions();
}

// Arrancar cuando la pagina cargue
window.addEventListener("load", init);
