import json
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path

from legendcars import config
from legendcars.export import build_data, dedupe, render
from legendcars.listing import Listing
from legendcars.matching import Match
from legendcars.store import Store

WL = config.load()


class ExportTest(unittest.TestCase):
    def test_dedupe_prefers_autoscout_and_links_others(self):
        a = {"id": "2dehands:1", "source": "2dehands", "url": "u1", "model_id": "m", "year": 1992, "km": 120_400, "price": 15_000}
        b = {"id": "autoscout24:1", "source": "autoscout24", "url": "u2", "model_id": "m", "year": 1992, "km": 120_000, "price": 15_000}
        out = dedupe([a, b])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["source"], "autoscout24")
        self.assertEqual(out[0]["also"], [{"src": "2dehands", "url": "u1"}])

    def test_store_roundtrip_and_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(tmp)
            for i, price in enumerate([9_000, 10_000, 11_000, 12_000, 13_000]):
                lst = Listing(id=f"autoscout24:{i}", source="autoscout24", url=f"https://x/{i}", title="Volkswagen Corrado",
                              subtitle="VR6 </script>", year=1993, km=150_000 + i, price=price, model_id="vw-corrado")
                store.upsert(lst, Match(variants=[("VR6", 1.5)]), "2026-10-01")
            store.save()
            self.assertEqual(store.mark_missing("autoscout24", "vw-corrado", {"autoscout24:0"}, "2026-10-02"), 4)
            store.save()

            again = Store(tmp)
            self.assertEqual(sum(r["active"] for r in again.records.values()), 1)
            self.assertEqual(len(list(again.history())), 5)

            for i in range(1, 5):
                again.records[f"autoscout24:{i}"]["active"] = True
            data = build_data(WL, again, today=date(2026, 10, 13))
            self.assertEqual(len(data["listings"]), 5)
            self.assertEqual(data["listings"][0]["days"], 12)

            out = render(data, Path(tmp) / "index.html")
            html = out.read_text(encoding="utf-8")
            self.assertNotIn("/*INLINE:", html)
            payload = re.search(r"window\.LEGEND_DATA = (.*?);\n</script>", html, re.S).group(1)
            self.assertEqual(len(json.loads(payload)["listings"]), 5)
            self.assertNotIn("VR6 </script>", html)


if __name__ == "__main__":
    unittest.main()


class TitleTest(unittest.TestCase):
    def test_display_title(self):
        from legendcars.export import display_title
        self.assertEqual(display_title("BMW Z4", "BMW Z4 M Coupé (2006)"), "BMW Z4 M Coupé (2006)")
        self.assertEqual(display_title("BMW 320", "i Cabrio"), "BMW 320 i Cabrio")
        self.assertEqual(display_title("Volkswagen Corrado", ""), "Volkswagen Corrado")


class CountryTest(unittest.TestCase):
    def test_country_codes_are_iso(self):
        from legendcars.export import _compact
        base = {"id": "x", "source": "kleinanzeigen", "url": "u", "model_id": "m", "price": 5000}
        self.assertEqual(_compact({**base, "country": "D"}, date(2026, 10, 13))["cc"], "DE")
        self.assertEqual(_compact({**base, "country": "DE"}, date(2026, 10, 13))["cc"], "DE")
        self.assertEqual(_compact({**base, "country": "NL"}, date(2026, 10, 13))["cc"], "NL")
