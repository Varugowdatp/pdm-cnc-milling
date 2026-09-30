/* ==================================================================
   SCREEN 2 — MACHINE HMI
   ==================================================================
   The operator's console for one machine: five analogue sensor dials,
   the health ring, an RUL countdown, per-mechanism stress, live trend
   charts and the alarm banner — all fed by the SSE stream while a
   replay is running.

   LIFECYCLE NOTE
   The SSE connection and the fallback poll timer MUST be torn down in
   leave(). Without that, navigating away leaves a socket open and a
   timer writing into a detached DOM, and every visit to this screen
   would add another one.
   ================================================================== */

SCREENS.machine = (() => {

  let host = null;
  let machineId = null;
  let source = null;          // EventSource
  let pollTimer = null;
  let trail = [];             // recent readings for the trend charts
  let reference = null;

  const TRAIL_MAX = 90;

  async function enter(param, el) {
    host = el;
    reference = await App.getReference();
    machineId = param || null;

    if (!machineId) return renderPicker();

    renderShell();
    await loadHistory();
    connect();
    pollTimer = setInterval(pollStatus, 3000);
  }

  function leave() {
    if (source) { source.close(); source = null; }
    clearInterval(pollTimer);
    pollTimer = null;
    trail = [];
  }

  /* ===============================================================
     NO MACHINE SELECTED — offer the trajectory catalogue
     =============================================================== */
  async function renderPicker() {
    host.innerHTML = `
      <div class="screen-head">
        <div>
          <h2>Machine HMI</h2>
          <p class="sub">Select a machine to monitor, or start a new replay from a real
            run-to-failure trajectory in the dataset.</p>
        </div>
      </div>
      <div class="grid cols-2">
        <div class="panel"><h3>Monitored Machines</h3><div id="mp-live"></div></div>
        <div class="panel"><h3>Start a New Replay</h3><div id="mp-cat"></div></div>
      </div>`;

    const [{ machines }, cat] = await Promise.all([API.machines(), API.catalogue(18)]);

    host.querySelector("#mp-live").innerHTML = machines.length
      ? machines.map(m => `
          <div class="mc-row" style="padding:8px 0;border-top:1px solid var(--grid);cursor:pointer"
               data-go="${App.escapeHTML(m.machine_id)}">
            <span><span class="led" style="--level-color:${W.LEVEL_COLORS[m.alarm_level] || "#94a3b8"};
                  display:inline-block;vertical-align:-2px;margin-right:8px"></span>
              <b class="mono">${App.escapeHTML(m.machine_id)}</b></span>
            <span>${m.health_index === null || m.health_index === undefined
                    ? "—" : m.health_index.toFixed(0) + " health"}</span>
          </div>`).join("")
      : `<div class="empty small">No machines yet. Start one from the right →</div>`;

    host.querySelectorAll("[data-go]").forEach(n =>
      n.onclick = () => App.go("machine", n.dataset.go));

    host.querySelector("#mp-cat").innerHTML = `
      <div class="tbl-wrap" style="max-height:340px;overflow-y:auto">
        <table>
          <thead><tr><th>Trajectory</th><th>Type</th><th>Life</th><th>Fails by</th><th></th></tr></thead>
          <tbody>
            ${cat.machines.map(m => `
              <tr>
                <td class="mono">${m.machine_id}</td>
                <td>${m.machine_type}</td>
                <td class="num">${m.life_hours} h</td>
                <td><span class="badge WARNING">${m.failure_mode}</span></td>
                <td><button class="btn sm primary" data-start="${m.machine_id}">Replay</button></td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>`;

    host.querySelectorAll("[data-start]").forEach(btn => btn.onclick = async () => {
      const src = btn.dataset.start;
      btn.disabled = true;
      try {
        await API.simStart({ machine_id: src, source_machine: src, interval: 1.0, restart: true });
        App.go("machine", src);
      } catch (err) {
        App.toast(err.message, "err");
        btn.disabled = false;
      }
    });
  }

  /* ===============================================================
     SHELL
     =============================================================== */
  function renderShell() {
    host.innerHTML = `
      <div class="screen-head">
        <div>
          <h2 class="mono">${App.escapeHTML(machineId)}</h2>
          <p class="sub" id="mh-sub">Connecting…</p>
        </div>
        <div class="btn-row">
          <button class="btn ok"     id="mh-start">▶ START</button>
          <button class="btn danger" id="mh-stop">■ STOP</button>
          <button class="btn ghost"  id="mh-back">← All Machines</button>
        </div>
      </div>

      <div id="mh-banner"></div>

      <div class="grid" style="grid-template-columns: 300px minmax(0,1fr); align-items:start">

        <!-- LEFT COLUMN : health + RUL + stress -->
        <div class="grid" style="gap:var(--gap)">
          <div class="panel center">
            <div id="mh-ring"></div>
            <div id="mh-rul" class="mt"></div>
          </div>
          <div class="panel">
            <h3>Mechanism Stress</h3>
            <div id="mh-stress"></div>
          </div>
          <div class="panel">
            <h3>Model Opinion</h3>
            <div id="mh-probs"></div>
          </div>
        </div>

        <!-- RIGHT COLUMN : dials + trends -->
        <div class="grid" style="gap:var(--gap)">
          <div class="panel">
            <h3>Live Sensor Readings <span id="mh-cycle" class="mono small"></span></h3>
            <div class="grid cols-5" id="mh-gauges"></div>
          </div>

          <div class="grid cols-2">
            <div class="panel">
              <h3>Health &amp; Failure Probability</h3>
              <div id="mh-chart-health"></div>
            </div>
            <div class="panel">
              <h3>Governing Physics</h3>
              <div id="mh-chart-physics"></div>
            </div>
          </div>

          <div class="panel">
            <h3>Ground Truth <span class="small muted" style="text-transform:none;letter-spacing:0">
              held out from the model — so you can judge it</span></h3>
            <div id="mh-truth"></div>
          </div>
        </div>
      </div>`;

    host.querySelector("#mh-back").onclick = () => App.go("machine");
    host.querySelector("#mh-start").onclick = start;
    host.querySelector("#mh-stop").onclick = stop;
  }

  /* ===============================================================
     DATA
     =============================================================== */
  async function loadHistory() {
    try {
      const data = await API.machine(machineId, TRAIL_MAX);
      trail = (data.readings || []).map(r => ({
        cycle: r.cycle, ts: r.ts,
        health: r.health_index, p_fail: r.p_failure, stress: r.overall_stress,
        temp_delta: r.temp_delta, power: r.power, strain: r.strain,
        tool_wear: r.tool_wear, torque: r.torque, speed: r.rotational_speed,
        air: r.air_temperature, process: r.process_temperature,
        level: r.alarm_level, predicted: r.predicted_class,
      }));

      if (data.live) {
        paint(data.live);
      } else if (trail.length) {
        paintFromRow(data.readings[data.readings.length - 1]);
      } else {
        paintEmpty();
      }
      drawCharts();
      updateStatusLine(data.simulation);
    } catch (err) {
      host.querySelector("#mh-sub").textContent = err.message;
    }
  }

  function connect() {
    if (source) source.close();
    source = API.stream(machineId, {
      reading: r => { push(r); paint(r); drawCharts(); },
      status:  s => updateStatusLine(s),
      end:     s => { updateStatusLine(s); App.toast(`${machineId}: replay finished.`); },
    });
    source.onerror = () => { /* EventSource retries on its own */ };
  }

  async function pollStatus() {
    try {
      const s = await API.simStatus(machineId);
      updateStatusLine(s);
    } catch { /* no simulation for this machine - fine */ }
  }

  function push(r) {
    trail.push({
      cycle: r.ground_truth ? undefined : undefined,
      ts: r.timestamp,
      health: r.health.index,
      p_fail: r.prediction.p_failure,
      stress: r.physics.overall_stress,
      temp_delta: r.derived.temp_delta,
      power: r.derived.power,
      strain: r.derived.strain,
      tool_wear: r.reading.tool_wear,
      torque: r.reading.torque,
      speed: r.reading.rotational_speed,
      air: r.reading.air_temperature,
      process: r.reading.process_temperature,
      level: r.alarm.level,
      predicted: r.prediction.class,
    });
    if (trail.length > TRAIL_MAX) trail.shift();
  }

  /* ===============================================================
     PAINT
     =============================================================== */
  function paintEmpty() {
    host.querySelector("#mh-gauges").innerHTML =
      `<div class="empty small" style="grid-column:1/-1">
         No readings yet. Press <b>START</b> to begin the replay.</div>`;
    W.healthRing(host.querySelector("#mh-ring"), 0);
  }

  /* a database row and a live SSE payload have different shapes;
     normalise the row into the payload shape so paint() is the only
     place that knows how to draw */
  function paintFromRow(row) {
    paint({
      reading: {
        machine_type: row.machine_type,
        air_temperature: row.air_temperature,
        process_temperature: row.process_temperature,
        rotational_speed: row.rotational_speed,
        torque: row.torque, tool_wear: row.tool_wear,
      },
      derived: { temp_delta: row.temp_delta, power: row.power, strain: row.strain },
      prediction: {
        class: row.predicted_class, p_failure: row.p_failure,
        confidence: row.confidence, probabilities: null,
      },
      physics: { overall_stress: row.overall_stress, dominant_mode: row.dominant_mode, stress: null },
      health: { index: row.health_index },
      rul: { hours: row.rul_hours, readings: row.rul_readings, method: "trend" },
      alarm: { level: row.alarm_level, message: "", mode_name: "", recommended_action: "" },
    });
  }

  function paint(r) {
    const S = reference.sensors;

    /* ---- dials ---- */
    const dials = [
      ["air_temperature", r.reading.air_temperature, 1],
      ["process_temperature", r.reading.process_temperature, 1],
      ["rotational_speed", r.reading.rotational_speed, 0],
      ["torque", r.reading.torque, 1],
      ["tool_wear", r.reading.tool_wear, 0],
    ];
    const gaugeHost = host.querySelector("#mh-gauges");
    gaugeHost.innerHTML = dials.map(() => `<div></div>`).join("");
    dials.forEach(([key, value, dp], i) => {
      const spec = S[key];
      /* colour the dial by how close the value is to its own range top */
      const frac = (value - spec.min) / (spec.max - spec.min);
      const color = key === "tool_wear"
        ? W.stressColor(value / 240)
        : (frac > 0.92 || frac < 0.08 ? "#f59e0b" : "#38bdf8");
      W.gauge(gaugeHost.children[i], {
        value, min: spec.min, max: spec.max,
        label: spec.label, unit: spec.unit, color, size: 148, decimals: dp,
      });
    });

    /* ---- health ring + RUL ---- */
    W.healthRing(host.querySelector("#mh-ring"), r.health.index || 0);

    const rul = r.rul || {};
    const rulColor = rul.unbounded ? "#22c55e"
      : (rul.hours < 3 ? "#ef4444" : rul.hours < 10 ? "#f59e0b" : "#38bdf8");
    host.querySelector("#mh-rul").innerHTML = `
      <div class="label small muted" style="letter-spacing:1.1px;text-transform:uppercase;font-weight:700">
        Remaining Useful Life</div>
      <div class="mono" style="font-size:33px;font-weight:700;color:${rulColor};line-height:1.15">
        ${App.rulText(rul)}</div>
      <div class="small muted">${App.rulNote(rul)}</div>`;

    /* ---- stress bars ---- */
    if (r.physics.stress) {
      W.stressBars(host.querySelector("#mh-stress"), r.physics.stress, r.physics.dominant_mode);
    }

    /* ---- probabilities ---- */
    if (r.prediction.probabilities) {
      W.probBars(host.querySelector("#mh-probs"), r.prediction.probabilities, r.prediction.class);
    }

    /* ---- alarm banner ---- */
    banner(r);

    /* ---- ground truth ---- */
    truth(r);

    const cycleEl = host.querySelector("#mh-cycle");
    if (cycleEl && r.simulation) {
      cycleEl.textContent = ` — reading ${r.simulation.position} / ${r.simulation.total}`;
    }
  }

  function banner(r) {
    const a = r.alarm || {};
    const level = a.level || "NORMAL";
    const icons = { NORMAL: "✓", ADVISORY: "ℹ", WARNING: "▲", CRITICAL: "⛔" };
    const color = W.LEVEL_COLORS[level];

    host.querySelector("#mh-banner").innerHTML = `
      <div class="alarm-banner ${level}">
        <div class="ab-icon" style="color:${color}">${icons[level] || "•"}</div>
        <div class="ab-body">
          <div class="ab-title" style="color:${color}">
            ${level}${a.mode_name ? " — " + App.escapeHTML(a.mode_name) : ""}
            ${a.predicted ? `<span class="badge ADVISORY" style="margin-left:8px">PREDICTED</span>` : ""}
            ${a.has_breached ? `<span class="badge CRITICAL" style="margin-left:8px">LIMIT BREACHED</span>` : ""}
          </div>
          <div class="ab-msg">${App.escapeHTML(a.message || "")}</div>
          ${a.recommended_action && level !== "NORMAL"
            ? `<div class="ab-msg" style="margin-top:6px">
                 <b style="color:var(--text)">Action:</b> ${App.escapeHTML(a.recommended_action)}</div>`
            : ""}
        </div>
      </div>`;
  }

  /* The honest panel: show what actually happens to this machine, so
     the viewer can judge the prediction instead of trusting it. */
  function truth(r) {
    const el = host.querySelector("#mh-truth");
    if (!el) return;
    const g = r.ground_truth;

    if (!g) {
      el.innerHTML = `<div class="small muted">
        Ground truth is only available while replaying a dataset trajectory.</div>`;
      return;
    }

    const lead = g.readings_to_failure;
    const correct = g.correct;

    el.innerHTML = `
      <div class="grid cols-4">
        <div>
          <div class="small muted">Model says</div>
          <div class="mono" style="font-size:19px;font-weight:700;color:${
            r.prediction.class === "Normal" ? "var(--ok)" : "var(--warn)"}">
            ${r.prediction.class}</div>
        </div>
        <div>
          <div class="small muted">Actual state now</div>
          <div class="mono" style="font-size:19px;font-weight:700">${g.actual_class}</div>
        </div>
        <div>
          <div class="small muted">Will fail by</div>
          <div class="mono" style="font-size:19px;font-weight:700;color:var(--crit)">
            ${g.eventual_failure_mode || "—"}</div>
        </div>
        <div>
          <div class="small muted">Time to failure</div>
          <div class="mono" style="font-size:19px;font-weight:700">
            ${lead === null || lead === undefined ? "—"
              : (lead <= 0 ? "FAILED" : `${lead} rdg · ${g.hours_to_failure} h`)}</div>
        </div>
      </div>
      <div class="mt small" style="color:${correct ? "var(--ok)" : "var(--warn)"}">
        ${correct
          ? "✓ Prediction matches the horizon label for this reading."
          : "✗ Prediction differs from the horizon label — often an EARLY warning outside the 15-reading label window."}
      </div>`;
  }

  /* ===============================================================
     CHARTS
     =============================================================== */
  function drawCharts() {
    if (!trail.length) return;
    const labels = trail.map((_, i) => String(i - trail.length + 1));

    W.lineChart(host.querySelector("#mh-chart-health"), {
      height: 200,
      labels,
      yMin: 0, yMax: 100,
      bands: [
        { from: 0,  to: 40,  color: "#ef4444" },
        { from: 40, to: 65,  color: "#f59e0b" },
        { from: 85, to: 100, color: "#22c55e" },
      ],
      series: [
        { name: "Health index", color: "#38bdf8",
          data: trail.map(t => t.health), fill: true, width: 2.4 },
        { name: "P(failure) %", color: "#ef4444",
          data: trail.map(t => t.p_fail === null || t.p_fail === undefined ? null : t.p_fail * 100),
          dash: "5 4" },
      ],
    });

    /* the governing physical quantities, each normalised to its own
       limit so four different units share one axis honestly */
    const T = reference.thresholds;
    W.lineChart(host.querySelector("#mh-chart-physics"), {
      height: 200,
      labels,
      yMin: 0, yMax: 120,
      bands: [{ from: 100, to: 120, color: "#ef4444" }],
      series: [
        { name: "Tool wear (% of 240 min)", color: "#f59e0b",
          data: trail.map(t => pct(t.tool_wear, T.tool_wear_max)) },
        { name: "Power (% of 9000 W)", color: "#a78bfa",
          data: trail.map(t => pct(t.power, T.power_max)) },
        { name: "Strain (% of limit)", color: "#38bdf8",
          data: trail.map(t => pct(t.strain, T.osf_limit.M)) },
        { name: "Overall stress %", color: "#ef4444",
          data: trail.map(t => t.stress === null || t.stress === undefined ? null : t.stress * 100),
          width: 2.4 },
      ],
    });
  }

  const pct = (v, limit) =>
    (v === null || v === undefined || !isFinite(v)) ? null : (v / limit) * 100;

  /* ===============================================================
     CONTROLS
     =============================================================== */
  async function start() {
    try {
      await API.simStart({
        machine_id: machineId, source_machine: machineId,
        interval: 1.0, loop: false, restart: true,
      });
      trail = [];
      App.toast(`${machineId}: replay started.`, "ok");
      connect();
    } catch (err) {
      App.toast(err.message, "err");
    }
  }

  async function stop() {
    try {
      await API.simStop(machineId);
      App.toast(`${machineId}: replay stopped.`);
    } catch (err) {
      App.toast(err.message, "err");
    }
  }

  function updateStatusLine(s) {
    const el = host.querySelector("#mh-sub");
    if (!el) return;
    if (!s) {
      el.innerHTML = `Not currently replaying. Press <b>START</b> to begin.`;
      return;
    }
    const lead = s.lead_time_readings;
    el.innerHTML = `
      Replaying <b class="mono">${App.escapeHTML(s.source_machine)}</b> ·
      reading <b>${s.position}/${s.total}</b> (${s.progress_pct}%) ·
      ${s.running ? `<span style="color:var(--ok)">● RUNNING</span>`
                  : `<span style="color:var(--muted)">■ ${s.finished ? "finished" : "stopped"}</span>`}
      ${s.eventual_failure_mode
        ? ` · true failure <b style="color:var(--crit)">${s.eventual_failure_mode}</b> at cycle ${s.fails_at_cycle}`
        : ""}
      ${lead ? ` · <b style="color:var(--ok)">first warned ${lead} readings (${s.lead_time_hours} h) ahead</b>` : ""}`;
  }

  return { enter, leave };
})();
