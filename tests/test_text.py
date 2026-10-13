import unittest

from legendcars.text import normalize, parse_int, parse_year


class TextTest(unittest.TestCase):
    def test_normalize_keeps_decimal_points(self):
        self.assertEqual(normalize("BMW Z3 2.8i Roadster"), "bmw z3 2.8i roadster")

    def test_normalize_strips_accents_and_punctuation(self):
        self.assertEqual(normalize("Mercedes 300 CE-24 Coupé", "(A124)"), "mercedes 300 ce 24 coupe a124")

    def test_normalize_drops_sentence_dots(self):
        self.assertEqual(normalize("Topstaat. 1e eig."), "topstaat 1e eig")

    def test_parse_helpers(self):
        self.assertEqual(parse_int("116.303 km"), 116303)
        self.assertIsNone(parse_int(""))
        self.assertEqual(parse_year("03-1999"), 1999)
        self.assertIsNone(parse_year("onbekend"))


if __name__ == "__main__":
    unittest.main()


class NormTest(unittest.TestCase):
    def test_fuel(self):
        from legendcars.listing import norm_fuel
        self.assertEqual(norm_fuel("Gasolina"), "petrol")
        self.assertEqual(norm_fuel("Benzin"), "petrol")
        self.assertEqual(norm_fuel("Autogas (LPG)"), "lpg")
        self.assertEqual(norm_fuel("Diésel"), "diesel")
