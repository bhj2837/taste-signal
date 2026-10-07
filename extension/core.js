// 확장의 계산 핵심. DOM 을 쓰지 않는 순수 함수만 둔다.
// Python 쪽과 같은 값을 내야 한다: normalize.py(편차), label_rules.py v2(분류), score.py(맛 편차), eval_rules.py(C).
// 대조는 extension/parity.mjs.

import { RULES } from "./rules_v2.js";

export const MIN_COUNT = 5; // 편차를 쓰는 리뷰어 후기 수 하한
export const CEILING = 4.8; // 이 후기를 뺀 본인 평균이 이 이상이면 뺀다
export const MIN_N = 15; // 판단 보류 기준
export const BOOT = 2000;
const ASPECTS = ["taste", "service", "wait", "price", "other"];
const NON_TASTE = ["service", "wait", "price", "other"];

// 카카오맵 후기 응답(reviews 배열의 원소)을 계산에 쓰는 형태로. 수집기의 화이트리스트와 같은 필드만 읽는다.
export function fromApi(r) {
  const owner = (r.meta && r.meta.owner) || {};
  return {
    review_id: r.review_id,
    star: r.star_rating,
    text: r.contents || "",
    registered_at: r.registered_at,
    updated_at: r.updated_at,
    rc: owner.review_count,
    avg: owner.average_score,
  };
}

// Python round(x, 4) 와 같은 값. 저장된 이진수의 정확한 값으로 반올림하고, 정확히 반이면 짝수 쪽으로 간다.
// Math.round(x * 1e4) 는 곱셈에서 오차가 생기고 반을 늘 올려서 수십 건이 0.0001 씩 달랐다.
export function round4(x) {
  const [, f] = Math.abs(x).toFixed(100).split(".");
  const tie = f[4] === "5" && /^0*$/.test(f.slice(5));
  if (!tie) return Number(x.toFixed(4));
  let t = Math.trunc(Math.abs(x) * 1e4);
  if (t % 2) t += 1;
  return (Math.sign(x) * t) / 1e4;
}

// normalize.derive 와 같다. others 는 이 후기를 뺀 본인 평균, delta 는 별점과의 차이(-4 에서 +4).
export function derive(r) {
  const { rc, avg, star } = r;
  const others = rc && rc >= 2 && avg != null ? (avg * rc - star) / (rc - 1) : null;
  let delta = null;
  if (others != null && rc >= MIN_COUNT) delta = Math.max(-4, Math.min(4, star - others));
  return {
    ...r,
    others: others != null ? round4(others) : null,
    delta: delta != null ? round4(delta) : null,
  };
}

// --- 규칙 분류기 v2 ---------------------------------------------------------

const one = (s) => new RegExp(s, "u");
const all = (s) => new RegExp(s, "gu");
const C = {
  split: all(RULES.split),
  hedge: one(RULES.hedge),
  override: RULES.override.map(([a, p, s]) => [a, p, one(s), all(s)]),
  polar: RULES.polar.map(([a, p, s]) => [a, p, one(s), all(s)]),
  mention: RULES.mention.map(([a, s]) => [a, one(s)]),
  generic: RULES.generic.map(([p, s]) => [p, one(s), all(s)]),
};

function classifyClause(clause) {
  const found = [];
  let text = clause;
  for (const [aspect, pol, rx, rxg] of [...C.override, ...C.polar]) {
    if (rx.test(text)) {
      text = text.replace(rxg, " ");
      if (aspect) found.push([aspect, pol]);
    }
  }
  const mentioned = new Set(C.mention.filter(([, rx]) => rx.test(text)).map(([a]) => a));
  const generic = [];
  for (const [pol, rx, rxg] of C.generic) {
    if (rx.test(text)) {
      text = text.replace(rxg, " ");
      generic.push(pol);
    }
  }
  const polarAspects = new Set(found.map(([a]) => a));
  let targets = [...mentioned].filter((a) => !polarAspects.has(a));
  const out = found.map(([a, p]) => [a, p, false]);
  if (generic.length) {
    if (!targets.length && !found.length) targets = ["taste"];
    for (const a of targets) for (const p of generic) out.push([a, p, true]);
  }
  return out;
}

