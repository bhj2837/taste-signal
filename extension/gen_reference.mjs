// 확장의 기준 분포를 만든다. 수집 데이터가 있어야 돈다(저장소에는 없다).
//
//   node extension/gen_reference.mjs data/reviews.jsonl data/reviews_seongsu.jsonl
//
// 가게마다 core.js 로 계산한 숫자만 남긴다: 맛 편차(d), 그 표준오차(se), 경험 많은 손님 편차(exp).
// 가게 이름, place_id, 후기는 넣지 않는다. 판단 보류인 가게는 뺀다. 순서는 맛 편차 순으로 섞어 출처를 숨긴다.

import { readFileSync, writeFileSync } from "node:fs";
import { scoreShop, expDelta, oneOffShare } from "./core.js";

const files = process.argv.slice(2);
const shops = [];
const oneOff = [];
for (const f of files) {
  const by = new Map();
  for (const l of readFileSync(f, "utf8").split("\n")) {
    if (!l) continue;
    const r = JSON.parse(l);
    if (!by.has(r.place_id)) by.set(r.place_id, []);
    by.get(r.place_id).push({ review_id: r.review_id, star: r.star, text: r.text, rc: r.rc, avg: r.avg });
  }
  for (const rows of by.values()) {
    oneOff.push(oneOffShare(rows));
    const s = scoreShop(rows);
    if (s.taste.hold) continue;
    const exp = expDelta(rows);
    shops.push({
      d: +s.taste.value.toFixed(3),
      se: +((s.taste.ci[1] - s.taste.ci[0]) / 3.92).toFixed(3),
      exp: exp == null ? null : +exp.toFixed(3),
    });
  }
}
shops.sort((a, b) => b.d - a.d);
oneOff.sort((a, b) => a - b);
const ref = {
  note: "카카오맵 서울 마포(홍대, 합정, 연남)와 성동(성수, 한양대, 마장) 고깃집, 2026-10-06 수집. 규칙 분류기 v2.",
  shops,
  oneOffTop10: +oneOff[Math.floor(oneOff.length * 0.9)].toFixed(3),
};
writeFileSync(
  new URL("./reference.js", import.meta.url),
  "// 생성 파일. node extension/gen_reference.mjs 로 다시 만든다. 가게 이름 없이 숫자만 있다.\n" +
    `export const REFERENCE = {\n  note: ${JSON.stringify(ref.note)},\n  oneOffTop10: ${ref.oneOffTop10},\n  shops: [\n` +
    shops.map((x) => `    ${JSON.stringify(x)},`).join("\n") +
    "\n  ],\n};\n",
);
console.log(`가게 ${shops.length}곳 (보류 제외), 일회성 계정 상위 10% 기준 ${ref.oneOffTop10}`);
