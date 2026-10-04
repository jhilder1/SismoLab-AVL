// =====================================================
// Report queue and continuous processing (Section 8)
// =====================================================

// Spanish label, colour family and a short generic reason for each decision
// process_next_report can return (domain/scenario.py:295 onward). The family
// picks the CSS class: create/correct the catalogue, only confirm, or reject.
const REPORT_DECISIONS = {
    CREATED:            { label: "Creado",                family: "create",  why: "Identificador desconocido: se registra como evento nuevo" },
    CORRECTED:          { label: "Corregido",              family: "create",  why: "Revision mayor que la vigente: se actualizan los datos" },
    REACTIVATED:        { label: "Reactivado",             family: "create",  why: "Revision mayor sobre un evento archivado: vuelve al AVL" },
    CONFIRMED:          { label: "Confirmado",             family: "confirm", why: "Misma revision y mismos datos: se anade la estacion" },
    CONFIRMED_ARCHIVED: { label: "Confirmado (archivado)", family: "confirm", why: "Misma revision y mismos datos sobre un evento archivado" },
    CONFLICT:           { label: "Conflicto",              family: "reject",  why: "Misma revision pero datos distintos: se rechaza" },
    OUTDATED:           { label: "Desactualizado",         family: "reject",  why: "Revision menor que la vigente: se descarta" },
    REJECTED:           { label: "Rechazado",              family: "reject",  why: "Datos invalidos o evento eliminado: no se aplica" },
};

// The frontend's own record of processed steps. Section 8 asks that each
// step show its decision and rotations, not that the record survive a
// restart (unlike the undo stack or the named versions), so it lives only
// here, most recent first.
let reportHistory = [];
let continuousRunning = false;
let continuousLoop = null;      // promise of the running loop, so a recovery can wait for it
let recoveryRunning = false;    // Section 8: no report is processed while this is true

function renderQueue(reports) {
    const box = $("queue-pending");
    if (!reports || reports.length === 0) {
        box.innerHTML = '<p class="muted">Cola vacia: no hay reportes pendientes.</p>';
        return;
    }
    // Position in the queue, not the event's priority, decides this order:
    // that is the point being shown here (Section 8).
    const rows = reports.map((r, i) => `<tr class="${i === 0 ? "queue-next" : ""}">
        <td>${i === 0 ? "Siguiente" : i + 1}</td>
        <td>SIS-${String(r.event_id).padStart(6, "0")}</td>
        <td>${esc(r.station_id)}</td>
        <td>${r.revision}</td>
        <td>${r.magnitude}</td>
        <td>${r.depth_km}</td>
        <td>(${r.epicenter.x}, ${r.epicenter.y})</td>
        <td>${esc((r.occurrence_time || "").replace("T", " ").replace("Z", ""))}</td>
    </tr>`).join("");
    box.innerHTML = `<table class="queue-table">
        <tr><th>#</th><th>Evento</th><th>Estacion</th><th>Rev</th><th>M</th><th>H (km)</th><th>Epicentro</th><th>Ocurrencia</th></tr>
        ${rows}
    </table>`;
}

// Extra, decision-specific detail the backend does provide (a rejection's
// reason, or the two revisions compared in an outdated report).
function decisionExtra(result) {
    const parts = [];
    if (result.reason) parts.push(result.reason);
    if (result.report_rev !== undefined && result.current_rev !== undefined) {
        parts.push(`reporte rev ${result.report_rev} vs vigente rev ${result.current_rev}`);
    }
    return parts.join(" — ");
}

function renderHistory() {
    const box = $("queue-history");
    if (!reportHistory.length) {
        box.innerHTML = '<p class="muted">Sin reportes procesados todavia.</p>';
        return;
    }
    box.innerHTML = reportHistory.map(entry => {
        if (entry.note) {
            return `<div class="history-entry family-reject">
                <div class="history-head"><span class="history-decision">Pausa</span></div>
                <div class="history-why">${esc(entry.note)}</div>
            </div>`;
        }
        const meta = REPORT_DECISIONS[entry.result] || { label: entry.result, family: "confirm", why: "" };
        const rot = entry.rotations;
        const rotated = rot.ll || rot.rr || rot.lr || rot.rl || rot.simple_left || rot.simple_right;
        const rotText = rotated
            ? `LL=${rot.ll} RR=${rot.rr} LR=${rot.lr} RL=${rot.rl} | giro izq=${rot.simple_left} der=${rot.simple_right}`
            : "sin rotaciones";
        const extra = entry.extra ? ` — ${esc(entry.extra)}` : "";
        return `<div class="history-entry family-${meta.family}">
            <div class="history-head">
                <span class="history-decision">${esc(meta.label)}</span>
                <span class="history-who">${esc(entry.station)} &rarr; SIS-${String(entry.eventId).padStart(6, "0")} rev ${entry.revision}</span>
            </div>
            <div class="history-why">${esc(meta.why)}${extra}</div>
            <div class="history-rot">${rotText}</div>
        </div>`;
    }).join("");
}