function merge(votes) {
  if (!votes.length) return "none";
  let pos = 0, neg = 0, mixed = 0;
  for (const [p, w] of votes) {
    if (p === "pos") pos += w;
    else if (p === "neg") neg += w;
    else if (p === "mixed") mixed += w;
  }
  if (pos && pos >= 2 * (neg + mixed)) return "pos";
  if (neg && neg >= 2 * (pos + mixed)) return "neg";
  return "mixed";
}

export function classify(text) {
  const per = Object.fromEntries(ASPECTS.map((a) => [a, []]));
  const genericTasteNeg = [];
  let otherNeg = false;
  for (const clause of (text || "").split(C.split)) {
    if (!clause.trim()) continue;
    const weight = C.hedge.test(clause) ? 0.5 : 1.0;
    const seen = new Set();
    for (const [aspect, pol, gen] of classifyClause(clause)) {
      const key = `${aspect}|${pol}|${gen}`;
      if (seen.has(key)) continue;
      seen.add(key);
      const vote = [pol, pol === "neg" ? weight : 1.0];
      if (aspect === "taste" && pol === "neg" && gen) {
        genericTasteNeg.push(vote);
        continue;
      }
      if (aspect !== "taste" && pol === "neg" && !gen) otherNeg = true;
      per[aspect].push(vote);
    }
  }
  // 코드북 규칙 8: 대상 없는 부정어가 맛 이외의 불만과 함께 있으면 그 불만에 대한 말로 읽는다
  if (!otherNeg) per.taste.push(...genericTasteNeg);
  return Object.fromEntries(ASPECTS.map((a) => [a, merge(per[a])]));
}

// score.is_clean 과 같다. 별점을 맛의 근거로 쓸 수 있는가.
export function isClean(label) {
  const taste = label.taste;
  if (taste === "none") return false;
  const others = NON_TASTE.map((a) => label[a]).filter((v) => v !== "none");
  if (!others.length) return true;
  if (taste === "mixed" || others.includes("mixed")) return false;
  return others.every((o) => o === taste);
}

// --- 점수 -------------------------------------------------------------------

// 시드를 고정한 난수. 같은 후기 묶음이면 화면을 다시 열어도 구간이 같다.
export function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const mean = (xs) => xs.reduce((s, x) => s + x, 0) / xs.length;

// score.boot_ci 와 같은 백분위 위치. 난수는 달라서 구간 끝은 Python 과 조금 다르다.
export function bootCi(xs, rand, n = BOOT) {
  if (!xs.length) return null;
  const ms = [];
  for (let i = 0; i < n; i++) {
    let s = 0;
    for (let j = 0; j < xs.length; j++) s += xs[Math.floor(rand() * xs.length)];
    ms.push(s / xs.length);
  }
  ms.sort((a, b) => a - b);
  return [ms[Math.floor(0.025 * n)], ms[Math.floor(0.975 * n) - 1]];
}

function stat(xs, rand) {
  return { n: xs.length, value: xs.length ? mean(xs) : null, ci: bootCi(xs, rand), hold: xs.length < MIN_N };
}

// 가게 하나. reviews 는 fromApi 를 거친 후기 목록(중복 없이).
// overall = C, 전체 편차(천장 제외). 「맛 점수」 가 아니다 — 본문 없는 후기도 들어가서 맛 편차보다 낮게 나온다.
// taste   = 규칙 v2 로 맛을 근거로 쓸 수 있는 후기만 남긴 편차. 참고값.
// showTaste = 둘 다 보류가 아니고 C 가 taste 의 95% 구간 밖일 때만 참고값을 띄운다.
export function scoreShop(reviews, seed = 0) {
  const rows = reviews.map(derive);
  const usable = rows.filter((r) => r.delta != null && r.others < CEILING);
  const overall = stat(usable.map((r) => r.delta), rng(seed));
  const clean = usable.filter((r) => isClean(classify(r.text)));
  const taste = stat(clean.map((r) => r.delta), rng(seed + 1));
  const showTaste =
    !overall.hold && !taste.hold && (overall.value < taste.ci[0] || overall.value > taste.ci[1]);
  return {
    n: rows.length,
    n_ceiling: rows.filter((r) => r.delta != null && r.others >= CEILING).length,
    overall,
    taste,
    showTaste,
  };
}

