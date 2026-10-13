import unittest

from legendcars import config
from legendcars.market import analyse, blended_trend, observed_trend

WL = config.load()


def rec(i, price, km=150_000, variants=(), flags=(), model="vw-corrado", year=1992, **kw):
    return {
        "id": f"t:{i}", "source": "autoscout24", "model_id": model, "active": True, "price": price, "km": km,
        "year": year, "gearbox": "manual", "fuel": "petrol", "price_type": "FIXED",
        "variants": [list(v) for v in variants], "flags": list(flags), **kw,
    }


class MarketTest(unittest.TestCase):
    def test_fair_value_from_comparables(self):
        records = [rec(i, p) for i, p in enumerate([10_000, 11_000, 12_000, 13_000, 14_000])] + [rec(9, 8_000)]
        rows, stats = analyse(records, WL, [])
        cheap = next(r for r in rows if r["id"] == "t:9")
        self.assertEqual(cheap["comps"], 5)
        self.assertEqual(cheap["fair"], 12_000)
        self.assertEqual(stats["vw-corrado"]["active"], 6)

    def test_too_few_comparables_means_no_deal_signal(self):
        rows, _ = analyse([rec(1, 9_000), rec(2, 20_000)], WL, [])
        self.assertTrue(all(r["fair"] == r["price"] for r in rows))
        self.assertTrue(all(r["conf"] < 0.7 for r in rows))

    def test_tiers_are_compared_separately(self):
        vr6 = [rec(f"v{i}", 20_000 + i * 500, variants=[("VR6", 1.5)]) for i in range(5)]
        base = [rec(f"b{i}", 8_000 + i * 500) for i in range(5)]
        rows, _ = analyse(vr6 + base, WL, [])
        r = next(r for r in rows if r["id"] == "t:v0")
        self.assertEqual(r["tier"], "VR6")
        self.assertGreater(r["fair"], 20_000)

    def test_low_km_raises_fair_value_and_rate(self):
        comps = [rec(i, 10_000, km=150_000) for i in range(5)]
        rows, _ = analyse(comps + [rec(9, 10_000, km=40_000)], WL, [])
        r = next(r for r in rows if r["id"] == "t:9")
        self.assertGreater(r["fair"], 10_000)
        self.assertEqual(r["rate"]["km"], 1.0)
        self.assertEqual(r["rate"]["gearbox"], 0.5)

    def test_inactive_and_cheap_listings_skipped(self):
        rows, _ = analyse([rec(1, 500), rec(2, 9_000, active=False)], WL, [])
        self.assertEqual(rows, [])

    def test_observed_trend_needs_history(self):
        ids = {f"t:{i}": "vw-corrado" for i in range(30)}
        hist = [(f"t:{i}", "2025-01-01", 10_000) for i in range(15)] + [(f"t:{i}", "2026-01-01", 11_000) for i in range(15, 30)]
        tr = observed_trend(ids, hist)["vw-corrado"]
        self.assertAlmostEqual(tr["annualPct"], 10.0, delta=0.3)
        used, w = blended_trend(WL.model("vw-corrado"), tr)
        self.assertGreater(used, WL.model("vw-corrado").trend)
        self.assertLessEqual(w, 0.6)
        self.assertEqual(observed_trend(ids, hist[:5]), {})


if __name__ == "__main__":
    unittest.main()


class SuspiciousDealTest(unittest.TestCase):
    def test_far_below_market_is_capped_and_flagged(self):
        records = [rec(i, 30_000) for i in range(5)] + [rec(9, 10_000)]
        rows, _ = analyse(records, WL, [])
        r = next(r for r in rows if r["id"] == "t:9")
        self.assertEqual(r["fair"], 20_000)
        self.assertIn("Prijs verdacht laag", r["flags"])
        self.assertLess(r["conf"], 0.7)


class RegressionTest(unittest.TestCase):
    def test_older_and_higher_km_cars_get_lower_fair_value(self):
        records = []
        for i in range(30):
            year = 1996 + i % 8
            km = 80_000 + (i * 7919) % 200_000
            price = 4_000 * (1.12 ** (year - 1996)) * (1 - 0.3 * km / 100_000 / 2)
            records.append(rec(i, round(price), km=km, year=year, model="bmw-e39"))
        rows, _ = analyse(records, WL, [])
        by_id = {r["id"]: r for r in rows}
        for r in rows:
            self.assertLess(abs(r["fair"] / r["price"] - 1), 0.05, r)
        old = min(rows, key=lambda r: (r["year"], -r["km"]))
        new = max(rows, key=lambda r: (r["year"], -r["km"]))
        self.assertLess(by_id[old["id"]]["fair"], by_id[new["id"]]["fair"])


class CleanKmTest(unittest.TestCase):
    def test_placeholder_km_becomes_unknown(self):
        from legendcars.market import clean_km
        self.assertIsNone(clean_km({"km": 1000, "year": 1990}, 2026)["km"])
        self.assertEqual(clean_km({"km": 1000, "year": 2024}, 2026)["km"], 1000)
        self.assertEqual(clean_km({"km": 85_000, "year": 1990}, 2026)["km"], 85_000)
