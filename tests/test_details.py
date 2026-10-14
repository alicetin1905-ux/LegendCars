import json
import unittest

from legendcars import config, details

WL = config.load()


def next_data(page_props: dict) -> str:
    return '<script id="__NEXT_DATA__" type="application/json">' + json.dumps({"props": {"pageProps": page_props}}) + "</script>"


class DetailParserTest(unittest.TestCase):
    def test_autoscout24(self):
        html = next_data({"listingDetails": {
            "description": "Eerste eigenaar.<br />Volledige onderhoudshistoriek, altijd binnen gestald.",
            "createdTimestampWithOffset": "2026-08-18T09:26:16.176Z",
            "vehicle": {"hadAccident": False, "rawData": {"condition": {"numberOfPreviousOwners": {"raw": 1},
                                                                         "damage": {"accidentFree": True}}}},
        }})
        p = details.parse_autoscout24(html)
        self.assertEqual((p["posted"], p["owners"], p["accident_free"]), ("2026-08-18", 1, True))
        d = details.to_detail(p, "2026-10-13")
        self.assertIn("Onderhoudshistoriek", d["cond"]["pos"])
        self.assertIn("Garagewagen", d["cond"]["pos"])

    def test_adevinta(self):
        cfg = {"listing": {"stats": {"viewCount": 8966, "favoritedCount": 56, "since": "2019-05-13T07:07:33Z"},
                           "carDetails": {"carPassUrl": "https://public.car-pass.be/x", "hasNapStatus": False}}}
        html = ("<script>window.__CONFIG__ = " + json.dumps(cfg) + ";</script>"
                '<div data-collapsable="description">Spider 1988, wat roest aan de dorpels</div>')
        p = details.parse_adevinta(html)
        self.assertEqual((p["posted"], p["views"], p["favs"]), ("2019-05-13", 8966, 56))
        d = details.to_detail(p, "2026-10-13")
        self.assertIn("Car-Pass/NAP", d["cond"]["pos"])
        self.assertIn("Roest", d["cond"]["neg"])

    def test_kleinanzeigen(self):
        html = ('<p id="viewad-description-text">Reparierter Unfallschaden. Kein Rost!</p>'
                '<li class="addetailslist--detail">Fahrzeugzustand<span class="addetailslist--detail--value">Unbeschädigtes Fahrzeug</span></li>'
                '<div id="viewad-extra-info"><span>04.09.2026</span></div>')
        p = details.parse_kleinanzeigen(html)
        self.assertEqual((p["posted"], p["accident_free"]), ("2026-09-04", True))
        c = details.to_detail(p, "2026-10-13")["cond"]
        self.assertIn("Ongeval", c["neg"])
        self.assertNotIn("Schadevrij", c["pos"])  # tekst van de verkoper wint
        self.assertIn("Roestvrij", c["pos"])

    def test_willhaben(self):
        html = next_data({"advertDetails": {"firstPublishedDate": "2026-09-30T12:11:59+0200", "attributes": {"attribute": [
            {"name": "DESCRIPTION", "values": ["H-Kennzeichen, Scheckheft"]},
            {"name": "CONDITION_REPORT", "values": ["Ja"]},
            {"name": "CONDITION_REPORT_VALID_UNTIL", "values": ["09.2027"]},
        ]}}})
        p = details.parse_willhaben(html)
        self.assertEqual(p["posted"], "2026-09-30")
        c = details.to_detail(p, "2026-10-13")["cond"]
        self.assertTrue({"Oldtimerplaat", "Onderhoudshistoriek", "Keuring OK"} <= set(c["pos"]))


class CandidatesTest(unittest.TestCase):
    def test_only_within_default_filters_and_not_recent(self):
        base = {"active": True, "source": "2dehands", "model_id": "vw-corrado", "price": 8000, "km": 150000,
                "country": "B", "lat": 51.2, "lon": 4.4}
        recs = [
            {**base, "id": "a"},
            {**base, "id": "b", "price": 20000},                      # te duur
            {**base, "id": "c", "lat": 48.1, "lon": 11.6},           # München: te ver
            {**base, "id": "d", "detail": {"fetched": "2026-10-10"}},  # recent opgehaald
            {**base, "id": "e", "source": "coches"},                  # geen parser
        ]
        self.assertEqual([r["id"] for r in details.candidates(recs, WL, "2026-10-13")], ["a"])


if __name__ == "__main__":
    unittest.main()
