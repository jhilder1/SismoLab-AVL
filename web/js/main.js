// =====================================================
// Init: load the stations and the initial state
// =====================================================

async function init() {
    // Fill the station selects
    const stations = await eel.get_stations()();
    for (const sel of [document.getElementById("ev-station"), document.getElementById("rp-station")]) {
        sel.innerHTML = stations.map(s => `<option value="${s.station_id}">${s.station_id}</option>`).join("");
    }
    // Default date
    const now = "2026-01-01T00:00";
    $("ev-time").value = now;
    $("rp-time").value = now;

    renderHistory();
    refresh();
    refreshVersions();
}

// Start when the page has loaded
window.addEventListener("load", init);

function addZoomPan(svg) {
    if (!svg || svg._zoomPanAdded) return;
    svg._zoomPanAdded = true;
    svg.style.cursor = "grab";

    let isPanning = false;
    let startPoint = { x: 0, y: 0 };
    let viewBox = { x: 0, y: 0, w: 0, h: 0 };

    function parseViewBox() {
        const vb = svg.getAttribute("viewBox");
        if (vb) {
            const p = vb.split(" ").map(Number);
            return { x: p[0], y: p[1], w: p[2], h: p[3] };
        }
        return { x: 0, y: 0, w: svg.clientWidth || 1000, h: svg.clientHeight || 1000 };
    }

    svg.addEventListener("pointerdown", e => {
        isPanning = true;
        svg.style.cursor = "grabbing";
        viewBox = parseViewBox();
        startPoint = { x: e.clientX, y: e.clientY };
        svg.setPointerCapture(e.pointerId);
    });

    svg.addEventListener("pointermove", e => {
        if (!isPanning) return;
        e.preventDefault();
        const rect = svg.getBoundingClientRect();
        const scaleX = viewBox.w / rect.width;
        const scaleY = viewBox.h / rect.height;
        
        const dx = (e.clientX - startPoint.x) * scaleX;
        const dy = (e.clientY - startPoint.y) * scaleY;
        
        svg.setAttribute("viewBox", `${viewBox.x - dx} ${viewBox.y - dy} ${viewBox.w} ${viewBox.h}`);
    });

    svg.addEventListener("pointerup", e => {
        isPanning = false;
        svg.style.cursor = "grab";
        svg.releasePointerCapture(e.pointerId);
    });

    svg.addEventListener("wheel", e => {
        e.preventDefault();
        const vb = parseViewBox();
        const rect = svg.getBoundingClientRect();
        
        const mx = e.clientX - rect.left;
        const my = e.clientY - rect.top;
        
        const svgX = vb.x + (mx / rect.width) * vb.w;
        const svgY = vb.y + (my / rect.height) * vb.h;

        const zoom = e.deltaY > 0 ? 1.2 : 0.83333; // 0.8333 is approx 1/1.2
        const newW = vb.w * zoom;
        const newH = vb.h * zoom;
        
        const newX = svgX - (mx / rect.width) * newW;
        const newY = svgY - (my / rect.height) * newH;
        
        svg.setAttribute("viewBox", `${newX} ${newY} ${newW} ${newH}`);
    });
}
