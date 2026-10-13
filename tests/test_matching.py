import unittest

from legendcars import config
from legendcars.listing import Listing
from legendcars.matching import match, reject_reason

WL = config.load()


def L(title, source="2dehands", year=1995, **kw):
    return Listing(id=f"{source}:x", source=source, url="", title=title, year=year, **kw)


class MatchingTest(unittest.TestCase):
    def test_corrado_vr6_variant(self):
        m = match(L("Volkswagen Corrado 2.9 VR6 kuipstoelen", year=1993), WL.model("vw-corrado"), WL.settings)
        self.assertIsNotNone(m)
        self.assertIn("VR6", [v for v, _ in m.variants])
        self.assertEqual(m.tier, "VR6")

    def test_year_outside_range_rejected(self):
        self.assertIn("bouwjaar", reject_reason(L("VW Corrado", year=1999), WL.model("vw-corrado"), WL.settings))

    def test_wanted_ads_and_parts_rejected(self):
        model = WL.model("bmw-z3-cabrio")
        self.assertIsNotNone(reject_reason(L("Gezocht: BMW Z3 roadster", year=1998), model, WL.settings))
        self.assertIsNotNone(reject_reason(L("BMW Z3 onderdelen", year=1998), model, WL.settings))

    def test_text_keywords_only_for_free_text_sites(self):
        model = WL.model("bmw-e36-coupe-cabrio")
        # AutoScout24 zoekt al op merk/model: titel zonder "e36" is ok
        self.assertIsNone(reject_reason(L("BMW 320", source="autoscout24", year=1995, body="cabrio"), model, WL.settings))
        # op 2dehands moet het herkenbaar zijn
        self.assertIsNotNone(reject_reason(L("Mooie cabrio te koop", year=1995, body="cabrio"), model, WL.settings))

    def test_body_filter(self):
        model = WL.model("bmw-z3-cabrio")
        self.assertIsNotNone(reject_reason(L("BMW Z3 2.8", year=1999, body="coupe"), model, WL.settings))
        self.assertIsNone(reject_reason(L("BMW Z3 2.8", year=1999, body="cabrio"), model, WL.settings))

    def test_required_keyword_on_all_sources(self):
        model = WL.model("vw-golf3-gti-vr6")
        self.assertIsNotNone(reject_reason(L("Volkswagen Golf 1.4 CL", source="autoscout24", year=1995), model, WL.settings))
        self.assertIsNone(reject_reason(L("Volkswagen Golf GTI 16V", source="autoscout24", year=1995), model, WL.settings))

    def test_r107_needs_450_sl(self):
        model = WL.model("mercedes-r107-450")
        self.assertIsNone(reject_reason(L("Mercedes-Benz 450 SL", source="autoscout24", year=1978), model, WL.settings))
        self.assertIsNotNone(reject_reason(L("Mercedes-Benz 450 SEL 6.9", source="autoscout24", year=1978), model, WL.settings))

    def test_w140_excludes_r129(self):
        model = WL.model("mercedes-w140-500")
        self.assertIsNotNone(reject_reason(L("Mercedes-Benz 500 SL", source="autoscout24", year=1993), model, WL.settings))
        self.assertIsNone(reject_reason(L("Mercedes-Benz S 500 L", source="autoscout24", year=1996), model, WL.settings))

    def test_variant_year_range(self):
        model = WL.model("toyota-celica")
        m = match(L("Toyota Celica 1.6 ST", year=1979), model, WL.settings)
        self.assertIn("Klassieke Celica (A/TA)", [v for v, _ in m.variants])
        m = match(L("Toyota Celica 1.8 ST", year=1996), model, WL.settings)
        self.assertNotIn("Klassieke Celica (A/TA)", [v for v, _ in m.variants])

    def test_max_year_filter(self):
        self.assertEqual(WL.settings.max_year, 1999)
        self.assertEqual(WL.model("honda-s2000").years, (1999, 1999))
        self.assertIn("bmw-z4-coupe", WL.skipped)
        self.assertIsNotNone(reject_reason(L("Honda S2000", year=2001), WL.model("honda-s2000"), WL.settings))

    def test_german_wanted_ads_rejected(self):
        model = WL.model("vw-corrado")
        self.assertIsNotNone(reject_reason(L("Suche VW Corrado VR6", source="kleinanzeigen", year=1993), model, WL.settings))

    def test_risk_flags(self):
        m = match(L("VW Corrado G60 restauratieproject", year=1990), WL.model("vw-corrado"), WL.settings)
        self.assertIn("Project/restauratie", m.flags)


class WatchlistTest(unittest.TestCase):
    def test_every_model_has_a_search(self):
        for m in WL.models:
            self.assertTrue(m.as24 or m.query, m.id)
            self.assertLessEqual(m.years[0], m.years[1], m.id)
            self.assertTrue(1 <= m.rarity <= 5 and 1 <= m.demand <= 5, m.id)


if __name__ == "__main__":
    unittest.main()


class LookalikeTest(unittest.TestCase):
    def test_styling_mentions_do_not_count_as_variant(self):
        model = WL.model("bmw-e36-coupe-cabrio")
        m = match(L("BMW 318is Coupe allestimento M3", source="autoscout24", year=1994), model, WL.settings)
        self.assertNotIn("M3", [v for v, _ in m.variants])
        m = match(L("BMW 328i cabrio met M3 velgen", source="autoscout24", year=1996), model, WL.settings)
        self.assertNotIn("M3", [v for v, _ in m.variants])
        m = match(L("BMW M3 3.2 cabrio", source="autoscout24", year=1997), model, WL.settings)
        self.assertIn("M3", [v for v, _ in m.variants])

    def test_duetto_only_real_years(self):
        model = WL.model("alfa-spider")
        m = match(L("Alfa Romeo Spider Duetto", source="autoscout24", year=1982), model, WL.settings)
        self.assertNotIn("Duetto (1966-69)", [v for v, _ in m.variants])
        m = match(L("Alfa Romeo Spider Duetto 1600", source="autoscout24", year=1967), model, WL.settings)
        self.assertIn("Duetto (1966-69)", [v for v, _ in m.variants])
