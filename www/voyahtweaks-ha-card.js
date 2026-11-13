/*
 * VOYAH FREE card for the "voyahtweaks-ha" Home Assistant integration.
 *
 * Lovelace card: status + controls in tabs. It talks only to Home Assistant
 * (entities and services), never to the Voyahtweaks API. Entities are found
 * through the entity registry (platform "voyahtweaks-ha" + translation_key).
 *
 * Dashboard resource: /local/voyahtweaks-ha-card.js  (type: JavaScript module)
 *
 * Card config:
 *   type: custom:voyah-free-card
 *   image: /local/voyah-free-black.png   # optional photo (top view looks best)
 *   name: VOYAH FREE                      # optional
 *   device_id: ""                         # optional, when several vehicles
 *   entities:                             # optional manual override by key
 *     soc: sensor.my_custom_soc
 */

const DOMAIN = "voyahtweaks-ha";
const UI_KEY = "voyah_free_card_ui_v1";

const I18N = {
  ru: {
    online: "Онлайн", offline: "Офлайн", nodata: "Нет данных",
    fresh: "Данные актуальны", stale: "Данные устарели", fresh_unknown: "Свежесть неизвестна",
    warn_stale: (a) => `Данные не обновлялись ${a}. Автомобиль может находиться в спящем режиме.`,
    warn_unknown: "Время последнего обновления автомобиля неизвестно.",
    warn_api: (e) => `Нет связи с API Voyahtweaks${e ? " (" + e + ")" : ""}. Показаны последние известные значения.`,
    last_seen: "Автомобиль обновлялся",
    charging: "Заряжается", not_charging: "Не заряжается", plugged: "Кабель подключён, зарядка не идёт",
    charger: "Тип зарядки", ch_none: "Не подключена", ch_ac: "Медленная (AC)", ch_dc: "Быстрая (DC)",
    power: "Мощность", left: "до конца", cabin: "Температура в салоне", outside: "Снаружи",
    clim_on: "Климат работает", clim_off: "Климат выключен",
    soc: "Заряд", soh: "SOH батареи", range: "Запас хода", range_real: "Реальный запас хода",
    mileage: "Пробег", speed: "Скорость", pack: "Температура батареи", v12: "12 В батарея",
    tires: "Шины", tire_hint: "давление · температура",
    fl: "левая передняя", fr: "правая передняя", rl: "левая задняя", rr: "правая задняя",
    location: "Местоположение", on_map: "Открыть на карте", no_gps: "Координат пока нет",
    h_access: "Доступ", h_glass: "Окна и люк", h_climate: "Климат", h_charge: "Зарядка", h_safety: "Охрана и запуск",
    lock: "Закрыть", unlock: "Открыть", locked: "Закрыт", unlocked: "Открыт",
    trunk_open: "Открыть багажник", trunk_close: "Закрыть багажник",
    find: "Найти машину", find_stop: "Стоп", hazard: "Аварийка",
    win_open: "Открыть окна", win_close: "Закрыть окна", win_vent: "Проветрить",
    roof_open: "Открыть люк", roof_close: "Закрыть люк", roof_vent: "Люк: вентиляция",
    c_start: "Запустить", c_stop: "Выключить", c_heat: "Быстрый обогрев", c_cool: "Быстрое охлаждение",
    c_temp: "Целевая температура", c_seat_fl: "Сиденье водителя", c_seat_fr: "Сиденье пассажира",
    c_glass: "Обогрев стекла", c_runtime: "Работать (мин)", seat_off: "Выкл",
    seat_heat: (n) => `Подогрев ${n}`, seat_vent: (n) => `Вентиляция ${n}`,
    ch_target: "Заряжать до", ch_start: "Начать зарядку", ch_stop: "Остановить",
    ch_sched: "Расписание", ch_from: "С", ch_to: "До", ch_daily: "Повторять ежедневно",
    ch_set: "Задать расписание", ch_cancel: "Отменить расписание",
    sentry: "Охрана", sentry_on: "Включить охрану", sentry_off: "Выключить охрану",
    keyless: "Запуск без ключа", keyless_hint: "Команда может завести автомобиль.",
    d_open: "открыта", w_open: "открыто", w_ajar: "приоткрыто", roof: "Люк", trunk: "Багажник",
    closed: "Закрыт", open: "Открыт", vent: "Вентиляция",
    c_unlock: "Открыть замки автомобиля?", c_trunk: "Открыть багажник?",
    c_keyless: "Запустить автомобиль без ключа? Убедитесь, что это безопасно.",
    c_keyless2: "Последнее подтверждение: запустить двигатель/систему?",
    done: "Выполнено", failed: "Команда не выполнена",
    min: ["минуту", "минуты", "минут"], hrs: ["час", "часа", "часов"], lt_min: "менее минуты",
    controls_off: "Управление автомобилем выключено. Включите его: Настройки → Устройства и службы → VoyahTweaks → Настроить → «Разрешить управление автомобилем».",
    no_entities: "Сущности интеграции voyahtweaks-ha не найдены",
    seat_title: "Сиденья",
    t_status: "Статус", t_control: "Управление", t_climate: "Климат", t_charge: "Зарядка",
  },
  en: {
    online: "Online", offline: "Offline", nodata: "No data",
    fresh: "Data is fresh", stale: "Data is stale", fresh_unknown: "Freshness unknown",
    warn_stale: (a) => `No update for ${a}. The vehicle may be asleep.`,
    warn_unknown: "The vehicle's last update time is unknown.",
    warn_api: (e) => `Voyahtweaks API unreachable${e ? " (" + e + ")" : ""}. Showing last known values.`,
    last_seen: "Vehicle last seen",
    charging: "Charging", not_charging: "Not charging", plugged: "Plugged in, not charging",
    charger: "Charger", ch_none: "Not connected", ch_ac: "Slow (AC)", ch_dc: "Fast (DC)",
    power: "Power", left: "remaining", cabin: "Cabin temperature", outside: "Outside",
    clim_on: "Climate running", clim_off: "Climate off",
    soc: "Charge", soh: "Battery SOH", range: "Range", range_real: "Real range",
    mileage: "Mileage", speed: "Speed", pack: "Battery temp", v12: "12 V battery",
    tires: "Tires", tire_hint: "pressure · temperature",
    fl: "front left", fr: "front right", rl: "rear left", rr: "rear right",
    location: "Location", on_map: "Open on map", no_gps: "No position yet",
    h_access: "Access", h_glass: "Windows & sunroof", h_climate: "Climate", h_charge: "Charging", h_safety: "Sentry & start",
    lock: "Lock", unlock: "Unlock", locked: "Locked", unlocked: "Unlocked",
    trunk_open: "Open tailgate", trunk_close: "Close tailgate",
    find: "Find vehicle", find_stop: "Stop", hazard: "Hazards",
    win_open: "Open windows", win_close: "Close windows", win_vent: "Vent",
    roof_open: "Open sunroof", roof_close: "Close sunroof", roof_vent: "Sunroof vent",
    c_start: "Start", c_stop: "Turn off", c_heat: "Rapid heat", c_cool: "Rapid cool",
    c_temp: "Target temperature", c_seat_fl: "Driver seat", c_seat_fr: "Passenger seat",
    c_glass: "Windshield heating", c_runtime: "Run time (min)", seat_off: "Off",
    seat_heat: (n) => `Heat ${n}`, seat_vent: (n) => `Vent ${n}`,
    ch_target: "Charge up to", ch_start: "Start charging", ch_stop: "Stop",
    ch_sched: "Schedule", ch_from: "From", ch_to: "To", ch_daily: "Repeat daily",
    ch_set: "Set schedule", ch_cancel: "Cancel schedule",
    sentry: "Sentry", sentry_on: "Sentry on", sentry_off: "Sentry off",
    keyless: "Keyless start", keyless_hint: "This command can start the vehicle.",
    d_open: "open", w_open: "open", w_ajar: "ajar", roof: "Sunroof", trunk: "Tailgate",
    closed: "Closed", open: "Open", vent: "Vent",
    c_unlock: "Unlock the vehicle?", c_trunk: "Open the tailgate?",
    c_keyless: "Start the vehicle without a key? Make sure it is safe.",
    c_keyless2: "Final confirmation: start the vehicle?",
    done: "Done", failed: "Command failed",
    min: ["minute", "minutes", "minutes"], hrs: ["hour", "hours", "hours"], lt_min: "less than a minute",
    controls_off: "Vehicle control is disabled. Enable it: Settings → Devices & services → VoyahTweaks → Configure → “Allow vehicle control”.",
    no_entities: "No voyahtweaks-ha entities found",
    seat_title: "Seats",
    t_status: "Status", t_control: "Control", t_climate: "Climate", t_charge: "Charging",
  },
};

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const DEFAULT_UI = { tab: "status", temp: 22, seat_fl: 0, seat_fr: 0, glass: false, runtime: 15, max_soc: 80, from: "23:00", to: "06:00", cycle: true };

