"""정답 레이블 없이 지표를 검증한다.

조작 여부의 정답은 만들 수 없다. 그래서 정확도는 재지 않는다. 대신 레이블이 필요 없는
세 가지를 잰다.

  구간       편차의 95% 부트스트랩 구간. 점추정 순위가 구간으로도 갈리는가
  반분 신뢰도  리뷰를 무작위로 반 갈라 양쪽 가게 순위가 얼마나 같은가
  조작 비용   가짜 5점 몇 개면 지표가 0.1 움직이는가 (계정 종류별)

난수 시드를 고정해 두었으므로 같은 데이터에서는 같은 숫자가 나온다.
"""

import random
from collections import defaultdict
from statistics import mean

from metrics import analyze, loo_delta, summarize
from report import load

SEED = 0
BOOT = 2000
SPLITS = 500
STEP = 0.1  # 조작 비용: 이만큼 움직이면 "움직였다"
MAX_FAKE = 400

ATTACKERS = (
    ("일회성 계정 (후기 1, 평균 5.0)", 1, 5.0),
    ("키운 계정 (후기 10, 평균 4.3)", 10, 4.3),
    ("키운 계정 (후기 30, 평균 4.0)", 30, 4.0),
)


def by_shop(rows):
    out = defaultdict(list)
    for r in rows:
        out[r["shop"]].append(r)
    return out


def deltas(rows):
    return [d for d in (loo_delta(r) for r in rows) if d is not None]


def percentile(sorted_xs, q):
    return sorted_xs[min(len(sorted_xs) - 1, int(q * len(sorted_xs)))]


def bootstrap_ci(xs, rng, n=BOOT):
    means = sorted(mean(rng.choices(xs, k=len(xs))) for _ in range(n))
    return percentile(means, 0.025), percentile(means, 0.975)


def ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    out = [0] * len(xs)
    for rank, i in enumerate(order):
        out[i] = rank
    return out


def spearman(a, b):
    ra, rb = ranks(a), ranks(b)
    n = len(a)
    return 1 - 6 * sum((x - y) ** 2 for x, y in zip(ra, rb)) / (n * (n * n - 1))


def split_half(shops, score, rng, n=SPLITS):
    """리뷰를 반으로 갈라 두 쪽에서 매긴 가게 순위의 스피어만 상관, n번."""
    out = []
    for _ in range(n):
        a, b = [], []
        for rows in shops.values():
            s = rows[:]
            rng.shuffle(s)
            h = len(s) // 2
            a.append(score(s[:h]))
            b.append(score(s[h:]))
        out.append(spearman(a, b))
    return sorted(out)


def fakes_to_move(rows, peer_median, key, reviewer_count, reviewer_avg):
    """가짜 5점을 몇 개 넣어야 key 지표가 STEP 이상 움직이는가. 못 움직이면 None."""
    base = summarize(rows, peer_median)[key]
    fake = {
        "shop": rows[0]["shop"],
        "reviewer_count": reviewer_count,
        "reviewer_avg": reviewer_avg,
        "star": 5.0,
        "paid": False,
    }
    for k in range(1, MAX_FAKE + 1):
        value = summarize(rows + [fake] * k, peer_median)[key]
        if base is None or value is None:
            return None
        if abs(value - base) >= STEP:
            return k
    return None


def main():
    rng = random.Random(SEED)
    rows = list(load())
    shops = by_shop(rows)
    peer_median, results = analyze(rows)

    print(f"리뷰 {len(rows)}건 / 가게 {len(shops)}곳 / 시드 {SEED}\n")

    print(f"== 1. 편차의 95% 부트스트랩 구간 (리뷰 재표집 {BOOT}회)\n")
    print(f"{'가게':<22}{'편차':>8}{'하한':>8}{'상한':>8}{'리뷰어':>8}")
    for r in results:
        d = deltas(shops[r["shop"]])
        if not d:
            print(f"{r['shop']:<22}{'-':>8}")
            continue
        lo, hi = bootstrap_ci(d, rng)
        print(f"{r['shop']:<22}{mean(d):>+8.2f}{lo:>+8.2f}{hi:>+8.2f}{len(d):>8}")

    print(f"\n== 2. 반분 신뢰도 (스피어만, {SPLITS}회)\n")
    candidates = (
        ("편차", lambda s: mean(deltas(s) or [0.0])),
        ("원평균", lambda s: mean(r["star"] for r in s)),
        ("보정 평점", lambda s: summarize(s, peer_median)["r_hat"]),
    )
    for name, score in candidates:
        cs = split_half(shops, score, rng)
        print(
            f"{name:<10} 중앙 {percentile(cs, 0.5):.2f}"
            f"  (5~95%: {percentile(cs, 0.05):.2f} ~ {percentile(cs, 0.95):.2f})"
        )

    print(f"\n== 3. 조작 비용 — 가짜 5점 몇 개면 {STEP} 움직이나 ({MAX_FAKE}개까지)\n")
    for r in results:
        shop_rows = shops[r["shop"]]
        delta = f"{r['delta']:+.2f}" if r["delta"] is not None else "-"
        print(f"{r['shop']} (n={len(shop_rows)}, 편차 {delta})")
        for label, rc, avg in ATTACKERS:
            cells = []
            for key, name in (("raw_mean", "원평균"), ("r_hat", "보정"), ("delta", "편차")):
                k = fakes_to_move(shop_rows, peer_median, key, rc, avg)
                cells.append(f"{name} {k if k else '움직이지 않음'}")
            print(f"  {label:<24}" + "  ".join(f"{c:<16}" for c in cells))


if __name__ == "__main__":
    main()
