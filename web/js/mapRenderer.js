// =====================================================
// Actions: each one calls eel and then refreshes
// =====================================================
// =====================================================
// Geographic map (section 15): 0-1000 km plane
// =====================================================

const MAP_SIZE = 1000;   // km on each axis
const MAP_PAD = 46;      // room for axis labels

const mapX = km => MAP_PAD + km;
const mapY = km => MAP_PAD + (MAP_SIZE - km);   // y grows upward on screen

// Magnitude -2.0..10.0 mapped to a 4..15 px radius.
const magRadius = m => 4 + ((Math.max(-2, Math.min(10, m)) + 2) / 12) * 11;

const PRIORITY_FILL = { 1: "#2e7d32", 2: "#ef6c00", 3: "#c62828" };

function drawMap() {
    const svg = $("map-svg");
    const side = MAP_SIZE + MAP_PAD * 2;
    svg.setAttribute("viewBox", `0 0 ${side} ${side}`);
    svg.setAttribute("width", side);
    svg.setAttribute("height", side);

    let html = "";

    // Plane background
    html += `<rect class="map-plane" x="${MAP_PAD}" y="${MAP_PAD}" width="${MAP_SIZE}" height="${MAP_SIZE}"/>`;
    // Grid and axis labels every 100 km
    for (let k = 0; k <= MAP_SIZE; k += 100) {
        html += `<line class="map-grid" x1="${mapX(k)}" y1="${mapY(0)}" x2="${mapX(k)}" y2="${mapY(MAP_SIZE)}"/>`;
        html += `<line class="map-grid" x1="${mapX(0)}" y1="${mapY(k)}" x2="${mapX(MAP_SIZE)}" y2="${mapY(k)}"/>`;
        html += `<text class="map-axis" x="${mapX(k)}" y="${mapY(0) + 22}">${k}</text>`;
        html += `<text class="map-axis map-axis-y" x="${MAP_PAD - 10}" y="${mapY(k) + 4}">${k}</text>`;
    }

    // Zones: populated ones get a distinct fill, since priority depends on them
    for (const z of (zonesCache || [])) {
        const populated = z.populated ?? z.is_populated;
        const x = mapX(z.x_min);
        const y = mapY(z.y_max);
        const w = z.x_max - z.x_min;
        const h = z.y_max - z.y_min;
        html += `<rect class="map-zone ${populated ? "pop" : "npop"}" x="${x}" y="${y}" width="${w}" height="${h}">
            <title>${esc(z.name || "")} - ${populated ? "poblada" : "no poblada"}</title></rect>`;
        html += `<text class="map-zone-lbl" x="${x + 6}" y="${y + 18}">${esc(z.name || "")}</text>`;
    }

    // Events: colour = priority, radius = magnitude, hollow = already reviewed
    for (const e of (lastState.events || [])) {
        const cx = mapX(e.epicenter.x);
        const cy = mapY(e.epicenter.y);
        const r = magRadius(e.magnitude);
        const reviewed = e.attention_state === "reviewed";
        const stroke = PRIORITY_FILL[e.priority] || "#3a4a6b";
        const fill = reviewed ? "none" : stroke;
        // Costly access (section 9): dashed ring, separate from the priority colour
        if (costlyIds.has(e.event_id)) {
            html += `<circle class="map-costly" cx="${cx}" cy="${cy}" r="${r + 6}"/>`;
        }
        html += `<circle class="map-event" cx="${cx}" cy="${cy}" r="${r}" fill="${fill}" stroke="${stroke}" stroke-width="2.5">
            <title>SIS-${String(e.event_id).padStart(6, "0")} | M=${e.magnitude} | P=${e.priority} | H=${e.depth_km} km | Epi=(${e.epicenter.x}, ${e.epicenter.y}) | ${e.attention_state}</title></circle>`;
        html += `<text class="map-event-lbl" x="${cx}" y="${cy - r - 5}">${e.event_id}</text>`;
    }

    svg.innerHTML = html;
}
