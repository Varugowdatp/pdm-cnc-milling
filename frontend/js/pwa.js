/* ==================================================================
   PWA  —  service-worker registration + "Install app" popup
   ==================================================================
   Chrome / Edge / Android fire `beforeinstallprompt` once the site is
   installable (HTTPS or localhost, manifest, service worker). We keep
   that event and show our own popup, styled like the rest of the HMI,
   instead of relying on the easy-to-miss icon in the address bar.

   iOS Safari has no install API, so there the popup explains the
   manual "Share -> Add to Home Screen" step instead.

   "Not now" hides the popup for 3 days; the Install button in the top
   bar stays available whenever the browser allows installing.
   ================================================================== */

const PWA = (() => {

  const SNOOZE_KEY = "pdm-install-snoozed-until";
  const SNOOZE_MS = 3 * 24 * 60 * 60 * 1000;
  let deferredPrompt = null;

  const isStandalone = () =>
    window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;

  const isIOS = () =>
    /iphone|ipad|ipod/i.test(navigator.userAgent) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);

  function snoozed() {
    try { return Date.now() < Number(localStorage.getItem(SNOOZE_KEY) || 0); }
    catch { return false; }
  }

  function snooze() {
    try { localStorage.setItem(SNOOZE_KEY, String(Date.now() + SNOOZE_MS)); } catch { /* private mode */ }
  }

  function closePopup() {
    const el = document.getElementById("install-popup");
    if (el) el.remove();
  }

  function showPopup({ ios = false } = {}) {
    if (document.getElementById("install-popup") || isStandalone()) return;

    const body = ios
      ? `Tap <b>Share</b> <span class="ip-share">⎋</span> in Safari, then <b>Add to Home Screen</b>.`
      : `Install the Predictive Maintenance HMI as an app: it opens in its own window
         and gets an icon on your desktop or home screen.`;

    const el = document.createElement("div");
    el.id = "install-popup";
    el.className = "install-popup";
    el.setAttribute("role", "dialog");
    el.setAttribute("aria-labelledby", "ip-title");
    el.innerHTML = `
      <img src="/icons/icon-192.png" alt="" class="ip-icon" />
      <div class="ip-text">
        <h3 id="ip-title">Install PdM SCADA</h3>
        <p>${body}</p>
        <div class="ip-actions">
          ${ios ? "" : `<button class="btn primary" id="ip-install">Install</button>`}
          <button class="btn" id="ip-later">${ios ? "Got it" : "Not now"}</button>
        </div>
      </div>`;
    document.body.appendChild(el);

    const install = el.querySelector("#ip-install");
    if (install) install.addEventListener("click", promptInstall);
    el.querySelector("#ip-later").addEventListener("click", () => { snooze(); closePopup(); });
  }

  async function promptInstall() {
    closePopup();
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    if (outcome !== "accepted") snooze();
    deferredPrompt = null;
    setTopbarButton(false);
  }

  function setTopbarButton(visible) {
    const btn = document.getElementById("install-btn");
    if (btn) btn.hidden = !visible;
  }

  function init() {
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch((err) =>
        console.warn("Service worker registration failed:", err));
    }

    window.addEventListener("beforeinstallprompt", (e) => {
      e.preventDefault();               // suppress the browser mini-bar; we show our own popup
      deferredPrompt = e;
      setTopbarButton(true);
      if (!snoozed()) setTimeout(() => showPopup(), 2500);
    });

    window.addEventListener("appinstalled", () => {
      deferredPrompt = null;
      setTopbarButton(false);
      closePopup();
      if (window.App) App.toast("App installed. Launch it from your desktop or home screen.", "ok");
    });

    document.addEventListener("DOMContentLoaded", () => {
      const btn = document.getElementById("install-btn");
      if (btn) btn.addEventListener("click", () => (deferredPrompt ? promptInstall() : showPopup({ ios: isIOS() })));
      if (isIOS() && !isStandalone() && !snoozed()) setTimeout(() => showPopup({ ios: true }), 2500);
      if (isIOS() && !isStandalone()) setTopbarButton(true);
    });
  }

  return { init };
})();

PWA.init();
