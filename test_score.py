"""score.py 의 clean 규칙과 등급, grade.py 의 지표. 실행: python3 -m unittest"""

import unittest

from grade import kappa, macro_f1
from score import is_clean, tiers


def label(taste, service="none", wait="none", price="none", other="none"):
    return {"taste": taste, "service": service, "wait": wait, "price": price, "other": other}


class Clean(unittest.TestCase):
    def test_no_taste_is_excluded_both_ways(self):
        self.assertFalse(is_clean(label("none", service="neg")))
        self.assertFalse(is_clean(label("none", service="pos")))

    def test_taste_only(self):
        self.assertTrue(is_clean(label("neg")))

    def test_same_direction(self):
        self.assertTrue(is_clean(label("pos", service="pos")))

    def test_opposite_direction_contaminates(self):
        self.assertFalse(is_clean(label("pos", service="neg")))
        self.assertFalse(is_clean(label("neg", other="pos")))

    def test_mixed_with_others_is_unclear(self):
        self.assertFalse(is_clean(label("mixed", price="neg")))
        self.assertTrue(is_clean(label("mixed")))


class Tiers(unittest.TestCase):
    def shop(self, name, d, lo, hi, hold=False):
        return {"shop": name, "taste_delta": d, "taste_delta_ci": (lo, hi), "hold": hold}

    def test_overlapping_share_tier(self):
        out = tiers([
            self.shop("a", 0.6, 0.4, 0.8),
            self.shop("b", 0.5, 0.3, 0.7),   # 상한 0.7 이 a 의 하한 0.4 보다 높다 -> 같은 묶음
            self.shop("c", 0.0, -0.2, 0.2),  # 상한 0.2 가 a 의 하한 0.4 보다 낮다 -> 새 묶음
        ])
        self.assertEqual([r["tier"] for r in out], [1, 1, 2])

    def test_hold_gets_no_tier(self):
        out = tiers([self.shop("a", 0.6, 0.4, 0.8), self.shop("b", 0.9, 0.0, 1.5, hold=True)])
        self.assertEqual([(r["shop"], r["tier"]) for r in out], [("a", 1), ("b", None)])


class Metrics(unittest.TestCase):
    def test_macro_f1_perfect(self):
        self.assertEqual(macro_f1(["pos", "neg"], ["pos", "neg"]), 1.0)

    def test_kappa_perfect_and_chance(self):
        self.assertEqual(kappa(["pos", "neg", "pos"], ["pos", "neg", "pos"]), 1.0)
        self.assertAlmostEqual(kappa(["pos", "neg"], ["neg", "pos"]), -1.0)


if __name__ == "__main__":
    unittest.main()
