"""맛 점수. METHOD.md 4절.

  python3 score.py                         규칙 분류기 레이블로 계산
  python3 score.py data/labels/llm.jsonl   다른 분류기 레이블로 계산
  python3 score.py --counts-only           점수는 숨기고 표본 크기만 본다

--counts-only 는 분류기를 채점하기 전에 쓴다. 점수를 먼저 보면 코드북과 규칙을 고칠 때
미리 적어 둔 예측 쪽으로 기울 수 있다.
"""

import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean

BASE = Path(__file__).parent
NON_TASTE = ("service", "wait", "price", "other")
FULL_WEIGHT_AT = 10
MIN_CLEAN = 15  # 판단 보류 기준. 임시값
# 천장: 이 후기를 뺀 본인 평균이 이 값 이상인 리뷰어는 맛 편차에서 뺀다(METHOD.md 3절 「천장 효과」).
# 5점을 줘도 +0.2 미만이고 4점을 주면 -0.8 이상이라 손해 쪽으로 기운다. 반분 신뢰도를 0.74 에서 0.58 로
# 떨어뜨리는 대가를 알고 넣었다(2026-10-06 결정).
CEILING = 4.8
BOOT = 2000
Z_TIER = 1.96  # 등급을 가르는 차이 검정 기준(양측 5%)
SEED = 0
POS_VALUE = {"pos": 1.0, "mixed": 0.5, "neg": 0.0}


def is_clean(label):
    """별점을 맛의 근거로 쓸 수 있는가. METHOD.md 4절 표."""
    taste = label["taste"]
    if taste == "none":
        return False
    others = [label[a] for a in NON_TASTE if label[a] != "none"]
    if not others:
        return True
    if taste == "mixed" or "mixed" in others:
        return False
    return all(o == taste for o in others)


def weight(rc):
    return min(1.0, (rc or 0) / FULL_WEIGHT_AT)


def boot_ci(values, stat, rng, n=BOOT):
    if not values:
        return None, None
    xs = sorted(stat(rng.choices(values, k=len(values))) for _ in range(n))
    return xs[int(0.025 * n)], xs[int(0.975 * n) - 1]


def weighted_rate(pairs):
    w = sum(p[0] for p in pairs)
    return sum(p[0] * p[1] for p in pairs) / w if w else None


def summarize(rows, rng):
    with_text = [r for r in rows if r["text"].strip()]
    taste = [r for r in rows if r["label"]["taste"] != "none"]
    clean = [
        r["delta"]
        for r in rows
        if is_clean(r["label"]) and r["delta"] is not None and r["others"] < CEILING
    ]
    ceiling = sum(
        1 for r in rows if is_clean(r["label"]) and r["delta"] is not None and r["others"] >= CEILING
    )
    pos_pairs = [(weight(r["rc"]), POS_VALUE[r["label"]["taste"]]) for r in taste]
    low = [r for r in with_text if r["delta"] is not None and r["delta"] < 0]
    filtered = [r for r in low if r["label"]["taste"] == "none"]
    all_delta = [r["delta"] for r in rows if r["delta"] is not None]
    return {
        "shop": rows[0]["shop"],
        "n": len(rows),
        "n_text": len(with_text),
        "n_taste": len(taste),
        "n_clean": len(clean),
        "n_ceiling": ceiling,
        "taste_delta": mean(clean) if clean else None,
        "taste_delta_ci": boot_ci(clean, mean, rng),
        "taste_pos": weighted_rate(pos_pairs),
        "taste_pos_ci": boot_ci(pos_pairs, weighted_rate, rng),
        "filtered_rate": len(filtered) / len(low) if low else None,
        "n_low": len(low),
        "complaints": {a: sum(1 for r in with_text if r["label"][a] == "neg") for a in NON_TASTE},
        "raw_mean": mean(r["star"] for r in rows),
        "delta": mean(all_delta) if all_delta else None,
        "hold": len(clean) < MIN_CLEAN,
    }


