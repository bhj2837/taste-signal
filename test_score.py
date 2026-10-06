"""score.py 의 clean 규칙과 등급, grade.py 의 지표. 실행: python3 -m unittest"""

import random
import unittest

from grade import kappa, macro_f1
from score import is_clean, summarize, tiers


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


class Ceiling(unittest.TestCase):
    def test_reviewer_near_five_is_left_out(self):
        def row(others, delta):
            return {"shop": "a", "star": 5.0, "text": "맛있다", "rc": 20, "others": others, "delta": delta,
                    "label": label("pos")}
        rows = [row(4.9, 0.1), row(4.0, 1.0)]
        out = summarize(rows, random.Random(0))
        self.assertEqual((out["n_clean"], out["n_ceiling"]), (1, 1))
        self.assertAlmostEqual(out["taste_delta"], 1.0)


class Tiers(unittest.TestCase):
    def shop(self, name, d, lo, hi, hold=False):
        return {"shop": name, "taste_delta": d, "taste_delta_ci": (lo, hi), "hold": hold}

    def test_clear_gap_starts_new_tier(self):
        out = tiers([
            self.shop("a", 0.6, 0.4, 0.8),
            self.shop("b", 0.5, 0.3, 0.7),   # 차이 0.1, 표준오차 약 0.14 -> 같은 묶음
            self.shop("c", 0.0, -0.2, 0.2),  # a 와 차이 0.6, z 약 4.2 -> 새 묶음
        ])
        self.assertEqual([r["tier"] for r in out], [1, 1, 2])

    def test_overlapping_intervals_can_still_split(self):
        # 구간은 겹치지만(0.55 < 0.65) 차이는 z 약 2.2 라 갈린다. 옛 규칙은 같은 묶음으로 봤다.
        out = tiers([self.shop("a", 0.8, 0.65, 0.95), self.shop("b", 0.4, 0.25, 0.55)])
        self.assertEqual([r["tier"] for r in out], [1, 2])

    def test_wide_head_does_not_swallow(self):
        # 구간이 넓은 a 가 맨 위여도, 좁은 b 와 확실히 다른 c 는 b 기준으로 갈린다.
        out = tiers([
            self.shop("a", 1.0, -0.5, 2.5),
            self.shop("b", 0.9, 0.8, 1.0),
            self.shop("c", 0.6, 0.5, 0.7),
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
