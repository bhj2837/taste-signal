// 데이터 없이 도는 테스트. node --test extension/
// 분류 예문은 test_label_rules.py 의 V2 와 같다(지어낸 문장).

import { test } from "node:test";
import assert from "node:assert/strict";
import { classify, derive, fromApi, isClean, round4, scoreShop } from "./core.js";

const pick = (text, ...aspects) => aspects.map((a) => classify(text)[a]);

test("Python round 와 같은 반올림", () => {
  assert.equal(round4(0.40625), 0.4062); // 정확히 반이면 짝수 쪽
  assert.equal(round4(3.59375), 3.5938);
  assert.equal(round4((2.9 * 17 - 4) / 16), 2.8312); // 저장된 값이 반보다 조금 작다
  assert.equal(round4(-2.23125), -2.2313); // 음수도 같은 규칙
});

test("편차는 이 후기를 뺀 본인 평균과의 차이, 후기 5개 미만이면 없음", () => {
  const r = derive({ star: 5, rc: 10, avg: 4.0 });
  assert.equal(r.others, 3.8889);
  assert.equal(r.delta, 1.1111);
  assert.equal(derive({ star: 5, rc: 4, avg: 4.0 }).delta, null);
  assert.equal(derive({ star: 1, rc: 2, avg: 1.0 }).delta, null);
});

test("카카오맵 응답에서 쓰는 필드만 읽는다", () => {
  const r = fromApi({ review_id: 1, star_rating: 4, contents: "맛있어요", meta: { owner: { review_count: 12, average_score: 3.5, map_user_id: "x" } } });
  assert.deepEqual(Object.keys(r).sort(), ["avg", "rc", "registered_at", "review_id", "star", "text", "updated_at"]);
  assert.equal(r.rc, 12);
});

test("v2 회귀 예문", () => {
  assert.deepEqual(pick("고기가 너무맛있어요", "taste"), ["pos"]);
  assert.deepEqual(pick("잡내 하나도 안 나고 부드러워요", "taste"), ["pos"]);
  assert.deepEqual(pick("양고기인데 냄새가 전혀 없어요", "taste"), ["pos"]);
  assert.deepEqual(pick("캠핑 감성 느끼고 싶으면 오세요 고기도 맛있어요", "taste"), ["pos"]);
  assert.deepEqual(pick("비싸지 않은 가격에 고기도 좋아요", "price"), ["pos"]);
  assert.deepEqual(pick("정말 맛있었지만 좀 짰어요", "taste"), ["pos"]);
  assert.deepEqual(pick("직원이 너무 불친절해요. 다신 안 갑니다", "taste", "service"), ["none", "neg"]);
  assert.deepEqual(pick("불친절하고 맛도 없어요", "taste", "service"), ["neg", "neg"]);
  assert.deepEqual(pick("30분 기다려서 먹을 맛은 아니에요", "taste"), ["neg"]);
  assert.deepEqual(pick("웨이팅이 길었지만 고기가 맛있어요", "taste", "wait"), ["pos", "none"]);
});

test("맛과 다른 측면이 반대면 별점을 맛의 근거로 쓰지 않는다", () => {
  assert.equal(isClean(classify("맛있는데 너무 불친절해요")), false);
  assert.equal(isClean(classify("맛있고 친절해요")), true);
  assert.equal(isClean(classify("")), false);
});

const many = (n, star, text, avg = 3.5) =>
  Array.from({ length: n }, (_, i) => ({ review_id: `${text}${star}${i}`, star, text, rc: 20, avg }));

test("표본이 15건 미만이면 보류", () => {
  const s = scoreShop(many(10, 5, "맛있어요"));
  assert.equal(s.overall.hold, true);
  assert.equal(s.showTaste, false);
});

test("천장 리뷰어는 뺀다", () => {
  const s = scoreShop([...many(20, 5, "맛있어요"), ...many(5, 5, "맛있어요", 4.95)]);
  assert.equal(s.overall.n, 20);
  assert.equal(s.n_ceiling, 5);
});

test("응대 불만이 몰리면 참고값을 띄운다", () => {
  // 맛을 말한 후기는 후하고, 응대 불만과 본문 없는 후기가 전체 편차를 끌어내린다
  const s = scoreShop([...many(30, 5, "고기가 정말 맛있어요"), ...many(30, 1, "직원이 너무 불친절해요"), ...many(20, 2, "")]);
  assert.equal(s.overall.hold, false);
  assert.equal(s.taste.hold, false);
  assert.ok(s.overall.value < s.taste.value);
  assert.equal(s.showTaste, true);
});

test("거르기로 바뀌는 게 없으면 참고값을 띄우지 않는다", () => {
  const s = scoreShop([...many(20, 5, "고기가 맛있어요"), ...many(20, 3, "맛은 별로예요")]);
  assert.equal(s.showTaste, false);
});
