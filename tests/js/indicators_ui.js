// Loads the web/js scripts with a fake DOM and a fake eel that replays real backend
// answers (written by tests/test_queries_indicators.py) and checks what the
// Indicadores tab, the Section 11 queries and the burst loader put on screen.
// Usage: node tests/js/indicators_ui.js web/js <data.json>   (exit code 0 = passed)
const fs = require("fs");
const path = require("path");
const { loadApp, checker, sleep } = require(path.join(__dirname, "fake_env.js"));

const data = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const ok = v => async () => v;
let burstAnswer = null;
const eel = {
    get_state: () => ok(data.state),
    get_action_log: () => ok(data.log),
    query_by_magnitude: (a, b) => ok(a === "6" && b === "5" ? data.magnitude_bad : data.magnitude),
    query_by_depth_and_dates: () => ok(data.depthdates),
    query_costly_high_priority: () => ok(data.costly),
    query_event_associations: () => ok(data.assoc),
    load_burst: () => async () => burstAnswer,
};
const { el, run } = loadApp(process.argv[2], eel);
const { check, report } = checker();

(async () => {
    await run("refresh()");
    run("showTree('indicators')");
    await sleep(20);
    const s = data.state;
    check("stats giro izq", el("st-sl").textContent === s.rotations.simple_left);
    check("panel shown", el("indicators-panel").style.display === "flex");
    check("structure table", el("ind-structure").innerHTML.includes(`<td>Eventos activos</td><td>${s.counts.active}</td>`));
    check("costly label has L", el("ind-priority").innerHTML.includes(`L=${s.parameters.L_depth}`));
    check("operations table", el("ind-operations").innerHTML.includes("Archivos masivos"));
    check("rotations table", el("ind-rotations").innerHTML.includes("Giros simples a la derecha"));
    const inorderIds = s.traversals.inorder.map(k => String(k[2])).join(" → ");
    check("inorder ids", el("trav-inorder").innerHTML === inorderIds.replace(/&/g, "&amp;"));
    check("inorder count", el("trav-n-inorder").textContent === `(${s.counts.active} nodos)`);
    const levels = el("trav-level_order").innerHTML;
    check("level 0 is root", levels.startsWith(`<div><span class="trav-level">Nivel 0:</span> ${s.traversals.level_order[0][2]}</div>`));
    check("levels = height + 1", (levels.match(/Nivel /g) || []).length === s.tree.height + 1);
    el("trav-format").value = "key";
    run("renderTraversals()");
    const k = s.traversals.preorder[0];
    check("key format", el("trav-preorder").innerHTML.startsWith(`(${k[0]}, ${k[1]}, ${k[2]})`));
    const log = el("action-log").innerHTML;
    check("log has undo", log.includes("Deshacer") && log.includes("Archivo masivo"));
    check("log has change chips", log.includes('class="chg up"') && log.includes('class="chg down"'));
    check("log entries", (log.match(/action-entry/g) || []).length === data.log.length);

    el("q-mag-min").value = "6.0"; el("q-mag-max").value = "9.9";
    await run("runQueryMagnitude()");
    check("magnitude cost", el("query-cost").textContent.includes(`Nodos del AVL examinados: ${data.magnitude.data.nodes_examined} de`));
    check("magnitude explain", el("query-results").innerHTML.includes("descartada, exige M &lt; 4.5"));
    el("q-mag-min").value = "6"; el("q-mag-max").value = "5";
    await run("runQueryMagnitude()");
    check("magnitude error", el("query-results").innerHTML.includes("query-error"));

    el("q-dd-depth").value = "20"; el("q-dd-from").value = ""; el("q-dd-to").value = "";
    await run("runQueryDepthDates()");
    check("depthdates requires dates", el("log-msg").textContent.includes("fechas"));
    el("q-dd-from").value = "2025-01-01T00:00"; el("q-dd-to").value = "2027-01-01T00:00";
    await run("runQueryDepthDates()");
    check("depthdates all nodes", el("query-cost").textContent.includes(`${data.depthdates.data.nodes_examined} de ${s.counts.active}`));

    await run("runQueryCostly()");
    check("costly cost", el("query-cost").textContent.includes("subarboles descartados"));
    el("q-assoc-id").value = "1";
    await run("runQueryAssociations()");
    check("assoc cost", el("query-cost").textContent.startsWith("Nodos del AVL examinados: 0"));

    burstAnswer = data.burst_ok;
    await run("loadBurst()");
    const info = data.burst_ok.info;
    check("burst queued", el("burst-result").innerHTML.includes(
        `${info.count} reporte(s) de ${info.stations.length} estacion(es) encolados`)
        && el("burst-result").innerHTML.includes(`Posiciones ${info.first_position} a ${info.queue_size}`));
    burstAnswer = data.burst_bad;
    await run("loadBurst()");
    check("burst rejected", el("burst-result").innerHTML.includes("rafaga rechazada")
        && el("burst-result").innerHTML.includes("unknown station"));
    check("burst action label", run("ACTION_LABELS.LOAD_BURST") === "Carga de rafaga");

    report();
})().catch(e => { console.error(e); process.exit(2); });