def se_from_ci(ci):
    """부트스트랩 95% 구간 폭을 표준오차로 바꾼다(정규 근사)."""
    return (ci[1] - ci[0]) / 3.92


def clearly_lower(a, b, z=Z_TIER):
    """b 의 맛 편차가 a 보다 낮다고 말할 수 있는가. 두 가게 차이를 직접 검정한다."""
    gap = a["taste_delta"] - b["taste_delta"]
    return gap / math.hypot(se_from_ci(a["taste_delta_ci"]), se_from_ci(b["taste_delta_ci"])) > z


def tiers(results):
    """맛 편차 순으로 놓고, 다음 가게가 지금 묶음의 어느 가게보다든 확실히 낮으면 새 묶음.

    2026-10-06 이전 규칙은 「다음 가게의 구간 상한이 묶음 첫 가게의 구간 하한보다 낮으면」이었다.
    95% 구간 둘이 겹치지 않는 것은 차이 검정으로 p 약 0.006 에 해당해 너무 엄격하고,
    87곳에서는 1등급에 21곳이 들어갔다. 구간 겹침 대신 차이를 직접 검정한다.
    """
    ranked = sorted(
        (r for r in results if r["taste_delta"] is not None and not r["hold"]),
        key=lambda r: r["taste_delta"],
        reverse=True,
    )
    tier, members = 0, []
    for r in ranked:
        if not members or any(clearly_lower(m, r) for m in members):
            tier, members = tier + 1, []
        members.append(r)
        r["tier"] = tier
    for r in results:
        r.setdefault("tier", None)
    return ranked + [r for r in results if r["tier"] is None]


def load(labels_path, reviews=None):
    labels = {}
    for line in labels_path.open(encoding="utf-8"):
        l = json.loads(line)
        labels[l["review_id"]] = l
    by_shop = defaultdict(list)
    for line in (reviews or BASE / "data" / "reviews.jsonl").open(encoding="utf-8"):
        r = json.loads(line)
        r["label"] = labels[r["review_id"]]
        by_shop[r["shop"]].append(r)
    return by_shop


def fmt(x, spec="+.2f"):
    return "-" if x is None else format(x, spec)


def main(argv):
    counts_only = "--counts-only" in argv
    paths = [a for a in argv if not a.startswith("--")]
    labels_path = Path(paths[0]) if paths else BASE / "data" / "labels" / "rules.jsonl"
    rng = random.Random(SEED)
    results = [summarize(rows, rng) for rows in load(labels_path).values()]
    print(f"레이블 {labels_path.name} / 가게 {len(results)}곳\n")

    if counts_only:
        print(f"{'가게':<20}{'후기':>6}{'본문':>6}{'맛언급':>7}{'clean':>7}{'낮은별점':>8}  보류")
        for r in sorted(results, key=lambda r: -r["n_clean"]):
            print(f"{r['shop']:<20}{r['n']:>6}{r['n_text']:>6}{r['n_taste']:>7}{r['n_clean']:>7}{r['n_low']:>8}  {'보류' if r['hold'] else ''}")
        return

    head = f"{'등급':>4}  {'가게':<20}{'맛편차':>8}{'구간':>16}{'clean':>7}{'천장':>6}{'맛긍정률':>9}{'걸러짐':>8}{'전체편차':>9}  불만(응대 웨이팅 가격 기타)"
    print(head)
    for r in tiers(results):
        lo, hi = r["taste_delta_ci"]
        ci = f"{fmt(lo)} ~ {fmt(hi)}" if lo is not None else "-"
        tier = "보류" if r["hold"] else str(r["tier"])
        c = r["complaints"]
        print(
            f"{tier:>4}  {r['shop']:<20}{fmt(r['taste_delta']):>8}{ci:>16}{r['n_clean']:>7}{r['n_ceiling']:>6}"
            f"{fmt(r['taste_pos'], '.0%'):>9}{fmt(r['filtered_rate'], '.0%'):>8}{fmt(r['delta']):>9}"
            f"  {c['service']} {c['wait']} {c['price']} {c['other']}"
        )


if __name__ == "__main__":
    main(sys.argv[1:])
