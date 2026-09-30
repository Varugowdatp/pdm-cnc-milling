/* ==================================================================
   SCREEN 3 — MANUAL INPUT CONTROL PANEL
   ==================================================================
   The software replacement for reading a physical gauge and typing it
   in. Slider + numeric entry for each of the five sensors, then the
   full verdict: class, probabilities, health, RUL, alarm, action, and
   the exact per-prediction explanation.

   The presets exist because a blank form is a bad demo: an examiner
   should be able to produce a heat-dissipation failure in one click
   and see the panel respond, rather than guessing which numbers matter.
   ================================================================== */

SCREENS.manual = (() => {

  let host = null;
  let reference = null;

  /* Preset operating points.
     ------------------------------------------------------------------
     These are REAL READINGS lifted from the dataset, taken from machines
     inside the prediction-horizon window - i.e. genuinely on the
     approach to a failure that has NOT yet happened (`failure_class`
     is still Normal, `label_horizon` names the coming failure, and no
     hard limit is breached).

     They were not hand-picked to look good. An earlier version used
     invented "sounds about right" numbers, and two of them - labelled
     "approaching power failure" and "approaching overstrain" - actually
     predicted Normal, because an isolated reading at high power with a
     fresh tool does not resemble the trajectory the model learned. A
     preset whose label contradicts its output teaches the wrong thing,
     so each one is now a measured row the model does classify correctly.
     ------------------------------------------------------------------ */
  const PRESETS = {
    healthy: { label: "Healthy machine", machine_type: "M",
      air_temperature: 298.0, process_temperature: 308.0,
      rotational_speed: 1558, torque: 38.5, tool_wear: 71 },

    hdf: { label: "Approaching heat failure", machine_type: "L",
      air_temperature: 303.05, process_temperature: 312.17,
      rotational_speed: 1208, torque: 46.7, tool_wear: 101.2 },

    pwf: { label: "Approaching power failure", machine_type: "M",
      air_temperature: 302.56, process_temperature: 312.75,
      rotational_speed: 2121, torque: 38.6, tool_wear: 78.3 },

    osf: { label: "Approaching overstrain", machine_type: "M",
      air_temperature: 300.27, process_temperature: 309.53,
      rotational_speed: 1230, torque: 45.2, tool_wear: 85.4 },

    twf: { label: "Approaching tool wear failure", machine_type: "L",
      air_temperature: 301.41, process_temperature: 312.08,
      rotational_speed: 2975, torque: 23.3, tool_wear: 198.1 },
  };

  async function enter(_param, el) {
    host = el;
    reference = await App.getReference();
    render();
    applyPreset("healthy");
    await submit();                 // land on a populated panel, not an empty one
  }

  function render() {
    const S = reference.sensors;

    const field = (key) => {
      const s = S[key];
      const step = key === "rotational_speed" ? 1 : (key === "tool_wear" ? 1 : 0.1);
      return `
        <label class="field">
          <span class="lbl">
            <span>${s.label}</span>
            <span class="range">${s.min}–${s.max} ${s.unit}</span>
          </span>
          <input type="number" id="f-${key}" step="${step}"
                 data-min="${s.min}" data-max="${s.max}" />
          <input type="range" id="r-${key}" min="${s.min}" max="${s.max}" step="${step}" />
        </label>`;
    };

    host.innerHTML = `
      <div class="screen-head">
        <div>
          <h2>Manual Input</h2>
          <p class="sub">
            Enter one sensor reading and get the complete verdict. This panel replaces the
            synopsis's physical sensor rig — the schema, units and limits are identical.
          </p>
        </div>
      </div>

      <div class="grid" style="grid-template-columns: 340px minmax(0,1fr); align-items:start">

        <!-- CONTROL PANEL -->
        <div class="panel">
          <h3>Sensor Entry</h3>

          <label class="field">
            <span class="lbl"><span>Machine Variant</span></span>
            <select id="f-machine_type">
              ${reference.machine_types.map(t => `<option value="${t}">${t}</option>`).join("")}
            </select>
          </label>

          ${Object.keys(S).map(field).join("")}

          <label class="field">
            <span class="lbl"><span>Machine ID</span><span class="range">optional — to save</span></span>
            <input type="text" id="f-machine_id" placeholder="e.g. CNC-01" />
          </label>

          <div class="btn-row mt">
            <button class="btn primary" id="m-run">ANALYSE</button>
            <button class="btn" id="m-save">Analyse &amp; Save</button>
          </div>

          <h3 class="mt">Presets</h3>
          <div class="btn-row">
            ${Object.entries(PRESETS).map(([k, p]) =>
              `<button class="btn sm ghost" data-preset="${k}">${p.label}</button>`).join("")}
          </div>
        </div>

        <!-- RESULT -->
        <div class="grid" style="gap:var(--gap)">
          <div id="m-banner"></div>
          <div class="grid cols-3">
            <div class="panel center" id="m-ring-panel"><div id="m-ring"></div></div>
            <div class="panel"><h3>Class Probabilities</h3><div id="m-probs"></div></div>
            <div class="panel"><h3>Mechanism Stress</h3><div id="m-stress"></div></div>
          </div>
          <div class="grid cols-2">
            <div class="panel"><h3>Verdict</h3><div id="m-verdict"></div></div>
            <div class="panel">
              <h3>Why — Decision-Path Attribution</h3>
              <div id="m-explain"></div>
            </div>
          </div>
          <div class="panel"><h3>Derived Physics</h3><div id="m-derived"></div></div>
        </div>
      </div>`;

    /* keep the number box and the slider in lockstep */
    Object.keys(S).forEach(key => {
      const num = host.querySelector(`#f-${key}`);
      const rng = host.querySelector(`#r-${key}`);
      num.addEventListener("input", () => { rng.value = num.value; flagRange(num); });
      rng.addEventListener("input", () => { num.value = rng.value; flagRange(num); });
    });

    host.querySelector("#m-run").onclick = () => submit(false);
    host.querySelector("#m-save").onclick = () => submit(true);
    host.querySelectorAll("[data-preset]").forEach(b =>
      b.onclick = () => { applyPreset(b.dataset.preset); submit(false); });
  }

  function flagRange(input) {
    const v = parseFloat(input.value);
    const lo = parseFloat(input.dataset.min), hi = parseFloat(input.dataset.max);
    input.classList.toggle("out-of-range", isFinite(v) && (v < lo || v > hi));
  }

  function applyPreset(name) {
    const p = PRESETS[name];
    if (!p) return;
    host.querySelector("#f-machine_type").value = p.machine_type;
    Object.keys(reference.sensors).forEach(key => {
      host.querySelector(`#f-${key}`).value = p[key];
      host.querySelector(`#r-${key}`).value = p[key];
      flagRange(host.querySelector(`#f-${key}`));
    });
  }

  function collect() {
    const reading = { machine_type: host.querySelector("#f-machine_type").value };
    Object.keys(reference.sensors).forEach(key => {
      reading[key] = parseFloat(host.querySelector(`#f-${key}`).value);
    });
    return reading;
  }

  async function submit(save = false) {
    const reading = collect();

    const bad = Object.entries(reading).find(([k, v]) => k !== "machine_type" && !isFinite(v));
    if (bad) return App.toast(`${bad[0]} must be a number.`, "err");

    const machineId = host.querySelector("#f-machine_id").value.trim();
    if (save && !machineId) return App.toast("Enter a Machine ID to save the reading.", "err");

    try {
      const result = await API.predict({
        ...reading, explain: true,
        save, machine_id: machineId || null,
      });
      paint(result);
      if (save) App.toast(`Saved to ${machineId}.`, "ok");
    } catch (err) {
      App.toast(err.message, "err");
    }
  }

  /* ===============================================================
     RESULT
     =============================================================== */
  function paint(r) {
    const level = r.alarm.level;
    const color = W.LEVEL_COLORS[level];
    const icons = { NORMAL: "✓", ADVISORY: "ℹ", WARNING: "▲", CRITICAL: "⛔" };

    host.querySelector("#m-banner").innerHTML = `
      <div class="alarm-banner ${level}">
        <div class="ab-icon" style="color:${color}">${icons[level]}</div>
        <div class="ab-body">
          <div class="ab-title" style="color:${color}">
            ${level} — ${App.escapeHTML(r.alarm.mode_name)}
            ${r.alarm.predicted ? `<span class="badge ADVISORY" style="margin-left:8px">PREDICTED</span>` : ""}
            ${r.alarm.has_breached ? `<span class="badge CRITICAL" style="margin-left:8px">LIMIT BREACHED</span>` : ""}
          </div>
          <div class="ab-msg">${App.escapeHTML(r.alarm.message)}</div>
        </div>
      </div>`;

    W.healthRing(host.querySelector("#m-ring"), r.health.index);
    W.probBars(host.querySelector("#m-probs"), r.prediction.probabilities, r.prediction.class);
    W.stressBars(host.querySelector("#m-stress"), r.physics.stress, r.physics.dominant_mode);

    /* ---- verdict ---- */
    const rul = r.rul;
    host.querySelector("#m-verdict").innerHTML = `
      <div class="mc-row"><span>Prediction</span>
        <b style="color:${r.prediction.class === "Normal" ? "var(--ok)" : color}">
          ${r.prediction.class}</b></div>
      <div class="mc-row"><span>Confidence</span>
        <b>${(r.prediction.confidence * 100).toFixed(1)}%</b></div>
      <div class="mc-row"><span>Health index</span>
        <b style="color:${W.healthColor(r.health.index)}">${r.health.index} — ${r.health.label}</b></div>
      <div class="mc-row"><span>Remaining life</span>
        <b>${App.rulText(rul)}</b></div>
      <div class="mc-row"><span>RUL basis</span>
        <b class="small" style="font-weight:600">${App.rulNote(rul)}</b></div>
      <div class="mc-row"><span>Dominant mechanism</span>
        <b>${r.physics.dominant_mode}</b></div>

      <p class="small muted mt" style="line-height:1.6;margin-bottom:0">
        <b style="color:var(--text)">What this means:</b> ${App.escapeHTML(r.prediction.meaning)}
      </p>
      ${level !== "NORMAL" ? `
        <p class="small mt" style="line-height:1.6;margin-bottom:0">
          <b style="color:var(--text)">Cause:</b> <span class="muted">${App.escapeHTML(r.alarm.cause)}</span><br/>
          <b style="color:var(--text)">Action:</b> <span class="muted">${App.escapeHTML(r.alarm.recommended_action)}</span>
        </p>` : ""}
      ${r.input_warnings?.length ? `
        <p class="small mt" style="color:var(--warn);margin-bottom:0">
          ${r.input_warnings.map(App.escapeHTML).join("<br/>")}
        </p>` : ""}`;

    /* ---- explanation ---- */
    const ex = r.explanation;
    const exHost = host.querySelector("#m-explain");
    if (ex) {
      exHost.innerHTML = `
        <p class="small muted" style="margin-top:0;line-height:1.6">
          ${App.escapeHTML(ex.narrative)}
        </p>
        <div id="m-drivers"></div>
        <p class="small muted" style="margin-bottom:0;border-top:1px solid var(--grid);padding-top:9px">
          Baseline ${(ex.base_rate * 100).toFixed(1)}% → prediction
          ${(ex.predicted_probability * 100).toFixed(1)}% for
          <b style="color:var(--text)">${ex.target_class}</b>.
          Contributions sum <b>exactly</b> to the model's output — this is the prediction,
          not an approximation of it.
        </p>`;
      W.driverBars(exHost.querySelector("#m-drivers"), ex.top_drivers);
    } else {
      exHost.innerHTML = `<div class="empty small">No explanation requested.</div>`;
    }

    /* ---- derived ---- */
    const T = reference.thresholds;
    const d = r.derived;
    const limitFor = {
      temp_delta: `min ${T.temp_delta_min} K`,
      power: `${T.power_min}–${T.power_max} W`,
      strain: `max ${T.osf_limit[r.reading.machine_type] ?? T.osf_limit.L}`,
      torque_speed_ratio: "—",
    };
    const names = {
      temp_delta: "Thermal Gradient", power: "Mechanical Power",
      strain: "Tool Strain", torque_speed_ratio: "Load Characteristic",
    };
    const units = { temp_delta: "K", power: "W", strain: "min·Nm", torque_speed_ratio: "Nm/rpm" };

    host.querySelector("#m-derived").innerHTML = `
      <div class="grid cols-4">
        ${Object.keys(names).map(k => `
          <div>
            <div class="small muted">${names[k]}</div>
            <div class="mono" style="font-size:20px;font-weight:700">${W.fmt(d[k], 2)}
              <span class="small muted" style="font-weight:400">${units[k]}</span></div>
            <div class="small muted">limit: ${limitFor[k]}</div>
          </div>`).join("")}
      </div>`;
  }

  return { enter };
})();
