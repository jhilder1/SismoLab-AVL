// =====================================================
// Update Stats Bar
// =====================================================

function updateStats(state) {
    $("st-active").textContent = state.counts.active;
    $("st-archived").textContent = state.counts.archived;
    $("st-deleted").textContent = state.counts.deleted;
    $("st-queue").textContent = state.counts.queued_reports;
    $("st-undo").textContent = state.counts.undo_depth;
    $("st-pending").textContent = state.counts.pending;
    $("st-costly").textContent = state.counts.costly_access;
    $("st-costly").style.color = state.counts.costly_access > 0 ? "var(--yellow)" : "";
    $("st-limit").textContent = state.parameters.L_depth;
    $("st-height").textContent = state.tree.height;
    $("st-leaves").textContent = state.tree.leaves;
    $("st-balanced").textContent = state.tree.balanced ? "Si" : "NO";
    $("st-balanced").style.color = state.tree.balanced ? "var(--green)" : "var(--red)";
    $("st-ll").textContent = state.rotations.ll;
    $("st-rr").textContent = state.rotations.rr;
    $("st-lr").textContent = state.rotations.lr;
    $("st-rl").textContent = state.rotations.rl;
    $("st-sl").textContent = state.rotations.simple_left;
    $("st-sr").textContent = state.rotations.simple_right;
}

function updateStress(isStress) {
    const badge = $("stress-badge");
    if (isStress) {
        badge.textContent = "ESTRES";
        badge.className = "badge badge-on";
    } else {
        badge.textContent = "Normal";
        badge.className = "badge badge-off";
    }
}

// =====================================================
// Update Events List (right panel)
// =====================================================

function updateEvents(events) {
    const list = $("events-list");
    if (!events || events.length === 0) {
        list.innerHTML = '<p class="muted">Sin eventos.</p>';
        return;
    }
    // Descending priority first
    events.sort((a, b) => b.priority - a.priority || b.magnitude - a.magnitude);
    list.innerHTML = events.map(e => {
        const pClass = "p" + e.priority;
        const pName = ["", "LOW", "MED", "HIGH"][e.priority];
        return `<div class="event-card ${pClass}">
            <div class="ev-id">SIS-${String(e.event_id).padStart(6, "0")}</div>
            <div class="ev-detail">M=${e.magnitude} | P=${pName} | Prof=${e.depth_km}km | Rev=${e.revision}</div>
            <div class="ev-detail">Epi=(${e.epicenter.x}, ${e.epicenter.y}) | ${e.attention_state}</div>
            <button class="btn btn-sm" onclick="window.markReviewed(${e.event_id})" style="margin-top: 5px; width: 100%;">Marcar Revisado</button>
        </div>`;
    }).join("");
}

window.markReviewed = async function(id) {
    const res = await eel.mark_reviewed(id)();
    log(res.message, res.ok ? "info" : "error");
    if (res.ok) refresh();
};

function renderArchived(archived) {
    const list = $("archived-list");
    if (!archived || archived.length === 0) {
        list.innerHTML = '<p class="muted">Sin eventos archivados.</p>';
        return;
    }
    // Descending id order
    archived.sort((a, b) => b.event_id - a.event_id);
    list.innerHTML = archived.map(e => {
        const pClass = "p" + e.priority;
        const pName = ["", "LOW", "MED", "HIGH"][e.priority];
        return `<div class="event-card ${pClass}">
            <div class="ev-id">SIS-${String(e.event_id).padStart(6, "0")} (Archivado)</div>
            <div class="ev-detail">M=${e.magnitude} | P=${pName} | Prof=${e.depth_km}km</div>
        </div>`;
    }).join("");
}