// --- 티어 ---------------------------------------------------------------------
// vault 티어표와 같은 규칙(score.tiers): 맛 편차 순으로 놓고, 다음 가게가 지금 묶음의 어느 가게보다든
// 차이 검정(z > 1.96)으로 확실히 낮으면 새 묶음. 기준 분포는 수집한 가게를 이 파일로 계산한 숫자(reference.js).

export const Z_TIER = 1.96;
export const EXP_RC = 30; // 경험 많은 손님: 후기 30개 이상
export const EXP_MIN = 8;
export const GAP = 0.25; // 경험 많은 손님 백분위가 이만큼 벌어지면 표시
const LETTER = ["S", "A", "B", "C"];
export const letter = (tier) => LETTER[tier - 1] || "D";

const seFromCi = (ci) => (ci[1] - ci[0]) / 3.92;

function clearlyLower(a, b) {
  return (a.d - b.d) / Math.hypot(a.se, b.se) > Z_TIER;
}

// shops: [{ d, se, ... }]. 같은 배열에 tier 를 적어 돌려준다(맛 편차 내림차순).
export function tiers(shops) {
  const ranked = [...shops].sort((x, y) => y.d - x.d);
  let tier = 0, members = [];
  for (const r of ranked) {
    if (!members.length || members.some((m) => clearlyLower(m, r))) {
      tier += 1;
      members = [];
    }
    members.push(r);
    r.tier = tier;
  }
  return ranked;
}

// 후기 30개 이상 리뷰어만의 편차(본문으로 거르지 않음, 천장 제외). 만들기 비싼 계정이라 조작에 강하다.
export function expDelta(reviews) {
  const xs = reviews.map(derive).filter((r) => r.delta != null && r.others < CEILING && r.rc >= EXP_RC).map((r) => r.delta);
  return xs.length >= EXP_MIN ? mean(xs) : null;
}

export const oneOffShare = (reviews) => (reviews.length ? reviews.filter((r) => r.rc === 1).length / reviews.length : null);

const below = (xs, v) => xs.filter((x) => x < v).length / xs.length;

// 보고 있는 가게(score = scoreShop 결과)를 기준 분포 ref 에 끼워 넣어 티어를 매긴다.
export function placeInReference(score, exp, ref) {
  if (score.taste.hold) return null;
  const rated = ref.shops.filter((s) => s.d != null);
  const me = { d: score.taste.value, se: seFromCi(score.taste.ci), me: true };
  const all = [...rated.map((s) => ({ ...s })), me];
  tiers(all);
  const tasteShare = below(rated.map((s) => s.d), me.d);
  let check = null;
  if (exp != null) {
    const both = rated.filter((s) => s.exp != null);
    const gap = below(both.map((s) => s.exp), exp) - below(both.map((s) => s.d), me.d);
    check = gap <= -GAP ? "lower" : gap >= GAP ? "higher" : "same";
  }
  return { tier: me.tier, letter: letter(me.tier), top: 1 - tasteShare, n: rated.length, check };
}

// 전체 편차가 그 업종 기준 분포에서 상위 몇 퍼센트인가. 맛 평가 불가 업종에서 쓴다.
export function overallInReference(score, ref) {
  if (score.overall.hold) return null;
  const cs = ref.shops.map((s) => s.c);
  return { top: 1 - below(cs, score.overall.value), n: cs.length };
}

// 페이지의 업종 이름(예: "돈까스,우동")을 묶음 열쇠로. 모르면 null.
export function groupOf(category, reference) {
  const name = (category || "").replace(/^장소 카테고리/, "").trim();
  return reference.categories[name] || null;
}
