/* ==================================================================
   SCREEN 1 — PLANT OVERVIEW
   ==================================================================
   The wall display. Every monitored machine as a status card, sorted
   worst-first by the backend so the machine that needs attention is
   always top-left. Refreshes on a timer.
   ================================================================== */

SCREENS.overview = (() => {

  let timer = null;
  let host = null;

  async function enter(_param, el) {
    host = el;
    render();                       // shell first, so it never looks frozen
    await refresh();
    timer = setInterval(refresh, 4000);
  }

  function leave() {
    clearInterval(timer);
    timer = null;
  }

  function render() {
    host.innerHTML = `
      <div class="screen-head">
        <div>
          <h2>Plant Overview</h2>
          <p class="sub">
            Live status of every monitored machine. A predicted failure class means the
            machine is <b>heading for</b> that failure within the prediction horizon —
            not that it has already failed.
          </p>
        </div>
        <div class="btn-row">
          <button class="btn" id="ov-demo">▶ Start Demo Plant</button>
          <button class="btn ghost" id="ov-stopall">■ Stop All</button>
          <button class="btn ghost danger" id="ov-reset">Reset Plant</button>
        </div>
      </div>

      <div class="grid cols-5" id="ov-kpis"></div>
      <div class="grid cols-4 mt" id="ov-cards"></div>`;

    host.querySelector("#ov-demo").onclick = startDemo;
    host.querySelector("#ov-stopall").onclick = async () => {
      await API.simStopAll();
      App.toast("All simulations stopped.");
      refresh();
    };
    host.querySelector("#ov-reset").onclick = async () => {
      if (!confirm("Clear every machine, reading and alarm?")) return;
      await API.reset();
      App.toast("Plant history cleared.", "ok");
      refresh();
    };
  }

  /* Spin up a few machines so the dashboard is never empty at a demo.
     Different speeds and different failure modes make the wall look
     like a real plant rather than four copies of one machine. */
  async function startDemo() {
    const btn = host.querySelector("#ov-demo");
    btn.disabled = true;
    btn.textContent = "Starting…";
    try {
      const { machines } = await API.catalogue(24);
      if (!machines.length) throw new Error("No trajectories available.");

      /* pick a spread of failure modes where possible */
      const picked = [];
      const seen = new Set();
      for (const m of machines) {
        if (!seen.has(m.failure_mode)) { picked.push(m); seen.add(m.failure_mode); }
        if (picked.length === 4) break;
      }
      while (picked.length < 4 && picked.length < machines.length) {
        const next = machines[picked.length];
        if (!picked.includes(next)) picked.push(next);
      }

      await Promise.all(picked.map((m, i) =>
        API.simStart({
          machine_id: `MACHINE-${String(i + 1).padStart(2, "0")}`,
          source_machine: m.machine_id,
          interval: [0.7, 1.0, 1.3, 1.6][i % 4],
          loop: false,
          restart: true,
        })));

      App.toast(`Started ${picked.length} machines: ${picked.map(p => p.failure_mode).join(", ")}`, "ok");
      refresh();
    } catch (err) {
      App.toast(err.message, "err");
    } finally {
      btn.disabled = false;
      btn.textContent = "▶ Start Demo Plant";
    }
  }

  async function refresh() {
    if (!host || host.hidden) return;
    let data;
    try {
      data = await API.machines();
    } catch (err) {
      host.querySelector("#ov-cards").innerHTML = App.errorPanel(err.message);
      return;
    }

    renderKPIs(data.summary);
    renderCards(data.machines);
  }

  function renderKPIs(s) {
    const lv = s.by_alarm_level || {};
    const kpis = [
      { label: "Machines", value: s.machines, note: "registered", cls: "" },
      { label: "Mean Health", value: s.mean_health ?? "—", note: "across the plant",
        cls: s.mean_health === null ? "" : (s.mean_health >= 85 ? "ok" : s.mean_health >= 65 ? "" : s.mean_health >= 40 ? "warn" : "crit") },
      { label: "At Risk", value: s.machines_at_risk, note: "failure predicted",
        cls: s.machines_at_risk > 0 ? "warn" : "ok" },
      { label: "Critical", value: lv.CRITICAL || 0, note: "machines in alarm",
        cls: (lv.CRITICAL || 0) > 0 ? "crit" : "ok" },
      { label: "Open Alarms", value: s.open_alarms, note: "unacknowledged",
        cls: s.open_alarms > 0 ? "warn" : "ok" },
    ];

    host.querySelector("#ov-kpis").innerHTML = kpis.map(k => `
      <div class="kpi ${k.cls}">
        <div class="label">${k.label}</div>
        <div class="value">${k.value}</div>
        <div class="note">${k.note}</div>
      </div>`).join("");
  }

  function renderCards(machines) {
    const el = host.querySelector("#ov-cards");

    if (!machines.length) {
      el.className = "mt";
      el.innerHTML = `
        <div class="panel">
          <div class="empty">
            <span class="big">🏭</span>
            <b>No machines are being monitored yet.</b><br />
            Press <b>Start Demo Plant</b> to replay real run-to-failure trajectories,
            or add readings from the <a href="#/manual" style="color:var(--accent)">Manual Input</a>
            panel.
          </div>
        </div>`;
      return;
    }

    el.className = "grid cols-4 mt";
    el.innerHTML = machines.map(card).join("");

    el.querySelectorAll("[data-machine]").forEach(node =>
      node.onclick = () => App.go("machine", node.dataset.machine));
  }

  function card(m) {
    const level = m.alarm_level || "NORMAL";
    const color = W.LEVEL_COLORS[level] || "#94a3b8";
    const health = m.health_index;
    const hColor = health === null || health === undefined ? "#94a3b8" : W.healthColor(health);
    const pred = m.predicted_class || "—";
    const predicting = pred !== "Normal" && pred !== "—";

    return `
      <div class="machine-card ${level}" data-machine="${App.escapeHTML(m.machine_id)}"
           style="--level-color:${color}">
        <div class="mc-head">
          <div>
            <div class="mc-id">${App.escapeHTML(m.machine_id)}</div>
            <div class="mc-type">Variant ${m.machine_type || "?"} ·
              ${m.reading_count || 0} readings</div>
          </div>
          <span class="led ${level === "CRITICAL" ? "blink" : ""}"></span>
        </div>

        <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:2px">
          <span class="mono" style="font-size:29px;font-weight:700;color:${hColor}">
            ${health === null || health === undefined ? "—" : health.toFixed(0)}</span>
          <span class="small muted">health</span>
          <span class="spacer"></span>
          <span class="badge ${level}">${level}</span>
        </div>
        <div class="bar">
          <span style="width:${health || 0}%;background:${hColor}"></span>
        </div>

        <div class="mc-row">
          <span>Prediction</span>
          <b style="color:${predicting ? color : "var(--ok)"}">${App.escapeHTML(pred)}</b>
        </div>
        <div class="mc-row">
          <span>Remaining life</span>
          <b>${App.rulText({ hours: m.rul_hours })}</b>
        </div>
        <div class="mc-row">
          <span>Tool wear</span>
          <b>${m.tool_wear === null || m.tool_wear === undefined ? "—" : m.tool_wear.toFixed(0) + " min"}</b>
        </div>
        <div class="mc-row">
          <span>Last seen</span>
          <b>${App.clockTime(m.last_seen)}</b>
        </div>

        ${m.open_alarms > 0
          ? `<div class="mc-row" style="margin-top:8px">
               <span class="badge WARNING">${m.open_alarms} open alarm${m.open_alarms > 1 ? "s" : ""}</span>
             </div>` : ""}
      </div>`;
  }

  return { enter, leave };
})();
