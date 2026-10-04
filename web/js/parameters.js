// =====================================================
// Parameters W, R, L, T (sections 7, 9 and 10)
// =====================================================

// Order matches update_parameters(w_hours, r_km, l_depth, t_archive_hours).
const PARAM_FIELDS = [
    ["par-w", "W_hours"],
    ["par-r", "R_km"],
    ["par-l", "L_depth"],
    ["par-t", "T_archive_hours"],
];

// Preload the current values, but never overwrite a field being edited.
function fillParameters(params) {
    for (const [id, key] of PARAM_FIELDS) {
        const input = $(id);
        if (document.activeElement !== input) input.value = params[key];
    }
}

// An empty field is sent as null so a single parameter can be changed.
async function applyParameters() {
    const args = PARAM_FIELDS.map(([id]) => val(id).trim() === "" ? null : Number(val(id)));
    const res = await eel.update_parameters(...args)();
    log(res.message, res.ok ? "ok" : "err");
    refresh();
}

