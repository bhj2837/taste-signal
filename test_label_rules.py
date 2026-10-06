"""규칙 분류기가 CODEBOOK.md 의 판정 예시를 따르는지. 예시 문장은 지어낸 것이다.

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


class V2(unittest.TestCase):
    """v2 에서 고친 오류. 예시 문장은 지어낸 것이다."""

    def test_no_space_praise_is_not_bland(self):
        # v1 은 「너무맛있」 안의 「무맛」 을 맛 부정으로 잡았다
        self.assertEqual(pick("고기가 너무맛있어요", "taste"), ("pos",))

    def test_no_off_smell_is_praise(self):
        self.assertEqual(pick("잡내 하나도 안 나고 부드러워요", "taste"), ("pos",))
        self.assertEqual(pick("양고기인데 냄새가 전혀 없어요", "taste"), ("pos",))

    def test_feel_is_not_greasy(self):
        self.assertEqual(pick("캠핑 감성 느끼고 싶으면 오세요 고기도 맛있어요", "taste"), ("pos",))

    def test_not_expensive(self):
        self.assertEqual(pick("비싸지 않은 가격에 고기도 좋아요", "price"), ("pos",))

    def test_hedged_complaint_counts_half(self):
        self.assertEqual(pick("정말 맛있었지만 좀 짰어요", "taste"), ("pos",))

    def test_generic_negative_next_to_service_is_not_taste(self):
        # 코드북 규칙 8
        self.assertEqual(pick("직원이 너무 불친절해요. 다신 안 갑니다", "taste", "service"), ("none", "neg"))
        self.assertEqual(pick("불친절하고 맛도 없어요", "taste", "service"), ("neg", "neg"))

    def test_not_worth_eating(self):
        self.assertEqual(pick("30분 기다려서 먹을 맛은 아니에요", "taste"), ("neg",))

    def test_wait_as_fact_is_not_complaint(self):
        self.assertEqual(pick("웨이팅이 길었지만 고기가 맛있어요", "taste", "wait"), ("pos", "none"))


class V3(unittest.TestCase):
    """v3 에서 고친 오류. 마포 88곳 전부를 개발용으로 썼다. 예시 문장은 지어낸 것이다."""

    def test_comma_list_shares_the_verdict(self):
        self.assertEqual(pick("맛, 분위기, 가격 다 만족", "taste", "other", "price"), ("pos", "pos", "pos"))

    def test_menu_item_with_food_predicate(self):
        self.assertEqual(pick("파채가 야무지고 된장찌개가 구수해요", "taste"), ("pos",))

    def test_quality_predicates(self):
        self.assertEqual(pick("고기 질이 너무 떨어져요", "taste"), ("neg",))
        self.assertEqual(pick("고기 퀄리티가 확실히 달라요", "taste"), ("pos",))
        self.assertEqual(pick("소고기가 질겨요", "taste"), ("neg",))
        self.assertEqual(pick("맛이 너무 없어요", "taste"), ("neg",))

    def test_revisit_intent(self):
        self.assertEqual(pick("벌써 다섯 번은 넘게 갔어요", "taste"), ("pos",))
        self.assertEqual(pick("또 먹고 싶어요", "taste"), ("pos",))
        # 상황 설명과 부정은 재방문 의사가 아니다
        self.assertEqual(pick("두 번 다시 가고 싶지 않아요", "taste"), ("neg",))
        self.assertEqual(pick("불판도 자주 갈아 주셨어요", "taste"), ("none",))

    def test_cannot_be_bad_is_praise(self):
        self.assertEqual(pick("삼겹살에 김치면 맛없을 수 없죠", "taste"), ("pos",))

    def test_taste_changed(self):
        self.assertEqual(pick("예전엔 자주 왔는데 맛이 변했어요", "taste"), ("neg",))
        self.assertEqual(pick("올 때마다 맛이 변함없어요", "taste"), ("pos",))

    def test_slang_needs_context(self):
        self.assertEqual(pick("어쩔 수 없이 고기를 직접 구웠어요", "taste"), ("none",))
        self.assertEqual(pick("존맛탱탱구리", "taste"), ("pos",))


if __name__ == "__main__":
    unittest.main()
