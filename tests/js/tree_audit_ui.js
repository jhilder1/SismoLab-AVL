// Runs the web/js scripts with real backend answers (written by
// tests/test_audit_and_correction.py) and checks the node tooltips of the
// tree (Section 15), the Auditoria tab (Section 14), the full correction form
// (Section 6) and the clock advanced by N hours (Section 3).
// Usage: node tests/js/tree_audit_ui.js web/js <data.json>   (exit code 0 = passed)
const fs = require("fs");
const path = require("path");
const { loadApp, checker, sleep } = require(path.join(__dirname, "fake_env.js"));

const data = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
let auditAnswer = data.audit_broken;
const calls = { correct: null, clock: null };
const ok = value => async () => value;
const eel = {
    get_state: () => ok(data.state),
    run_audit: () => async () => auditAnswer,
    correct_event: (...args) => { calls.correct = args; return ok({ ok: true, message: "corregido" }); },
    advance_clock: hours => {
        calls.clock = hours;
        return ok(Number(hours) > 0 ? { ok: true, clock: "2026-09-12T02:30:00" }
                                    : { ok: false, message: "Las horas a avanzar deben ser positivas" });
    },
};
const { el, run } = loadApp(process.argv[2], eel);
const { check, report } = checker();

(async () => {
    await run("refresh()");

    // Section 15: every node carries a tooltip with its key and links.
    const avl = run(`generateTreeSvgHtml(lastState.tree, "avl").html`);
    const titles = [...avl.matchAll(/<title>([^<]*)<\/title>/g)].map(m => m[1]);
    check("one tooltip per node", titles.length === data.state.counts.active);
    const root = data.state.tree.nodes;
    const rootTip = titles.find(t => t.startsWith(`SIS-${String(root.event_id).padStart(6, "0")}`));
    check("root tooltip: key, no parent, both links", rootTip
        && rootTip.includes(`K = ${root.key}`) && rootTip.includes("Padre: ninguno (raiz)")
        && rootTip.includes(`Izquierdo: SIS-${String(root.left.event_id).padStart(6, "0")}`)
        && rootTip.includes(`Derecho: SIS-${String(root.right.event_id).padStart(6, "0")}`)
        && rootTip.includes(`Profundidad 0 | Altura ${root.height} | FB ${root.bf}`));
    const child = root.left;
    const childTip = titles.find(t => t.startsWith(`SIS-${String(child.event_id).padStart(6, "0")}`));
    check("child tooltip names its parent and depth", childTip
        && childTip.includes(`Padre: SIS-${String(root.event_id).padStart(6, "0")}`) && childTip.includes("Profundidad 1"));
    check("costly node tooltip explains the mark", titles.some(t => t.includes("Acceso costoso: prioridad alta")));
    const bst = run(`generateTreeSvgHtml(lastState.bst, "bst").html`);
    check("BST tooltips have no balance factor", bst.includes("<title>") && !/<title>[^<]*FB /.test(bst));

    // Section 14: one report per inconsistent event.
    await run("runAudit()");
    await sleep(10);
    check("Verificar estructura opens the Auditoria tab", run("treeView") === "audit"
        && el("audit-panel").style.display === "flex");
    const broken = el("audit-report").innerHTML;
    check("one entry per inconsistent event", (broken.match(/class="audit-entry"/g) || []).length
        === data.audit_broken.report.length && data.audit_broken.report.length >= 2);
    check("every problem is listed", data.audit_broken.errors.every(
        e => broken.includes(e.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
                              .replace(/"/g, "&quot;").replace(/'/g, "&#39;"))));
    check("summary counts events and problems", el("audit-summary").textContent.includes(
        `eventos inconsistentes: ${data.audit_broken.report.length} | problemas: ${data.audit_broken.errors.length}`));
    check("log bar summarizes the result", el("log-msg").textContent.includes("evento(s) inconsistente(s)"));

    auditAnswer = data.audit_stress;
    await run("runAudit()");
    const stress = el("audit-report").innerHTML;
    const worst = Math.max(...data.audit_stress.unbalanced_nodes.map(n => Math.abs(n.balance_factor)));
    check("stress: expected imbalance apart, no error entries", stress.includes("Desbalance esperado del modo estres")
        && stress.includes(`el mayor |FB| = ${worst}`) && !stress.includes('class="audit-entry"')
        && stress.includes('audit-verdict ok'));

    // Section 6: every field of the form reaches the backend; empty ones as null.
    el("cor-id").value = "150"; el("cor-mag").value = ""; el("cor-depth").value = "12.5";
    el("cor-x").value = "320.5"; el("cor-y").value = "640"; el("cor-time").value = "2026-09-08T09:30:15";
    await run("correctEvent()");
    check("correction sends id, M, H, x, y and time", JSON.stringify(calls.correct)
        === JSON.stringify(["150", null, "12.5", "320.5", "640", "2026-09-08T09:30:15"]));

    // Section 3: the clock advances by the hours typed.
    el("clock-hours").value = "2.5";
    await run("advanceClock()");
    check("clock advances by the hours typed", calls.clock === "2.5" && el("log-msg").textContent.includes("2.5 h"));
    el("clock-hours").value = "-3";
    await run("advanceClock()");
    check("invalid hours show the backend message", el("log-msg").textContent.includes("positivas"));

    report();
})().catch(e => { console.error(e); process.exit(2); });
