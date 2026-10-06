// =====================================================
// Draw AVL Tree (SVG)
// =====================================================

const NODE_R = 22;
const H_GAP = 16;
const V_GAP = 60;

function generateTreeSvgHtml(treeData, treeViewType) {
    if (!treeData.nodes) return { empty: true };

    const positions = [];
    const edges = [];
    let minX = Infinity, maxX = -Infinity, maxY = 0;

    let column = 0;
    function layout(node, depth, parent) {
        if (!node) return null;
        const left = layout(node.left, depth + 1, node);
        const x = column * (NODE_R * 2 + H_GAP);
        column++;
        const y = depth * V_GAP + NODE_R + 10;
        const right = layout(node.right, depth + 1, node);

        positions.push({ x, y, node, depth, parent });
        if (x < minX) minX = x;
        if (x > maxX) maxX = x;
        if (y > maxY) maxY = y;
        for (const child of [left, right]) {
            if (child) edges.push({ x1: x, y1: y, x2: child.x, y2: child.y });
        }
        return { x, y };
    }

    const rootPos = layout(treeData.nodes, 0, null);

    const svgW = maxX - minX + NODE_R * 4;
    const svgH = maxY + NODE_R * 2 + 10;
    const offsetX = -minX + NODE_R * 2;

    let html = "";
    for (const e of edges) {
        html += `<line class="tree-edge" x1="${e.x1 + offsetX}" y1="${e.y1}" x2="${e.x2 + offsetX}" y2="${e.y2}"/>`;
    }

    for (const p of positions) {
        const n = p.node;
        const cx = p.x + offsetX;
        const cy = p.y;

        let fill = "#3a4a6b";
        if (n.priority === 3) fill = "#c62828";
        else if (n.priority === 2) fill = "#ef6c00";
        else if (n.priority === 1) fill = "#2e7d32";

        const hasBf = typeof n.bf === "number";
        let stroke = "none";
        let strokeW = 0;
        if (hasBf && Math.abs(n.bf) > 1) {
            stroke = "#ff1744";
            strokeW = 3;
        }

        html += `<g class="tree-node"><title>${esc(nodeTooltip(n, p.depth, p.parent, treeViewType))}</title>`;
        html += `<circle class="node-circle" cx="${cx}" cy="${cy}" r="${NODE_R}" fill="${fill}" stroke="${stroke}" stroke-width="${strokeW}"/>`;

        if (treeViewType === "avl" && costlyIds.has(n.event_id)) {
            html += `<circle class="node-costly" cx="${cx}" cy="${cy}" r="${NODE_R + 5}"/>`;
            html += `<text class="node-costly-mark" x="${cx + NODE_R + 3}" y="${cy - NODE_R + 4}">$</text>`;
        }
        html += `<text class="node-label" x="${cx}" y="${cy + 1}">ID:${n.event_id}</text>`;
        html += `<text class="node-sublabel" x="${cx}" y="${cy + 13}">M${n.magnitude}</text>`;

        if (hasBf) {
            const bfColor = Math.abs(n.bf) > 1 ? "#ff1744" : "var(--yellow)";
            html += `<text class="node-bf" x="${cx}" y="${cy - NODE_R - 4}" fill="${bfColor}">${n.bf}</text>`;
        }
        html += `</g>`;
    }
    return { empty: false, svgW, svgH, rootX: rootPos.x + offsetX, html };
}

// Section 15: hovering a node shows its whole key and its links, besides the
// id and magnitude drawn on it.
function nodeTooltip(n, depth, parent, treeType) {
    const link = child => child ? formatEventId(child.event_id) : "vacio";
    const lines = [
        `${formatEventId(n.event_id)}   K = ${n.key}`,
        `Padre: ${parent ? formatEventId(parent.event_id) : "ninguno (raiz)"}`
            + ` | Izquierdo: ${link(n.left)} | Derecho: ${link(n.right)}`,
        `Profundidad ${depth} | Altura ${n.height}` + (typeof n.bf === "number" ? ` | FB ${n.bf}` : ""),
    ];
    if (treeType === "avl" && costlyIds.has(n.event_id)) {
        lines.push(`Acceso costoso: prioridad alta y profundidad ${depth} > L = ${limitL}`);
    }
    return lines.join("\n");
}

function updateTree(treeData) {
    const svg = $("tree-svg");
    const emptyMsg = $("tree-empty");

    const res = generateTreeSvgHtml(treeData, treeView);

    if (res.empty) {
        svg.innerHTML = "";
        svg.style.display = "none";
        emptyMsg.style.display = "block";
        return;
    }

    emptyMsg.style.display = "none";
    svg.style.display = "block";

    // The drawing area is the whole visible panel, so zooming and panning
    // never get clipped by a box the size of a small tree. The starting view
    // shows the whole tree when it fits (never enlarged, centred, top
    // aligned). A tree too big to fit at MIN_SCALE starts at that scale,
    // at the top and centred on its root; dragging moves along it.
    const box = $("tree-container");
    const viewW = Math.max(200, (box.clientWidth || 0) - 2 * CONTAINER_PAD - 2);
    const viewH = Math.max(200, (box.clientHeight || 0) - 2 * CONTAINER_PAD - 2);
    const fit = Math.min(viewW / res.svgW, viewH / res.svgH);
    const scale = Math.min(1, Math.max(fit, MIN_SCALE));
    const vbW = viewW / scale;
    const vbH = viewH / scale;
    const x = vbW >= res.svgW
        ? (res.svgW - vbW) / 2
        : Math.min(Math.max(res.rootX - vbW / 2, 0), res.svgW - vbW);
    const home = `${x} 0 ${vbW} ${vbH}`;

    svg.setAttribute("width", viewW);
    svg.setAttribute("height", viewH);
    svg.setAttribute("viewBox", home);
    svg._homeViewBox = home;    // double click goes back here (addZoomPan)
    svg.innerHTML = res.html;
    addZoomPan(svg);
}

const CONTAINER_PAD = 10;   // .tree-container padding in style.css
const MIN_SCALE = 0.35;     // smallest starting zoom: nodes still tell apart

// Keep the drawing area matched to the panel when the window is resized.
let resizeFrame = null;
window.addEventListener("resize", () => {
    if (resizeFrame) return;
    resizeFrame = requestAnimationFrame(() => {
        resizeFrame = null;
        if (treeView === "avl" || treeView === "bst") drawCurrentTree();
    });
});

