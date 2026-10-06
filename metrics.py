"""별점을 판정하지 않고, 얼마나 믿을 수 있는지를 계산한다.

이 모듈은 "이 가게는 조작이다"를 출력하지 않는다. 그런 판정은 만들 수 없다는 것이
이 프로젝트의 결론이다 — 근거는 METHOD.md 「걸러낼 수 없는 것」.

출력은 셋이다.
  R_hat  동네 중앙값 쪽으로 수축시킨 보정 평점
  lower  그 평점의 95% 신뢰구간 하한. 순위는 이걸로 매긴다
  delta  경험 있는 리뷰어들이 자기 평소 평균보다 몇 점 더 줬는가
"""

from collections import defaultdict
from statistics import median

# 리뷰어 가중치: 후기 10개 이상이면 1표, 1개짜리 계정은 0.1표
FULL_WEIGHT_AT = 10
# 수축 강도. 리뷰가 k개 미만이면 동네 중앙값이 더 세진다
SHRINK_K = 10
# 별점 표준편차 경험값
STAR_SD = 1.2

# 칭찬봇 기준 — JMTguri 가 카카오맵 리뷰 175만 건에서 쓴 차등 임계값.
# 리뷰를 많이 쓸수록 평균이 높아도 정상일 수 있으므로 건수에 따라 기준을 달리 둔다.
PRAISE_BOT_TIERS = ((4.9, 3), (4.7, 7), (4.5, 25))


def is_praise_bot(reviewer_avg, reviewer_count):
    return any(
        reviewer_avg >= avg and reviewer_count >= cnt for avg, cnt in PRAISE_BOT_TIERS
    )


def weight(reviewer_count):
    return min(1.0, reviewer_count / FULL_WEIGHT_AT)


def loo_delta(row, min_count=5):
    """star 에서 '이 리뷰를 뺀 본인 평균'을 뺀 값.

    노출되는 avg 는 이 리뷰를 포함한 값이라, 후기가 적은 사람일수록 delta 가 0 으로
    눌린다. 후기 5개짜리는 자기 점수가 본인 평균의 20%를 차지한다. 그래서 자기
    리뷰를 빼고 다시 계산한다. avg 가 소수 1자리로 반올림되어 있어 rc 가 작으면
    오차가 커지므로 min_count 미만은 계산하지 않는다.
    """
    rc, avg, star = row["reviewer_count"], row["reviewer_avg"], row["star"]
    if rc < min_count:
        return None
    others = (avg * rc - star) / (rc - 1)
    return max(-4.0, min(4.0, star - others))


def summarize(shop_rows, peer_median):
    n = len(shop_rows)
    w_total = sum(weight(r["reviewer_count"]) for r in shop_rows)
    w_star = sum(weight(r["reviewer_count"]) * r["star"] for r in shop_rows)

    r_hat = (w_star + SHRINK_K * peer_median) / (w_total + SHRINK_K)
    se = STAR_SD / ((w_total + SHRINK_K) ** 0.5)

    deltas = [d for d in (loo_delta(r) for r in shop_rows) if d is not None]
    bots = [r for r in shop_rows if is_praise_bot(r["reviewer_avg"], r["reviewer_count"])]
    bot_rate = len(bots) / n
    count_median = median(r["reviewer_count"] for r in shop_rows)

    # 의심 신호는 점수를 깎지 않는다. 신뢰구간을 넓힐 뿐이다.
    # 유죄 선고를 하지 않으면 정직한 가게를 잘못 지목하는 비용이 사라진다.
    shallow = count_median < 3 and w_total >= 20
    botty = bot_rate > 0.40
    se *= 1 + 0.3 * shallow + 0.3 * botty

    return {
        "shop": shop_rows[0]["shop"],
        "n": n,
        "raw_mean": sum(r["star"] for r in shop_rows) / n,
        "n_eff": w_total,
        "r_hat": r_hat,
        "lower": r_hat - 1.96 * se,
        "delta": sum(deltas) / len(deltas) if deltas else None,
        "delta_n": len(deltas),
        "bot_rate": bot_rate,
        "count_median": count_median,
        "one_shot_rate": sum(1 for r in shop_rows if r["reviewer_count"] <= 1) / n,
        "five_star_rate": sum(1 for r in shop_rows if r["star"] >= 5) / n,
        "widened": round(1 + 0.3 * shallow + 0.3 * botty, 1),
    }


def analyze(rows):
    by_shop = defaultdict(list)
    for r in rows:
        by_shop[r["shop"]].append(r)

    # peer 중앙값: 같은 상권·업종 가게들의 가중평점 중앙값.
    # 절대 기준이 아니라 이 표본 안에서의 상대 기준이다.
    weighted = []
    for shop_rows in by_shop.values():
        wt = sum(weight(r["reviewer_count"]) for r in shop_rows)
        ws = sum(weight(r["reviewer_count"]) * r["star"] for r in shop_rows)
        weighted.append(ws / wt)
    peer_median = median(weighted)

    out = [summarize(rows_, peer_median) for rows_ in by_shop.values()]
    out.sort(key=lambda d: d["lower"], reverse=True)
    return peer_median, out
