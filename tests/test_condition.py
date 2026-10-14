import unittest

from legendcars.condition import assess


class ConditionTest(unittest.TestCase):
    def test_positive_signals(self):
        c = assess("1e eigenaar, Car-Pass OK, volledige onderhoudshistoriek, altijd binnen gestald, geen roest!")
        self.assertEqual(set(c.pos), {"1e eigenaar", "Car-Pass/NAP", "Onderhoudshistoriek", "Garagewagen", "Roestvrij"})
        self.assertEqual(c.neg, [])
        self.assertEqual(c.score, 4.0)  # afgetopt

    def test_negations_are_not_negative(self):
        for text in ["geen roest", "kein Rost", "sans rouille", "roestvrij", "Rostfrei", "unfallfrei", "ongevalvrij", "rust free"]:
            self.assertEqual(assess(text).neg, [], text)

    def test_negative_signals(self):
        c = assess("Reparierter Unfallschaden, Tauschmotor. Etwas Rost an den Schwellern. Tiefergelegt.")
        self.assertIn("Ongeval", c.neg)
        self.assertIn("Vervangen motor", c.neg)
        self.assertIn("Roest", c.neg)
        self.assertIn("Getuned", c.neg)
        self.assertLess(c.score, -2)

    def test_french_and_structured_fields(self):
        c = assess("Superbe état, 1 propriétaire, carnet d'entretien", owners=1, accident_free=True)
        self.assertIn("1e eigenaar", c.pos)
        self.assertIn("Onderhoudshistoriek", c.pos)
        self.assertIn("Schadevrij", c.pos)
        self.assertEqual(c.pos.count("1e eigenaar"), 1)

    def test_many_owners(self):
        self.assertIn("6 eigenaars", assess("", owners=6).neg)


if __name__ == "__main__":
    unittest.main()