// Runs exactly one queue step. The backend's result does not always carry
// the station or the revision (Section 8 still asks for both), so the
// pending report is read here before it is dequeued; the rotations it
// produced are the AVL's rotation counters before this call minus after.
// Nothing is dequeued on EMPTY or PAUSED, so no history entry is added then.
async function processOneReport() {
    if (recoveryRunning) {
        return { result: "PAUSED", message: "Recuperacion global en curso: la cola esta en pausa" };
    }
    const pending = lastState && lastState.queued_reports ? lastState.queued_reports[0] : null;
    const before = lastState ? { ...lastState.rotations } : null;

    const result = await eel.process_report()();
    if (result.result === "EMPTY" || result.result === "PAUSED") {
        return result;
    }

    await refresh();

    const after = lastState.rotations;
    const rotations = before ? {
        ll: after.ll - before.ll, rr: after.rr - before.rr,
        lr: after.lr - before.lr, rl: after.rl - before.rl,
        simple_left: after.simple_left - before.simple_left,
        simple_right: after.simple_right - before.simple_right,
    } : { ll: 0, rr: 0, lr: 0, rl: 0, simple_left: 0, simple_right: 0 };

    reportHistory.unshift({
        station: pending ? pending.station_id : "?",
        eventId: pending ? pending.event_id : result.event_id,
        revision: pending ? pending.revision : (result.revision ?? "?"),
        result: result.result,
        extra: decisionExtra(result),
        rotations,
    });
    renderHistory();

    return result;
}

async function processReport() {
    const result = await processOneReport();
    if (result.result === "EMPTY" || result.result === "PAUSED") {
        log(result.message, "info");
        return;
    }
    const meta = REPORT_DECISIONS[result.result];
    log(meta ? `${meta.label}: ${meta.why}` : `Reporte procesado: ${result.result}`,
        meta && meta.family === "reject" ? "err" : "ok");
}

// One report per step, each fully resolved before the next starts, with a
// visible pause in between (Section 8). continuousRunning guards against two
// loops at once; the loop also stops on an empty queue (via EMPTY), on
// PAUSED (a recovery is running), or when the button is clicked again.
let wakeContinuous = null;      // ends the pause between steps early

function sleepContinuous(ms) {
    return new Promise(resolve => {
        const timer = setTimeout(resolve, ms);
        wakeContinuous = () => { clearTimeout(timer); resolve(); };
    });
}

async function processContinuous() {
    if (continuousRunning) {
        await pauseContinuous();
        return;
    }
    if (recoveryRunning) {
        log("Recuperacion global en curso: la cola esta en pausa", "info");
        return;
    }
    continuousRunning = true;
    const button = $("btn-continuous");
    button.textContent = "Pausar";
    button.classList.replace("btn-primary", "btn-danger");
    continuousLoop = runContinuousLoop(Number(val("continuous-delay")));
    await continuousLoop;
}

async function runContinuousLoop(delay) {
    try {
        while (continuousRunning) {
            const result = await processOneReport();
            if (result.result === "EMPTY" || result.result === "PAUSED") {
                log(result.message, "info");
                break;
            }
            if (!continuousRunning) break;
            await sleepContinuous(delay);
        }
    } finally {
        continuousRunning = false;
        wakeContinuous = null;
        const button = $("btn-continuous");
        button.textContent = "Procesar continuo";
        button.classList.replace("btn-danger", "btn-primary");
    }
}

// Stops the continuous loop and waits until it has really stopped: the step
// in progress is resolved completely first (Section 8). Returns whether a
// loop was running; `note` is written to the decision history when it was.
async function pauseContinuous(note) {
    if (!continuousRunning) return false;
    continuousRunning = false;
    if (wakeContinuous) wakeContinuous();
    await continuousLoop;
    if (note) {
        reportHistory.unshift({ note });
        renderHistory();
    }
    return true;
}

// Section 8: asking for a global recovery pauses report processing. The
// running step finishes, then the recovery runs while no step can start;
// afterwards the queue stays paused until the user resumes it.
async function runWithQueuePaused(action) {
    recoveryRunning = true;
    try {
        const paused = await pauseContinuous(
            "Recuperacion global solicitada: el procesamiento continuo se detuvo despues del "
            + "paso en curso. Pulsa Procesar continuo para reanudar.");
        return { res: await action(), paused };
    } finally {
        recoveryRunning = false;
    }
}

