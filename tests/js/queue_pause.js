// Loads web/app.js with a fake DOM and a fake eel to check Section 8:
// a global recovery requested during continuous processing waits for the
// step in progress, runs while no step can start, and leaves the queue paused.
// Usage: node tests/js/queue_pause.js web/app.js   (exit code 0 = passed)
// Run from Python by tests/test_review_fixes.py (skipped when Node is missing).
const fs = require("fs");
const vm = require("vm");
const path = require("path");

const appPath = path.resolve(process.argv[2]);
const calls = [];
const sleep = ms => new Promise(r => setTimeout(r, ms));

const elements = {};
function el(id) {
    if (!elements[id]) {
        const classes = new Set(id === "btn-continuous" ? ["btn", "btn-primary"] : []);
        elements[id] = {
            id, textContent: "", innerHTML: "", value: id === "continuous-delay" ? "100" : "",
            style: {}, setAttribute() {}, getAttribute() { return null; }, addEventListener() {},
            classList: {
                add: c => classes.add(c), remove: c => classes.delete(c), contains: c => classes.has(c),
                toggle: (c, on) => (on ? classes.add(c) : classes.delete(c)),
                replace: (a, b) => { if (classes.has(a)) { classes.delete(a); classes.add(b); } },
            },
        };
    }
    return elements[id];
}

let queued = 5;
const state = () => ({
    parameters: { L_depth: 3, W_hours: 48, R_km: 40, T_archive_hours: 72 }, zones: [],
    tree: { nodes: null, height: -1, leaves: 0, balanced: true, root: null },
    bst: { nodes: null, height: -1, leaves: 0, root: null },
    counts: { active: 0, archived: 0, deleted: 0, queued_reports: queued, undo_depth: 0,
              pending: 0, costly_access: 0 },
    rotations: { ll: 0, rr: 0, lr: 0, rl: 0, simple_left: 0, simple_right: 0 },
    events: [], archived_events: [], stress_mode: false, clock: "2026-01-01T00:00:00",
    queued_reports: Array.from({ length: queued }, (_, i) => ({
        event_id: i + 1, station_id: "E1", revision: 1, magnitude: 1, depth_km: 1,
        epicenter: { x: 1, y: 1 }, occurrence_time: "2026-01-01T00:00:00Z" })),
});

const eel = {
    get_state: () => async () => state(),
    process_report: () => async () => {
        if (queued <= 0) return { result: "EMPTY", message: "Cola vacia" };
        calls.push("process:start");
        await sleep(60);                       // a step takes some time
        queued -= 1;
        calls.push("process:end");
        return { result: "CREATED", event_id: 1 };
    },
    recover_balance: () => async () => {
        calls.push("recover");
        return { result: "RECOVERED", message: "ok",
                 cost: { ll: 1, rr: 0, lr: 0, rl: 0, final_height: 2 } };
    },
};

const context = {
    eel, console, setTimeout, clearTimeout, Promise,
    alert: msg => calls.push("alert:" + msg.split("\n")[0]),
    confirm: () => true,
    document: { getElementById: el, querySelectorAll: () => [], activeElement: null },
};
context.window = context;
context.window.addEventListener = () => {};
vm.createContext(context);
vm.runInContext(fs.readFileSync(appPath, "utf8"), context);

(async () => {
    vm.runInContext("refresh()", context);
    await sleep(10);
    const loop = vm.runInContext("processContinuous()", context);  // not awaited
    await sleep(180);                    // a few steps run; one is in progress now
    const stepsBefore = calls.filter(c => c === "process:end").length;
    calls.push("--- user clicks Recuperar balance ---");
    await vm.runInContext("recoverBalance()", context);
    await loop;
    await sleep(300);                    // if the loop were still alive it would keep going

    const afterClick = calls.slice(calls.indexOf("--- user clicks Recuperar balance ---") + 1);
    const recoverAt = afterClick.indexOf("recover");
    const report = {
        steps_before_click: stepsBefore,
        calls_after_click: afterClick,
        step_in_progress_finished_before_recovery:
            afterClick.indexOf("process:end") !== -1 && afterClick.indexOf("process:end") < recoverAt,
        no_step_started_after_recovery: !afterClick.slice(recoverAt).includes("process:start"),
        loop_stopped: vm.runInContext("continuousRunning", context) === false,
        button_text: el("btn-continuous").textContent,
        history_note: vm.runInContext("reportHistory.find(e => e.note) ? 'yes' : 'no'", context),
        step_during_recovery: null,
    };
    // A step requested while a recovery is running is refused.
    vm.runInContext("recoveryRunning = true", context);
    report.step_during_recovery = (await vm.runInContext("processOneReport()", context)).result;
    console.log(JSON.stringify(report, null, 2));

    const ok = report.steps_before_click >= 1
        && report.step_in_progress_finished_before_recovery
        && report.no_step_started_after_recovery
        && report.loop_stopped
        && report.button_text === "Procesar continuo"
        && report.history_note === "yes"
        && report.step_during_recovery === "PAUSED";
    process.exit(ok ? 0 : 1);
})();
