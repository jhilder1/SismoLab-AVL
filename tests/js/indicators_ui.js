// Loads web/app.js with a fake DOM and a fake eel that replays real backend
// answers (written by tests/test_queries_indicators.py) and checks what the
// Indicadores tab, the Section 11 queries and the burst loader put on screen.
// Usage: node tests/js/indicators_ui.js web/app.js <data.json>   (exit code 0 = passed)
const fs = require("fs");
const vm = require("vm");

const data = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const elements = {};
function el(id) {
    if (!elements[id]) {
        elements[id] = {
            id, textContent: "", innerHTML: "", value: "", style: {},
            setAttribute() {}, getAttribute() { return null; }, addEventListener() {},
            classList: { add() {}, remove() {}, contains: () => false, toggle() {}, replace() {} },
        };
    }
    return elements[id];
}
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
    run_audit: () => ok(data.audit_stress),
};
const alerts = [];
const context = { eel, console, setTimeout, clearTimeout, Promise, alert: m => alerts.push(m), confirm: () => true,
    document: { getElementById: el, querySelectorAll: () => [], activeElement: null } };
context.window = context;
context.window.addEventListener = () => {};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), context);

const checks = [];
const check = (name, cond) => checks.push([name, Boolean(cond)]);
const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
    await vm.runInContext("refresh()", context);
    vm.runInContext("showTree('indicators')", context);
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
    vm.runInContext("renderTraversals()", context);
    const k = s.traversals.preorder[0];
    check("key format", el("trav-preorder").innerHTML.startsWith(`(${k[0]}, ${k[1]}, ${k[2]})`));
    const log = el("action-log").innerHTML;
    check("log has undo", log.includes("Deshacer") && log.includes("Archivo masivo"));
    check("log has change chips", log.includes('class="chg up"') && log.includes('class="chg down"'));
    check("log entries", (log.match(/action-entry/g) || []).length === data.log.length);

    el("q-mag-min").value = "6.0"; el("q-mag-max").value = "9.9";
    await vm.runInContext("runQueryMagnitude()", context);
    check("magnitude cost", el("query-cost").textContent.includes(`Nodos del AVL examinados: ${data.magnitude.data.nodes_examined} de`));
    check("magnitude explain", el("query-results").innerHTML.includes("descartada, exige M &lt; 4.5"));
    el("q-mag-min").value = "6"; el("q-mag-max").value = "5";
    await vm.runInContext("runQueryMagnitude()", context);
    check("magnitude error", el("query-results").innerHTML.includes("query-error"));

    el("q-dd-depth").value = "20"; el("q-dd-from").value = ""; el("q-dd-to").value = "";
    await vm.runInContext("runQueryDepthDates()", context);
    check("depthdates requires dates", el("log-msg").textContent.includes("fechas"));
    el("q-dd-from").value = "2025-01-01T00:00"; el("q-dd-to").value = "2027-01-01T00:00";
    await vm.runInContext("runQueryDepthDates()", context);
    check("depthdates all nodes", el("query-cost").textContent.includes(`${data.depthdates.data.nodes_examined} de ${s.counts.active}`));

    await vm.runInContext("runQueryCostly()", context);
    check("costly cost", el("query-cost").textContent.includes("subarboles descartados"));
    el("q-assoc-id").value = "1";
    await vm.runInContext("runQueryAssociations()", context);
    check("assoc cost", el("query-cost").textContent.startsWith("Nodos del AVL examinados: 0"));

    burstAnswer = data.burst_ok;
    await vm.runInContext("loadBurst()", context);
    const info = data.burst_ok.info;
    check("burst queued", el("burst-result").innerHTML.includes(
        `${info.count} reporte(s) de ${info.stations.length} estacion(es) encolados`)
        && el("burst-result").innerHTML.includes(`Posiciones ${info.first_position} a ${info.queue_size}`));
    burstAnswer = data.burst_bad;
    await vm.runInContext("loadBurst()", context);
    check("burst rejected", el("burst-result").innerHTML.includes("rafaga rechazada")
        && el("burst-result").innerHTML.includes("unknown station"));
    check("burst action label", vm.runInContext("ACTION_LABELS.LOAD_BURST", context) === "Carga de rafaga");

    await vm.runInContext("runAudit()", context);
    const worst = Math.max(...data.audit_stress.unbalanced_nodes.map(n => Math.abs(n.balance_factor)));
    check("stress audit reports the expected imbalance apart", alerts[alerts.length - 1].includes(
        `Desbalance esperado del modo estrés: ${data.audit_stress.unbalanced_nodes.length} nodo(s)`)
        && alerts[alerts.length - 1].includes(`|FB| = ${worst}`)
        && !alerts[alerts.length - 1].includes("cumple la propiedad AVL"));

    for (const [name, passed] of checks) console.log(passed ? "ok  " : "FAIL", name);
    process.exit(checks.every(c => c[1]) ? 0 : 1);
})().catch(e => { console.error(e); process.exit(2); });
