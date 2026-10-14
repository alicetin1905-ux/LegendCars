// Dagelijkse melding: nieuwe topkansen en prijsdalingen van vandaag.
//
//   node legendcars/alerts.mjs [docs/index.html] [uitvoermap]
//
// Leest de data uit het gebouwde dashboard en gebruikt dezelfde berekening (valuation.js)
// en standaardfilters als het dashboard. Schrijft alerts.md (GitHub-issue), alerts.txt
// (Telegram) en print het aantal kansen. Zonder kansen worden er geen bestanden geschreven.
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const V = require("./dashboard/valuation.js");

const RISK = new Set(["Project/restauratie", "Schade", "Defect", "Geen papieren", "Prijs verdacht laag"]);
const SOURCE_NAMES = { autoscout24: "AutoScout24", "2dehands": "2dehands", marktplaats: "Marktplaats", kleinanzeigen: "Kleinanzeigen", willhaben: "Willhaben", coches: "Coches.net" };
const eur = new Intl.NumberFormat("nl-BE", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });

export function loadData(file) {
  const html = fs.readFileSync(file, "utf8");
  const m = html.match(/window\.LEGEND_DATA = (.*?);\n<\/script>/s);
  if (!m) throw new Error("Geen LEGEND_DATA in " + file);
  return JSON.parse(m[1]);
}

function km(a, b, c, d) {
  const r = Math.PI / 180;
  const x = Math.sin(((c - a) * r) / 2) ** 2 + Math.cos(a * r) * Math.cos(c * r) * Math.sin(((d - b) * r) / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(x));
}

export function selectAlerts(data) {
  const d = data.defaults || {};
  const year = Number(data.today.slice(0, 4));
  const params = { horizon: d.horizon_years || 5, ...d };
  const minScore = d.alert_min_score ?? 75;
  const maxItems = d.alert_max_items ?? 15;
  const out = [];
  for (const l of data.listings) {
    const m = data.models[l.model];
    if (!m) continue;
    const isNew = l.first === data.today;
    const isDrop = l.drop > 0 && l.changed === data.today;
    if (!isNew && !isDrop) continue;
    if (d.price_min != null && l.price < d.price_min) continue;
    if (d.price_max != null && l.price > d.price_max) continue;
    if (d.max_km != null && l.km && l.km > d.max_km) continue;
    if (l.flags.some((f) => RISK.has(f)) || l.conf < 0.5) continue;
    let dist = null;
    if (d.home_lat != null && d.max_distance_km != null) {
      if (l.lat == null) continue;
      dist = km(d.home_lat, d.home_lon, l.lat, l.lon);
      if (dist > d.max_distance_km) continue;
    }
    const proj = V.project(l, params, year);
    const score = V.score(l, m, proj, V.DEFAULT_WEIGHTS).value;
    if (score < minScore || proj.net <= 0) continue;
    out.push({ l, m, proj, score, dist, kind: isNew ? "nieuw" : "prijsdaling", advice: V.bidAdvice(l, params, year) });
  }
  out.sort((a, b) => b.score - a.score);
  return out.slice(0, maxItems);
}

function line(a, md, ctx) {
  const l = a.l;
  const cond = l.cond || {};
  const plus = (cond.pos || []).slice(0, 3).join(", ");
  const min = (cond.neg || []).slice(0, 2).join(", ");
  const bits = [
    `${l.year || "?"}`,
    l.km ? `${Math.round(l.km / 1000)}.000 km` : "km ?",
    a.dist != null ? `${Math.round(a.dist)} km van ${ctx.home}` : null,
    `markt ${eur.format(l.fair)}`,
    `netto ${a.proj.net >= 0 ? "+" : ""}${eur.format(Math.round(a.proj.net))} na ${ctx.horizon} j`,
    `score ${Math.round(a.score)}`,
  ].filter(Boolean).join(" · ");
  const price = a.kind === "prijsdaling" ? `${eur.format(l.price)} (−${eur.format(l.drop)})` : eur.format(l.price);
  const adv = a.advice && a.advice.worth ? ` · bied ${eur.format(a.advice.bid)}, max. ${eur.format(a.advice.max)}` : "";
  const staat = [plus && `✓ ${plus}`, min && `✗ ${min}`].filter(Boolean).join("  ");
  if (md) {
    return `- **[${l.title}](${l.url})** — ${price}${adv}  \n  ${a.m.make} ${a.m.name} · ${bits}${staat ? `  \n  ${staat}` : ""} · _${SOURCE_NAMES[l.src] || l.src}_`;
  }
  return `• ${l.title} — ${price}${adv}\n  ${bits}${staat ? `\n  ${staat}` : ""}\n  ${l.url}`;
}

export function render(data, alerts, dashboardUrl) {
  const ctx = { home: (data.defaults || {}).home_label || "thuis", horizon: (data.defaults || {}).horizon_years || 5 };
  const nieuw = alerts.filter((a) => a.kind === "nieuw");
  const drops = alerts.filter((a) => a.kind === "prijsdaling");
  const md = [];
  const txt = [`LegendCars — ${alerts.length} kans${alerts.length === 1 ? "" : "en"} (${data.today})`];
  if (nieuw.length) {
    md.push(`### Nieuw online (${nieuw.length})`, ...nieuw.map((a) => line(a, true, ctx)), "");
    txt.push("", "NIEUW", ...nieuw.map((a) => line(a, false, ctx)));
  }
  if (drops.length) {
    md.push(`### Prijs gezakt (${drops.length})`, ...drops.map((a) => line(a, true, ctx)), "");
    txt.push("", "PRIJS GEZAKT", ...drops.map((a) => line(a, false, ctx)));
  }
  if (dashboardUrl) {
    md.push(`[Open het dashboard](${dashboardUrl})`);
    txt.push("", dashboardUrl);
  }
  md.push("", "_Automatisch gemaakt door de dagelijkse update. Filters en minimumscore: `watchlist.toml` → `[dashboard]`._");
  let text = txt.join("\n");
  if (text.length > 3900) text = text.slice(0, 3850) + "\n… (meer in het dashboard)";  // Telegram-limiet
  return { md: md.join("\n"), txt: text };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const file = process.argv[2] || "docs/index.html";
  const outDir = process.argv[3] || ".";
  const data = loadData(file);
  const alerts = selectAlerts(data);
  if (alerts.length) {
    const { md, txt } = render(data, alerts, process.env.DASHBOARD_URL);
    fs.writeFileSync(path.join(outDir, "alerts.md"), md);
    fs.writeFileSync(path.join(outDir, "alerts.txt"), txt);
  }
  console.log(alerts.length);
}
