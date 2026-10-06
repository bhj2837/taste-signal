"""맛 점수. METHOD.md 4절.

  python3 score.py                         규칙 분류기 레이블로 계산
  python3 score.py data/labels/llm.jsonl   다른 분류기 레이블로 계산
  python3 score.py --counts-only           점수는 숨기고 표본 크기만 본다

--counts-only 는 분류기를 채점하기 전에 쓴다. 점수를 먼저 보면 코드북과 규칙을 고칠 때
미리 적어 둔 예측 쪽으로 기울 수 있다.
"""

import json
import random
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean

BASE = Path(__file__).parent
NON_TASTE = ("service", "wait", "price", "other")
FULL_WEIGHT_AT = 10
MIN_CLEAN = 15  # 판단 보류 기준. 임시값
BOOT = 2000
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
    clean = [r["delta"] for r in rows if is_clean(r["label"]) and r["delta"] is not None]
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


def tiers(results):
    """맛 편차 순으로 놓고, 다음 가게의 구간 상한이 묶음 첫 가게의 구간 하한보다 낮으면 새 묶음."""
    ranked = sorted(
        (r for r in results if r["taste_delta"] is not None and not r["hold"]),
        key=lambda r: r["taste_delta"],
        reverse=True,
    )
    tier, head = 0, None
    for r in ranked:
        if head is None or r["taste_delta_ci"][1] < head["taste_delta_ci"][0]:
            tier, head = tier + 1, r
        r["tier"] = tier
    for r in results:
        r.setdefault("tier", None)
    return ranked + [r for r in results if r["tier"] is None]


def load(labels_path):
    labels = {}
    for line in labels_path.open(encoding="utf-8"):
        l = json.loads(line)
        labels[l["review_id"]] = l
    by_shop = defaultdict(list)
    for line in (BASE / "data" / "reviews.jsonl").open(encoding="utf-8"):
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

    head = f"{'등급':>4}  {'가게':<20}{'맛편차':>8}{'구간':>16}{'clean':>7}{'맛긍정률':>9}{'걸러짐':>8}{'전체편차':>9}  불만(응대 웨이팅 가격 기타)"
    print(head)
    for r in tiers(results):
        lo, hi = r["taste_delta_ci"]
        ci = f"{fmt(lo)} ~ {fmt(hi)}" if lo is not None else "-"
        tier = "보류" if r["hold"] else str(r["tier"])
        c = r["complaints"]
        print(
            f"{tier:>4}  {r['shop']:<20}{fmt(r['taste_delta']):>8}{ci:>16}{r['n_clean']:>7}"
            f"{fmt(r['taste_pos'], '.0%'):>9}{fmt(r['filtered_rate'], '.0%'):>8}{fmt(r['delta']):>9}"
            f"  {c['service']} {c['wait']} {c['price']} {c['other']}"
        )


if __name__ == "__main__":
    main(sys.argv[1:])
