// =====================================================
// Indicators, traversals and action log (Section 14)
// =====================================================

// Same names as domain/indicators.py, which the action log also uses.
const INDICATOR_LABELS = {
    active: "Eventos activos",
    archived: "Eventos en el historico",
    deleted: "IDs eliminados",
    queue: "Reportes en cola",
    height: "Altura del AVL",
    leaves: "Hojas",
    priority_high: "Prioridad alta",
    priority_medium: "Prioridad media",
    priority_low: "Prioridad baja",
    pending: "Pendientes de atencion",
    costly: "Con acceso costoso",
    events_created: "Eventos creados",
    reports_processed: "Reportes procesados",
    corrections: "Correcciones aceptadas",
    reports_discarded: "Reportes descartados",
    conflicts: "Conflictos",
    confirmations: "Confirmaciones",
    archive_operations: "Archivos masivos",
    archives: "Eventos archivados (acumulado)",
    ll: "Casos LL",
    rr: "Casos RR",
    lr: "Casos LR",
    rl: "Casos RL",
    simple_left: "Giros simples a la izquierda",
    simple_right: "Giros simples a la derecha",
};

const INDICATOR_GROUPS = [
    ["ind-structure", ["active", "archived", "deleted", "queue", "height", "leaves"]],
    ["ind-priority", ["priority_high", "priority_medium", "priority_low", "pending", "costly"]],
    ["ind-operations", ["corrections", "reports_discarded", "conflicts", "confirmations",
                        "archive_operations", "archives", "events_created", "reports_processed"]],
    ["ind-rotations", ["ll", "rr", "lr", "rl", "simple_left", "simple_right"]],
];

const ACTION_LABELS = {
    CREATE: "Crear evento", CORRECT: "Corregir evento", DELETE: "Eliminar evento",
    REVIEW: "Marcar revisado", ENQUEUE_REPORT: "Encolar reporte", PROCESS_REPORT: "Paso de la cola",
    ARCHIVE: "Archivo masivo", TOGGLE_STRESS: "Cambio de modo", RECOVER: "Recuperacion global",
    ADVANCE_CLOCK: "Avance del reloj", PARAM_UPDATE: "Cambio de parametros",
    LOAD_TOPOLOGY: "Carga por topologia", LOAD_INSERTIONS: "Carga por inserciones",
    RESTORE_VERSION: "Restaurar version", LOAD_BURST: "Carga de rafaga", UNDO: "Deshacer", REDO: "Rehacer",
};

function renderIndicators(state) {
    const values = state.indicators;
    for (const [id, names] of INDICATOR_GROUPS) {
        $(id).innerHTML = names.map(name => {
            const label = name === "costly"
                ? `${INDICATOR_LABELS.costly} (alta y profundidad > L=${state.parameters.L_depth})`
                : INDICATOR_LABELS[name];
            return `<tr><td>${esc(label)}</td><td>${values[name]}</td></tr>`;
        }).join("");
    }
}

const TRAVERSALS = ["inorder", "preorder", "postorder", "level_order"];

// Nodes per level of the drawn tree, to split the level-order list by level.
function levelSizes(root) {
    const sizes = [];
    let level = root ? [root] : [];
    while (level.length) {
        sizes.push(level.length);
        level = level.flatMap(n => [n.left, n.right].filter(Boolean));
    }
    return sizes;
}

// The backend sends each traversal as keys [P, M, I]; the selector shows
// either the event id or the whole key.
function renderTraversals() {
    if (!lastState || !lastState.traversals) return;
    const asKey = val("trav-format") === "key";
    const show = k => asKey ? `(${k[0]}, ${k[1]}, ${k[2]})` : String(k[2]);
    for (const name of TRAVERSALS) {
        const keys = lastState.traversals[name];
        $(`trav-n-${name}`).textContent = `(${keys.length} nodos)`;
        let html;
        if (!keys.length) {
            html = '<span class="muted">Arbol vacio.</span>';
        } else if (name === "level_order") {
            let start = 0;
            html = levelSizes(lastState.tree.nodes).map((size, depth) => {
                const row = keys.slice(start, start + size).map(show).join("  ");
                start += size;
                return `<div><span class="trav-level">Nivel ${depth}:</span> ${esc(row)}</div>`;
            }).join("");
        } else {
            html = esc(keys.map(show).join(" → "));
        }
        $(`trav-${name}`).innerHTML = html;
    }
}

function changeHtml(c) {
    const delta = c.after - c.before;
    return `<span class="chg ${delta > 0 ? "up" : "down"}">${esc(INDICATOR_LABELS[c.name] || c.name)}: `
        + `${c.before} &rarr; ${c.after} (${delta > 0 ? "+" : ""}${delta})</span>`;
}

async function refreshActionLog() {
    const entries = await eel.get_action_log(100)();
    const box = $("action-log");
    if (!entries.length) {
        box.innerHTML = '<p class="muted">Sin acciones registradas en esta sesion.</p>';
        return;
    }
    box.innerHTML = entries.map(e => `<div class="action-entry">
        <div class="action-head">
            <span class="action-type">#${e.seq} ${esc(ACTION_LABELS[e.type] || e.type)}</span>
            <span class="action-clock">reloj ${esc(e.clock.replace("T", " ").replace("Z", ""))}</span>
        </div>
        <div class="action-desc">${esc(e.description)}</div>
        <div class="action-changes">${e.changes.length ? e.changes.map(changeHtml).join("")
            : '<span class="muted">No cambio ningun indicador.</span>'}</div>
    </div>`).join("");
}

