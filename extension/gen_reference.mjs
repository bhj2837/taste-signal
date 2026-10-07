// 확장의 기준 분포를 업종별로 만든다. 수집 데이터가 있어야 돈다(저장소에는 없다).
//
//   node extension/gen_reference.mjs
//
// 업종마다 가게별 숫자만 남긴다: 맛 편차(d)와 그 표준오차(se), 후기 30개 이상 리뷰어 편차(exp), 전체 편차(c).
// 가게 이름, place_id, 후기는 넣지 않는다. 순서는 값 순으로 섞어 출처를 숨긴다.
//
// 업종마다 규칙 분류기 v2 를 검증해 맛 티어를 쓸지 정했다(사전 등록 2026-10-07, eval_cuisine.py).
// 기준을 넘지 못한 업종은 status 를 "unrated" 로 두고, 확장은 맛 평가 불가로 표시하고 전체 편차만 보여 준다.
//
// 업종 판별: 카카오 업종 경로의 이름(예: "돈까스,우동", "일본식라면", 프랜차이즈 이름)을 묶음에 대응시킨다.
// 고깃집은 "육류,고기" 아래와 "양꼬치", 일식과 중식은 "일식", "중식" 부터 아래 이름을 쓴다.
// "한식" 처럼 여러 묶음에 걸치는 상위 이름은 넣지 않는다. 대응표는 collect/places_*_all.tsv 에서 만든다.

import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { scoreShop, expDelta, oneOffShare } from "./core.js";

const GROUPS = {
  meat: {
    name: "고깃집",
    status: "rated",
    reviews: ["data/reviews.jsonl", "data/reviews_seongsu.jsonl", "data/reviews_seoul.jsonl"],
    places: "collect/places_seoul_all.tsv",
    from: (path) => path.slice(path.findIndex((p) => p === "육류,고기" || p === "양꼬치")),
    note: "서울 고깃집(마포, 성동, 그 밖의 23개 구), 2026-10-06과 07 수집",
  },
  jp: {
    name: "일식",
    status: "unrated",
    reason: "규칙 분류기가 일식 후기 300건 검증에서 맛 극성 일치 78.3퍼센트로 기준(80퍼센트)에 못 미쳤다",
    reviews: ["data/reviews_jp.jsonl"],
    places: "collect/places_jp_all.tsv",
    from: (path) => path.slice(path.indexOf("일식")),
    note: "서울 일식(라멘, 돈까스와 우동, 초밥 등), 2026-10-07 수집",
  },
  cn: {
    name: "중식",
    status: "unrated",
    reason: "규칙 분류기가 중식 후기 300건 검증에서 맛 극성 일치 67.7퍼센트, 잘못 걸러짐 22.7퍼센트로 두 기준에 다 못 미쳤다",
    reviews: ["data/reviews_cn.jsonl"],
    places: "collect/places_cn_all.tsv",
    from: (path) => path.slice(path.indexOf("중식")),
    note: "서울 중식(양꼬치 제외), 2026-10-07 수집",
  },
};

function shopsOf(files) {
  const shops = [], oneOff = [];
  for (const f of files) {
    if (!existsSync(f)) continue;
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
      if (s.overall.hold) continue;
      const exp = expDelta(rows);
      shops.push({
        d: s.taste.hold ? null : +s.taste.value.toFixed(3),
        se: s.taste.hold ? null : +((s.taste.ci[1] - s.taste.ci[0]) / 3.92).toFixed(3),
        exp: exp == null ? null : +exp.toFixed(3),
        c: +s.overall.value.toFixed(3),
      });
    }
  }
  shops.sort((a, b) => b.c - a.c);
  oneOff.sort((a, b) => a - b);
  return { shops, oneOffTop10: oneOff.length ? +oneOff[Math.floor(oneOff.length * 0.9)].toFixed(3) : null };
}

const categories = {};
const out = {};
for (const [key, g] of Object.entries(GROUPS)) {
  if (existsSync(g.places)) {
    for (const line of readFileSync(g.places, "utf8").split("\n")) {
      if (!line) continue;
      const path = line.split("\t")[2].split(" > ");
      for (const name of g.from(path)) categories[name] = key;
    }
  }
  const { shops, oneOffTop10 } = shopsOf(g.reviews);
  out[key] = { name: g.name, status: g.status, reason: g.reason || null, note: g.note, oneOffTop10, shops };
  const rated = shops.filter((s) => s.d != null).length;
  console.log(`${g.name}: 가게 ${shops.length}곳(전체 편차 보류 제외), 맛 편차 있는 곳 ${rated}, 상태 ${g.status}`);
}

let js = "// 생성 파일. node extension/gen_reference.mjs 로 다시 만든다. 가게 이름 없이 숫자만 있다.\n";
js += "export const REFERENCE = {\n  groups: {\n";
for (const [key, g] of Object.entries(out)) {
  js += `    ${key}: {\n      name: ${JSON.stringify(g.name)},\n      status: ${JSON.stringify(g.status)},\n`;
  js += `      reason: ${JSON.stringify(g.reason)},\n      note: ${JSON.stringify(g.note)},\n      oneOffTop10: ${g.oneOffTop10},\n      shops: [\n`;
  js += g.shops.map((x) => `        ${JSON.stringify(x)},`).join("\n") + "\n      ],\n    },\n";
}
js += "  },\n  categories: " + JSON.stringify(categories) + ",\n};\n";
writeFileSync(new URL("./reference.js", import.meta.url), js);
console.log(`업종 이름 ${Object.keys(categories).length}개`);