const STYLE = `
ha-card { display:block; overflow:hidden; background:#090d12; color:#e8edf4;
  font-family:"Inter","Segoe UI",system-ui,sans-serif;
  --accent:#3ddc97; --warn:#ffb020; --bad:#ff5d5d; --dim:#8a95a6; --line:rgba(255,255,255,.09); --card:#121821; --card2:#18202b; }
* { box-sizing:border-box; }
.head { display:flex; align-items:center; gap:10px; padding:14px 16px 0; flex-wrap:wrap; }
.head h1 { margin:0; font-size:15px; letter-spacing:.26em; font-weight:700; flex:1; min-width:120px; }
.chips { display:flex; gap:6px; flex-wrap:wrap; justify-content:flex-end; }
.chip { display:inline-flex; align-items:center; gap:6px; padding:5px 10px; border-radius:999px; font-size:12px;
  background:rgba(255,255,255,.06); border:1px solid var(--line); white-space:nowrap; }
.dot { width:7px; height:7px; border-radius:50%; background:var(--dim); }
.chip.ok .dot { background:var(--accent); box-shadow:0 0 6px var(--accent); }
.chip.warn .dot { background:var(--warn); box-shadow:0 0 6px var(--warn); }
.chip.bad .dot { background:var(--bad); box-shadow:0 0 6px var(--bad); }
.page { padding:12px 16px 16px; }
.banner { margin-bottom:12px; padding:10px 14px; border-radius:12px; font-size:13px; line-height:1.4; display:flex; gap:10px; align-items:flex-start;
  background:rgba(255,176,32,.12); border:1px solid rgba(255,176,32,.45); color:#ffd58a; }
.banner.bad { background:rgba(255,93,93,.12); border-color:rgba(255,93,93,.5); color:#ffb3b3; }
.banner.info { background:rgba(255,255,255,.05); border-color:var(--line); color:var(--dim); }
.col { display:grid; gap:12px; min-width:0; }
.card { background:var(--card); border:1px solid var(--line); border-radius:20px; padding:16px; min-width:0; }
.card > h2 { margin:0 0 12px; font-size:11.5px; font-weight:600; letter-spacing:.14em; text-transform:uppercase; color:var(--dim); }
/* hero */
.hero { padding:0; overflow:hidden; background:radial-gradient(ellipse at 50% 35%,#1d2633 0%,#0f141b 70%); }
.stage { position:relative; padding:18px 12px 6px; display:flex; justify-content:center; }
.stage .photo { width:100%; max-width:380px; max-height:480px; object-fit:contain; filter:drop-shadow(0 18px 26px rgba(0,0,0,.65)); }
.stage svg.car { width:100%; max-width:230px; height:auto; filter:drop-shadow(0 18px 24px rgba(0,0,0,.6)); }
.badge { position:absolute; display:inline-flex; align-items:center; gap:5px; padding:4px 9px; border-radius:999px; font-size:11.5px; font-weight:600;
  background:rgba(255,176,32,.16); border:1px solid rgba(255,176,32,.7); color:#ffd58a; backdrop-filter:blur(4px); }
.badge.ok { background:rgba(61,220,151,.14); border-color:rgba(61,220,151,.7); color:#9af0c8; }
.badge ha-icon { --mdc-icon-size:14px; }
.b-fl { left:8px; top:30%; } .b-fr { right:8px; top:30%; } .b-rl { left:8px; top:58%; } .b-rr { right:8px; top:58%; }
.b-trunk { left:50%; bottom:4px; transform:translateX(-50%); } .b-roof { left:50%; top:10px; transform:translateX(-50%); }
.b-lock { left:8px; top:8px; } .b-chg { right:8px; top:8px; }
.car .shell { fill:#07090c; stroke:#2b3340; stroke-width:1.5; }
.car .glass { fill:#10151c; stroke:#222b37; }
.car .pano { fill:#0b1016; stroke:#2b3340; } .car .pano.bad { fill:rgba(255,176,32,.35); stroke:var(--warn); }
.car .wheel { fill:#030405; stroke:#1d242d; }
.car .panel { fill:#12171e; stroke:#2b3340; transition:fill .3s; } .car .panel.bad { fill:var(--warn); stroke:var(--warn); }
.car .win { stroke:#2b3340; stroke-width:3; stroke-linecap:round; } .car .win.bad { stroke:var(--warn); }
.car .lamp { fill:#cfd8e6; opacity:.85; } .car .tail { fill:#ff3b3b; opacity:.8; }
.statusrow { display:grid; grid-template-columns:150px 1fr; gap:14px; padding:6px 16px 18px; align-items:center; }
.ring { position:relative; width:150px; height:150px; }
.ring svg { width:100%; height:100%; transform:rotate(-90deg); }
.ring .bg { stroke:rgba(255,255,255,.08); } .ring .fg { transition:stroke-dashoffset .8s ease, stroke .4s; stroke-linecap:round; }
.ring.charging .fg { animation:pulse 2s ease-in-out infinite; }
@keyframes pulse { 50% { opacity:.5; } }
.ring .center { position:absolute; inset:0; display:flex; flex-direction:column; align-items:center; justify-content:center; }
.soc { font-size:36px; font-weight:700; line-height:1; } .soc sup { font-size:15px; color:var(--dim); font-weight:500; margin-left:2px; }
.soc-l { font-size:10.5px; letter-spacing:.14em; color:var(--dim); margin-top:4px; text-transform:uppercase; }
.tiles { display:grid; gap:10px; }
.tile { background:var(--card2); border:1px solid var(--line); border-radius:16px; padding:12px 14px; min-width:0; }
.tile .l { font-size:10.5px; color:var(--dim); letter-spacing:.08em; text-transform:uppercase; }
.tile .v { font-size:22px; font-weight:700; margin-top:3px; display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.tile .v small { font-size:13px; font-weight:500; color:var(--dim); }
.tile .s { font-size:12px; color:var(--dim); margin-top:3px; line-height:1.35; }
.tile.ok { border-color:rgba(61,220,151,.55); background:linear-gradient(160deg,rgba(61,220,151,.14),var(--card2)); }
.tile.ok .v { color:#9af0c8; }
.tile.warn { border-color:rgba(255,176,32,.5); }
.tile ha-icon { --mdc-icon-size:22px; }
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(130px,1fr)); gap:10px; }
.tires { display:grid; grid-template-columns:repeat(2,1fr); gap:8px; }
.tire { display:flex; justify-content:space-between; gap:8px; align-items:baseline; padding:9px 11px; border-radius:12px; background:var(--card2); border:1px solid var(--line); font-size:13px; }
.tire .n { color:var(--dim); font-size:12px; } .tire .v { font-weight:600; white-space:nowrap; } .tire .v small { color:var(--dim); margin-left:6px; font-weight:500; }
a.link { color:var(--accent); text-decoration:none; font-size:13px; }
.tabs { display:flex; gap:6px; padding:12px 16px 0; overflow-x:auto; }
.tab { flex:1 1 0; display:inline-flex; align-items:center; justify-content:center; gap:6px; padding:9px 10px; border-radius:12px; white-space:nowrap;
  background:transparent; border:1px solid var(--line); color:var(--dim); font:inherit; font-size:13px; cursor:pointer; }
.tab.on { background:rgba(61,220,151,.14); border-color:rgba(61,220,151,.6); color:#e8edf4; }
.tab ha-icon { --mdc-icon-size:17px; }
/* controls */
.btns { display:grid; grid-template-columns:repeat(auto-fit,minmax(135px,1fr)); gap:8px; }
.btn { display:inline-flex; align-items:center; justify-content:center; gap:7px; padding:11px 12px; border-radius:12px; min-height:44px;
  background:var(--card2); border:1px solid var(--line); color:inherit; font:inherit; font-size:13.5px; cursor:pointer; text-align:center; }
.btn:hover { background:#202b39; } .btn:active { transform:scale(.98); }
.btn.primary { background:rgba(61,220,151,.16); border-color:rgba(61,220,151,.6); }
.btn.danger { background:rgba(255,93,93,.12); border-color:rgba(255,93,93,.6); color:#ffb3b3; }
.btn[disabled] { opacity:.45; cursor:progress; }
.btn ha-icon { --mdc-icon-size:19px; }
.row { display:flex; align-items:center; justify-content:space-between; gap:12px; margin:12px 0 4px; font-size:13px; flex-wrap:wrap; }
.row label { color:var(--dim); }
.stepper { display:flex; align-items:center; gap:10px; }
.stepper .val { min-width:74px; text-align:center; font-size:26px; font-weight:700; }
.stepper .btn { min-height:40px; width:44px; padding:0; }
select, input[type=number], input[type=time] { background:var(--card2); color:inherit; border:1px solid var(--line); border-radius:10px; padding:8px 10px; font:inherit; font-size:13.5px; }
input[type=range] { width:100%; accent-color:var(--accent); }
.sw { display:inline-flex; align-items:center; gap:8px; font-size:13.5px; cursor:pointer; }
.sub { margin:14px 0 8px; font-size:11.5px; color:var(--dim); letter-spacing:.1em; text-transform:uppercase; }
.hint { font-size:12px; color:var(--dim); margin-top:6px; }
.foot { text-align:right; font-size:11.5px; color:var(--dim); margin-top:14px; }
@media (max-width:640px) { .stage .photo { max-width:300px; } }
@media (max-width:480px) { .page { padding:10px; } .statusrow { grid-template-columns:1fr; justify-items:center; } .tiles { width:100%; } }
`;

class VoyahFreeCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._busy = new Set();
    this._cfg = {};
    this._sig = null;
    this._deferred = false;
    this._ui = { ...DEFAULT_UI, ...this._loadUi() };

    // delegated events survive innerHTML re-renders
    this.shadowRoot.addEventListener("click", (e) => {
      const el = e.target?.closest?.("[data-act]");
      if (el) this._act(el.dataset.act);
    });
    this.shadowRoot.addEventListener("input", (e) => this._onInput(e, false));
    this.shadowRoot.addEventListener("change", (e) => this._onInput(e, true));
  }

  // ---- Lovelace card interface -------------------------------------------
  static getStubConfig() { return { type: "custom:voyah-free-card", image: "/local/voyah-free-black.png" }; }
  setConfig(config) { this._cfg = { ...(config || {}) }; this._sig = null; if (this._hass) this._render(); }
  getCardSize() { return 12; }
  set hass(hass) { this._hass = hass; this._render(); }

  connectedCallback() {
    this._timer = setInterval(() => { this._sig = null; this._render(); }, 60000);
  }
  disconnectedCallback() { clearInterval(this._timer); this._timer = null; }

  // ---- ui state ----------------------------------------------------------
  _loadUi() {
    try { return JSON.parse(localStorage.getItem(UI_KEY) || "{}") || {}; } catch (_e) { return {}; }
  }
  _saveUi() {
    try { localStorage.setItem(UI_KEY, JSON.stringify(this._ui)); } catch (_e) { /* storage may be blocked */ }
  }
  _onInput(e, commit) {
    const el = e.target;
    const key = el?.dataset?.ui;
    if (!key) return;
    let v = el.type === "checkbox" ? !!el.checked : el.value;
    if (["seat_fl", "seat_fr", "runtime", "max_soc"].includes(key)) v = parseInt(v, 10);
    if (key === "temp") v = parseFloat(v);
    if (typeof v === "number" && !Number.isFinite(v)) return;
    this._ui[key] = v;
    this._saveUi();
    const lab = this.shadowRoot.querySelector?.(`[data-label="${key}"]`);
    if (lab) lab.textContent = key === "max_soc" ? `${v}%` : String(v);
    if (commit && this._deferred) { this._deferred = false; this._sig = null; this._render(); }
  }

  // ---- helpers -----------------------------------------------------------
  get _t() { return String(this._hass?.language || "en").toLowerCase().startsWith("ru") ? I18N.ru : I18N.en; }
  get _lang() { return this._hass?.language || "en"; }

  _discover() {
    const ents = this._hass?.entities || {};
    const dev = this._cfg.device_id;
    let found = Object.values(ents).filter(
      (e) => e.platform === DOMAIN && e.translation_key && (!dev || e.device_id === dev));
    if (!dev && found.length) {
      const first = found.map((e) => e.device_id).filter(Boolean).sort()[0];
      if (first) found = found.filter((e) => e.device_id === first);
    }
    const map = {};
    for (const e of found) map[e.translation_key] = e.entity_id;
    return Object.assign(map, this._cfg.entities || {});
  }
  _st(m, k) { return m[k] ? this._hass.states[m[k]] : undefined; }
  _val(m, k) { const s = this._st(m, k); return !s || s.state === "unknown" || s.state === "unavailable" ? null : s.state; }
  _num(m, k) { const v = this._val(m, k); if (v === null) return null; const n = parseFloat(String(v).replace(",", ".")); return Number.isFinite(n) ? n : null; }
  _on(m, k) { const v = this._val(m, k); return v === null ? null : v === "on"; }
  _unit(m, k) { return this._st(m, k)?.attributes?.unit_of_measurement || ""; }
  _fmt(m, k, d = 0) {
    const n = this._num(m, k);
    if (n === null) return "<span>—</span>";
    const u = this._unit(m, k);
    return `${esc(n.toLocaleString(this._lang, { maximumFractionDigits: d }))}${u ? `<small>${esc(u)}</small>` : ""}`;
  }
  _plural(n, f) {
    if (!String(this._lang).toLowerCase().startsWith("ru")) return n === 1 ? f[0] : f[1];
    const a = n % 10, b = n % 100;
    if (a === 1 && b !== 11) return f[0];
    if (a >= 2 && a <= 4 && (b < 10 || b >= 20)) return f[1];
    return f[2];
  }
  _dur(totalMin) {
    const t = this._t;
    if (totalMin < 1) return t.lt_min;
    const h = Math.floor(totalMin / 60), mi = Math.round(totalMin % 60), p = [];
    if (h) p.push(`${h} ${this._plural(h, t.hrs)}`);
    if (mi || !h) p.push(`${mi} ${this._plural(mi, t.min)}`);
    return p.join(" ");
  }
  _signature(m) {
    const parts = [this._lang, Math.floor(Date.now() / 60000), [...this._busy].join(","), JSON.stringify(this._ui), this._cfg.image || ""];
    for (const id of Object.values(m)) { const s = this._hass.states[id]; parts.push(id, s ? s.state + "|" + s.last_updated : "-"); }
    return parts.join(";");
  }

  // ---- actions -----------------------------------------------------------
  _plan(m) {
    const t = this._t, u = this._ui;
    const press = (k) => ["button", "press", { entity_id: m[k] }];
    const need = (k) => m[k];
    return {
      lock: need("ctl_lock") && (() => ["lock", "lock", { entity_id: m.ctl_lock }]),
      unlock: need("ctl_lock") && (() => confirm(t.c_unlock) && ["lock", "unlock", { entity_id: m.ctl_lock }]),
      trunk_open: need("ctl_tailgate") && (() => confirm(t.c_trunk) && ["cover", "open_cover", { entity_id: m.ctl_tailgate }]),
      trunk_close: need("ctl_tailgate") && (() => ["cover", "close_cover", { entity_id: m.ctl_tailgate }]),
      win_open: need("ctl_windows") && (() => ["cover", "open_cover", { entity_id: m.ctl_windows }]),
      win_close: need("ctl_windows") && (() => ["cover", "close_cover", { entity_id: m.ctl_windows }]),
      win_vent: need("btn_windows_vent") && (() => press("btn_windows_vent")),
      roof_open: need("ctl_sunroof") && (() => ["cover", "open_cover", { entity_id: m.ctl_sunroof }]),
      roof_close: need("ctl_sunroof") && (() => ["cover", "close_cover", { entity_id: m.ctl_sunroof }]),
      roof_vent: need("btn_sunroof_vent") && (() => press("btn_sunroof_vent")),
      find: need("btn_find_start") && (() => press("btn_find_start")),
      find_stop: need("btn_find_stop") && (() => press("btn_find_stop")),
      hazard: need("btn_hazard") && (() => press("btn_hazard")),
      sentry_on: need("ctl_sentry") && (() => ["switch", "turn_on", { entity_id: m.ctl_sentry }]),
      sentry_off: need("ctl_sentry") && (() => ["switch", "turn_off", { entity_id: m.ctl_sentry }]),
      keyless: need("btn_keyless_start") && (() => confirm(t.c_keyless) && confirm(t.c_keyless2) && press("btn_keyless_start")),
      temp_dec: () => { u.temp = Math.max(16, Math.round((u.temp - 0.5) * 2) / 2); this._saveUi(); return null; },
      temp_inc: () => { u.temp = Math.min(32, Math.round((u.temp + 0.5) * 2) / 2); this._saveUi(); return null; },
      climate_start: need("ctl_climate") && (() => ["voyahtweaks-ha", "climate_start", this._climatePayload(m, "temp")]),
      climate_heat: need("ctl_climate") && (() => ["voyahtweaks-ha", "climate_start", this._climatePayload(m, "rapid_heat")]),
      climate_cool: need("ctl_climate") && (() => ["voyahtweaks-ha", "climate_start", this._climatePayload(m, "rapid_cool")]),
      climate_stop: need("ctl_climate") && (() => ["climate", "set_hvac_mode", { entity_id: m.ctl_climate, hvac_mode: "off" }]),
      charge_start: need("ctl_charge") && (() => ["voyahtweaks-ha", "charge_start", { entity_id: m.ctl_charge, max_soc: u.max_soc }]),
      charge_stop: need("ctl_charge") && (() => ["switch", "turn_off", { entity_id: m.ctl_charge }]),
      charge_schedule: need("ctl_charge") && (() => ["voyahtweaks-ha", "charge_schedule", { entity_id: m.ctl_charge, start: u.from, end: u.to, max_soc: u.max_soc, cycle: !!u.cycle }]),
      charge_cancel: need("ctl_charge") && (() => ["voyahtweaks-ha", "charge_cancel_schedule", { entity_id: m.ctl_charge }]),
    };
  }
  _climatePayload(m, mode) {
    const u = this._ui, p = { entity_id: m.ctl_climate, mode };
    if (mode === "temp") p.temperature = u.temp;
    if (u.seat_fl) p.seat_fl = u.seat_fl;
    if (u.seat_fr) p.seat_fr = u.seat_fr;
    if (u.glass && mode !== "rapid_cool") p.glass_heat = true;
    if (u.runtime) p.runtime = u.runtime;
    return p;
  }
  _toast(message) {
    this.dispatchEvent(new CustomEvent("hass-notification", { detail: { message }, bubbles: true, composed: true }));
  }
  async _act(name) {
    if (name.startsWith("tab_")) { this._ui.tab = name.slice(4); this._saveUi(); this._sig = null; this._render(); return; }
    if (!this._hass || this._busy.size) return; // one command at a time
    const m = this._discover();
    const fn = this._plan(m)[name];
    if (!fn) return;
    const call = fn();
    if (name === "temp_dec" || name === "temp_inc") { this._sig = null; this._render(); return; }
    if (!call) return; // declined confirm
    const t = this._t;
    this._busy.add(name); this._sig = null; this._render();
    try {
      await this._hass.callService(call[0], call[1], call[2]);
      this._toast(t.done);
    } catch (err) {
      this._toast(`${t.failed}: ${err?.message || err}`);
    } finally {
      this._busy.delete(name); this._sig = null; this._render();
    }
  }

  // ---- rendering ---------------------------------------------------------
  _btn(act, icon, label, cls = "") {
    const busy = this._busy.has(act), off = this._busy.size > 0;
    return `<button class="btn ${cls}" data-act="${act}" ${off ? "disabled" : ""}><ha-icon icon="${busy ? "mdi:loading" : icon}"></ha-icon>${esc(label)}</button>`;
  }

  _car(open) {
    const c = (k) => (open[k] ? "bad" : "");
    const dr = (k, x, y, h, rot) => `<rect class="panel ${c(k)}" x="${x}" y="${y}" width="8" height="${h}" rx="3" ${open[k] ? `transform="rotate(${rot})"` : ""}/>`;
    return `<svg class="car" viewBox="0 0 200 400" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Voyah Free">
  <rect class="wheel" x="30" y="70" width="14" height="46" rx="6"/><rect class="wheel" x="156" y="70" width="14" height="46" rx="6"/>
  <rect class="wheel" x="30" y="268" width="14" height="46" rx="6"/><rect class="wheel" x="156" y="268" width="14" height="46" rx="6"/>
  <path class="shell" d="M64 16 Q100 2 136 16 Q152 22 154 46 L158 116 L158 300 L154 340 Q150 368 100 372 Q50 368 46 340 L42 300 L42 116 L46 46 Q48 22 64 16Z"/>
  <path class="lamp" d="M60 24 Q70 18 84 20 L82 28 Q70 26 62 32Z"/><path class="lamp" d="M140 24 Q130 18 116 20 L118 28 Q130 26 138 32Z"/>
  <path class="glass" d="M58 62 Q100 50 142 62 L148 112 L52 112Z"/>
  <path class="glass" d="M54 296 L146 296 L140 328 Q100 340 60 328Z"/>
  <rect class="pano ${open.roof ? "bad" : ""}" x="66" y="150" width="68" height="70" rx="9"/>
  <rect class="tail" x="62" y="364" width="22" height="4" rx="2"/><rect class="tail" x="116" y="364" width="22" height="4" rx="2"/>
  <line class="win ${c("w_fl")}" x1="46" y1="122" x2="46" y2="168"/><line class="win ${c("w_fr")}" x1="154" y1="122" x2="154" y2="168"/>
  <line class="win ${c("w_rl")}" x1="46" y1="204" x2="46" y2="248"/><line class="win ${c("w_rr")}" x1="154" y1="204" x2="154" y2="248"/>
  ${dr("d_fl", 36, 118, 84, "28 40 118")}${dr("d_fr", 156, 118, 84, "-28 160 118")}
  ${dr("d_rl", 36, 206, 80, "28 40 206")}${dr("d_rr", 156, 206, 80, "-28 160 206")}
  <rect class="panel ${c("trunk")}" x="68" y="346" width="64" height="10" rx="4" ${open.trunk ? 'transform="translate(0 10)"' : ""}/>
</svg>`;
  }

  _render() {
    if (!this._hass) return;
    const m = this._discover();
    const sig = this._signature(m);
    if (sig === this._sig) return;
    // don't destroy a field the user is editing
    const ae = this.shadowRoot.activeElement;
    if (ae && /^(INPUT|SELECT)$/.test(ae.tagName)) { this._deferred = true; return; }
    this._sig = sig;

    const t = this._t;
    if (!Object.keys(m).length) {
      this.shadowRoot.innerHTML = `<style>${STYLE}</style><ha-card><div class="page"><div class="banner info">${esc(t.no_entities)}</div></div></ha-card>`;
      return;
    }

    // ---- availability / freshness: kept strictly separate ----
    const online = this._on(m, "online"), apiOk = this._on(m, "api");
    const fs = this._st(m, "telemetry_fresh");
    const seenRaw = this._val(m, "last_seen");
    const seen = seenRaw ? new Date(seenRaw) : null;
    const ageMin = seen && !isNaN(seen) ? Math.max(0, Math.floor((Date.now() - seen.getTime()) / 60000)) : null;
    const thr = Number(fs?.attributes?.threshold_minutes) || 10;
    let fresh = fs && fs.state !== "unknown" ? fs.state === "on" : null;
    if (fresh === true && ageMin !== null && ageMin > thr) fresh = false;

    const chip = (cls, txt) => `<span class="chip ${cls}"><span class="dot"></span>${esc(txt)}</span>`;
    const chips = (online === null ? chip("", t.nodata) : chip(online ? "ok" : "bad", online ? t.online : t.offline)) +
      (fresh === null ? chip("", t.fresh_unknown) : chip(fresh ? "ok" : "warn", fresh ? t.fresh : t.stale));

    let banners = "";
    if (apiOk === false) banners += `<div class="banner bad"><ha-icon icon="mdi:cloud-off-outline"></ha-icon><div>${esc(t.warn_api(this._st(m, "api")?.attributes?.last_error))}</div></div>`;
    if (fresh === false) banners += `<div class="banner"><ha-icon icon="mdi:sleep"></ha-icon><div>${esc(ageMin !== null ? t.warn_stale(this._dur(ageMin)) : t.warn_unknown)}</div></div>`;
    else if (fresh === null && !seen) banners += `<div class="banner"><ha-icon icon="mdi:help-circle-outline"></ha-icon><div>${esc(t.warn_unknown)}</div></div>`;

    // ---- body state ----
    const dOpen = (k) => this._on(m, k) === true;
    const w = (k) => this._val(m, k);
    const tail = this._on(m, "tailgate") === true;
    const roof = this._val(m, "sunroof");
    const open = {
      d_fl: dOpen("door_fl"), d_fr: dOpen("door_fr"), d_rl: dOpen("door_rl"), d_rr: dOpen("door_rr"),
      w_fl: ["open", "ajar"].includes(w("window_fl")), w_fr: ["open", "ajar"].includes(w("window_fr")),
      w_rl: ["open", "ajar"].includes(w("window_rl")), w_rr: ["open", "ajar"].includes(w("window_rr")),
      trunk: tail, roof: roof === "open" || roof === "vent",
    };
    const badge = (cls, icon, txt, extra = "") => `<span class="badge ${extra} ${cls}"><ha-icon icon="${icon}"></ha-icon>${esc(txt)}</span>`;
    const pos = { fl: "b-fl", fr: "b-fr", rl: "b-rl", rr: "b-rr" };
    let badges = "";
    for (const p of ["fl", "fr", "rl", "rr"]) {
      if (open[`d_${p}`]) badges += badge(pos[p], "mdi:car-door", `${t[p]}: ${t.d_open}`);
      else if (open[`w_${p}`]) badges += badge(pos[p], "mdi:window-open-variant", `${t[p]}: ${w("window_" + p) === "ajar" ? t.w_ajar : t.w_open}`);
    }
    if (tail) badges += badge("b-trunk", "mdi:car-back", `${t.trunk}: ${t.open.toLowerCase()}`);
    if (open.roof) badges += badge("b-roof", "mdi:car-select", `${t.roof}: ${(roof === "vent" ? t.vent : t.open).toLowerCase()}`);
    const unlocked = this._on(m, "lock");
    if (unlocked !== null) badges += badge("b-lock", unlocked ? "mdi:lock-open-variant" : "mdi:lock", unlocked ? t.unlocked : t.locked, unlocked ? "" : "ok");

    const charging = this._on(m, "charging");
    if (charging === true) badges += badge("b-chg", "mdi:lightning-bolt", t.charging, "ok");

    const img = this._cfg.image;
    const stage = img
      ? `<img class="photo" src="${esc(img)}" alt="Voyah Free">`
      : this._car(open);

    // ---- charge / cabin ----
    const connected = this._on(m, "charger_connected");
    const ctype = this._val(m, "charge_type");
    const cpow = this._num(m, "charging_power");
    const rem = this._num(m, "charge_remaining");
    const chgTitle = charging === true ? t.charging : charging === false ? (connected ? t.plugged : t.not_charging) : t.nodata;
    const chgCls = charging === true ? "ok" : connected ? "warn" : "";
    const chgSub = [];
    if (ctype) chgSub.push(`${t.charger}: ${t["ch_" + ctype] || ctype}`);
    if (charging === true && cpow !== null) chgSub.push(`${t.power}: ${cpow.toLocaleString(this._lang, { maximumFractionDigits: 1 })} ${this._unit(m, "charging_power") || ""}`.trim());
    if (charging === true && rem !== null) chgSub.push(`${t.left}: ${this._dur(rem)}`);
    const chgState = this._val(m, "charge_state");
    if (chgState) chgSub.push(`chg_state: ${chgState}`);

    const cabin = this._num(m, "cabin_temp"), outside = this._num(m, "ambient_temp");
    const climOn = this._on(m, "climate_remote");
    const cabTxt = cabin === null ? "—" : `${cabin.toLocaleString(this._lang, { maximumFractionDigits: 1 })}`;
    const cabSub = [];
    if (climOn !== null) cabSub.push(climOn ? t.clim_on : t.clim_off);
    if (outside !== null) cabSub.push(`${t.outside}: ${outside.toLocaleString(this._lang, { maximumFractionDigits: 0 })}°`);

    // ---- SOC ring ----
    const soc = this._num(m, "soc"), R = 62, C = 2 * Math.PI * R;
    const pct = soc === null ? 0 : Math.min(100, Math.max(0, soc));
    const rc = soc === null ? "#5a6678" : soc > 50 ? "#3ddc97" : soc > 20 ? "#ffb020" : "#ff5d5d";

    // ---- metrics / tires / location ----
    const metric = (l, v, s = "") => `<div class="tile"><div class="l">${esc(l)}</div><div class="v">${v}</div>${s ? `<div class="s">${s}</div>` : ""}</div>`;
    const real = this._num(m, "range_real");
    const metrics = [
      metric(t.range, this._fmt(m, "range", 0), real !== null ? `${esc(t.range_real)}: ${esc(String(real))} ${esc(this._unit(m, "range_real"))}` : ""),
      metric(t.soh, this._fmt(m, "soh", 1)),
      metric(t.mileage, this._fmt(m, "mileage", 0)),
      metric(t.speed, this._fmt(m, "speed", 0)),
      metric(t.pack, this._fmt(m, "pack_temp_avg", 0)),
      metric(t.v12, this._fmt(m, "v12_voltage", 1)),
    ].join("");

    const pUnit = this._unit(m, "tire_pressure_fl");
    const tirePos = ["fl", "fr", "rl", "rr"];
    const hasTires = tirePos.some((p) => m[`tire_pressure_${p}`] || m[`tire_temp_${p}`]);
    const tires = hasTires ? `<div class="card"><h2>${esc(t.tires)} · ${esc(t.tire_hint)}</h2><div class="tires">${tirePos.map((p) => {
      const pr = this._num(m, `tire_pressure_${p}`), tp = this._num(m, `tire_temp_${p}`);
      const prT = pr === null ? "—" : pr.toLocaleString(this._lang, { maximumFractionDigits: 1 }) + (pUnit ? ` ${pUnit}` : "");
      return `<div class="tire"><span class="n">${esc(t[p])}</span><span class="v">${esc(prT)}<small>${esc(tp === null ? "—" : Math.round(tp) + "°")}</small></span></div>`;
    }).join("")}</div></div>` : "";

    const trk = this._st(m, "location");
    const lat = trk?.attributes?.latitude, lon = trk?.attributes?.longitude;
    const loc = m.location ? `<div class="card"><h2>${esc(t.location)}</h2>${
      typeof lat === "number" && typeof lon === "number"
        ? `<a class="link" target="_blank" rel="noopener noreferrer" href="https://yandex.ru/maps/?pt=${lon},${lat}&z=17&l=map">${esc(t.on_map)} · ${lat.toFixed(5)}, ${lon.toFixed(5)}</a>`
        : `<span class="hint">${esc(t.no_gps)}</span>`}</div>` : "";

    // ---- controls (each block only when its entities exist) ----
    const has = (...k) => k.some((x) => m[x]);
    const u = this._ui;
    const seatOpts = (cur) => [-3, -2, -1, 0, 1, 2, 3].map((n) =>
      `<option value="${n}" ${cur === n ? "selected" : ""}>${esc(n === 0 ? t.seat_off : n > 0 ? t.seat_heat(n) : t.seat_vent(-n))}</option>`).join("");

    const access = has("ctl_lock", "ctl_tailgate", "btn_find_start", "btn_hazard") ? `<div class="card"><h2>${esc(t.h_access)}</h2><div class="btns">
      ${m.ctl_lock ? this._btn("lock", "mdi:lock", t.lock, "primary") + this._btn("unlock", "mdi:lock-open-variant", t.unlock) : ""}
      ${m.ctl_tailgate ? this._btn("trunk_open", "mdi:car-back", t.trunk_open) + this._btn("trunk_close", "mdi:car-back", t.trunk_close) : ""}
      ${m.btn_find_start ? this._btn("find", "mdi:bullhorn", t.find) : ""}${m.btn_find_stop ? this._btn("find_stop", "mdi:bullhorn-outline", t.find_stop) : ""}
      ${m.btn_hazard ? this._btn("hazard", "mdi:car-light-alert", t.hazard) : ""}</div></div>` : "";

    const glass = has("ctl_windows", "ctl_sunroof") ? `<div class="card"><h2>${esc(t.h_glass)}</h2><div class="btns">
      ${m.ctl_windows ? this._btn("win_open", "mdi:window-open-variant", t.win_open) + this._btn("win_close", "mdi:window-closed-variant", t.win_close) : ""}
      ${m.btn_windows_vent ? this._btn("win_vent", "mdi:window-open", t.win_vent) : ""}
      ${m.ctl_sunroof ? this._btn("roof_open", "mdi:car-select", t.roof_open) + this._btn("roof_close", "mdi:car-select", t.roof_close) : ""}
      ${m.btn_sunroof_vent ? this._btn("roof_vent", "mdi:weather-windy", t.roof_vent) : ""}</div></div>` : "";

    const climate = m.ctl_climate ? `<div class="card"><h2>${esc(t.h_climate)}</h2>
      <div class="row"><label>${esc(t.c_temp)}</label><div class="stepper">
        ${this._btn("temp_dec", "mdi:minus", "")}<span class="val">${esc(u.temp.toFixed(1))}°</span>${this._btn("temp_inc", "mdi:plus", "")}</div></div>
      <div class="btns" style="margin-top:10px">
        ${this._btn("climate_start", "mdi:air-conditioner", t.c_start, "primary")}${this._btn("climate_stop", "mdi:power", t.c_stop)}
        ${this._btn("climate_heat", "mdi:fire", t.c_heat)}${this._btn("climate_cool", "mdi:snowflake", t.c_cool)}</div>
      <div class="sub">${esc(t.seat_title)}</div>
      <div class="row"><label>${esc(t.c_seat_fl)}</label><select data-ui="seat_fl">${seatOpts(u.seat_fl)}</select></div>
      <div class="row"><label>${esc(t.c_seat_fr)}</label><select data-ui="seat_fr">${seatOpts(u.seat_fr)}</select></div>
      <div class="row"><label class="sw"><input type="checkbox" data-ui="glass" ${u.glass ? "checked" : ""}> ${esc(t.c_glass)}</label>
        <span><label>${esc(t.c_runtime)}&nbsp;</label><input type="number" data-ui="runtime" min="1" max="120" step="1" value="${esc(u.runtime)}" style="width:76px"></span></div>
    </div>` : "";

    const charge = m.ctl_charge ? `<div class="card"><h2>${esc(t.h_charge)}</h2>
      <div class="row"><label>${esc(t.ch_target)}</label><b data-label="max_soc">${esc(u.max_soc)}%</b></div>
      <input type="range" data-ui="max_soc" min="50" max="100" step="1" value="${esc(u.max_soc)}">
      <div class="btns" style="margin-top:12px">${this._btn("charge_start", "mdi:ev-station", t.ch_start, "primary")}${this._btn("charge_stop", "mdi:stop", t.ch_stop)}</div>
      <div class="sub">${esc(t.ch_sched)}</div>
      <div class="row"><label>${esc(t.ch_from)} <input type="time" data-ui="from" value="${esc(u.from)}"></label>
        <label>${esc(t.ch_to)} <input type="time" data-ui="to" value="${esc(u.to)}"></label></div>
      <div class="row"><label class="sw"><input type="checkbox" data-ui="cycle" ${u.cycle ? "checked" : ""}> ${esc(t.ch_daily)}</label></div>
      <div class="btns">${this._btn("charge_schedule", "mdi:calendar-clock", t.ch_set)}${this._btn("charge_cancel", "mdi:calendar-remove", t.ch_cancel)}</div>
    </div>` : "";

    const sentryOn = this._on(m, "sentry_active");
    const safety = has("ctl_sentry", "btn_keyless_start") ? `<div class="card"><h2>${esc(t.h_safety)}</h2><div class="btns">
      ${m.ctl_sentry ? (sentryOn ? this._btn("sentry_off", "mdi:shield-off", t.sentry_off) : this._btn("sentry_on", "mdi:shield-car", t.sentry_on, "primary")) : ""}
      ${m.btn_keyless_start ? this._btn("keyless", "mdi:engine", t.keyless, "danger") : ""}</div>
      ${m.btn_keyless_start ? `<div class="hint">${esc(t.keyless_hint)}</div>` : ""}</div>` : "";

    const anyControl = access || glass || climate || charge || safety;
    const noControls = anyControl ? "" : `<div class="banner info"><ha-icon icon="mdi:information-outline"></ha-icon><div>${esc(t.controls_off)}</div></div>`;

    // ---- tabs: only those that have something to show ----
    const tabs = [["status", "mdi:car-info"]];
    if (access || glass || safety) tabs.push(["control", "mdi:remote"]);
    if (climate) tabs.push(["climate", "mdi:air-conditioner"]);
    if (charge) tabs.push(["charge", "mdi:ev-station"]);
    const tab = tabs.some(([k]) => k === u.tab) ? u.tab : "status";
    const tabsHtml = tabs.length > 1
      ? `<div class="tabs">${tabs.map(([k, ic]) => `<button class="tab ${tab === k ? "on" : ""}" data-act="tab_${k}"><ha-icon icon="${ic}"></ha-icon>${esc(t["t_" + k])}</button>`).join("")}</div>` : "";

    const statusPage = `
      <div class="card hero">
        <div class="stage">${stage}${badges}</div>
        <div class="statusrow">
          <div class="ring ${charging === true ? "charging" : ""}">
            <svg viewBox="0 0 150 150"><circle class="bg" cx="75" cy="75" r="${R}" fill="none" stroke-width="12"/>
              <circle class="fg" cx="75" cy="75" r="${R}" fill="none" stroke-width="12" stroke="${rc}"
                stroke-dasharray="${C.toFixed(1)}" stroke-dashoffset="${(C * (1 - pct / 100)).toFixed(1)}"/></svg>
            <div class="center"><div class="soc">${soc === null ? "—" : esc(Math.round(soc))}${soc === null ? "" : "<sup>%</sup>"}</div><div class="soc-l">${esc(t.soc)}</div></div>
          </div>
          <div class="tiles">
            <div class="tile ${chgCls}"><div class="l">${esc(t.h_charge)}</div>
              <div class="v"><ha-icon icon="${charging === true ? "mdi:lightning-bolt" : connected ? "mdi:power-plug" : "mdi:power-plug-off"}"></ha-icon>${esc(chgTitle)}</div>
              ${chgSub.length ? `<div class="s">${chgSub.map(esc).join("<br>")}</div>` : ""}</div>
            <div class="tile"><div class="l">${esc(t.cabin)}</div>
              <div class="v"><ha-icon icon="mdi:thermometer"></ha-icon>${esc(cabTxt)}${cabin === null ? "" : "<small>°C</small>"}</div>
              ${cabSub.length ? `<div class="s">${cabSub.map(esc).join(" · ")}</div>` : ""}</div>
          </div>
        </div>
      </div>
      <div class="card"><div class="grid">${metrics}</div></div>
      ${tires}${loc}${noControls}`;

    const pages = { status: statusPage, control: access + glass + safety, climate, charge };
    const foot = seen && !isNaN(seen) ? `<div class="foot">${esc(t.last_seen)}: ${esc(seen.toLocaleString(this._lang))}</div>` : "";

    this.shadowRoot.innerHTML = `<style>${STYLE}</style>
<ha-card>
  <div class="head"><h1>${esc(this._cfg.name || "VOYAH FREE")}</h1><div class="chips">${chips}</div></div>
  ${tabsHtml}
  <div class="page">
    ${banners}
    <div class="col">${pages[tab]}</div>
    ${foot}
  </div>
</ha-card>`;
  }
}

if (!customElements.get("voyah-free-card")) customElements.define("voyah-free-card", VoyahFreeCard);
window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "voyah-free-card")) {
  window.customCards.push({
    type: "voyah-free-card",
    name: "VOYAH FREE",
    description: "Voyah Free: status, charging, cabin temperature and controls (voyahtweaks-ha integration).",
  });
}