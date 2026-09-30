/* ==================================================================
   SVG WIDGETS  —  gauges, rings, charts
   ==================================================================
   Everything is hand-drawn SVG with NO charting library.

   That is a deliberate reliability decision, not minimalism for its
   own sake. A CDN chart library would make this demo depend on
   working internet at the moment it is presented; an offline projector
   in a lab would show a page of blank rectangles. Hand-drawn SVG has
   no dependency, no build step and no failure mode beyond the browser
   itself - and it lets the gauges look like real HMI instruments
   rather than a business dashboard.
   ================================================================== */

const W = (() => {

  const NS = "http://www.w3.org/2000/svg";
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

  /* ---------------------------------------------------------------
     Colour helpers - bands come from the backend, never hard-coded
     --------------------------------------------------------------- */
  let BANDS = [
    { min: 85, max: 100, level: "NORMAL",   color: "#22c55e", label: "Healthy" },
    { min: 65, max: 85,  level: "ADVISORY", color: "#38bdf8", label: "Monitor" },
    { min: 40, max: 65,  level: "WARNING",  color: "#f59e0b", label: "Degrading" },
    { min: 0,  max: 40,  level: "CRITICAL", color: "#ef4444", label: "Critical" },
  ];

  function setBands(bands) { if (bands && bands.length) BANDS = bands; }

  function healthColor(v) {
    const b = BANDS.find(b => v >= b.min && v <= b.max);
    return b ? b.color : "#94a3b8";
  }
  function healthLabel(v) {
    const b = BANDS.find(b => v >= b.min && v <= b.max);
    return b ? b.label : "Unknown";
  }

  const LEVEL_COLORS = {
    NORMAL: "#22c55e", ADVISORY: "#38bdf8",
    WARNING: "#f59e0b", CRITICAL: "#ef4444",
  };

  /* stress 0..1 -> colour, matching the alarm bands */
  function stressColor(s) {
    if (s >= 0.97) return "#ef4444";
    if (s >= 0.85) return "#f59e0b";
    if (s >= 0.70) return "#38bdf8";
    return "#22c55e";
  }

  /* ===============================================================
     ANALOGUE DIAL  —  one sensor
     ===============================================================
     A 240-degree sweep with a swinging needle, the way a real panel
     instrument reads. The coloured arc shows where the value sits in
     its operating range so an operator can judge it without reading
     the number.
     =============================================================== */
  function gauge(container, opts) {
    const {
      value = 0, min = 0, max = 100,
      label = "", unit = "", color = "#38bdf8",
      size = 150, decimals = 1,
    } = opts;

    const v = clamp(value, min, max);
    const frac = (max - min) ? (v - min) / (max - min) : 0;

    /* Sweep geometry.
       polar() puts 0 deg at the TOP and increases clockwise, so a
       240-degree dial that opens at the bottom must run from -120
       (lower-left) through 0 (top) to +120 (lower-right).

       This was originally -210, which swept the arc around the LEFT of
       the dial and left the gap on the right-hand side - visible only
       once the page was screenshotted in a real browser. */
    const START = -120, SWEEP = 240;                // degrees
    const angle = START + frac * SWEEP;
    const R = 74, CX = 100, CY = 100;

    const arc = (from, to, r) => {
      const p1 = polar(CX, CY, r, from), p2 = polar(CX, CY, r, to);
      const large = (to - from) > 180 ? 1 : 0;
      return `M ${p1.x} ${p1.y} A ${r} ${r} 0 ${large} 1 ${p2.x} ${p2.y}`;
    };

    /* tick marks every 1/8 of the sweep */
    let ticks = "";
    for (let i = 0; i <= 8; i++) {
      const a = START + (i / 8) * SWEEP;
      const outer = polar(CX, CY, R + 7, a);
      const inner = polar(CX, CY, R + (i % 2 ? 1 : -2), a);
      ticks += `<line x1="${inner.x}" y1="${inner.y}" x2="${outer.x}" y2="${outer.y}"
                      stroke="${i % 2 ? "#2b3f5f" : "#4a6285"}"
                      stroke-width="${i % 2 ? 1.4 : 2.4}" />`;
    }

    const needle = polar(CX, CY, R - 9, angle);

    container.innerHTML = `
      <div class="gauge-wrap">
        <svg viewBox="0 0 200 172" width="${size}" height="${size * 0.86}" role="img"
             aria-label="${label}: ${v.toFixed(decimals)} ${unit}">
          ${ticks}
          <path d="${arc(START, START + SWEEP, R)}" fill="none"
                stroke="#1e2d45" stroke-width="11" stroke-linecap="round" />
          <path d="${arc(START, angle, R)}" fill="none"
                stroke="${color}" stroke-width="11" stroke-linecap="round"
                style="transition: d .6s ease" />
          <line class="needle" x1="${CX}" y1="${CY}" x2="${needle.x}" y2="${needle.y}"
                stroke="${color}" stroke-width="2.8" stroke-linecap="round" />
          <circle cx="${CX}" cy="${CY}" r="7"  fill="#111c2e" stroke="${color}" stroke-width="2.4" />
          <circle cx="${CX}" cy="${CY}" r="2.4" fill="${color}" />
          <text x="${CX}" y="139" text-anchor="middle" class="gauge-value"
                fill="#e2e8f0">${fmt(v, decimals)}</text>
          <text x="${CX}" y="155" text-anchor="middle" class="gauge-unit"
                fill="#94a3b8">${unit}</text>
        </svg>
        <div class="gauge-label">${label}</div>
      </div>`;
  }

  function polar(cx, cy, r, deg) {
    const rad = (deg - 90) * Math.PI / 180;
    return { x: +(cx + r * Math.cos(rad)).toFixed(2),
             y: +(cy + r * Math.sin(rad)).toFixed(2) };
  }

  /* ===============================================================
     HEALTH RING  —  the machine's headline number
     =============================================================== */
  function healthRing(container, value, { size = 190, sublabel = "" } = {}) {
    const v = clamp(value, 0, 100);
    const color = healthColor(v);
    const R = 76, C = 2 * Math.PI * R;
    const dash = (v / 100) * C;

    container.innerHTML = `
      <div class="gauge-wrap">
        <svg viewBox="0 0 200 200" width="${size}" height="${size}" role="img"
             aria-label="Health index ${v}">
          <circle cx="100" cy="100" r="${R}" fill="none" stroke="#1e2d45" stroke-width="15" />
          <circle class="ring-progress" cx="100" cy="100" r="${R}" fill="none"
                  stroke="${color}" stroke-width="15" stroke-linecap="round"
                  stroke-dasharray="${dash} ${C}"
                  transform="rotate(-90 100 100)"
                  style="filter: drop-shadow(0 0 7px ${color}88)" />
          <text x="100" y="94" text-anchor="middle"
                style="font-family:var(--mono);font-size:41px;font-weight:700"
                fill="${color}">${v.toFixed(0)}</text>
          <text x="100" y="115" text-anchor="middle"
                style="font-size:11px;letter-spacing:1.4px" fill="#94a3b8">HEALTH INDEX</text>
          <text x="100" y="136" text-anchor="middle"
                style="font-size:12.5px;font-weight:700;letter-spacing:.6px"
                fill="${color}">${healthLabel(v).toUpperCase()}</text>
          ${sublabel ? `<text x="100" y="154" text-anchor="middle"
                              style="font-size:10.5px" fill="#94a3b8">${sublabel}</text>` : ""}
        </svg>
      </div>`;
  }

  /* ===============================================================
     STRESS BARS  —  the four failure mechanisms side by side
     =============================================================== */
  function stressBars(container, stress, dominant) {
    const order = ["TWF", "HDF", "PWF", "OSF"];
    const names = { TWF: "Tool Wear", HDF: "Heat Dissip.", PWF: "Power", OSF: "Overstrain" };

    container.innerHTML = order.map(mode => {
      const v = stress[mode] || 0;
      const pct = (v * 100).toFixed(0);
      const col = stressColor(v);
      const isDom = mode === dominant;
      return `
        <div class="driver">
          <div class="driver-head">
            <span>${names[mode]}
              ${isDom ? `<span class="badge" style="color:${col};border-color:${col}66;background:${col}18;margin-left:5px">DOMINANT</span>` : ""}
            </span>
            <span class="dv" style="color:${col}">${pct}%</span>
          </div>
          <div class="bar"><span style="width:${pct}%;background:${col}"></span></div>
        </div>`;
    }).join("");
  }

  /* ===============================================================
     LINE CHART  —  multi-series trend
     ===============================================================
     Handles nulls by breaking the path, keeps a fixed viewBox and
     scales via CSS so it stays crisp at any panel width.
     =============================================================== */
  function lineChart(container, opts) {
    const {
      series = [],          // [{name, data:[], color, axis:'left'|'right'}]
      labels = [],
      height = 210,
      yMin = null, yMax = null,
      bands = null,         // [{from,to,color}] horizontal shading
      showLegend = true,
    } = opts;

    const VW = 800, VH = height;
    const PAD = { l: 46, r: 14, t: 12, b: 26 };
    const plotW = VW - PAD.l - PAD.r;
    const plotH = VH - PAD.t - PAD.b;

    const all = series.flatMap(s => s.data).filter(v => v !== null && v !== undefined && isFinite(v));
    if (!all.length) {
      container.innerHTML = `<div class="empty small">No data yet.</div>`;
      return;
    }

    let lo = yMin !== null ? yMin : Math.min(...all);
    let hi = yMax !== null ? yMax : Math.max(...all);
    if (lo === hi) { lo -= 1; hi += 1; }
    const pad = (hi - lo) * 0.08;
    if (yMin === null) lo -= pad;
    if (yMax === null) hi += pad;

    const n = Math.max(...series.map(s => s.data.length), 1);
    const X = i => PAD.l + (n === 1 ? plotW / 2 : (i / (n - 1)) * plotW);
    const Y = v => PAD.t + plotH - ((v - lo) / (hi - lo)) * plotH;

    /* grid + y labels */
    let grid = "";
    for (let i = 0; i <= 4; i++) {
      const y = PAD.t + (i / 4) * plotH;
      const val = hi - (i / 4) * (hi - lo);
      grid += `<line x1="${PAD.l}" y1="${y.toFixed(1)}" x2="${VW - PAD.r}" y2="${y.toFixed(1)}"
                     stroke="#1e2d45" stroke-width="1" />
               <text x="${PAD.l - 7}" y="${(y + 3.5).toFixed(1)}" text-anchor="end"
                     style="font-size:10px;font-family:var(--mono)" fill="#94a3b8">${fmtAxis(val)}</text>`;
    }

    /* horizontal bands (e.g. alarm zones) */
    let bandEls = "";
    (bands || []).forEach(b => {
      const y1 = Y(Math.min(b.to, hi)), y2 = Y(Math.max(b.from, lo));
      if (y2 > y1) bandEls += `<rect x="${PAD.l}" y="${y1.toFixed(1)}" width="${plotW}"
                                     height="${(y2 - y1).toFixed(1)}" fill="${b.color}" opacity="0.10" />`;
    });

    /* x labels: first, middle, last */
    let xlabels = "";
    if (labels.length) {
      [0, Math.floor(n / 2), n - 1].forEach(i => {
        if (labels[i] === undefined) return;
        const anchor = i === 0 ? "start" : (i === n - 1 ? "end" : "middle");
        xlabels += `<text x="${X(i).toFixed(1)}" y="${VH - 8}" text-anchor="${anchor}"
                          style="font-size:10px;font-family:var(--mono)" fill="#94a3b8">${labels[i]}</text>`;
      });
    }

    /* paths - break on null so gaps are honest, not interpolated */
    const paths = series.map(s => {
      let d = "", pen = false;
      s.data.forEach((v, i) => {
        if (v === null || v === undefined || !isFinite(v)) { pen = false; return; }
        d += `${pen ? "L" : "M"} ${X(i).toFixed(1)} ${Y(v).toFixed(1)} `;
        pen = true;
      });
      const last = lastPoint(s.data);
      const dot = last.i >= 0
        ? `<circle cx="${X(last.i).toFixed(1)}" cy="${Y(last.v).toFixed(1)}" r="3.2"
                   fill="${s.color}" style="filter:drop-shadow(0 0 5px ${s.color})" />`
        : "";
      const area = s.fill
        ? `<path d="${d} L ${X(last.i).toFixed(1)} ${(PAD.t + plotH).toFixed(1)} L ${X(0).toFixed(1)} ${(PAD.t + plotH).toFixed(1)} Z"
                 fill="${s.color}" opacity="0.10" />`
        : "";
      return `${area}<path d="${d.trim()}" fill="none" stroke="${s.color}"
                          stroke-width="${s.width || 2}" stroke-linejoin="round"
                          stroke-linecap="round" ${s.dash ? `stroke-dasharray="${s.dash}"` : ""} />${dot}`;
    }).join("");

    const legend = showLegend && series.length > 1
      ? `<div class="legend" style="margin-top:8px">` +
        series.map(s => `<span><i style="background:${s.color}"></i>${s.name}</span>`).join("") +
        `</div>`
      : "";

    container.innerHTML = `
      <div class="chart-host">
        <svg viewBox="0 0 ${VW} ${VH}" preserveAspectRatio="none" style="height:${height}px">
          ${bandEls}${grid}${paths}${xlabels}
        </svg>
      </div>${legend}`;
  }

  function lastPoint(arr) {
    for (let i = arr.length - 1; i >= 0; i--) {
      const v = arr[i];
      if (v !== null && v !== undefined && isFinite(v)) return { i, v };
    }
    return { i: -1, v: 0 };
  }

  /* ===============================================================
     PROBABILITY BARS  —  the model's full opinion
     =============================================================== */
  function probBars(container, probabilities, predicted) {
    const entries = Object.entries(probabilities).sort((a, b) => b[1] - a[1]);
    const colors = {
      Normal: "#22c55e", TWF: "#f59e0b", HDF: "#ef4444",
      PWF: "#a78bfa", OSF: "#38bdf8",
    };
    container.innerHTML = entries.map(([cls, p]) => {
      const pct = (p * 100);
      const col = colors[cls] || "#94a3b8";
      const isPred = cls === predicted;
      return `
        <div class="driver">
          <div class="driver-head">
            <span style="${isPred ? "font-weight:700" : ""}">${cls}
              ${isPred ? `<span class="badge" style="color:${col};border-color:${col}66;background:${col}18;margin-left:5px">PREDICTED</span>` : ""}
            </span>
            <span class="dv">${pct.toFixed(1)}%</span>
          </div>
          <div class="bar"><span style="width:${pct}%;background:${col}"></span></div>
        </div>`;
    }).join("");
  }

  /* ===============================================================
     ATTRIBUTION BARS  —  signed, diverging from centre
     ===============================================================
     Contributions are signed, so a bar growing right means "pushed
     the prediction toward this class" and left means "pushed away".
     A single-sided bar chart would hide that distinction.
     =============================================================== */
  function driverBars(container, drivers) {
    if (!drivers || !drivers.length) {
      container.innerHTML = `<div class="empty small">No attribution available.</div>`;
      return;
    }
    const maxAbs = Math.max(...drivers.map(d => Math.abs(d.contribution))) || 1;

    container.innerHTML = drivers.map(d => {
      const w = (Math.abs(d.contribution) / maxAbs) * 50;   // % of half-width
      const pos = d.contribution > 0;
      const val = d.value === null ? "—" : `${fmt(d.value, 2)} ${d.unit || ""}`;
      return `
        <div class="driver">
          <div class="driver-head">
            <span>${d.label}</span>
            <span class="dv">${val} &nbsp;<b style="color:${pos ? "#ef4444" : "#22c55e"}">
              ${pos ? "+" : ""}${d.contribution.toFixed(3)}</b></span>
          </div>
          <div class="driver-track">
            <div class="zero"></div>
            <div class="fill ${pos ? "pos" : "neg"}" style="width:${w}%"></div>
          </div>
        </div>`;
    }).join("");
  }

  /* ===============================================================
     CONFUSION MATRIX
     =============================================================== */
  function confusionMatrix(container, cm) {
    const { labels, matrix } = cm;
    const rowTotals = matrix.map(r => r.reduce((a, b) => a + b, 0));

    const head = `<tr><th></th>${labels.map(l => `<th>${l}</th>`).join("")}<th>Recall</th></tr>`;
    const rows = matrix.map((row, i) => {
      const total = rowTotals[i] || 1;
      const cells = row.map((v, j) => {
        const frac = v / total;
        const correct = i === j;
        const bg = correct
          ? `rgba(34,197,94,${0.12 + frac * 0.55})`
          : (v > 0 ? `rgba(239,68,68,${0.08 + frac * 0.45})` : "transparent");
        return `<td class="num" style="background:${bg}"
                    title="${v} of ${total} true ${labels[i]} predicted as ${labels[j]}">
                  ${v.toLocaleString()}</td>`;
      }).join("");
      const recall = (row[i] / total * 100).toFixed(1);
      return `<tr><th style="text-align:left">${labels[i]}</th>${cells}
                  <td class="num"><b>${recall}%</b></td></tr>`;
    }).join("");

    container.innerHTML = `
      <div class="tbl-wrap">
        <table><thead>${head}</thead><tbody>${rows}</tbody></table>
      </div>
      <p class="small muted mt" style="margin-bottom:0">
        Rows are the true horizon label, columns the prediction. The green diagonal is
        correct; red off-diagonal cells are confusions.
      </p>`;
  }

  /* ---------------------------------------------------------------
     formatting
     --------------------------------------------------------------- */
  function fmt(v, dp = 1) {
    if (v === null || v === undefined || !isFinite(v)) return "—";
    const a = Math.abs(v);
    if (a >= 10000) return v.toFixed(0).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    if (a >= 1000)  return v.toFixed(0);
    return v.toFixed(dp);
  }
  function fmtAxis(v) {
    const a = Math.abs(v);
    if (a >= 10000) return (v / 1000).toFixed(0) + "k";
    if (a >= 100)   return v.toFixed(0);
    if (a >= 10)    return v.toFixed(1);
    return v.toFixed(2);
  }

  return {
    setBands, healthColor, healthLabel, stressColor, LEVEL_COLORS,
    gauge, healthRing, stressBars, lineChart, probBars, driverBars,
    confusionMatrix, fmt,
  };
})();
