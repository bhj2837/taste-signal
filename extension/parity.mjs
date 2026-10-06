// core.js 가 Python 과 같은 값을 내는지 대조한다. 수집 데이터가 있어야 돌아간다(저장소에는 없다).
//
//   node extension/parity.mjs data/reviews.jsonl data/labels/rules_mapo_v2.jsonl
//
// 첫 파일은 normalize.py 결과, 둘째는 v2 고정본으로 단 레이블이다.
// 후기마다 others, delta, 레이블이 같아야 하고, 가게마다 C 와 맛 편차의 점추정과 표본 수가 같아야 한다.
// 구간은 난수가 달라서 끝값 차이만 보고한다.

import { readFileSync } from "node:fs";
import { classify, derive, scoreShop, CEILING, isClean } from "./core.js";

const [reviewsPath, labelsPath] = process.argv.slice(2);
const lines = (p) => readFileSync(p, "utf8").split("\n").filter(Boolean).map((l) => JSON.parse(l));
const py = lines(reviewsPath);
const labels = new Map(lines(labelsPath).map((l) => [l.review_id, l]));
const ASPECTS = ["taste", "service", "wait", "price", "other"];

let bad = { others: 0, delta: 0, label: 0 };
const byShop = new Map();
for (const r of py) {
  const js = derive({ review_id: r.review_id, star: r.star, text: r.text, rc: r.rc, avg: r.avg });
  if (js.others !== r.others) bad.others++;
  if (js.delta !== r.delta) bad.delta++;
  const a = classify(r.text), b = labels.get(r.review_id);
  if (ASPECTS.some((x) => a[x] !== b[x])) {
    if (bad.label++ < 5) console.log("레이블 다름", r.review_id, JSON.stringify(a), JSON.stringify(b));
  }
  if (!byShop.has(r.shop)) byShop.set(r.shop, []);
  byShop.get(r.shop).push(r);
}
console.log(`후기 ${py.length}건  others 다름 ${bad.others}  delta 다름 ${bad.delta}  레이블 다름 ${bad.label}`);

// 가게 단위: Python 정의(eval_rules.plain, score.summarize 의 clean)로 직접 계산한 값과 비교
const mean = (xs) => xs.reduce((s, x) => s + x, 0) / xs.length;
let shopBad = 0, ciGap = 0, nCi = 0;
for (const [shop, rows] of byShop) {
  const usable = rows.filter((r) => r.delta != null && r.others < CEILING);
  const pyC = usable.length ? mean(usable.map((r) => r.delta)) : null;
  const pyClean = usable.filter((r) => isClean(labels.get(r.review_id))).map((r) => r.delta);
  const pyT = pyClean.length ? mean(pyClean) : null;
  const s = scoreShop(rows.map((r) => ({ review_id: r.review_id, star: r.star, text: r.text, rc: r.rc, avg: r.avg })));
  const close = (x, y) => (x == null && y == null) || (x != null && y != null && Math.abs(x - y) < 1e-9);
  if (!close(s.overall.value, pyC) || !close(s.taste.value, pyT) || s.taste.n !== pyClean.length) shopBad++;
  if (s.taste.ci && pyClean.length >= 15) {
    const sd = Math.sqrt(pyClean.reduce((t, x) => t + (x - pyT) ** 2, 0) / pyClean.length / pyClean.length);
    ciGap = Math.max(ciGap, Math.abs(s.taste.ci[1] - s.taste.ci[0] - 3.92 * sd));
    nCi++;
  }
}
console.log(`가게 ${byShop.size}곳  점추정·표본 수 다름 ${shopBad}  구간 폭과 정규근사(3.92·SE)의 최대 차이 ${ciGap.toFixed(3)} (${nCi}곳)`);
process.exitCode = bad.others + bad.delta + bad.label + shopBad ? 1 : 0;
