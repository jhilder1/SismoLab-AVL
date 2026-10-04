// A fake browser to run the web/js scripts under Node: getElementById returns plain
// objects that remember textContent, innerHTML, value, style and classes.
// `eel` is a fake of the Python endpoints, built by each test script.
const fs = require("fs");
const vm = require("vm");

function loadApp(appPath, eel) {
    const elements = {};
    function el(id) {
        if (!elements[id]) {
            const classes = new Set();
            elements[id] = {
                id, textContent: "", innerHTML: "", value: "", style: {},
                setAttribute() {}, getAttribute() { return null; }, addEventListener() {},
                classList: {
                    add: c => classes.add(c), remove: c => classes.delete(c), contains: c => classes.has(c),
                    toggle: (c, on) => (on ? classes.add(c) : classes.delete(c)),
                    replace: (a, b) => { if (classes.has(a)) { classes.delete(a); classes.add(b); } },
                },
            };
        }
        return elements[id];
    }
    const alerts = [];
    const context = {
        eel, console, setTimeout, clearTimeout, Promise,
        alert: message => alerts.push(message),
        confirm: () => true,
        document: { getElementById: el, querySelectorAll: () => [], activeElement: null },
    };
    context.window = context;
    context.window.addEventListener = () => {};
    vm.createContext(context);
    let src = "";
    try {
        if (fs.statSync(appPath).isDirectory()) {
            const files = ["globals.js", "ui.js", "tabs.js", "treeRenderer.js", "mapRenderer.js", "actions.js", "queue.js", "queries.js", "indicators.js", "parameters.js", "file.js", "main.js"];
            for (const file of files) src += fs.readFileSync(appPath + "/" + file, "utf8") + "\n";
        } else {
            src = fs.readFileSync(appPath, "utf8");
        }
    } catch (e) {
        src = fs.readFileSync(appPath, "utf8");
    }
    vm.runInContext(src, context);
    return { el, alerts, run: code => vm.runInContext(code, context) };
}

// Collects named checks; report() prints them and exits 0 only if all passed.
function checker() {
    const checks = [];
    return {
        check: (name, condition) => checks.push([name, Boolean(condition)]),
        report() {
            for (const [name, passed] of checks) console.log(passed ? "ok  " : "FAIL", name);
            process.exit(checks.every(c => c[1]) ? 0 : 1);
        },
    };
}

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

module.exports = { loadApp, checker, sleep };