const RESUME_HINT = "La cola quedo en pausa: pulsa Procesar continuo para reanudar.";

async function undoAction() {
    const res = await eel.undo_action()();
    const msg = res.message || `Deshecho: ${res.description}`;
    log(msg, res.result === "UNDONE" ? "ok" : "info");
    refresh();
}

async function redoAction() {
    const res = await eel.redo_action()();
    const msg = res.message || `Rehecho: ${res.description}`;
    log(msg, res.result === "REDONE" ? "ok" : "info");
    refresh();
}

async function toggleStress() {
    // Leaving stress mode runs a global recovery first, so it also pauses the queue.
    const leaving = Boolean(lastState && lastState.stress_mode);
    const call = () => eel.toggle_stress()();
    const { res, paused } = leaving ? await runWithQueuePaused(call) : { res: await call(), paused: false };

    let msg = res.message || ("Modo estres: " + (res.stress_mode ? "ACTIVADO" : "desactivado"));
    if (res.errors && res.errors.length) {
        msg += ` (${res.errors.length} problema(s) en la auditoria; el primero: ${res.errors[0]}. `
            + `Detalle completo en Verificar estructura)`;
    }
    if (paused) msg += " " + RESUME_HINT;
    log(msg, res.stress_mode ? "err" : "ok");
    refresh();
}

async function recoverBalance() {
    const { res, paused } = await runWithQueuePaused(() => eel.recover_balance()());
    const pauseText = paused ? "\n\n" + RESUME_HINT : "";
    if (res.result === "RECOVERED") {
        const c = res.cost;
        const msg = `Balance recuperado.\n\nRotaciones realizadas:\nLL=${c.ll}  RR=${c.rr}  LR=${c.lr}  RL=${c.rl}\nAltura final del árbol=${c.final_height}` + pauseText;
        log(msg.replace(/\n/g, ' '), "ok");
        alert(msg);
    } else {
        log(res.message + (paused ? " " + RESUME_HINT : ""), "info");
        alert(res.message + pauseText);
    }
    refresh();
}

// Section 14: "Verificar estructura" opens the Auditoria tab, which shows one
// report per inconsistent event. While the tab is open it is checked again
// on every refresh, so it never shows the result of an older tree.
async function runAudit() {
    if (treeView !== "audit") showTree("audit");
    const res = await refreshAudit();
    const unbalanced = res.unbalanced_nodes.length;
    log(res.is_valid
        ? `Verificacion OK: ${res.nodes_checked} nodos, 0 errores`
          + (res.stress_mode && unbalanced ? ` | ${unbalanced} nodo(s) desbalanceado(s) por el modo estres` : "")
        : `Verificacion: ${res.report.length} evento(s) inconsistente(s), ${res.errors.length} problema(s)`,
        res.is_valid ? "ok" : "err");
}

async function refreshAudit() {
    const res = await eel.run_audit()();
    renderAudit(res);
    return res;
}

function renderAudit(res) {
    const summary = $("audit-summary");
    summary.textContent = `${res.nodes_checked} nodos verificados | modo ${res.stress_mode ? "estres" : "normal"} `
        + `| eventos inconsistentes: ${res.report.length} | problemas: ${res.errors.length}`;
    summary.classList.remove("hidden");

    let html = res.is_valid
        ? `<div class="audit-verdict ok">Sin errores de orden global por K, unicidad, referencias, alturas
            ni factores de balance${res.stress_mode ? " (aparte del desbalance esperado del modo estres)" : ""}.</div>`
        : `<div class="audit-verdict bad">Se encontraron problemas en ${res.report.length} evento(s).</div>`;

    if (res.report.length) {
        html += `<h4>Reporte por evento inconsistente</h4>` + res.report.map(r => `<div class="audit-entry">
            <div class="audit-head">${formatEventId(r.event_id)} ${statusBadgeHtml(r.status)}</div>
            <ul>${r.problems.map(problem => `<li>${esc(problem)}</li>`).join("")}</ul>
        </div>`).join("");
    }

    const unbalanced = res.unbalanced_nodes;
    if (res.stress_mode && unbalanced.length) {
        const worst = unbalanced.reduce((m, n) => Math.max(m, Math.abs(n.balance_factor)), 0);
        html += `<h4>Desbalance esperado del modo estres</h4>
            <p class="audit-text">${unbalanced.length} nodo(s) con factor fuera de {-1, 0, 1}, el mayor |FB| = ${worst}.
            No es un error en modo estres: Recuperar Balance lo corrige.</p>
            <div class="audit-unbalanced">${unbalanced.map(n =>
                `${formatEventId(n.event_id)} (FB ${n.balance_factor})`).join(" · ")}</div>`;
    } else if (res.is_avl) {
        html += `<p class="audit-text">Todos los factores de balance estan en {-1, 0, 1}: el arbol cumple la propiedad AVL.</p>`;
    }
    html += `<p class="ind-note">Se verifica el orden global por K (el inorden debe ser estrictamente creciente, no
        solo cada hijo frente a su padre), la unicidad de los IDs, que el AVL y el indice por ID tengan los mismos
        eventos, las alturas y factores de balance recalculados, y que cada referencia cumpla la seccion 7 sin
        formar ciclos.</p>`;
    $("audit-report").innerHTML = html;
}

