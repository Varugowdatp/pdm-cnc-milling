/* ==================================================================
   API CLIENT
   ==================================================================
   Thin wrapper over fetch. Two jobs beyond transport:

   1. Turn a FastAPI error body into a readable message. FastAPI puts
      the reason in `detail`, which is either a string or a list of
      validation errors - the UI must never show "[object Object]".

   2. Cache /api/reference. Thresholds, colours and the sensor schema
      come from the backend so the frontend never hard-codes a limit;
      but they cannot change while the page is open, so fetch once.
   ================================================================== */

const API = (() => {

  const BASE = "";
  let referenceCache = null;

  async function request(path, options = {}) {
    let res;
    try {
      res = await fetch(BASE + path, options);
    } catch (networkError) {
      throw new Error("Cannot reach the server. Is the backend running?");
    }

    const isJSON = (res.headers.get("content-type") || "").includes("json");
    const body = isJSON ? await res.json().catch(() => null) : await res.text();

    if (!res.ok) throw new Error(describeError(body, res.status));
    return body;
  }

  /* FastAPI's `detail` is a string for HTTPException and a list of
     objects for Pydantic validation failures. Flatten both. */
  function describeError(body, status) {
    if (!body) return `Request failed (HTTP ${status}).`;
    if (typeof body === "string") return body;

    const detail = body.detail;
    if (typeof detail === "string") return detail;

    if (Array.isArray(detail)) {
      return detail.map(d => {
        const field = Array.isArray(d.loc) ? d.loc.filter(p => p !== "body").join(".") : "";
        return field ? `${field}: ${d.msg}` : d.msg;
      }).join("; ");
    }
    return `Request failed (HTTP ${status}).`;
  }

  const json = (path, method, payload) => request(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: payload === undefined ? undefined : JSON.stringify(payload),
  });

  return {
    /* ---- system ---- */
    health:    ()  => request("/api/health"),
    reset:     ()  => json("/api/system/reset", "POST"),

    async reference() {
      if (!referenceCache) referenceCache = await request("/api/reference");
      return referenceCache;
    },

    /* ---- prediction ---- */
    predict:  (reading) => json("/api/predict", "POST", reading),

    predictBatch(file, { explain = false, save = false } = {}) {
      const form = new FormData();
      form.append("file", file);
      return request(`/api/predict/batch?explain=${explain}&save=${save}`,
                     { method: "POST", body: form });
    },

    templateURL: () => "/api/predict/template",

    /* ---- plant ---- */
    machines:      ()   => request("/api/machines"),
    machine:       (id, history = 120) =>
                          request(`/api/machines/${encodeURIComponent(id)}?history=${history}`),
    history:       (id, limit = 200) =>
                          request(`/api/machines/${encodeURIComponent(id)}/history?limit=${limit}`),
    addMachine:    (m)  => json("/api/machines", "POST", m),
    deleteMachine: (id) => request(`/api/machines/${encodeURIComponent(id)}`, { method: "DELETE" }),

    /* ---- simulation ---- */
    catalogue:  (limit = 40) => request(`/api/simulate/catalogue?limit=${limit}`),
    simStart:   (cfg) => json("/api/simulate/start", "POST", cfg),
    simStop:    (id)  => json(`/api/simulate/stop?machine_id=${encodeURIComponent(id)}`, "POST"),
    simStopAll: ()    => json("/api/simulate/stop-all", "POST"),
    simStatus:  (id)  => request("/api/simulate/status" + (id ? `?machine_id=${encodeURIComponent(id)}` : "")),

    /* Server-sent events. Returns the EventSource so the caller can close it. */
    stream(machineId, handlers = {}) {
      const es = new EventSource(`/api/simulate/stream/${encodeURIComponent(machineId)}`);
      Object.entries(handlers).forEach(([event, fn]) => {
        es.addEventListener(event, e => {
          try { fn(JSON.parse(e.data)); }
          catch (err) { console.error("Bad SSE payload", err); }
        });
      });
      return es;
    },

    /* ---- alarms ---- */
    alarms(opts = {}) {
      const q = new URLSearchParams();
      if (opts.machine_id) q.set("machine_id", opts.machine_id);
      if (opts.level) q.set("level", opts.level);
      if (opts.unacknowledged_only) q.set("unacknowledged_only", "true");
      q.set("limit", opts.limit || 200);
      return request(`/api/alarms?${q}`);
    },
    ackAlarm: (id, by = "operator") =>
                json(`/api/alarms/${id}/acknowledge`, "POST", { by }),
    ackAll:   (machineId) =>
                json("/api/alarms/acknowledge-all" +
                     (machineId ? `?machine_id=${encodeURIComponent(machineId)}` : ""), "POST"),

    /* ---- model insights ---- */
    modelInfo:    () => request("/api/model/info"),
    modelMetrics: () => request("/api/model/metrics"),
    modelVerify:  (n = 20) => request(`/api/model/verify?samples=${n}`),
  };
})();
