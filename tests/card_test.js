// Renders the card with a fake hass in plain Node (no real browser/HA).
const assert = require("assert");
class FakeEl {
  constructor(){ this.innerHTML=""; this.listeners = {}; this._delegated = []; }
  attachShadow(){ this.shadowRoot = this; return this; }
  dispatchEvent(){}
  // the card delegates clicks/inputs on the shadow root
  addEventListener(ev, fn){ this._delegated.push([ev, fn]); }
  // minimal: finds [data-act] buttons in the rendered HTML
  querySelectorAll(sel){
    const out = [];
    for (const m of this.innerHTML.matchAll(/data-act="([a-z_]+)"/g)) {
      const el = { dataset: { act: m[1] }, disabled: false, addEventListener: (ev, fn) => { (this.listeners[m[1]] ||= []).push(fn); } };
      out.push(el);
    }
    return { forEach: (f) => out.forEach(f) };
  }
}
global.confirm = () => true;
global.HTMLElement = FakeEl;
const defs = {};
global.customElements = { get: (n)=>defs[n], define: (n,c)=>{ defs[n]=c; } };
global.window = { customCards: [] };
global.setInterval = () => 0; global.clearInterval = () => {};
require("../www/voyahtweaks-ha-card.js");
const Card = defs["voyah-free-card"];

const keys = {
  sensor: ["soc","soh","range","range_real","mileage","speed","charging_power","pack_temp_avg","window_fl","window_fr","window_rl","window_rr","sunroof","sentry","last_seen"],
  tires: ["tire_pressure_fl","tire_temp_fl","tire_pressure_rr","tire_temp_rr"],
  lock: ["ctl_lock"], button: ["btn_find_start"], cover: ["ctl_tailgate"],
  binary_sensor: ["api","online","telemetry_fresh","charging","door_fl","door_fr","door_rl","door_rr","tailgate","lock","sentry_active"],
};
function build(states) {
  const entities = {}, st = {};
  for (const [dom0, ks] of Object.entries(keys)) for (const k of ks) {
    const dom = dom0 === "tires" ? "sensor" : dom0;
    const id = `${dom}.voyah_${k}`;
    entities[id] = { entity_id: id, platform: "voyahtweaks-ha", translation_key: k, device_id: "dev1" };
    const s = states[k] ?? "unknown";
    st[id] = { state: String(s.state ?? s), attributes: s.attributes || {}, last_updated: "2026-11-11T12:00:00Z" };
  }
  // foreign entity that must be ignored
  entities["sensor.other"] = { entity_id: "sensor.other", platform: "other", translation_key: "soc", device_id: "x" };
  return { entities, states: st, language: "ru" };
}
function render(states, tab) {
  const c = new Card(); c.setConfig({ type: "custom:voyah-free-card" }); c.hass = build(states);
  if (tab) { c._ui.tab = tab; c._sig = null; c._render(); }
  return c.shadowRoot.innerHTML;
}
const minsAgo = (m) => new Date(Date.now() - m*60000).toISOString();

// 1) fresh + charging + open driver door
let html = render({
  soc: { state: "44", attributes: { unit_of_measurement: "%" } },
  soh: { state: "96.8", attributes: { unit_of_measurement: "%" } },
  range: { state: "78", attributes: { unit_of_measurement: "km" } },
  range_real: { state: "52", attributes: { unit_of_measurement: "km" } },
  charging_power: { state: "4.6", attributes: { unit_of_measurement: "kW" } },
  online: "on", api: "on", charging: "on", lock: "off",
  telemetry_fresh: { state: "on", attributes: { threshold_minutes: 10 } },
  last_seen: minsAgo(1), door_fl: "on", door_fr: "off", window_fl: "closed", sunroof: "vent",
  sentry_active: "off", tailgate: "off",
});
assert(html.includes("VOYAH FREE"));
assert(html.includes("Онлайн") && html.includes("Данные актуальны"));
assert(!html.includes("спящем режиме"), "no sleep warning when fresh");
assert(html.includes('class="soc">44<sup>%</sup>'), "SOC has exactly one %");
assert(!/%%/.test(html) && !html.includes("%<small>%"), "no doubled percent");
assert(html.includes("96,8") || html.includes("96.8"));
assert(html.includes("charging"), "charging ring class");
assert(html.includes("rotate(28 40 118)"), "FL door drawn open");
assert(html.includes("левая передняя"), "FL tire label");
assert(html.includes("Люк: вентиляция"), "sunroof vent badge");
console.log("fresh scenario OK");

