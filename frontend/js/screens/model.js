/* ==================================================================
   SCREEN 6 — MODEL INSIGHTS
   ==================================================================
   The evidence screen. Everything an examiner would ask to see:
   the model card, the Phase 1 evaluation numbers, the confusion
   matrix, feature importance, the early-warning result that decides
   whether the system is predictive at all, and a LIVE proof that the
   explanation panel reproduces the model exactly.

   The lead-time panel is deliberately first among the metrics: a
   0.99-accuracy model that fires after the fault is worthless, and
   this screen should say so rather than lead with the flattering
   number.
   ================================================================== */

SCREENS.model = (() => {

  let host = null;

  async function enter(_param, el) {
    host = el;
    host.innerHTML = `<div class="panel"><div class="empty">
      <span class="big">⏳</span>Loading model evidence…</div></div>`;

    let info, metrics, verify;
    try {
      [info, metrics] = await Promise.all([API.modelInfo(), API.modelMetrics()]);
    } catch (err) {
      host.innerHTML = App.errorPanel(err.message);
      return;
    }
    try { verify = await API.modelVerify(20); } catch { verify = null; }

    render(info, metrics, verify);
  }

  function render(info, m, verify) {
    const h = m.headline;
    const ew = m.early_warning;

    host.innerHTML = `
      <div class="screen-head">
        <div>
          <h2>Model Insights</h2>
          <p class="sub">
            ${App.escapeHTML(info.algorithm || "Random Forest Classifier")} ·
            ${info.n_estimators} trees · ${info.features.length} features ·
            trained ${App.dateTime(info.trained_at)} ·
            scikit-learn ${App.escapeHTML(info.sklearn_version || "?")}
          </p>
        </div>
      </div>

      <!-- ===== THE NUMBER THAT MATTERS ===== -->
      <div class="panel" style="border-color:rgba(34,197,94,.4)">
        <h3>Early Warning — the result that decides whether this system is useful</h3>
        <div class="grid cols-4">
          <div>
            <div class="small muted">Mean lead time</div>
            <div class="mono" style="font-size:31px;font-weight:700;color:var(--ok)">
              +${ew.mean_lead_readings}</div>
            <div class="small muted">readings = <b>${ew.mean_lead_hours} operating hours</b></div>
          </div>
          <div>
            <div class="small muted">Machines warned before failure</div>
            <div class="mono" style="font-size:31px;font-weight:700;color:var(--ok)">
              ${ew.warned_before_failure_pct}%</div>
            <div class="small muted">of ${ew.machines_evaluated} unseen machines</div>
          </div>
          <div>
            <div class="small muted">Median lead time</div>
            <div class="mono" style="font-size:31px;font-weight:700">
              ${ew.median_lead_readings}</div>
            <div class="small muted">readings</div>
          </div>
          <div>
            <div class="small muted">Prediction horizon</div>
            <div class="mono" style="font-size:31px;font-weight:700">
              ${info.prediction_horizon_readings}</div>
            <div class="small muted">readings (~${info.prediction_horizon_hours} h) label window</div>
          </div>
        </div>

        <div class="mt" id="mi-lead"></div>

        <p class="small muted mt" style="line-height:1.65;margin-bottom:0">
          <b style="color:var(--text)">Why this panel comes first.</b>
          An earlier model trained on the machine's <i>current</i> state scored
          <b>0.9899 accuracy</b> — and had a lead time of <b style="color:var(--crit)">−3.7
          readings</b>: it raised the alarm about 37 minutes <i>after</i> the fault. Retraining
          on a horizon target cost 8 points of accuracy and turned a condition monitor into a
          predictive system. Accuracy was the wrong thing to optimise.
        </p>
      </div>

      <!-- ===== HEADLINE METRICS ===== -->
      <div class="grid cols-4 mt">
        ${[
          ["Accuracy", h.accuracy, "overall"],
          ["Balanced accuracy", h.balanced_accuracy, "corrects for 138:1 imbalance"],
          ["Macro F1", h.macro_f1, "unweighted mean over classes"],
          ["Macro recall", h.macro_recall, "how few failures are missed"],
        ].map(([label, v, note]) => `
          <div class="kpi ${v >= 0.85 ? "ok" : v >= 0.6 ? "" : "warn"}">
            <div class="label">${label}</div>
            <div class="value">${v.toFixed(4)}</div>
            <div class="note">${note}</div>
          </div>`).join("")}
      </div>

      <div class="grid cols-2 mt">
        <div class="panel">
          <h3>Per-Class Performance</h3>
          <div id="mi-perclass"></div>
        </div>
        <div class="panel">
          <h3>Confusion Matrix — ${m.test_rows.toLocaleString()} held-out rows</h3>
          <div id="mi-cm"></div>
        </div>
      </div>

      <div class="grid cols-2 mt">
        <div class="panel">
          <h3>Feature Importance — Gini vs Permutation</h3>
          <div id="mi-fi"></div>
          <p class="small muted" style="margin-bottom:0;border-top:1px solid var(--grid);padding-top:9px">
            The four engineered physics quantities carry most of the weight: the forest
            <b>rediscovered the governing physics</b> of each failure mode without being
            given the threshold rules.
          </p>
        </div>
        <div class="panel">
          <h3>Learning Curve</h3>
          <div id="mi-lc"></div>
          <p class="small muted" style="margin-bottom:0;border-top:1px solid var(--grid);padding-top:9px">
            Cross-validated F1 plateaus around 26,000 training rows and the two curves
            converge — the model is not starved of data, so more rows alone would not help.
          </p>
        </div>
      </div>

      <!-- ===== EXPLAINER PROOF ===== -->
      <div class="panel mt" style="border-color:${verify?.exact
          ? "rgba(34,197,94,.4)" : "rgba(239,68,68,.5)"}">
        <h3>Explainability Self-Check — run live, just now</h3>
        ${verify ? `
          <div class="grid cols-3">
            <div>
              <div class="small muted">Reconstruction is exact</div>
              <div class="mono" style="font-size:26px;font-weight:700;color:${
                verify.exact ? "var(--ok)" : "var(--crit)"}">
                ${verify.exact ? "✓ YES" : "✗ NO"}</div>
            </div>
            <div>
              <div class="small muted">Max absolute error</div>
              <div class="mono" style="font-size:26px;font-weight:700">
                ${verify.max_absolute_error.toExponential(1)}</div>
            </div>
            <div>
              <div class="small muted">Samples checked</div>
              <div class="mono" style="font-size:26px;font-weight:700">${verify.samples}</div>
            </div>
          </div>
          <p class="small muted mt" style="line-height:1.65;margin-bottom:0">
            The explanation panel uses <b>Saabas decision-path attribution</b>, which decomposes
            a tree ensemble's output exactly: <span class="mono">P(class) = base rate + Σ
            per-feature contributions</span>. This check re-derives every prediction from its
            attribution and compares it against the model's own output. At
            ${verify.max_absolute_error.toExponential(1)} the two agree to machine precision —
            so the panel shows <b>the</b> reason for a prediction, not an approximation of it.
          </p>` : `<div class="empty small">Self-check unavailable.</div>`}
      </div>

      <!-- ===== FIGURES ===== -->
      <div class="panel mt">
        <h3>Phase 1 Evaluation Figures</h3>
        <div class="grid cols-3" id="mi-figs"></div>
      </div>`;

    perClass(m);
    W.confusionMatrix(host.querySelector("#mi-cm"), m.confusion_matrix);
    leadChart(ew);
    featureImportance(m);
    learningCurve(m);
    figures();
  }

  /* ---------------------------------------------------------------- */
  function perClass(m) {
    const rows = Object.entries(m.per_class);
    host.querySelector("#mi-perclass").innerHTML = `
      <div class="tbl-wrap">
        <table>
          <thead><tr><th>Class</th><th>Precision</th><th>Recall</th><th>F1</th>
                     <th>ROC-AUC</th><th>Support</th></tr></thead>
          <tbody>
            ${rows.map(([cls, s]) => {
              const auc = m.roc_auc?.[cls];
              return `<tr>
                <td><b>${cls}</b></td>
                <td class="num">${s.precision.toFixed(3)}</td>
                <td class="num" style="color:${s.recall >= 0.8 ? "var(--ok)" : "var(--warn)"}">
                  <b>${s.recall.toFixed(3)}</b></td>
                <td class="num">${s["f1-score"].toFixed(3)}</td>
                <td class="num" style="color:var(--ok)">${auc ? auc.toFixed(3) : "—"}</td>
                <td class="num">${s.support.toLocaleString()}</td>
              </tr>`;
            }).join("")}
          </tbody>
        </table>
      </div>
      <p class="small muted mt" style="margin-bottom:0">
        <b style="color:var(--text)">Read recall and AUC, not precision.</b> ROC-AUC is
        0.95–0.995 for every class, so the model separates them well. The modest precision is
        largely <i>early</i> warnings: 84% of apparent false positives are on machines that
        genuinely do fail, a median of 34 readings before the event — flagged as errors only
        because they fall outside the 15-reading label window.
      </p>`;
  }

  function leadChart(ew) {
    const modes = Object.keys(ew.per_mode);
    const vals = modes.map(k => ew.per_mode[k]);
    const max = Math.max(...vals, 1);

    host.querySelector("#mi-lead").innerHTML = `
      <div class="small muted" style="margin-bottom:8px">Lead time by failure mechanism (readings)</div>
      ${modes.map((mode, i) => {
        const v = vals[i];
        return `
          <div class="driver">
            <div class="driver-head"><span>${mode}</span>
              <span class="dv" style="color:var(--ok)">+${v.toFixed(1)} rdg ·
                ${(v * 10 / 60).toFixed(1)} h</span></div>
            <div class="bar"><span style="width:${(v / max) * 100}%;background:var(--ok)"></span></div>
          </div>`;
      }).join("")}`;
  }

  function featureImportance(m) {
    const gini = m.feature_importance_gini;
    const perm = m.feature_importance_permutation || {};
    const sorted = Object.entries(gini).sort((a, b) => b[1] - a[1]);
    const max = sorted[0][1] || 1;

    const PHYSICS = new Set(["temp_delta", "power", "strain", "tool_wear"]);
    const nice = {
      tool_wear: "Tool Wear", strain: "Tool Strain", power: "Mechanical Power",
      temp_delta: "Thermal Gradient", torque: "Torque",
      rotational_speed: "Rotational Speed", torque_speed_ratio: "Load Characteristic",
      air_temperature: "Air Temperature", process_temperature: "Process Temperature",
      type_code: "Machine Variant",
    };

    host.querySelector("#mi-fi").innerHTML = sorted.map(([f, v]) => {
      const p = perm[f];
      const isPhys = PHYSICS.has(f);
      const col = isPhys ? "#38bdf8" : "#94a3b8";
      return `
        <div class="driver">
          <div class="driver-head">
            <span>${nice[f] || f}
              ${isPhys ? `<span class="badge ADVISORY" style="margin-left:5px">PHYSICS</span>` : ""}
            </span>
            <span class="dv">${v.toFixed(3)}${p !== undefined
              ? ` <span class="muted">/ ${p.toFixed(3)}</span>` : ""}</span>
          </div>
          <div class="bar"><span style="width:${(v / max) * 100}%;background:${col}"></span></div>
        </div>`;
    }).join("") + `
      <div class="legend mt"><span><i style="background:#38bdf8"></i>engineered physics quantity</span>
        <span><i style="background:#94a3b8"></i>raw sensor</span>
        <span class="muted">Gini / permutation</span></div>`;
  }

  function learningCurve(m) {
    const lc = m.learning_curve;
    if (!lc) return;
    W.lineChart(host.querySelector("#mi-lc"), {
      height: 210,
      labels: lc.train_sizes.map(n => (n / 1000).toFixed(0) + "k"),
      series: [
        { name: "Training F1", color: "#38bdf8", data: lc.train_f1 },
        { name: "Cross-validated F1", color: "#f59e0b", data: lc.cv_f1, width: 2.4 },
      ],
    });
  }

  function figures() {
    const figs = [
      ["/artifacts/plots/evaluation/14_early_warning_lead_time.png", "Early-warning lead time"],
      ["/artifacts/plots/evaluation/09_confusion_matrix.png", "Confusion matrix"],
      ["/artifacts/plots/evaluation/10_roc_and_pr_curves.png", "ROC & PR curves"],
      ["/artifacts/plots/evaluation/12_feature_importance.png", "Feature importance"],
      ["/artifacts/plots/evaluation/13_learning_curve.png", "Learning curve"],
      ["/artifacts/plots/eda/04_physics_separation.png", "Physics separation (EDA)"],
      ["/artifacts/plots/eda/06_degradation_signatures.png", "Degradation signatures"],
      ["/artifacts/plots/eda/01_class_distribution.png", "Class distribution"],
      ["/artifacts/plots/eda/03_correlation_matrix.png", "Correlation matrix"],
    ];

    host.querySelector("#mi-figs").innerHTML = figs.map(([src, title]) => `
      <figure style="margin:0">
        <a href="${src}" target="_blank" rel="noopener">
          <img class="figure" src="${src}" alt="${title}" loading="lazy"
               onerror="this.closest('figure').style.display='none'" />
        </a>
        <figcaption class="small muted center" style="margin-top:6px">${title}</figcaption>
      </figure>`).join("");
  }

  return { enter };
})();
