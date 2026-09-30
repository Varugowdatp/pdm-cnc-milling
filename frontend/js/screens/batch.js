/* ==================================================================
   SCREEN 4 — BATCH ANALYSIS
   ==================================================================
   Upload a CSV or Excel file of readings, score every row, and get an
   annotated file back.

   The download is built in the browser from the JSON response rather
   than fetched from a second endpoint: the data is already here, so a
   round trip would only add a way for the two to disagree.
   ================================================================== */

SCREENS.batch = (() => {

  let host = null;
  let lastResult = null;
  let filter = "all";

  function enter(_param, el) {
    host = el;
    render();
  }

  function render() {
    host.innerHTML = `
      <div class="screen-head">
        <div>
          <h2>Batch Analysis</h2>
          <p class="sub">
            Score a whole file of readings at once. Accepts the canonical column names and
            the raw UCI AI4I spellings (<span class="mono small">Air temperature [K]</span>,
            <span class="mono small">Type</span>, …). Rows that cannot be parsed are reported
            individually rather than failing the upload.
          </p>
        </div>
        <div class="btn-row">
          <a class="btn ghost" href="/api/predict/template" download>⬇ CSV Template</a>
        </div>
      </div>

      <div class="panel">
        <div class="drop-zone" id="b-drop">
          <span class="big">📄</span>
          <b>Drop a CSV or Excel file here</b><br />
          <span class="small muted">or click to choose · max 25 MB · 20,000 rows</span>
          <input type="file" id="b-file" accept=".csv,.xlsx,.xls" hidden />
        </div>
        <div class="btn-row mt">
          <label class="small muted" style="display:flex;align-items:center;gap:7px">
            <input type="checkbox" id="b-explain" style="width:auto" />
            include per-row explanation (slower)
          </label>
          <span class="spacer"></span>
          <button class="btn ghost" id="b-sample">Use dataset sample</button>
        </div>
      </div>

      <div id="b-out" class="mt"></div>`;

    const drop = host.querySelector("#b-drop");
    const input = host.querySelector("#b-file");

    drop.onclick = () => input.click();
    input.onchange = () => input.files[0] && upload(input.files[0]);

    ["dragenter", "dragover"].forEach(ev =>
      drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add("over"); }));
    ["dragleave", "drop"].forEach(ev =>
      drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove("over"); }));
    drop.addEventListener("drop", e => {
      const f = e.dataTransfer.files[0];
      if (f) upload(f);
    });

    host.querySelector("#b-sample").onclick = useSample;
  }

  /* Pull a real run-to-failure trajectory from the backend so the screen
     is demonstrable without the user having a CSV to hand - and so what
     they see is an actual machine degrading, not a single synthetic row. */
  async function useSample() {
    const btn = host.querySelector("#b-sample");
    btn.disabled = true;
    btn.textContent = "Fetching…";
    try {
      const res = await fetch("/api/predict/sample?rows=300");
      if (!res.ok) throw new Error("Could not fetch the sample trajectory.");
      const text = await res.text();
      await upload(new File([text], "sample_run_to_failure.csv", { type: "text/csv" }));
    } catch (err) {
      App.toast(err.message, "err");
    } finally {
      btn.disabled = false;
      btn.textContent = "Use dataset sample";
    }
  }

  async function upload(file) {
    const out = host.querySelector("#b-out");
    out.innerHTML = `<div class="panel"><div class="empty">
        <span class="big">⏳</span>Scoring <b>${App.escapeHTML(file.name)}</b>…</div></div>`;

    const explain = host.querySelector("#b-explain").checked;
    try {
      lastResult = await API.predictBatch(file, { explain });
      filter = "all";
      paint();
    } catch (err) {
      out.innerHTML = App.errorPanel(err.message);
    }
  }

  /* ===============================================================
     RESULTS
     =============================================================== */
  function paint() {
    const r = lastResult;
    const s = r.summary;
    const out = host.querySelector("#b-out");

    const lv = s.by_alarm_level || {};
    const kpis = [
      { label: "Rows scored", value: s.total, note: r.rows_rejected
          ? `${r.rows_rejected} rejected` : "all rows valid", cls: "" },
      { label: "Failure predicted", value: s.predicted_failure,
        note: `${s.failure_rate_pct}% of rows`, cls: s.predicted_failure ? "warn" : "ok" },
      { label: "Mean health", value: s.mean_health,
        cls: s.mean_health >= 85 ? "ok" : s.mean_health >= 40 ? "warn" : "crit", note: "across the file" },
      { label: "Critical", value: lv.CRITICAL || 0, note: "readings in alarm",
        cls: (lv.CRITICAL || 0) ? "crit" : "ok" },
      { label: "Machines", value: s.machines || "—", note: "distinct IDs", cls: "" },
    ];

    out.innerHTML = `
      <div class="grid cols-5">${kpis.map(k => `
        <div class="kpi ${k.cls}">
          <div class="label">${k.label}</div>
          <div class="value">${k.value}</div>
          <div class="note">${k.note}</div>
        </div>`).join("")}
      </div>

      ${r.rows_rejected ? `
        <div class="panel mt">
          <h3>Rejected Rows (${r.rows_rejected})</h3>
          <div class="small muted">
            ${r.errors.map(e => `Row ${e.row}: ${App.escapeHTML(e.error)}`).join("<br/>")}
            ${r.rows_rejected > r.errors.length
              ? `<br/>… and ${r.rows_rejected - r.errors.length} more.` : ""}
          </div>
        </div>` : ""}

      <div class="grid cols-2 mt">
        <div class="panel">
          <h3>Predicted Class Distribution</h3>
          <div id="b-classes"></div>
        </div>
        <div class="panel">
          <h3>Health Across the File</h3>
          <div id="b-chart"></div>
        </div>
      </div>

      <div class="panel mt">
        <h3>
          Scored Readings
          <span style="display:flex;gap:6px">
            ${["all", "CRITICAL", "WARNING", "ADVISORY", "NORMAL"].map(f =>
              `<button class="btn sm ${filter === f ? "primary" : "ghost"}" data-filter="${f}">
                 ${f === "all" ? "All" : f}</button>`).join("")}
            <button class="btn sm" id="b-dl">⬇ Annotated CSV</button>
          </span>
        </h3>
        <div id="b-table"></div>
      </div>`;

    /* class distribution as bars */
    const total = s.total || 1;
    const colors = { Normal: "#22c55e", TWF: "#f59e0b", HDF: "#ef4444", PWF: "#a78bfa", OSF: "#38bdf8" };
    out.querySelector("#b-classes").innerHTML = Object.entries(s.by_class)
      .sort((a, b) => b[1] - a[1])
      .map(([cls, n]) => {
        const pct = (n / total * 100);
        return `
          <div class="driver">
            <div class="driver-head"><span>${cls}</span>
              <span class="dv">${n.toLocaleString()} · ${pct.toFixed(1)}%</span></div>
            <div class="bar"><span style="width:${pct}%;background:${colors[cls] || "#94a3b8"}"></span></div>
          </div>`;
      }).join("");

    /* health trace over the file */
    W.lineChart(out.querySelector("#b-chart"), {
      height: 190, yMin: 0, yMax: 100,
      bands: [{ from: 0, to: 40, color: "#ef4444" }, { from: 40, to: 65, color: "#f59e0b" }],
      labels: r.results.map((_, i) => String(i + 1)),
      series: [{ name: "Health", color: "#38bdf8", fill: true,
                 data: r.results.map(x => x.health_index) }],
      showLegend: false,
    });

    renderTable();

    out.querySelectorAll("[data-filter]").forEach(b =>
      b.onclick = () => { filter = b.dataset.filter; paint(); });
    out.querySelector("#b-dl").onclick = download;
  }

  function renderTable() {
    const rows = filter === "all"
      ? lastResult.results
      : lastResult.results.filter(r => r.alarm_level === filter);

    const el = host.querySelector("#b-table");
    if (!rows.length) {
      el.innerHTML = `<div class="empty small">No rows at this level.</div>`;
      return;
    }

    const shown = rows.slice(0, 400);
    el.innerHTML = `
      <div class="tbl-wrap" style="max-height:460px;overflow-y:auto">
        <table>
          <thead><tr>
            <th>Row</th><th>Machine</th><th>Type</th>
            <th>Air K</th><th>Proc K</th><th>RPM</th><th>Torque</th><th>Wear</th>
            <th>Prediction</th><th>Conf.</th><th>Health</th><th>RUL h</th><th>Alarm</th>
          </tr></thead>
          <tbody>
            ${shown.map(r => `
              <tr class="row-${r.alarm_level}">
                <td class="num">${r.row}</td>
                <td class="mono">${App.escapeHTML(r.machine_id || "—")}</td>
                <td>${r.machine_type}</td>
                <td class="num">${r.air_temperature.toFixed(1)}</td>
                <td class="num">${r.process_temperature.toFixed(1)}</td>
                <td class="num">${r.rotational_speed.toFixed(0)}</td>
                <td class="num">${r.torque.toFixed(1)}</td>
                <td class="num">${r.tool_wear.toFixed(0)}</td>
                <td><b style="color:${r.is_failure_predicted ? "var(--warn)" : "var(--ok)"}">
                  ${r.predicted_class}</b></td>
                <td class="num">${(r.confidence * 100).toFixed(0)}%</td>
                <td class="num" style="color:${W.healthColor(r.health_index)}">
                  ${r.health_index.toFixed(0)}</td>
                <td class="num">${r.rul_hours >= 166 ? "stable" : r.rul_hours.toFixed(1)}</td>
                <td><span class="badge ${r.alarm_level}">${r.alarm_level}</span></td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>
      ${rows.length > shown.length
        ? `<p class="small muted mt" style="margin-bottom:0">
             Showing the first ${shown.length.toLocaleString()} of
             ${rows.length.toLocaleString()} rows. Download the CSV for the full set.</p>`
        : ""}`;
  }

  /* Build the annotated CSV in the browser from the response we already
     hold - no second request, so the file and the table cannot diverge. */
  function download() {
    const rows = lastResult.results;
    if (!rows.length) return;

    const skip = new Set(["explanation"]);
    const cols = Object.keys(rows[0]).filter(c => !skip.has(c));

    const esc = v => {
      if (v === null || v === undefined) return "";
      const s = String(v);
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };

    const csv = [cols.join(","), ...rows.map(r => cols.map(c => esc(r[c])).join(","))].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = (lastResult.filename || "batch").replace(/\.[^.]+$/, "") + "_scored.csv";
    a.click();
    URL.revokeObjectURL(url);
    App.toast(`Downloaded ${rows.length.toLocaleString()} scored rows.`, "ok");
  }

  return { enter };
})();
