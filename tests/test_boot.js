/* ==================================================================
   BOOT / LOAD-ORDER TEST
   ==================================================================
   REGRESSION TEST for a bug that made the entire HMI blank.

   `app.js` declares `const SCREENS = {}` and every screen script
   registers itself onto it. index.html originally loaded app.js LAST,
   so all six screen scripts ran first and threw
   "ReferenceError: SCREENS is not defined" - a top-level `const` in a
   classic script lives in the global lexical environment and is not
   visible to a script that ran earlier.

   Nothing caught it: `node --check` passes each file in isolation, the
   widget tests eval widgets.js on its own, and the contract tests talk
   to the API rather than the browser. Only loading the files in the
   order the PAGE loads them exposes it.

   This test parses that order out of index.html itself, so it stays
   correct if the file list ever changes.

   Run:  node tests/test_boot.js
   ================================================================== */

const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const INDEX = path.join(ROOT, "frontend", "index.html");

const EXPECTED_SCREENS = ["overview", "machine", "manual", "batch", "alarms", "model"];

let failures = 0;
const fail = msg => { console.log("  FAIL " + msg); failures++; };
const pass = msg => console.log("  ok   " + msg);

/* ---- 1. read the real load order out of the real page ------------- */
const html = fs.readFileSync(INDEX, "utf8");
const sources = [...html.matchAll(/<script\s+src="([^"]+)"/g)].map(m => m[1]);

if (!sources.length) fail("index.html declares no scripts");
else pass(`index.html loads ${sources.length} scripts`);

const files = sources.map(src => path.join(ROOT, "frontend", src.replace(/^\//, "")));
for (const f of files) {
  if (!fs.existsSync(f)) fail(`missing file referenced by index.html: ${f}`);
}

/* ---- 2. minimal browser stubs ------------------------------------- */
function stubElement() {
  const el = {
    _html: "", hidden: false, className: "", style: {}, dataset: {},
    set innerHTML(v) { this._html = v; },
    get innerHTML() { return this._html; },
    querySelector: () => stubElement(),
    querySelectorAll: () => [],
    appendChild: () => {}, remove: () => {},
    addEventListener: () => {}, onclick: null,
    children: new Proxy({}, { get: () => stubElement() }),
  };
  return el;
}

global.document = {
  addEventListener: () => {},
  getElementById: () => stubElement(),
  querySelectorAll: () => [],
  createElement: () => stubElement(),
};
global.window = { addEventListener: () => {} };
global.location = { hash: "" };
global.fetch = () => Promise.reject(new Error("network disabled in test"));
global.EventSource = function () { return { addEventListener() {}, close() {} }; };
global.FormData = function () { return { append() {} }; };
global.URLSearchParams = URLSearchParams;

/* ---- 3. load them exactly as the browser would --------------------- */
/* Concatenating models the browser's shared global lexical scope: a
   `const` declared in an earlier script is visible to later ones, and
   referencing it from an earlier script throws - which is precisely the
   failure mode under test. */
const bundle = files.map(f => fs.readFileSync(f, "utf8")).join("\n;\n");

try {
  eval(bundle + "\n; global.__SCREENS__ = (typeof SCREENS !== 'undefined') ? SCREENS : null;"
              + "\n; global.__APP__ = (typeof App !== 'undefined') ? App : null;"
              + "\n; global.__API__ = (typeof API !== 'undefined') ? API : null;"
              + "\n; global.__W__ = (typeof W !== 'undefined') ? W : null;");
  pass("all scripts execute in index.html's declared order");
} catch (err) {
  fail(`scripts threw on load: ${err.constructor.name}: ${err.message}`);
  console.log(`\n${failures} FAILURE(S) - the HMI would render blank.`);
  process.exit(1);
}

/* ---- 4. the globals the page depends on ---------------------------- */
[["API", global.__API__], ["W", global.__W__],
 ["App", global.__APP__], ["SCREENS", global.__SCREENS__]].forEach(([name, val]) => {
  if (!val) fail(`global ${name} is not defined after load`);
  else pass(`global ${name} defined`);
});

/* ---- 5. every screen registered ------------------------------------ */
const registered = global.__SCREENS__ ? Object.keys(global.__SCREENS__) : [];
for (const name of EXPECTED_SCREENS) {
  if (!registered.includes(name)) fail(`screen "${name}" did not register on SCREENS`);
  else if (typeof global.__SCREENS__[name].enter !== "function")
    fail(`screen "${name}" has no enter()`);
  else pass(`screen "${name}" registered with enter()`);
}

/* ---- 6. screens holding live resources must tear them down --------- */
/* machine.js opens an SSE connection and a poll timer; alarms.js and
   overview.js hold refresh timers. Without leave() every visit leaks. */
["machine", "overview", "alarms"].forEach(name => {
  const s = global.__SCREENS__ && global.__SCREENS__[name];
  if (s && typeof s.leave !== "function")
    fail(`screen "${name}" holds a timer or socket but has no leave()`);
  else if (s) pass(`screen "${name}" has leave() teardown`);
});

/* ---- 7. nav links must point at registered screens ----------------- */
const routes = [...html.matchAll(/data-route="([^"]+)"/g)].map(m => m[1]);
routes.forEach(r => {
  if (!registered.includes(r)) fail(`nav link data-route="${r}" has no screen`);
});
if (routes.length) pass(`all ${routes.length} nav links resolve to a screen`);

/* ---- 8. no stale references to removed directories ----------------- */
if (/\/static\/|\/templates\//.test(html))
  fail("index.html references the removed static/ or templates/ scaffolding");
else pass("no stale asset paths");

console.log(failures ? `\n${failures} FAILURE(S)` : "\nALL BOOT TESTS PASSED");
process.exit(failures ? 1 : 0);
