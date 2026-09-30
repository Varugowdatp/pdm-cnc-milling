/* ==================================================================
   SCREEN 5 — ALARMS & MAINTENANCE LOG
   ==================================================================
   The operator's action list. The backend logs an alarm only when the
   band or mechanism CHANGES, so this is a list of events rather than a
   wall of duplicates — which is what makes the unacknowledged count
   meaningful.
   ================================================================== */

SCREENS.alarms = (() => {

  let host = null;
  let timer = null;
  let state = { level: "", unacked: false, machine: "" };

  function enter(_param, el) {
    host = el;
    render();
    refresh();
    timer = setInterval(refresh, 5000);
  }

  function leave() {
    clearInterval(timer);
    timer = null;
  }

  function render() {
    host.innerHTML = `
      <div class="screen-head">
        <div>
          <h2>Alarms &amp; Maintenance Log</h2>
          <p class="sub">
            One entry per alarm <b>event</b> — a machine sitting in CRITICAL for forty
            readings is one event, not forty. A <b>PREDICTED</b> alarm means act now while
            the machine still runs; a <b>BREACHED</b> alarm reports a limit already crossed.
          </p>
        </div>
        <div class="btn-row">
          <button class="btn" id="al-ackall">✓ Acknowledge All</button>
        </div>
      </div>

      <div class="panel">
        <h3>
          Filters
          <span style="display:flex;gap:6px;align-items:center">
            <input type="text" id="al-machine" placeholder="machine id…"
                   style="width:150px;padding:5px 9px;font-size:12px" />
            <label class="small muted" style="display:flex;align-items:center;gap:6px">
              <input type="checkbox" id="al-unacked" style="width:auto" /> open only
            </label>
          </span>
        </h3>
        <div class="btn-row" id="al-levels">
          ${["", "CRITICAL", "WARNING", "ADVISORY"].map(l =>
            `<button class="btn sm ${l === state.level ? "primary" : "ghost"}"
                     data-level="${l}">${l || "All levels"}</button>`).join("")}
        </div>
      </div>

      <div class="grid cols-4 mt" id="al-kpis"></div>
      <div class="panel mt"><div id="al-list"></div></div>`;

    host.querySelectorAll("[data-level]").forEach(b => b.onclick = () => {
      state.level = b.dataset.level;
      host.querySelectorAll("[data-level]").forEach(x =>
        x.classList.toggle("primary", x.dataset.level === state.level));
      host.querySelectorAll("[data-level]").forEach(x =>
        x.classList.toggle("ghost", x.dataset.level !== state.level));
      refresh();
    });

    host.querySelector("#al-unacked").onchange = e => {
      state.unacked = e.target.checked;
      refresh();
    };

    let debounce;
    host.querySelector("#al-machine").oninput = e => {
      clearTimeout(debounce);
      state.machine = e.target.value.trim();
      debounce = setTimeout(refresh, 350);
    };

    host.querySelector("#al-ackall").onclick = async () => {
      const n = await API.ackAll(state.machine || null);
      App.toast(`Acknowledged ${n.acknowledged} alarm(s).`, "ok");
      refresh();
    };
  }

  async function refresh() {
    if (!host || host.hidden) return;
    try {
      const data = await API.alarms({
        level: state.level || undefined,
        unacknowledged_only: state.unacked,
        machine_id: state.machine || undefined,
        limit: 300,
      });
      paint(data.alarms);
    } catch (err) {
      host.querySelector("#al-list").innerHTML = App.errorPanel(err.message);
    }
  }

  function paint(alarms) {
    const counts = { CRITICAL: 0, WARNING: 0, ADVISORY: 0, open: 0 };
    alarms.forEach(a => {
      counts[a.level] = (counts[a.level] || 0) + 1;
      if (!a.acknowledged) counts.open++;
    });

    host.querySelector("#al-kpis").innerHTML = [
      { label: "Total events", value: alarms.length, cls: "" },
      { label: "Critical", value: counts.CRITICAL, cls: counts.CRITICAL ? "crit" : "ok" },
      { label: "Warning", value: counts.WARNING, cls: counts.WARNING ? "warn" : "ok" },
      { label: "Unacknowledged", value: counts.open, cls: counts.open ? "warn" : "ok" },
    ].map(k => `
      <div class="kpi ${k.cls}">
        <div class="label">${k.label}</div>
        <div class="value">${k.value}</div>
      </div>`).join("");

    const el = host.querySelector("#al-list");
    if (!alarms.length) {
      el.innerHTML = `<div class="empty">
        <span class="big">✓</span><b>No alarms match this filter.</b><br/>
        <span class="small">Either the plant is healthy, or nothing is being monitored yet.</span>
      </div>`;
      return;
    }

    el.innerHTML = `
      <div class="tbl-wrap" style="max-height:600px;overflow-y:auto">
        <table>
          <thead><tr>
            <th>Time</th><th>Machine</th><th>Level</th><th>Mechanism</th>
            <th style="white-space:normal;min-width:320px">Message &amp; Action</th>
            <th>Health</th><th>RUL</th><th></th>
          </tr></thead>
          <tbody>
            ${alarms.map(a => `
              <tr class="row-${a.level} ${a.acknowledged ? "acked" : ""}">
                <td class="mono small">${App.dateTime(a.ts)}</td>
                <td class="mono"><a href="#/machine/${encodeURIComponent(a.machine_id)}"
                       style="color:var(--accent);text-decoration:none">${App.escapeHTML(a.machine_id)}</a></td>
                <td><span class="badge ${a.level}">${a.level}</span></td>
                <td>${App.escapeHTML(a.mode || "—")}</td>
                <td style="white-space:normal">
                  ${App.escapeHTML(a.message || "")}
                  <div class="small muted" style="margin-top:4px">
                    <b>Action:</b> ${App.escapeHTML(a.recommended_action || "—")}</div>
                </td>
                <td class="num" style="color:${a.health_index !== null
                    ? W.healthColor(a.health_index) : "inherit"}">
                  ${a.health_index === null ? "—" : a.health_index.toFixed(0)}</td>
                <td class="num">${a.rul_hours === null ? "—"
                    : (a.rul_hours >= 166 ? "stable" : a.rul_hours.toFixed(1) + " h")}</td>
                <td>${a.acknowledged
                    ? `<span class="small muted" title="${App.escapeHTML(a.acknowledged_at || "")}">
                         ✓ ${App.escapeHTML(a.acknowledged_by || "")}</span>`
                    : `<button class="btn sm" data-ack="${a.id}">Acknowledge</button>`}</td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>`;

    el.querySelectorAll("[data-ack]").forEach(b => b.onclick = async () => {
      b.disabled = true;
      try {
        await API.ackAlarm(b.dataset.ack);
        refresh();
      } catch (err) {
        App.toast(err.message, "err");
        b.disabled = false;
      }
    });
  }

  return { enter, leave };
})();
