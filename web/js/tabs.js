// =====================================================
// AVL / BST tabs
// =====================================================

function showTree(view) {
    treeView = view;
    $("tab-avl").classList.toggle("active", view === "avl");
    $("tab-bst").classList.toggle("active", view === "bst");
    $("tab-map").classList.toggle("active", view === "map");
    $("tab-queries").classList.toggle("active", view === "queries");
    $("tab-queue").classList.toggle("active", view === "queue");
    $("tab-history").classList.toggle("active", view === "history");
    $("tab-indicators").classList.toggle("active", view === "indicators");
    $("tab-audit").classList.toggle("active", view === "audit");
    drawCurrentTree();
}

function drawCurrentTree() {
    if (!lastState) return;
    const isMap = treeView === "map";
    const isQueries = treeView === "queries";
    const isQueue = treeView === "queue";
    const isHistory = treeView === "history";
    const isIndicators = treeView === "indicators";
    const isAudit = treeView === "audit";
    const isTree = !isMap && !isQueries && !isQueue && !isHistory && !isIndicators && !isAudit;
    $("tree-svg").style.display = isTree ? "block" : "none";
    $("map-svg").style.display = isMap ? "block" : "none";
    $("map-legend").style.display = isMap ? "flex" : "none";
    $("queries-panel").style.display = isQueries ? "flex" : "none";
    $("queue-panel").style.display = isQueue ? "flex" : "none";
    $("history-panel").style.display = isHistory ? "flex" : "none";
    $("indicators-panel").style.display = isIndicators ? "flex" : "none";
    $("audit-panel").style.display = isAudit ? "flex" : "none";
    $("tree-empty").style.display = "none";

    if (isAudit) {
        $("tree-root").textContent = "Verificar estructura (Seccion 14)";
        refreshAudit();
        return;
    }

    if (isIndicators) {
        // Redrawn on every refresh so the values follow each action live.
        $("tree-root").textContent = "Indicadores, recorridos y registro de acciones (Seccion 14)";
        renderIndicators(lastState);
        renderTraversals();
        refreshActionLog();
        return;
    }

    if (isQueue) {
        // The pending list and the history are refreshed by their own
        // functions (renderQueue on every refresh, renderHistory on every
        // processed step); this tab only needs its own header text.
        const n = (lastState.queued_reports || []).length;
        $("tree-root").textContent = `Cola FIFO de reportes | ${n} pendiente(s)`;
        return;
    }
    if (isHistory) {
        $("tree-root").textContent = `Histórico | ${(lastState.archived_events || []).length} archivados`;
        return;
    }
    if (isQueries) {
        // The queries panel keeps whatever result is already on screen: it
        // does not redraw on every refresh, same as the search result box.
        $("tree-root").textContent = "Consultas del catalogo activo (Seccion 11)";
        return;
    }
    if (isMap) {
        drawMap();
        const n = (lastState.events || []).length;
        $("tree-root").textContent = `Plano 0-1000 km | ${n} eventos activos`;
        return;
    }
    const data = treeView === "bst" ? lastState.bst : lastState.tree;
    const label = treeView === "bst" ? "BST" : "AVL";
    updateTree(data);
    $("tree-root").textContent = `${label} | Raiz: ${data.root || "--"} | Altura: ${data.height} | Hojas: ${data.leaves}`;
}

