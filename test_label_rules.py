"""규칙 분류기 v0 가 CODEBOOK.md 의 판정 예시를 따르는지. 예시 문장은 지어낸 것이다.

실행: python3 -m unittest
"""

import unittest

from label_rules import classify


def pick(text, *aspects):
    out = classify(text)
    return tuple(out[a] for a in aspects)


class Codebook(unittest.TestCase):
    def test_price_vs_quality_is_taste(self):
        self.assertEqual(pick("가격 대비 품질이 별로예요", "taste", "price"), ("neg", "none"))

    def test_expensive_but_tasty(self):
        self.assertEqual(pick("비싸지만 맛있어요", "taste", "price"), ("pos", "neg"))

    def test_not_worth_the_wait_is_taste(self):
        self.assertEqual(pick("웨이팅할 만큼은 아니에요", "taste", "wait"), ("neg", "none"))

    def test_worth_the_wait(self):
        self.assertEqual(pick("기다린 보람이 있네요", "taste", "wait"), ("pos", "none"))

    def test_long_wait_but_tasty(self):
        self.assertEqual(pick("웨이팅이 너무 길었는데 고기는 맛있었어요", "taste", "wait"), ("pos", "neg"))

    def test_rude_but_tasty(self):
        self.assertEqual(pick("맛있는데 직원이 불친절해요", "taste", "service"), ("pos", "neg"))

    def test_unkind_is_not_kind(self):
        self.assertEqual(pick("너무 불친절해요", "service"), ("neg",))

    def test_mixed_by_menu(self):
        self.assertEqual(pick("목살은 맛있는데 찌개는 맛없어요", "taste"), ("mixed",))

    def test_neutral_is_mixed(self):
        self.assertEqual(pick("나쁘지 않아요", "taste"), ("mixed",))

    def test_targetless_praise_is_taste(self):
        self.assertEqual(pick("최고예요 또 올게요", "taste", "service"), ("pos", "none"))

    def test_menu_list_is_none(self):
        self.assertEqual(pick("삼겹살 목살 먹었어요", "taste"), ("none",))

    def test_small_portion_is_price(self):
        self.assertEqual(pick("양이 적어요", "taste", "price"), ("none", "neg"))

    def test_grill_yourself_is_service(self):
        self.assertEqual(pick("알아서 구워 먹으라고 함", "service", "taste"), ("neg", "none"))

    def test_jinjja_is_not_salty(self):
        self.assertEqual(pick("진짜 맛있어요", "taste"), ("pos",))

    def test_yangnyeom_is_not_portion(self):
        self.assertEqual(pick("양념이 맛있어요", "price"), ("none",))

    def test_empty_text(self):
        self.assertEqual(set(classify("").values()), {"none"})


if __name__ == "__main__":
    unittest.main()
