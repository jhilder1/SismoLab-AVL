


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

// =====================================================
// Refresh: trae el estado y actualiza toda la pantalla
// =====================================================

async function refresh() {
    try {
        const state = await eel.get_state()();
        lastState = state;
        updateStats(state);
        drawCurrentTree();
        updateEvents(state.events);
        updateStress(state.stress_mode);
        $("clock").textContent = state.clock.replace("T", " ");
    } catch (e) {
        log("Error al conectar con Python: " + e, "err");
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
    drawCurrentTree();
}

function drawCurrentTree() {
    if (!lastState) return;
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

async function processReport() {
    const res = await eel.process_report()();
    const msg = res.message || `Reporte procesado: ${res.result}` +
        (res.event_id ? ` (evento ${res.event_id})` : "") +
        (res.reason ? ` - ${res.reason}` : "");
    log(msg, res.result === "CREATED" || res.result === "CONFIRMED" || res.result === "CORRECTED" ? "ok" : "info");
    refresh();
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

    refresh();
}

// Arrancar cuando la pagina cargue
window.addEventListener("load", init);
