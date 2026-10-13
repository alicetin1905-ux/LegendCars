// node --test tests/
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const V = require("../legendcars/dashboard/valuation.js");

const params = {
  horizon: 5, storage_per_month: 50, insurance_per_year: 150, tax_per_year: 50,
  maintenance_per_year: 300, buy_costs: 500, sell_pct: 5, deal_credit: 50,
};
const base = { price: 10000, fair: 10000, year: 1992, conf: 1, rate: { trend: 4, variant: 0, km: 0, gearbox: 0, fuel: 0, condition: 0 } };

test("age adjustment around the 30-year line (default)", () => {
  assert.equal(V.OLDTIMER_AGE, 30);
  assert.equal(V.ageAdjustment(1998, 2026, 5), 1.0); // wordt 30 tijdens stockage
  assert.equal(V.ageAdjustment(2003, 2026, 5), 0);
  assert.equal(V.ageAdjustment(1990, 2026, 5), 0.3);
  assert.equal(V.ageAdjustment(1975, 2026, 5), 0);
  assert.equal(V.ageAdjustment(null, 2026, 5), 0);
});

test("oldtimer age is configurable", () => {
  assert.equal(V.ageAdjustment(2003, 2026, 5, 25), 1.0);
  const parts = V.rateParts({ year: 2003, rate: {} }, { horizon: 5, oldtimer_age: 25 }, 2026);
  assert.equal(parts.find((p) => p.key === "age").value, 1.0);
  assert.equal(V.oldtimerAge({}), 30);
});

test("projection arithmetic", () => {
  const p = V.project(base, params, 2026);
  assert.equal(p.ratePct, 4.3);
  assert.ok(Math.abs(p.value - 10000 * Math.pow(1.043, 5)) < 1e-6);
  assert.equal(p.yearlyCosts, 50 * 12 + 150 + 50 + 300);
  assert.equal(p.invested, 10000 + 500 + 1100 * 5);
  assert.ok(Math.abs(p.net - (p.value * 0.95 - p.invested)) < 1e-6);
});

test("bargain counts partially, overpaying fully", () => {
  assert.equal(V.startValue({ price: 8000, fair: 10000 }, params), 9000);
  assert.equal(V.startValue({ price: 12000, fair: 10000 }, params), 10000);
});

test("rate is clamped", () => {
  const wild = { ...base, rate: { ...base.rate, trend: 40 } };
  assert.equal(V.annualRate(wild, params, 2026), 15);
});

test("series starts at start value and ends at projected value", () => {
  const s = V.series(base, params, 2026);
  assert.equal(s.length, 6);
  assert.equal(s[0].value, 10000);
  assert.ok(Math.abs(s[5].value - V.project(base, params, 2026).value) < 1e-6);
});

test("score is 0-100 and rewards better returns", () => {
  const w = { ret: 50, deal: 15, rarity: 10, demand: 15, conf: 10 };
  const m = { rarity: 3, demand: 4 };
  const lo = V.score(base, m, V.project(base, params, 2026), w).value;
  const better = { ...base, rate: { ...base.rate, trend: 9 } };
  const hi = V.score(better, m, V.project(better, params, 2026), w).value;
  assert.ok(lo >= 0 && hi <= 100 && hi > lo);
});
