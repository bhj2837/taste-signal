"""metrics.py 경계 조건. 실행: python3 -m unittest"""

import unittest

from metrics import analyze, loo_delta


def row(shop, rc, avg, star):
    return {"shop": shop, "reviewer_count": rc, "reviewer_avg": avg, "star": star, "paid": False}


class LooDelta(unittest.TestCase):
    def test_below_min_count_is_skipped(self):
        # 후기 4개 이하는 반올림된 평균 때문에 오차가 커서 계산하지 않는다
        self.assertIsNone(loo_delta(row("a", 4, 4.0, 5.0)))

    def test_removes_own_review_from_average(self):
        # 후기 5개, 평균 4.2, 이 가게 5점 -> 나머지 4개 평균 4.0 -> 편차 +1.0
        self.assertAlmostEqual(loo_delta(row("a", 5, 4.2, 5.0)), 1.0)

    def test_generous_reviewer_gets_small_delta(self):
        # 평소 5점만 주는 사람의 5점은 정보가 없다
        self.assertAlmostEqual(loo_delta(row("a", 10, 5.0, 5.0)), 0.0)

    def test_clipped_to_four(self):
        # 반올림 노출 때문에 나머지 평균이 1 아래로 계산될 수 있다
        self.assertEqual(loo_delta(row("a", 5, 1.0, 5.0)), 4.0)


class Ordering(unittest.TestCase):
    def test_sorted_by_delta_not_lower_bound(self):
        rows = (
            # 원평균은 높지만 후한 리뷰어뿐 -> 편차 0
            [row("후한", 20, 5.0, 5.0)] * 30
            # 원평균은 낮지만 깐깐한 리뷰어가 평소보다 높게 줬다 -> 편차 양수
            + [row("깐깐", 20, 3.0, 4.0)] * 30
        )
        _, out = analyze(rows)
        self.assertEqual([r["shop"] for r in out], ["깐깐", "후한"])

    def test_shop_without_delta_goes_last(self):
        rows = [row("편차있음", 20, 4.0, 3.0)] * 10 + [row("편차없음", 1, 5.0, 5.0)] * 10
        _, out = analyze(rows)
        self.assertEqual(out[-1]["shop"], "편차없음")
        self.assertIsNone(out[-1]["delta"])


if __name__ == "__main__":
    unittest.main()