// 2) sleeping car: fresh entity says off, last values still shown + warning
html = render({
  soc: { state: "44", attributes: { unit_of_measurement: "%" } },
  online: "off", api: "on",
  telemetry_fresh: { state: "off", attributes: { threshold_minutes: 10 } },
  last_seen: minsAgo(18),
});
assert(html.includes("Офлайн") && html.includes("Данные устарели"));
assert(/Данные не обновлялись 18 минут\. Автомобиль может находиться в спящем режиме\./.test(html), html.match(/banner[^]*?<\/div>/)?.[0]);
assert(html.includes('class="soc">44<sup>%</sup>'), "last known SOC stays visible");
console.log("sleep scenario OK");

// 3) API down but car data present: separate red banner
html = render({
  soc: { state: "44", attributes: { unit_of_measurement: "%" } },
  online: "on", api: { state: "off", attributes: { last_error: "server_error (503)" } },
  telemetry_fresh: { state: "on", attributes: { threshold_minutes: 10 } }, last_seen: minsAgo(2),
});
assert(html.includes("banner bad") && html.includes("server_error (503)"));
assert(html.includes("Данные актуальны"), "API error does not change freshness chip");
console.log("api-down scenario OK");

// 4) HTML escaping + live-age override (state says on, but last_seen is old)
html = render({
  soc: "50", telemetry_fresh: { state: "on", attributes: { threshold_minutes: 10 } },
  last_seen: minsAgo(25), online: "on",
});
assert(html.includes("Данные устарели"), "live age beats stale 'on' state");
assert(/25 минут/.test(html));
console.log("live-age scenario OK");

// 5) no integration entities
const c = new Card(); c.setConfig({}); c.hass = { entities: {}, states: {}, language: "en" };
assert(c.shadowRoot.innerHTML.includes("No voyahtweaks-ha entities found"));
console.log("empty scenario OK");

// 6) tyres: proper labels, values, no invented unit
html = render({
  tire_pressure_fl: "2.4", tire_temp_fl: "17", tire_pressure_rr: "2.6", tire_temp_rr: { state: "18.4" },
  online: "on", lock: "on", tailgate: "off",
});
assert(html.includes("Шины") && html.includes("левая передняя") && html.includes("правая задняя"));
assert(/2,4/.test(html) && /17°/.test(html) && /2,6/.test(html) && /18°/.test(html), html.match(/class="tires"[^]*?<\/div><\/div>/)?.[0]);
assert(!html.includes("bcm_") && !html.includes("tyre"), "no raw key names");
console.log("tyre scenario OK");

// 7) action buttons: unlock offered when locked==false, only when entities exist
html = render({ lock: "off", online: "on", tailgate: "off" }, "control");
assert(html.includes('data-act="unlock"') && html.includes('data-act="find"') && html.includes('data-act="trunk_open"'));
html = render({ lock: "on", online: "on", tailgate: "on" }, "control");
assert(html.includes('data-act="lock"') && html.includes('data-act="trunk_close"'));
// no command entities (commands disabled) -> no action bar
const c2 = new Card(); c2.setConfig({});
const h = build({ soc: "50", online: "on" });
for (const id of Object.keys(h.entities)) if (/ctl_|btn_/.test(h.entities[id].translation_key || "")) delete h.entities[id];
c2.hass = h;
assert(!c2.shadowRoot.innerHTML.includes("data-act"), "no action bar without command entities");
console.log("actions scenario OK");

// 8) clicks call the right HA services (and honour a declined confirm)
(async () => {
  const calls = [];
  const c = new Card(); c.setConfig({});
  const hs = build({ lock: "off", online: "on", tailgate: "off" });
  hs.callService = async (d, sv, data) => { calls.push([d, sv, data.entity_id]); };
  c.hass = hs;
  await c._act("unlock");
  await c._act("find");
  await c._act("trunk_open");
  assert.deepStrictEqual(calls, [
    ["lock", "unlock", "lock.voyah_ctl_lock"],
    ["button", "press", "button.voyah_btn_find_start"],
    ["cover", "open_cover", "cover.voyah_ctl_tailgate"],
  ]);
  global.confirm = () => false;
  calls.length = 0;
  await c._act("unlock");
  assert.strictEqual(calls.length, 0, "declined confirm sends nothing");
  console.log("click scenario OK");
})();
