/* ==================================================================
   APPLICATION SHELL
   ==================================================================
   Hash routing, screen lifecycle, shared helpers.

   Each screen module registers itself on `SCREENS` with an optional
   `enter(param)` and `leave()`. `leave()` matters more than it looks:
   the Machine HMI holds an open SSE connection and a polling timer,
   and without a teardown hook they would keep running - and keep
   writing into a detached DOM - after the operator navigates away.
   ================================================================== */

const SCREENS = {};

const App = (() => {

  let current = null;
  let reference = null;

  /* ---------------------------------------------------------------
     ROUTING
     --------------------------------------------------------------- */
  function parseHash() {
    const raw = (location.hash || "#/overview").replace(/^#\/?/, "");
    const [route, ...rest] = raw.split("/");
    return { route: route || "overview", param: rest.join("/") || null };
  }

  async function route() {
    const { route, param } = parseHash();
    const target = SCREENS[route] ? route : "overview";

    if (current && current !== target && SCREENS[current]?.leave) {
      try { SCREENS[current].leave(); } catch (e) { console.error(e); }
    }

    document.querySelectorAll(".screen").forEach(s => (s.hidden = true));
    const host = document.getElementById("screen-" + target);
    if (host) host.hidden = false;

    document.querySelectorAll("#nav a").forEach(a =>
      a.classList.toggle("active", a.dataset.route === target));

    current = target;

    try {
      await SCREENS[target].enter?.(param, host);
    } catch (err) {
      console.error(err);
      if (host) host.innerHTML = errorPanel(err.message);
    }
  }

  function go(route, param) {
    location.hash = "#/" + route + (param ? "/" + param : "");
  }

  /* ---------------------------------------------------------------
     SHARED HELPERS
     --------------------------------------------------------------- */
  function toast(message, kind = "") {
    const host = document.getElementById("toasts");
    const el = document.createElement("div");
    el.className = "toast " + kind;
    el.textContent = message;
    host.appendChild(el);
    setTimeout(() => {
      el.style.transition = "opacity .3s, transform .3s";
      el.style.opacity = "0";
      el.style.transform = "translateX(20px)";
      setTimeout(() => el.remove(), 320);
    }, kind === "err" ? 6000 : 3400);
  }

  const errorPanel = msg => `
    <div class="panel">
      <div class="empty">
        <span class="big">⚠</span>
        <b>Something went wrong</b><br />
        <span class="small">${escapeHTML(msg)}</span>
      </div>
    </div>`;

  const escapeHTML = s => String(s ?? "").replace(/[&<>"']/g,
    c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  /* Times arrive as ISO-8601 UTC; show the operator local wall-clock. */
  function clockTime(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    return isNaN(d) ? "—" : d.toLocaleTimeString([], { hour12: false });
  }
  function dateTime(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    return isNaN(d) ? "—" : d.toLocaleString([], { hour12: false });
  }

  /* RUL must never present a guess as a measurement, and an unbounded
     extrapolation is not a number - it is "no degradation detected". */
  /* RUL_CAP is 999 readings = 166.5 h. A value at the cap is not a
     166-hour forecast, it is the engine saying "no degradation trend" -
     so it must read STABLE whether or not the `unbounded` flag survived
     the round trip through the database. */
  const RUL_CAP_HOURS = 166;

  function rulText(rul) {
    if (!rul) return "—";
    const h = rul.hours;
    if (rul.unbounded || (h !== null && h !== undefined && h >= RUL_CAP_HOURS)) return "STABLE";
    if (h === null || h === undefined) return "—";
    if (h >= 48) return (h / 24).toFixed(1) + " d";
    return h.toFixed(1) + " h";
  }
  function rulNote(rul) {
    if (!rul) return "";
    const h = rul.hours;
    if (rul.unbounded || (h !== null && h !== undefined && h >= RUL_CAP_HOURS))
      return "no degradation trend detected";
    return rul.method === "trend"
      ? `trend fit${rul.trend_r2 !== undefined ? ` · R²=${rul.trend_r2}` : ""} · ${rul.confidence} confidence`
      : "nominal estimate · low confidence";
  }

  async function getReference() {
    if (!reference) {
      reference = await API.reference();
      W.setBands(reference.health_bands);
    }
    return reference;
  }

  /* ---------------------------------------------------------------
     STATUS BAR
     --------------------------------------------------------------- */
  async function pollHealth() {
    const dot = document.getElementById("conn-dot");
    const text = document.getElementById("conn-text");
    try {
      const h = await API.health();
      dot.className = "dot " + (h.status === "ok" ? "ok" : "err");
      text.textContent = h.status === "ok"
        ? `online · ${h.machines} machines · ${h.readings.toLocaleString()} readings`
        : "degraded";
    } catch {
      dot.className = "dot err";
      text.textContent = "backend offline";
    }
  }

  function startClock() {
    const el = document.getElementById("clock");
    const tick = () => (el.textContent = new Date().toLocaleTimeString([], { hour12: false }));
    tick();
    setInterval(tick, 1000);
  }

  /* ---------------------------------------------------------------
     BOOT
     --------------------------------------------------------------- */
  async function boot() {
    startClock();
    await pollHealth();
    setInterval(pollHealth, 10000);

    try {
      await getReference();
    } catch (err) {
      toast("Could not load reference constants: " + err.message, "err");
    }

    window.addEventListener("hashchange", route);
    await route();
  }

  return { boot, go, toast, escapeHTML, clockTime, dateTime,
           rulText, rulNote, getReference, errorPanel };
})();

document.addEventListener("DOMContentLoaded", App.boot);
