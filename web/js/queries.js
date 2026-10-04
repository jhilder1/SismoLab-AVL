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

// Why a query could (or could not) skip branches, shown above its results.
function queryExplainHtml(text, items) {
    const list = items && items.length ? `<ul>${items.map(i => `<li>${i}</li>`).join("")}</ul>` : "";
    return `<div class="query-explain">${text}${list}</div>`;
}

async function runQueryMagnitude() {
    const minMag = val("q-mag-min"), maxMag = val("q-mag-max");
    if (minMag === "" || maxMag === "") { log("Magnitud minima y maxima son obligatorias", "err"); return; }
    const res = await eel.query_by_magnitude(minMag, maxMag)();
    if (!res.ok) { showQueryError(res.message); return; }
    const d = res.data;
    showQueryCost(`Nodos del AVL examinados: ${d.nodes_examined} de ${d.active} activos `
        + `| subarboles descartados sin visitarlos: ${d.pruned_subtrees} | resultados=${d.count}`);
    // Section 11 asks which branches K lets us skip: the magnitude bounds the
    // priority, so only these runs of keys can hold a match.
    const runs = d.runs.map(r => r.searched
        ? `<b>${PRIORITY_NAME[r.priority]}</b>: se recorren las claves ${esc(r.text)}`
        : `<b>${PRIORITY_NAME[r.priority]}</b>: descartada, exige ${esc(r.rule)}`);
    const explain = queryExplainHtml("Poda por K = (P, M, I): la magnitud limita la prioridad posible, asi que "
        + "solo estos tramos de claves pueden tener resultados. Un subarbol cuyas claves quedan fuera de "
        + "todos se descarta completo.", runs);
    showQueryResults(explain + (d.results.length ? d.results.map(eventCardHtml).join("")
        : '<p class="muted">Ningun evento activo tiene una magnitud en ese intervalo.</p>'));
}

async function runQueryDepthDates() {
    const depth = val("q-dd-depth"), from = val("q-dd-from"), to = val("q-dd-to");
    if (depth === "" || !from || !to) {
        log("Indica la profundidad maxima y las fechas desde y hasta", "err");
        return;
    }
    // datetime-local gives "YYYY-MM-DDTHH:MM"; the backend reads it as UTC.
    const res = await eel.query_by_depth_and_dates(depth, from, to)();
    if (!res.ok) { showQueryError(res.message); return; }
    const d = res.data;
    showQueryCost(`Nodos del AVL examinados: ${d.nodes_examined} de ${d.active} activos | resultados=${d.count}`);
    const explain = queryExplainHtml("La profundidad del hipocentro y la fecha no forman parte de K, asi que la "
        + "posicion de un nodo no dice nada de ellas: ninguna rama se puede descartar y se examinan todos "
        + "los nodos, O(n) aun con el arbol balanceado. Resultados en orden de ocurrencia.");
    showQueryResults(explain + (d.results.length ? d.results.map(eventCardHtml).join("")
        : '<p class="muted">Ningun evento activo cumple la profundidad y las fechas.</p>'));
}

async function runQueryAssociations() {
    const id = val("q-assoc-id");
    if (!id) { log("Indica un ID de evento", "err"); return; }
    const res = await eel.query_event_associations(id)();
    if (!res.ok) { showQueryError(res.message); return; }
    const d = res.data;

    // The AVL is not walked here: the event comes from the id index and the
    // candidates from the active and archived events (the AVL does not hold
    // the archived ones), so the AVL count is 0 and the scan is reported apart.
    showQueryCost(`Nodos del AVL examinados: ${d.nodes_examined} | eventos activos y archivados revisados: `
        + `${d.events_scanned} (2 pasadas: candidatos y referencias entrantes) `
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
    showQueryCost(`Nodos del AVL examinados: ${d.nodes_examined} de ${d.active} activos `
        + `| subarboles descartados: ${d.pruned_subtrees} | limite L=${d.limit_L} | eventos costosos=${d.count}`);
    const explain = queryExplainHtml("ALTA es la mayor prioridad, asi que sus claves estan a la derecha de todas "
        + "las demas: el subarbol izquierdo de un nodo de prioridad menor solo tiene claves menores y se descarta. "
        + "Los nodos visitados al buscar cada evento por su clave son su profundidad + 1.");
    showQueryResults(explain + (d.costly_events.length ? d.costly_events.map(costlyCardHtml).join("")
        : '<p class="muted">Ningun evento de prioridad alta supera el limite L.</p>'));
}

async function runQueryCompare() {
    const res = await eel.compare_trees_view()();
    if (!res.ok) { showQueryError(res.message); return; }
    const d = res.data;
    showQueryCost(`Comparacion de los arboles actuales: las mismas ${d.size} claves, `
        + `con las mismas operaciones en el mismo orden (cada clave se busca una vez en cada arbol)`);
    const row = (label, key) => `<tr><td>${label}</td><td>${esc(d.avl[key] ?? "--")}</td><td>${esc(d.bst[key] ?? "--")}</td></tr>`;

    let tableHtml = `<table class="query-table">
        <tr><th></th><th>AVL</th><th>BST</th></tr>
        ${row("Raiz", "root")}
        ${row("Altura", "height")}
        ${row("Profundidad maxima", "max_depth")}
        ${row("Hojas", "leaves")}
        ${row("Comparaciones totales (buscar todas las claves)", "total_comparisons")}
        ${row("Comparaciones promedio", "avg_comparisons")}
        ${row("Peor busqueda (comparaciones)", "max_comparisons")}
    </table>`;

    let avlHtml = `<p class="muted">Árbol vacío</p>`;
    let bstHtml = `<p class="muted">Árbol vacío</p>`;

    if (lastState && lastState.tree && lastState.tree.nodes) {
        const avlData = generateTreeSvgHtml(lastState.tree, "avl");
        avlHtml = `<svg id="compare-avl-svg" width="100%" style="height:350px; background:var(--bg2); border-radius:var(--radius); border:1px solid var(--border);" viewBox="0 0 ${avlData.svgW} ${avlData.svgH}">${avlData.html}</svg>`;
    }

    if (lastState && lastState.bst && lastState.bst.nodes) {
        const bstData = generateTreeSvgHtml(lastState.bst, "bst");
        bstHtml = `<svg id="compare-bst-svg" width="100%" style="height:350px; background:var(--bg2); border-radius:var(--radius); border:1px solid var(--border);" viewBox="0 0 ${bstData.svgW} ${bstData.svgH}">${bstData.html}</svg>`;
    }

    showQueryResults(tableHtml + `
        <div style="display:flex; gap:16px; margin-top:20px; flex-wrap:wrap;">
            <div style="flex:1; min-width:300px;">
                <h4 style="color:var(--text); margin-bottom:8px; text-align:center;">Árbol AVL (Balanceado)</h4>
                ${avlHtml}
            </div>
            <div style="flex:1; min-width:300px;">
                <h4 style="color:var(--text); margin-bottom:8px; text-align:center;">Árbol BST (No Balanceado)</h4>
                ${bstHtml}
            </div>
        </div>
    `);

    setTimeout(() => {
        if ($("compare-avl-svg")) addZoomPan($("compare-avl-svg"));
        if ($("compare-bst-svg")) addZoomPan($("compare-bst-svg"));
    }, 10);
}

