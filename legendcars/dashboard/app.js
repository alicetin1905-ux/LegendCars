/* LegendCars dashboard: filters, rangschikking en detailweergave. Data staat in window.LEGEND_DATA. */
(function () {
  "use strict";

  var D = window.LEGEND_DATA;
  var V = window.Valuation;
  if (!D || !V) return;

  var STORE_KEY = "legendcars-state-v2";
  var PAGE = 60;
  var CURRENT_YEAR = Number((D.today || "").slice(0, 4)) || new Date().getFullYear();
  var SOURCE_NAMES = { autoscout24: "AutoScout24", "2dehands": "2dehands", marktplaats: "Marktplaats", kleinanzeigen: "Kleinanzeigen" };
  var COUNTRY_NAMES = { B: "België", NL: "Nederland", D: "Duitsland", L: "Luxemburg", F: "Frankrijk", A: "Oostenrijk", I: "Italië", E: "Spanje" };

  var COST_FIELDS = [
    { key: "storage_per_month", label: "Stalling", unit: "€ / maand", step: 5 },
    { key: "insurance_per_year", label: "Verzekering", unit: "€ / jaar", step: 10 },
    { key: "tax_per_year", label: "Verkeersbelasting", unit: "€ / jaar", step: 10 },
    { key: "maintenance_per_year", label: "Onderhoud", unit: "€ / jaar", step: 50 },
    { key: "buy_costs", label: "Aankoopkosten", unit: "€ eenmalig", step: 50 },
    { key: "sell_pct", label: "Verkoopkosten", unit: "% van waarde", step: 0.5 },
    { key: "deal_credit", label: "Koopje telt mee", unit: "% van verschil", step: 5 },
  ];
  var WEIGHT_FIELDS = [
    { key: "ret", label: "Verwacht rendement" },
    { key: "deal", label: "Prijs t.o.v. markt" },
    { key: "rarity", label: "Zeldzaamheid" },
    { key: "demand", label: "Vraag bij liefhebbers" },
    { key: "conf", label: "Betrouwbaarheid data" },
  ];
  var DEFAULT_WEIGHTS = { ret: 50, deal: 15, rarity: 10, demand: 15, conf: 10 };

  var defaults = Object.assign(
    { horizon_years: 5, storage_per_month: 60, insurance_per_year: 180, tax_per_year: 50, maintenance_per_year: 400, buy_costs: 500, sell_pct: 5, deal_credit: 50 },
    D.defaults || {}
  );

  function freshState() {
    return {
      horizon: defaults.horizon_years,
      make: "", model: "", country: "", source: "", sort: "score", q: "",
      priceMin: num(defaults.price_min), priceMax: num(defaults.price_max), maxKm: num(defaults.max_km),
      manual: false, hideRisk: true, hideLowConf: true, gainOnly: false,
      costs: pick(defaults, COST_FIELDS.map(function (f) { return f.key; })),
      weights: Object.assign({}, DEFAULT_WEIGHTS),
    };
  }

  function num(x) {
    var n = Number(x);
    return x === "" || x == null || isNaN(n) ? null : n;
  }

  function pick(obj, keys) {
    var o = {};
    keys.forEach(function (k) { o[k] = Number(obj[k]); });
    return o;
  }

  var state = freshState();
  try {
    var saved = JSON.parse(localStorage.getItem(STORE_KEY) || "null");
    if (saved && typeof saved === "object") {
      state = Object.assign(state, saved, {
        costs: Object.assign(state.costs, saved.costs || {}),
        weights: Object.assign(state.weights, saved.weights || {}),
      });
    }
  } catch (e) { /* geen opslag beschikbaar: standaardwaarden */ }

  function persist() {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(state)); } catch (e) { /* negeren */ }
  }

  var limit = PAGE;
  var openId = null;

  /* ---------- formattering ---------- */
  var eur = new Intl.NumberFormat("nl-BE", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
  var int = new Intl.NumberFormat("nl-BE", { maximumFractionDigits: 0 });
  function fmtEur(x) { return x == null || isNaN(x) ? "–" : eur.format(Math.round(x)); }
  function fmtSigned(x) { return (x >= 0 ? "+" : "−") + eur.format(Math.abs(Math.round(x))); }
  function fmtPct(x, digits) { var d = digits == null ? 1 : digits; return (x >= 0 ? "+" : "−") + Math.abs(x * 100).toFixed(d).replace(".", ",") + "%"; }
  function fmtRate(x) { return (x >= 0 ? "+" : "−") + Math.abs(x).toFixed(1).replace(".", ",") + "%"; }
  function fmtKm(x) { return x ? int.format(x) + " km" : "km onbekend"; }
  function fmtDate(iso) {
    if (!iso) return "";
    var d = new Date(iso);
    return isNaN(d) ? iso : d.toLocaleDateString("nl-BE", { day: "numeric", month: "short", year: "numeric" });
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function yearsLabel(h) { return h + (h === 1 ? " jaar" : " jaar"); }

  function params() {
    return Object.assign({ horizon: state.horizon }, state.costs);
  }

  /* ---------- berekening ---------- */
  var models = D.models || {};
  var listings = (D.listings || []).filter(function (l) { return models[l.model]; });

  function compute() {
    var p = params();
    return listings.map(function (l) {
      var proj = V.project(l, p, CURRENT_YEAR);
      var sc = V.score(l, models[l.model], proj, state.weights);
      return { l: l, m: models[l.model], proj: proj, score: sc.value, scoreParts: sc.parts };
    });
  }

  var RISK = { "Project/restauratie": 1, Schade: 1, Defect: 1, "Geen papieren": 1, "Prijs verdacht laag": 1 };

  function filtered(rows) {
    var q = state.q.trim().toLowerCase();
    return rows.filter(function (r) {
      var l = r.l;
      if (state.make && r.m.make !== state.make) return false;
      if (state.model && l.model !== state.model) return false;
      if (state.priceMin != null && l.price < state.priceMin) return false;
      if (state.priceMax != null && l.price > state.priceMax) return false;
      if (state.maxKm != null && l.km && l.km > state.maxKm) return false;
      if (state.country && l.cc !== state.country) return false;
      if (state.source && l.src !== state.source) return false;
      if (state.manual && l.gear !== "manual") return false;
      if (state.hideRisk && l.flags.some(function (f) { return RISK[f]; })) return false;
      if (state.hideLowConf && l.conf < 0.5) return false;
      if (state.gainOnly && r.proj.net <= 0) return false;
      if (q && (l.title + " " + l.variants.join(" ")).toLowerCase().indexOf(q) === -1) return false;
      return true;
    });
  }

  var SORTS = {
    score: function (a, b) { return b.score - a.score; },
    net: function (a, b) { return b.proj.net - a.proj.net; },
    annual: function (a, b) { return b.proj.annual - a.proj.annual; },
    deal: function (a, b) { return b.l.fair / b.l.price - a.l.fair / a.l.price; },
    price: function (a, b) { return a.l.price - b.l.price; },
    new: function (a, b) { return (a.l.days == null ? 1e9 : a.l.days) - (b.l.days == null ? 1e9 : b.l.days); },
  };

  function median(xs) {
    if (!xs.length) return null;
    var s = xs.slice().sort(function (a, b) { return a - b; });
    var mid = Math.floor(s.length / 2);
    return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
  }

  /* ---------- UI: filters ---------- */
  function $(id) { return document.getElementById(id); }

  function fillSelect(el, options, value, allLabel) {
    el.innerHTML = '<option value="">' + esc(allLabel) + "</option>" + options.map(function (o) {
      return '<option value="' + esc(o.value) + '"' + (o.value === value ? " selected" : "") + ">" + esc(o.label) + "</option>";
    }).join("");
    if (value && !options.some(function (o) { return o.value === value; })) el.value = "";
  }

  function countBy(fn) {
    var c = {};
    listings.forEach(function (l) { var k = fn(l); if (k) c[k] = (c[k] || 0) + 1; });
    return c;
  }

  function buildFilterOptions() {
    var makes = {};
    Object.keys(models).forEach(function (id) { makes[models[id].make] = true; });
    fillSelect($("f-make"), Object.keys(makes).sort().map(function (m) { return { value: m, label: m }; }), state.make, "Alle merken");
    buildModelOptions();
    var cc = countBy(function (l) { return l.cc; });
    fillSelect($("f-country"), Object.keys(cc).sort(function (a, b) { return cc[b] - cc[a]; }).map(function (c) {
      return { value: c, label: (COUNTRY_NAMES[c] || c) + " (" + cc[c] + ")" };
    }), state.country, "Alle landen");
    var sc = countBy(function (l) { return l.src; });
    fillSelect($("f-source"), Object.keys(sc).map(function (s) {
      return { value: s, label: (SOURCE_NAMES[s] || s) + " (" + sc[s] + ")" };
    }), state.source, "Alle websites");
  }

  function buildModelOptions() {
    var ids = Object.keys(models).filter(function (id) { return !state.make || models[id].make === state.make; });
    ids.sort(function (a, b) { return (models[a].make + models[a].name).localeCompare(models[b].make + models[b].name); });
    fillSelect($("f-model"), ids.map(function (id) {
      var m = models[id];
      return { value: id, label: (state.make ? "" : m.make + " ") + m.name + " (" + (m.active || 0) + ")" };
    }), state.model, "Alle modellen");
    state.model = $("f-model").value;
  }

  function buildCostFields() {
    $("cost-grid").innerHTML = COST_FIELDS.map(function (f) {
      return '<div class="cost-field"><label for="c-' + f.key + '">' + esc(f.label) + '</label><div class="with-unit">' +
        '<input type="number" id="c-' + f.key + '" min="0" step="' + f.step + '" value="' + state.costs[f.key] + '" data-cost="' + f.key + '">' +
        '<span class="unit">' + esc(f.unit) + "</span></div></div>";
    }).join("");
    $("weight-grid").innerHTML = WEIGHT_FIELDS.map(function (f) {
      return '<div class="cost-field"><label for="w-' + f.key + '">' + esc(f.label) + ' <span id="wv-' + f.key + '">' + state.weights[f.key] + "</span></label>" +
        '<input type="range" id="w-' + f.key + '" min="0" max="100" step="5" value="' + state.weights[f.key] + '" data-weight="' + f.key + '"></div>';
    }).join("");
  }

  function syncControls() {
    $("horizon").value = state.horizon;
    $("f-pmin").value = state.priceMin == null ? "" : state.priceMin;
    $("f-pmax").value = state.priceMax == null ? "" : state.priceMax;
    $("f-km").value = state.maxKm == null ? "" : state.maxKm;
    $("f-sort").value = state.sort;
    $("f-q").value = state.q;
    $("f-manual").checked = state.manual;
    $("f-risk").checked = state.hideRisk;
    $("f-conf").checked = state.hideLowConf;
    $("f-gain").checked = state.gainOnly;
  }

  function bind() {
    $("horizon").addEventListener("input", function (e) { state.horizon = Number(e.target.value); update(); });
    $("f-make").addEventListener("change", function (e) { state.make = e.target.value; state.model = ""; buildModelOptions(); update(true); });
    $("f-model").addEventListener("change", function (e) { state.model = e.target.value; update(true); });
    [["f-pmin", "priceMin"], ["f-pmax", "priceMax"], ["f-km", "maxKm"]].forEach(function (pair) {
      var t;
      $(pair[0]).addEventListener("input", function (e) {
        clearTimeout(t);
        t = setTimeout(function () { state[pair[1]] = num(e.target.value); update(true); }, 250);
      });
    });
    $("f-country").addEventListener("change", function (e) { state.country = e.target.value; update(true); });
    $("f-source").addEventListener("change", function (e) { state.source = e.target.value; update(true); });
    $("f-sort").addEventListener("change", function (e) { state.sort = e.target.value; update(true); });
    var qTimer;
    $("f-q").addEventListener("input", function (e) {
      clearTimeout(qTimer);
      qTimer = setTimeout(function () { state.q = e.target.value; update(true); }, 150);
    });
    $("f-manual").addEventListener("change", function (e) { state.manual = e.target.checked; update(true); });
    $("f-risk").addEventListener("change", function (e) { state.hideRisk = e.target.checked; update(true); });
    $("f-conf").addEventListener("change", function (e) { state.hideLowConf = e.target.checked; update(true); });
    $("f-gain").addEventListener("change", function (e) { state.gainOnly = e.target.checked; update(true); });
    $("cost-grid").addEventListener("input", function (e) {
      var k = e.target.getAttribute("data-cost");
      if (!k) return;
      var v = Number(e.target.value);
      if (!isNaN(v) && v >= 0) { state.costs[k] = v; update(); }
    });
    $("weight-grid").addEventListener("input", function (e) {
      var k = e.target.getAttribute("data-weight");
      if (!k) return;
      state.weights[k] = Number(e.target.value);
      $("wv-" + k).textContent = state.weights[k];
      update();
    });
    $("reset").addEventListener("click", function () {
      var keepOpen = $("costs").open;
      state = freshState();
      buildFilterOptions();
      buildCostFields();
      syncControls();
      $("costs").open = keepOpen;
      update(true);
    });
    $("more").addEventListener("click", function () { limit += PAGE; update(); });
    $("model-chart").addEventListener("click", function (e) {
      var btn = e.target.closest("[data-model]");
      if (!btn) return;
      var id = btn.getAttribute("data-model");
      state.model = state.model === id ? "" : id;
      if (state.model) state.make = "";
      $("f-make").value = state.make;
      buildModelOptions();
      $("f-model").value = state.model;
      update(true);
      if (state.model) $("list-h").scrollIntoView({ behavior: "smooth", block: "start" });
    });
    $("list").addEventListener("click", function (e) {
      if (e.target.closest("a")) return;
      var row = e.target.closest("[data-id]");
      if (!row) return;
      var id = row.getAttribute("data-id");
      openId = openId === id ? null : id;
      update();
    });
    $("list").addEventListener("keydown", function (e) {
      if ((e.key === "Enter" || e.key === " ") && e.target.matches(".row-main")) {
        e.preventDefault();
        e.target.click();
      }
    });
  }

  /* ---------- UI: render ---------- */
  function renderMeta() {
    var nModels = Object.keys(models).length;
    $("meta").textContent = nModels + " modellen · " + int.format(listings.length) + " advertenties · bijgewerkt " + fmtDate(D.generated);
    var srcCount = countBy(function (l) { return l.src; });
    $("foot").innerHTML = "Bronnen: " + Object.keys(srcCount).map(function (s) {
      return esc(SOURCE_NAMES[s] || s) + " " + srcCount[s];
    }).join(" · ") + ". Schattingen op basis van vraagprijzen, geen financieel advies.";
  }

  function renderKpis(all, rows) {
    var h = state.horizon;
    var top = rows.slice().sort(SORTS.net)[0];
    var byModel = modelStats(all);
    var best = byModel.filter(function (s) { return s.n >= 3; })[0];
    var gains = rows.filter(function (r) { return r.proj.net > 0; }).length;
    var med = median(rows.map(function (r) { return r.l.price; }));
    var tiles = [
      { label: "Advertenties in selectie", value: int.format(rows.length), sub: gains + " met winst na " + yearsLabel(h) },
      { label: "Beste model (mediaan)", value: best ? fmtPct(best.annual) + "/j" : "–", sub: best ? best.m.make + " " + best.m.name : "te weinig data" },
      { label: "Grootste netto winst", value: top ? fmtSigned(top.proj.net) : "–", sub: top ? top.l.title : "" },
      { label: "Mediaanprijs selectie", value: med ? fmtEur(med) : "–", sub: "kosten " + fmtEur(V.yearlyCosts(state.costs)) + " per jaar" },
    ];
    $("kpis").innerHTML = tiles.map(function (t) {
      return '<div class="kpi"><div class="k-label">' + esc(t.label) + '</div><div class="k-value">' + esc(t.value) + '</div><div class="k-sub">' + esc(t.sub) + "</div></div>";
    }).join("");
  }

  /* Per model: mediaan rendement per jaar over de advertenties die door de filters (behalve model) komen. */
  function modelStats(all) {
    var saveModel = state.model;
    state.model = "";
    var rows = filtered(all);
    state.model = saveModel;
    var groups = {};
    rows.forEach(function (r) { (groups[r.l.model] = groups[r.l.model] || []).push(r); });
    return Object.keys(groups).map(function (id) {
      var g = groups[id];
      return {
        id: id, m: models[id], n: g.length,
        annual: median(g.map(function (r) { return r.proj.annual; })),
        net: median(g.map(function (r) { return r.proj.net; })),
        price: median(g.map(function (r) { return r.l.price; })),
      };
    }).sort(function (a, b) { return b.annual - a.annual; });
  }

  function renderModelChart(all) {
    var stats = modelStats(all);
    $("models-hint").textContent = "Mediaan netto rendement per jaar na kosten, bij " + yearsLabel(state.horizon) + " stockeren. Klik op een model om te filteren.";
    if (!stats.length) {
      $("model-chart").innerHTML = '<p class="empty">Geen advertenties binnen deze filters.</p>';
      return;
    }
    var vals = stats.map(function (s) { return s.annual; });
    var lo = Math.min(0, Math.floor(Math.min.apply(null, vals) * 50) / 50);
    var hi = Math.max(0.02, Math.ceil(Math.max.apply(null, vals) * 50) / 50);
    function x(v) { return ((v - lo) / (hi - lo)) * 100; }
    var zero = x(0);
    var html = stats.map(function (s) {
      var a = x(Math.min(0, s.annual));
      var b = x(Math.max(0, s.annual));
      return '<button type="button" class="m-row' + (state.model === s.id ? " active" : "") + '" data-model="' + esc(s.id) + '" title="' +
        esc(s.m.make + " " + s.m.name + " · " + s.n + " advertenties · mediaanprijs " + fmtEur(s.price) + " · mediaan netto " + fmtSigned(s.net)) + '">' +
        '<span class="m-name">' + esc(s.m.make + " " + s.m.name) + " <small>(" + s.n + ")</small></span>" +
        '<span class="m-track"><span class="m-zero" style="left:' + zero + '%"></span><span class="m-bar' + (s.annual < 0 ? " neg" : "") +
        '" style="left:' + a + "%;width:" + Math.max(0.6, b - a) + '%"></span></span>' +
        '<span class="m-val ' + (s.annual >= 0 ? "pos" : "neg") + '">' + fmtPct(s.annual) + "</span></button>";
    }).join("");
    var ticks = [];
    var step = (hi - lo) > 0.12 ? 0.04 : 0.02;
    for (var t = Math.ceil(lo / step) * step; t <= hi + 1e-9; t += step) ticks.push(t);
    html += '<div class="m-axis" aria-hidden="true"><span></span><span class="ax">' + ticks.map(function (t) {
      return '<span style="left:' + x(t) + '%">' + Math.round(t * 100) + "%</span>";
    }).join("") + "</span><span></span></div>";
    $("model-chart").innerHTML = html;
  }

  function thumb(l, m) {
    var initials = esc((m.make || "?").slice(0, 2).toUpperCase());
    if (!l.img) return '<div class="thumb-ph" aria-hidden="true">' + initials + "</div>";
    return '<img class="thumb" loading="lazy" referrerpolicy="no-referrer" alt="" src="' + esc(l.img) + '" data-ph="' + initials + '">';
  }

  function chips(l, m) {
    var out = [];
    l.variants.forEach(function (v) { out.push('<span class="chip">' + esc(v) + "</span>"); });
    var age = l.year ? CURRENT_YEAR - l.year : null;
    if (age != null) {
      if (age >= V.OLDTIMER_AGE) out.push('<span class="chip brass">Oldtimer</span>');
      else if (age + state.horizon >= V.OLDTIMER_AGE) out.push('<span class="chip brass">Oldtimer in ' + (l.year + V.OLDTIMER_AGE) + "</span>");
    }
    if (l.gear === "manual") out.push('<span class="chip plain">Manueel</span>');
    else if (l.gear === "automatic") out.push('<span class="chip plain">Automaat</span>');
    if (l.pt === "MIN_BID") out.push('<span class="chip plain">Bieden</span>');
    l.flags.forEach(function (f) { out.push('<span class="chip risk">' + esc(f) + "</span>"); });
    return out.length ? '<div class="chips">' + out.join("") + "</div>" : "";
  }

  function rowHtml(r, i) {
    var l = r.l, m = r.m, p = r.proj;
    var dealPct = l.fair / l.price - 1;
    var dealTxt = l.comps >= 4
      ? '<span class="' + (dealPct >= 0.05 ? "pos" : dealPct <= -0.05 ? "neg" : "") + '">markt ' + fmtEur(l.fair) + "</span>"
      : "markt onbekend";
    var open = openId === l.id;
    return '<li class="row" data-id="' + esc(l.id) + '">' +
      '<div class="row-main" tabindex="0" role="button" aria-expanded="' + open + '">' +
      '<span class="rank">' + (i + 1) + "</span>" + thumb(l, m) +
      '<div class="car"><div class="car-title">' + esc(l.title) + '</div><div class="car-model">' + esc(m.make + " " + m.name) + " · " +
      esc(COUNTRY_NAMES[l.cc] || l.cc || "") + " · " + esc(SOURCE_NAMES[l.src] || l.src) + (l.also.length ? " +" + l.also.length : "") + "</div>" + chips(l, m) + "</div>" +
      '<div class="num c-yk"><span class="lbl">Bouwjaar · km</span><div class="main">' + (l.year || "–") + '</div><div class="sub2">' + fmtKm(l.km) + "</div></div>" +
      '<div class="num c-price"><span class="lbl">Prijs · markt</span><div class="main">' + fmtEur(l.price) + '</div><div class="sub2">' + dealTxt + "</div></div>" +
      '<div class="num c-value"><span class="lbl">Waarde over ' + yearsLabel(state.horizon) + '</span><div class="main">' + fmtEur(p.value) + '</div><div class="sub2">' + fmtRate(p.ratePct) + " per jaar</div></div>" +
      '<div class="num c-net"><span class="lbl">Netto</span><div class="main ' + (p.net >= 0 ? "pos" : "neg") + '">' + fmtSigned(p.net) + "</div></div>" +
      '<div class="num c-annual"><span class="lbl">Per jaar</span><div class="main ' + (p.annual >= 0 ? "pos" : "neg") + '">' + fmtPct(p.annual) + "</div></div>" +
      '<div class="score c-score"><span class="lbl">Score</span><span class="s-val">' + Math.round(r.score) + '</span><span class="s-bar"><i style="width:' + Math.round(r.score) + '%"></i></span></div>' +
      "</div>" + (open ? detailHtml(r) : "") + "</li>";
  }

  function detailHtml(r) {
    var l = r.l, m = r.m, p = r.proj, par = params();
    var parts = V.rateParts(l, par, CURRENT_YEAR).filter(function (x) { return x.value !== 0 || x.key === "trend"; });
    var model = models[l.model];
    var trendNote = model.observed ? " (incl. " + Math.round(model.observedWeight * 100) + "% gemeten: " + fmtRate(model.observed.annualPct) + ")" : " (startinschatting)";
    var rateRows = parts.map(function (x) {
      var label = x.label + (x.key === "trend" ? trendNote : x.key === "variant" && l.variants.length ? " (" + l.variants.join(", ") + ")" : "");
      return "<dt>" + esc(label) + "</dt><dd>" + fmtRate(x.value) + "</dd>";
    }).join("") + '<dt class="total">Groei per jaar</dt><dd class="total">' + fmtRate(p.ratePct) + "</dd>";

    var h = par.horizon;
    var costRows =
      "<dt>Vraagprijs</dt><dd>" + fmtEur(l.price) + "</dd>" +
      "<dt>Marktwaarde" + (l.comps >= 4 ? " (" + l.comps + " vergelijkbare)" : " (te weinig vergelijkbare)") + "</dt><dd>" + fmtEur(l.fair) + "</dd>" +
      "<dt>Startwaarde in berekening</dt><dd>" + fmtEur(p.start) + "</dd>" +
      "<dt>Waarde na " + yearsLabel(h) + "</dt><dd>" + fmtEur(p.value) + "</dd>" +
      "<dt>Verkoopkosten (" + par.sell_pct + "%)</dt><dd>−" + fmtEur(p.value - p.sellNet) + "</dd>" +
      "<dt>Aankoopkosten</dt><dd>−" + fmtEur(par.buy_costs) + "</dd>" +
      "<dt>Kosten " + yearsLabel(h) + " (" + fmtEur(p.yearlyCosts) + "/j)</dt><dd>−" + fmtEur(p.yearlyCosts * h) + "</dd>" +
      '<dt class="total">Netto resultaat</dt><dd class="total ' + (p.net >= 0 ? "pos" : "neg") + '">' + fmtSigned(p.net) + "</dd>";

    var facts = [];
    if (l.hp) facts.push(l.hp + " pk");
    if (l.fuel) facts.push({ petrol: "benzine", diesel: "diesel", lpg: "LPG" }[l.fuel] || l.fuel);
    if (l.body) facts.push({ cabrio: "cabrio", coupe: "coupé" }[l.body] || l.body);
    if (l.city) facts.push(l.city);
    if (l.seller) facts.push(l.seller === "dealer" ? "handelaar" : "particulier");
    var seen = l.days != null ? (l.days === 0 ? "vandaag voor het eerst gezien" : "online sinds " + fmtDate(l.first) + " (" + l.days + " d)") : "";
    var drop = l.firstPrice && l.firstPrice > l.price ? " · prijs gezakt van " + fmtEur(l.firstPrice) : "";

    var links = '<a class="btn" href="' + esc(l.url) + '" target="_blank" rel="noopener">Bekijk op ' + esc(SOURCE_NAMES[l.src] || l.src) + "</a>" +
      l.also.map(function (a) {
        return '<a class="btn ghost" href="' + esc(a.url) + '" target="_blank" rel="noopener">' + esc(SOURCE_NAMES[a.src] || a.src) + "</a>";
      }).join("");

    return '<div class="detail">' +
      "<div><h4>Groei per jaar</h4><dl class=\"kv\">" + rateRows + "</dl>" +
      '<p class="hint" style="margin-top:8px">' + esc(facts.join(" · ")) + (seen ? "<br>" + esc(seen + drop) : "") + "</p></div>" +
      "<div><h4>Rekensom</h4><dl class=\"kv\">" + costRows + "</dl>" +
      '<p class="hint" style="margin-top:8px">Betrouwbaarheid ' + Math.round(l.conf * 100) + "% · zeldzaamheid " + m.rarity + "/5 · vraag " + m.demand + "/5</p></div>" +
      '<div class="chart"><h4>Waarde vs. totale investering</h4>' + chartSvg(V.series(l, par, CURRENT_YEAR)) +
      '<div class="legend"><span><i class="sw" style="background:var(--accent)"></i>Waarde auto</span><span><i class="sw" style="background:var(--brass)"></i>Geïnvesteerd (aankoop + kosten)</span></div>' +
      '<div class="links">' + links + "</div></div>" +
      "</div>";
  }

  function chartSvg(pts) {
    var W = 360, H = 170, L = 52, R = 10, T = 10, B = 24;
    var ys = [];
    pts.forEach(function (p) { ys.push(p.value, p.invested); });
    var lo = Math.min.apply(null, ys), hi = Math.max.apply(null, ys);
    var pad = (hi - lo) * 0.1 || hi * 0.1 || 1;
    lo = Math.max(0, lo - pad); hi = hi + pad;
    var n = pts.length - 1 || 1;
    function x(t) { return L + (t / n) * (W - L - R); }
    function y(v) { return T + (1 - (v - lo) / (hi - lo)) * (H - T - B); }
    function path(key) { return pts.map(function (p, i) { return (i ? "L" : "M") + x(p.t).toFixed(1) + " " + y(p[key]).toFixed(1); }).join(" "); }
    var area = path("value") + " L" + x(n).toFixed(1) + " " + (H - B) + " L" + x(0).toFixed(1) + " " + (H - B) + " Z";
    var grid = "";
    for (var i = 0; i <= 3; i++) {
      var v = lo + ((hi - lo) * i) / 3;
      grid += '<line x1="' + L + '" x2="' + (W - R) + '" y1="' + y(v).toFixed(1) + '" y2="' + y(v).toFixed(1) + '" stroke="var(--line)" stroke-width="1"/>' +
        '<text x="' + (L - 6) + '" y="' + (y(v) + 4).toFixed(1) + '" text-anchor="end" font-size="10" fill="var(--muted)">' + (v >= 1000 ? Math.round(v / 1000) + "k" : Math.round(v)) + "</text>";
    }
    var xt = "";
    var every = n > 8 ? Math.ceil(n / 5) : 1;
    pts.forEach(function (p) {
      if (p.t % every === 0 || p.t === n) xt += '<text x="' + x(p.t).toFixed(1) + '" y="' + (H - 6) + '" text-anchor="middle" font-size="10" fill="var(--muted)">' + (p.t === 0 ? "nu" : "+" + p.t + "j") + "</text>";
    });
    var last = pts[pts.length - 1];
    return '<svg viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="Projectie van waarde en investering">' + grid +
      '<path d="' + area + '" fill="var(--accent)" fill-opacity="0.12" stroke="none"/>' +
      '<path d="' + path("invested") + '" fill="none" stroke="var(--brass)" stroke-width="2" stroke-dasharray="5 4"/>' +
      '<path d="' + path("value") + '" fill="none" stroke="var(--accent)" stroke-width="2.5"/>' +
      '<circle cx="' + x(last.t).toFixed(1) + '" cy="' + y(last.value).toFixed(1) + '" r="4" fill="var(--accent)"/>' +
      '<circle cx="' + x(last.t).toFixed(1) + '" cy="' + y(last.invested).toFixed(1) + '" r="3.5" fill="var(--brass)"/>' + xt + "</svg>";
  }

  function renderList(all) {
    var rows = filtered(all).sort(SORTS[state.sort] || SORTS.score);
    var shown = rows.slice(0, limit);
    $("col-value").textContent = "Waarde over " + yearsLabel(state.horizon);
    var sortLabel = $("f-sort").options[$("f-sort").selectedIndex].text.toLowerCase();
    $("list-hint").textContent = int.format(rows.length) + " auto's, gesorteerd op " + sortLabel + ". Klik op een rij voor de rekensom.";
    $("list").innerHTML = shown.length ? shown.map(rowHtml).join("") : '<li class="empty">Geen auto\'s gevonden met deze filters.</li>';
    $("more").hidden = rows.length <= limit;
    $("more").textContent = "Meer tonen (" + int.format(rows.length - limit) + " resterend)";
    Array.prototype.forEach.call($("list").querySelectorAll("img.thumb"), function (img) {
      img.addEventListener("error", function () {
        var ph = document.createElement("div");
        ph.className = "thumb-ph";
        ph.setAttribute("aria-hidden", "true");
        ph.textContent = img.getAttribute("data-ph");
        img.replaceWith(ph);
      }, { once: true });
    });
    return rows;
  }

  function update(resetLimit) {
    if (resetLimit) limit = PAGE;
    $("horizon-out").textContent = yearsLabel(state.horizon);
    var all = compute();
    var rows = renderList(all);
    renderModelChart(all);
    renderKpis(all, rows);
    persist();
  }

  buildFilterOptions();
  buildCostFields();
  syncControls();
  bind();
  renderMeta();
  update(true);
})();
