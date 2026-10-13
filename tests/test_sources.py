import json
import unittest
from pathlib import Path

from legendcars import config
from legendcars.sources import adevinta, autoscout24

FIX = Path(__file__).parent / "fixtures"
WL = config.load()


class AutoScout24Test(unittest.TestCase):
    def test_parse_page_and_listing(self):
        html = (FIX / "autoscout24_page.html").read_text(encoding="utf-8")
        pp = autoscout24.parse_page(html)
        self.assertEqual(pp["numberOfPages"], 1)
        listing = autoscout24.parse_listing(pp["listings"][0], "cabrio")
        self.assertEqual(listing.id, "autoscout24:93aa19a1")
        self.assertEqual(listing.year, 1999)
        self.assertEqual(listing.km, 116303)
        self.assertEqual(listing.price, 16950)
        self.assertEqual(listing.gearbox, "automatic")
        self.assertEqual(listing.hp, 192)
        self.assertEqual(listing.country, "NL")
        self.assertEqual(listing.seller, "dealer")
        self.assertTrue(listing.url.startswith("https://www.autoscout24.be/nl/aanbod/"))

    def test_build_url(self):
        model = WL.model("bmw-e36-coupe-cabrio")
        url = autoscout24.build_url(model.as24[0], model, ["B", "NL"], 2)
        self.assertIn("mmmv=13%7C%7C38%7C", url)
        self.assertIn("fregfrom=1990", url)
        self.assertIn("body=2", url)
        self.assertIn("page=2", url)

    def test_missing_next_data(self):
        with self.assertRaises(ValueError):
            autoscout24.parse_page("<html>captcha</html>")


class AdevintaTest(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((FIX / "2dehands_search.json").read_text(encoding="utf-8"))

    def test_parse_fixed_price(self):
        listing = adevinta.parse_listing(self.data["listings"][0], "2dehands")
        self.assertEqual(listing.id, "2dehands:m2452456855")
        self.assertEqual(listing.price, 17975)
        self.assertEqual(listing.year, 1993)
        self.assertEqual(listing.km, 227836)
        self.assertEqual(listing.gearbox, "manual")
        self.assertEqual(listing.body, "coupe")
        self.assertEqual(listing.country, "B")
        self.assertTrue(listing.url.startswith("https://www.2dehands.be/v/"))

    def test_bid_without_price_and_zero_km(self):
        listing = adevinta.parse_listing(self.data["listings"][1], "2dehands")
        self.assertIsNone(listing.price)
        self.assertIsNone(listing.km)
        self.assertEqual(listing.price_type, "FAST_BID")

    def test_build_url_has_year_range(self):
        url = adevinta.build_url("marktplaats", "vw corrado", WL.model("vw-corrado"), 100)
        self.assertTrue(url.startswith("https://www.marktplaats.nl/lrp/api/search?"))
        self.assertIn("constructionYear%3A1988%3A1995", url)
        self.assertIn("offset=100", url)


if __name__ == "__main__":
    unittest.main()


class KleinanzeigenTest(unittest.TestCase):
    def test_parse_page(self):
        from legendcars.sources import kleinanzeigen
        html = (FIX / "kleinanzeigen_page.html").read_text(encoding="utf-8")
        listings, total = kleinanzeigen.parse_page(html)
        self.assertEqual(total, 393)
        self.assertEqual(len(listings), 2)
        a, b = listings
        self.assertEqual(a.id, "kleinanzeigen:3463093500")
        self.assertEqual(a.title, "VW Corrado Ringtool")
        self.assertEqual((a.price, a.km, a.year, a.price_type), (7800, 252169, 1993, "FIXED"))
        self.assertEqual(a.city, "Düren")
        self.assertEqual(a.country, "D")
        self.assertTrue(a.url.startswith("https://www.kleinanzeigen.de/s-anzeige/"))
        self.assertEqual((b.price, b.price_type, b.gearbox), (22900, "MIN_BID", "automatic"))

    def test_build_url(self):
        from legendcars.sources import kleinanzeigen
        url = kleinanzeigen.build_url("bmw z3", WL.model("bmw-z3-cabrio"), 2)
        self.assertEqual(url, "https://www.kleinanzeigen.de/s-autos/seite:2/bmw-z3/k0c216+autos.ez_i:1995%2C1999")


class WillhabenTest(unittest.TestCase):
    def test_parse(self):
        from legendcars.sources import willhaben
        sr = willhaben.parse_page((FIX / "willhaben_page.html").read_text(encoding="utf-8"))
        listing = willhaben.parse_advert(sr["advertSummaryList"]["advertSummary"][0])
        self.assertEqual(listing.id, "willhaben:1690839498")
        self.assertEqual(listing.title, "VW Corrado VR6 Turbo")
        self.assertEqual(listing.subtitle, "")  # specificatie staat al in de titel
        self.assertEqual((listing.year, listing.km, listing.price), (1992, 200000, 17999))
        self.assertEqual((listing.gearbox, listing.body, listing.fuel), ("manual", "coupe", "petrol"))
        self.assertEqual((listing.hp, listing.country, listing.seller), (174, "A", "private"))
        self.assertTrue(listing.url.startswith("https://www.willhaben.at/iad/gebrauchtwagen/d/auto/"))

    def test_build_url(self):
        from legendcars.sources import willhaben
        url = willhaben.build_url("bmw z3", WL.model("bmw-z3-cabrio"), 2)
        self.assertIn("keyword=bmw+z3", url)
        self.assertIn("YEAR_MODEL_FROM=1995&YEAR_MODEL_TO=1999", url)
        self.assertIn("page=2", url)


class CochesTest(unittest.TestCase):
    def test_parse(self):
        from legendcars.sources import coches
        res = coches.parse_page((FIX / "coches_page.html").read_text(encoding="utf-8"))
        listing = coches.parse_item(res["items"][0])
        self.assertEqual(listing.id, "coches:62618052")
        self.assertEqual((listing.year, listing.km, listing.price, listing.hp), (1990, 74645, 15999, 160))
        self.assertEqual((listing.body, listing.fuel, listing.country, listing.seller), ("coupe", "petrol", "E", "dealer"))
        self.assertTrue(listing.url.startswith("https://www.coches.net/volkswagen-corrado"))

    def test_make_slug_and_url(self):
        from legendcars.sources import coches
        self.assertEqual(coches.make_slug("Alfa Romeo"), "alfa_romeo")
        self.assertEqual(coches.make_slug("Mercedes-Benz"), "mercedes-benz")
        self.assertEqual(coches.build_url("bmw", 1999, 3), "https://www.coches.net/bmw/segunda-mano/?MaxYear=1999&pg=3")
