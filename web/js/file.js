// =====================================================
// File: save and load (Section 12)
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
// Named versions (Section 13)
// =====================================================

async function refreshVersions() {
    const list = await eel.list_versions()();
    const box = $("versions-list");
    if (!list.length) {
        box.innerHTML = '<p class="muted">Sin versiones guardadas.</p>';
        return;
    }
    // Most recent first.
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

