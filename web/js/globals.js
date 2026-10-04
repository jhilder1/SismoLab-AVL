


function $(id) { return document.getElementById(id); }

function log(msg, type) {
    const el = $("log-msg");
    el.textContent = msg;
    el.className = "log-msg " + (type || "");
}

function val(id) { return $(id).value; }

// Escapes text before it goes into innerHTML (messages that come from files).
function esc(text) {
    return String(text).replace(/[&<>"']/g, c => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[c]);
}

// Last state received and the view being shown (a tree, the map or a panel).
let lastState = null;
let treeView = "avl";
let zonesCache = null;
let limitL = 3;                 // access-depth budget L (section 9)
let costlyIds = new Set();      // event ids currently marked as costly access

// =====================================================
// Refresh: fetches the state and updates the whole screen
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
        renderArchived(state.archived_events);
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

