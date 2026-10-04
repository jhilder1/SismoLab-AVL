
async function createEvent() {
    const timeVal = val("ev-time") || (lastState ? lastState.clock.slice(0, 19) : "2026-01-01T00:00:00");
    const res = await eel.create_event(
        val("ev-id"), val("ev-mag"), val("ev-depth"),
        val("ev-x"), val("ev-y"), timeVal, val("ev-station")
    )();
    log(res.message, res.ok ? "ok" : "err");
    if (res.ok) refresh();
}

// Section 6: a correction replaces one or several data; an empty field keeps
// its value. datetime-local gives local text without zone, read as UTC.
async function correctEvent() {
    const fields = ["cor-mag", "cor-depth", "cor-x", "cor-y", "cor-time"].map(id => val(id) || null);
    const res = await eel.correct_event(val("cor-id"), ...fields)();
    log(res.message, res.ok ? "ok" : "err");
    if (res.ok) refresh();
}

// Section 6: the affected event is shown before it is deleted.
async function deleteEvent() {
    const id = val("del-id");
    const preview = await eel.preview_delete(id)();
    if (!preview.ok) { log(preview.message, "err"); return; }

    const e = preview.event;
    const ids = list => list.length ? list.map(formatEventId).join(", ") : "ninguno";
    const text = `Eliminar ${formatEventId(e.event_id)}\n\n`
        + `M=${e.magnitude} | P=${e.priority} | H=${e.depth_km} km | Rev=${e.revision}\n`
        + `Clave=${preview.key} | profundidad en el arbol=${preview.depth}\n\n`
        + `Solo se retira este evento. Sus ${preview.descendants.length} descendiente(s) siguen activos: `
        + `${ids(preview.descendants)}\n`
        + `Eventos que lo usan como referencia (se recalcula su asociacion): ${ids(preview.dependents)}\n\n`
        + `Su ID quedara como eliminado. La accion se puede deshacer.`;
    if (!confirm(text)) { log("Eliminacion cancelada", "info"); return; }

    const res = await eel.delete_event(id)();
    log(res.message, res.ok ? "ok" : "err");
    if (res.ok) refresh();
}

// Status of an id (Section 6): active, archived or deleted.
const STATUS_LABEL = { active: "ACTIVO", archived: "ARCHIVADO", deleted: "ELIMINADO" };

function statusBadgeHtml(status) {
    return `<span class="status-badge ${status}">${STATUS_LABEL[status] || status}</span>`;
}

function formatEventId(id) {
    return "SIS-" + String(id).padStart(6, "0");
}

// Current data of an event as the consultation of Section 6 lists it.
function eventDetailsHtml(e, key) {
    const date = (e.occurrence_time || "").replace("T", " ").replace("Z", " UTC");
    const stations = (e.reporting_stations || []).map(esc).join(", ") || "--";
    return `<div class="detail-group">
        <b>Datos vigentes:</b> M=${e.magnitude} | H=${e.depth_km} km | epicentro (${e.epicenter.x}, ${e.epicenter.y}) | ${esc(date)}<br>
        Revision ${e.revision} | estaciones con reportes aceptados: ${stations}<br>
        Zona poblada: ${e.in_populated_zone ? "si" : "no"} | prioridad ${PRIORITY_NAME[e.priority] || e.priority}
        | clave ${esc(key)} | atencion: ${e.attention_state === "reviewed" ? "revisado" : "pendiente"}
    </div>`;
}

function associationsHtml(a) {
    if (!a) return "";
    const item = r => `${formatEventId(r.event_id)} (M=${r.magnitude}${r.status === "archived" ? ", archivado" : ""})`;
    const list = rows => rows.length ? rows.map(item).join(", ") : "ninguno";
    return `<div class="detail-group"><b>Asociaciones:</b>
        referencia elegida: ${a.reference ? item(a.reference) : "ninguna"}<br>
        candidatos: ${list(a.candidates)}<br>
        lo usan como referencia: ${list(a.replicas)}
    </div>`;
}

async function searchEvent() {
    const res = await eel.search_event(val("search-id"))();
    const box = $("search-result");
    box.classList.remove("hidden");
    if (!res.ok) {
        box.innerHTML = esc(res.message);
        log(res.message, "err");
        return;
    }

    let html = `<b>${formatEventId(res.event_id)}</b>${statusBadgeHtml(res.status)}`;
    if (res.status === "active") {
        html += eventDetailsHtml(res.event, res.key) + `<div class="detail-group">
            <b>En el AVL:</b> profundidad del nodo ${res.depth} | altura ${res.height} |
            factor de balance ${res.balance_factor} | costo de acceso ${res.access_cost} nodo(s)
            ${res.costly ? `<br><span class="costly-flag">Acceso costoso: prioridad ALTA y profundidad ${res.depth} &gt; L=${res.limit_L}</span>` : ""}
        </div>` + associationsHtml(res.associations);
        log(`Evento activo encontrado. Costo de acceso: ${res.access_cost} nodo(s)`, "info");
    } else if (res.status === "archived") {
        html += eventDetailsHtml(res.event, res.key)
            + `<div class="detail-group">Esta en el historico: fuera del AVL activo, conserva datos y asociaciones.</div>`
            + associationsHtml(res.associations);
        log("El evento esta archivado en el historico", "info");
    } else {
        html += `<div class="detail-group">Fue eliminado: su ID no se puede reutilizar ni reactivar con reportes.
            Solo se recupera deshaciendo la eliminacion o restaurando una version.</div>`;
        log("El evento fue eliminado", "info");
    }
    box.innerHTML = html;
}

// Section 8: a burst file prepares the reports of N stations at once. They
// enter the queue in file order and none is applied until its step runs.
async function loadBurst() {
    const res = await eel.load_burst()();
    if (res.cancelled) { log(res.message, "info"); return; }
    const box = $("burst-result");
    box.classList.remove("hidden");
    if (!res.ok) {
        const items = (res.problems || []).map(p => `<li>${esc(p)}</li>`).join("");
        box.innerHTML = `<b class="err">${esc(res.file || "")}: rafaga rechazada</b>
            <div>Ningun reporte entro a la cola.</div><ul>${items}</ul>`;
        log(res.message, "err");
        return;
    }
    const i = res.info;
    box.innerHTML = `<b class="ok">${esc(res.file)}: ${i.count} reporte(s) de ${i.stations.length} estacion(es) encolados</b>
        <div>Posiciones ${i.first_position} a ${i.queue_size} de la cola (${esc(i.stations.join(", "))}).
        Ninguno se aplica hasta procesarlo.</div>
        ${i.description ? `<div class="muted">${esc(i.description)}</div>` : ""}`;
    log(`Rafaga ${res.file}: ${i.count} reportes encolados. Se deshace como una sola accion.`, "ok");
    refresh();
}

async function enqueueReport() {
    const timeVal = val("rp-time") || (lastState ? lastState.clock.slice(0, 19) : "2026-01-01T00:00:00");
    const res = await eel.enqueue_report(
        val("rp-evid"), val("rp-rev"), val("rp-station"),
        val("rp-mag"), val("rp-depth"),
        val("rp-x"), val("rp-y"), timeVal
    )();
    log(res.message, res.ok ? "ok" : "err");
    if (res.ok) refresh();
}

