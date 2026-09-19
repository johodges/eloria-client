"""Geometry contract for the decorative cliff-house balcony."""
from pathlib import Path
import sys
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE.parent / "_toolkit"))
import landmarks as L


class CliffHouseBalcony(unittest.TestCase):
    WIDTH = 5.0
    DEPTH = 5.6
    STOREYS = 3

    @classmethod
    def setUpClass(cls):
        cls.house = L.cliff_house(seed=41, width=cls.WIDTH,
                                  depth=cls.DEPTH, storeys=cls.STOREYS)
        cls.timber = [part for part in cls.house.parts
                      if part.material == L.TIMBER]
        cls.deck_y = 2.7 * (cls.STOREYS - 1)
        cls.jetty_front = cls.DEPTH * 0.575
        cls.deck_outer = cls.jetty_front + 1.05

    def test_supported_floor_projects_past_the_jetty_at_storey_top(self):
        decks = []
        for part in self.timber:
            low, high = part.bounds()
            if high[1] - low[1] <= 0.181 and high[0] - low[0] > self.WIDTH:
                decks.append((low, high))
        self.assertEqual(len(decks), 1)
        low, high = decks[0]
        self.assertAlmostEqual(high[1], self.deck_y, delta=1e-6)
        self.assertLessEqual(low[2], self.DEPTH * 0.5)
        self.assertGreater(high[2], self.jetty_front + 0.9)

    def test_outer_railing_and_two_side_returns_follow_the_deck_edges(self):
        rails = []
        for part in self.timber:
            low, high = part.bounds()
            height = high[1] - low[1]
            if low[1] >= self.deck_y and 0.9 < height < 1.2:
                rails.append((low, high))
        self.assertEqual(len(rails), 3)
        outer = [pair for pair in rails if pair[1][0] - pair[0][0] > self.WIDTH]
        sides = [pair for pair in rails if pair[1][2] - pair[0][2] > 0.9]
        self.assertEqual(len(outer), 1)
        self.assertEqual(len(sides), 2)
        self.assertAlmostEqual((outer[0][0][2] + outer[0][1][2]) * 0.5,
                               self.deck_outer, delta=1e-6)

    def test_brackets_reach_wall_and_deck_without_covering_window_bays(self):
        brackets = []
        for part in self.timber:
            low, high = part.bounds()
            if high[0] - low[0] <= 0.181 and high[1] < self.deck_y:
                brackets.append((low, high))
        self.assertEqual(len(brackets), 2)
        window_x = self.WIDTH * 0.22
        for low, high in brackets:
            self.assertLessEqual(low[2], self.DEPTH * 0.5 + 0.03)
            self.assertGreaterEqual(high[2], self.deck_outer - 0.2)
            self.assertGreaterEqual(high[1], self.deck_y - 0.3)
            self.assertLess(high[1], self.deck_y)
            self.assertTrue(high[0] < -window_x - 0.25 or
                            low[0] > window_x + 0.25)

    def test_balcony_does_not_declare_a_new_walk_surface(self):
        self.assertEqual(self.house.walk_parts, [])


if __name__ == "__main__":
    unittest.main()
