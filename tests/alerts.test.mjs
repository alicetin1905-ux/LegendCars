// node --test tests/alerts.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { selectAlerts, render } from "../legendcars/alerts.mjs";

const base = {
  id: "x", src: "2dehands", url: "https://example.test/1", title: "VW Corrado G60", model: "vw-corrado",
  year: 1990, km: 150000, price: 6000, fair: 11000, comps: 20, conf: 1, flags: [], variants: ["G60"],
  rate: { trend: 5, variant: 1.5, km: 0, gearbox: 0.5, fuel: 0, condition: 0.5 },
  cond: { score: 2, pos: ["Car-Pass/NAP", "Garagewagen"], neg: [] },
  lat: 51.0, lon: 5.0, first: "2026-10-14", drop: 0, changed: null,
};
const data = (listings) => ({
  today: "2026-10-14",
  defaults: { horizon_years: 5, buy_costs: 500, deal_credit: 50, sell_pct: 0, storage_per_month: 0, insurance_per_year: 0,
    tax_per_year: 0, maintenance_per_year: 0, oldtimer_age: 30, price_min: 2500, price_max: 9999, max_km: 250000,
    home_label: "Balen", home_lat: 51.17, home_lon: 5.17, max_distance_km: 250, alert_min_score: 70, alert_max_items: 15 },
  models: { "vw-corrado": { make: "Volkswagen", name: "Corrado", rarity: 3, demand: 5 } },
  listings,
});

test("new good listing within filters is selected", () => {
  const out = selectAlerts(data([base]));
  assert.equal(out.length, 1);
  assert.equal(out[0].kind, "nieuw");
  assert.ok(out[0].dist < 30);
});

test("old listings, far away, too expensive or risky are skipped", () => {
  const out = selectAlerts(data([
    { ...base, id: "old", first: "2026-10-01" },
    { ...base, id: "far", lat: 48.1, lon: 11.6 },
    { ...base, id: "pricey", price: 15000 },
    { ...base, id: "risk", flags: ["Schade"] },
  ]));
  assert.deepEqual(out.map((a) => a.l.id), []);
});

test("price drop today is selected and rendered with the drop", () => {
  const d = data([{ ...base, id: "drop", first: "2026-09-01", drop: 800, dropPct: 0.12, changed: "2026-10-14" }]);
  const out = selectAlerts(d);
  assert.equal(out[0].kind, "prijsdaling");
  const { md, txt } = render(d, out, "https://dash.test/");
  assert.match(md, /Prijs gezakt \(1\)/);
  assert.match(md, /−€\s?800/);
  assert.match(md, /\[VW Corrado G60\]\(https:\/\/example\.test\/1\)/);
  assert.match(txt, /km van Balen/);
});