// Section 3: the clock only moves forward, by the hours the user asks for.
async function advanceClock() {
    const hours = val("clock-hours");
    const res = await eel.advance_clock(hours)();
    if (!res.ok) { log(res.message, "err"); return; }
    log(`Reloj avanzado ${hours} h, hasta ${res.clock.replace("T", " ")}`, "info");
    refresh();
}

// Section 10: the rule picks the branch; the user sees which one, its ids,
// how many events and why, and can only confirm that one.
const ARCHIVE_BUTTON_TEXT = "Archivar rama de eventos antiguos";

async function showEligibleBranches() {
    const panel = $("eligible-branches-panel");
    const btn = $("btn-show-branches");
    if (panel.style.display !== "none") {
        panel.style.display = "none";
        btn.textContent = ARCHIVE_BUTTON_TEXT;
        return;
    }
    btn.textContent = "Cargando…";
    const preview = await eel.preview_archive()();
    btn.textContent = ARCHIVE_BUTTON_TEXT;
    $("eligible-branches-list").innerHTML = archivePreviewHtml(preview);
    panel.style.display = "block";
}

function archivePreviewHtml(p) {
    const ids = list => list.map(formatEventId).join(", ");
    let html = `<p class="archive-criteria">${esc(p.criteria)}</p>`;

    if (!p.selected) {
        html += `<p class="muted archive-none">${esc(p.justification[0])} El escenario se conserva.</p>`;
    } else {
        const b = p.selected;
        html += `<div class="archive-card">
            <div class="archive-title">Rama seleccionada: raiz ${formatEventId(b.root_id)}</div>
            <div class="archive-detail">${b.count} evento(s) | profundidad de la raiz: ${b.root_depth} | clave ${esc(b.root_key)}</div>
            <div class="archive-ids">${esc(ids(b.event_ids))}</div>
            <ul class="archive-why">${p.justification.map(j => `<li>${esc(j)}</li>`).join("")}</ul>
            <button onclick='archiveBranch(${JSON.stringify(b.event_ids)})' class="btn btn-sm btn-warn full-w">
                Archivar esta rama (${b.count} eventos)</button>
        </div>`;
    }

    if (p.others.length) {
        html += `<div class="archive-section">Otras ramas elegibles (no seleccionadas)</div>`;
        html += p.others.map(o => `<div class="archive-other">${formatEventId(o.root_id)}:
            ${o.count} evento(s) — ${esc(o.why_not)}</div>`).join("");
    }

    const rejected = p.rejected_low_roots;
    if (rejected.length) {
        const shown = rejected.slice(0, 8);
        html += `<div class="archive-section">Raices de prioridad BAJA no elegibles</div>`;
        html += shown.map(r => `<div class="archive-other">${formatEventId(r.root_id)}: su subarbol contiene
            ${formatEventId(r.offender_id)} (${esc(r.reason)})</div>`).join("");
        if (rejected.length > shown.length) {
            html += `<div class="archive-other">… y ${rejected.length - shown.length} mas</div>`;
        }
    }
    return html;
}

async function archiveBranch(eventIds) {
    if (!confirm(`¿Archivar ${eventIds.length} evento(s)?\n\n${eventIds.map(formatEventId).join(", ")}\n\n`
            + `Pasan al historico con sus datos y asociaciones. La accion se puede deshacer.`)) return;
    const res = await eel.archive_selected_branch(eventIds)();
    if (res.ok) {
        log(`Archivados ${res.count} evento(s) en una sola accion.`, "ok");
        $("eligible-branches-panel").style.display = "none";
    } else {
        // The scenario changed since the preview: show the current selection.
        log(res.message || "Error al archivar", "err");
        $("eligible-branches-list").innerHTML = archivePreviewHtml(await eel.preview_archive()());
    }
    refresh();
}

