"""티어표. 맛 편차 등급을 정렬 기준으로 쓰고, 다른 지표는 표시만 한다.

  python3 tier_table.py [레이블 파일] [후기 파일]  >  표.md

가게 이름이 들어간 표를 만든다. 결과는 저장소에 넣지 않는다(README 5절).

정렬    맛 편차의 차이 검정 등급(score.tiers). 1부터 S, A, B, C, 5 이상은 D
확인    후기 30개 이상 리뷰어만의 편차(본문으로 거르지 않음, 천장 제외). 만들기 비싼 계정이라 조작에 강하다.
        이 값의 가게 간 백분위가 맛 편차 백분위와 0.25 이상 벌어지면 표시한다
표시    일회성 계정 비율, 도착률 급증 주의 후기 비율, 가격, 응대, 웨이팅 불만률.
        모두 표에 오른 가게 중 상위 10퍼센트일 때만 붙인다. 정렬에는 쓰지 않는다

후보 지표의 반분 신뢰도는 마포 88곳에서 쟀다. 맛 쪽 지표들은 서로 0.7에서 0.9로 겹쳐서 정렬에 섞지 않았고,
일회성 계정 비율은 맛 편차와 상관이 마포 0.06, 성동 -0.06이라 따로 표시한다. 불만률은 어느 측면이 안정적인지가
상권마다 달라서(가격은 마포, 웨이팅은 성동) 표시로만 쓴다. 재방문 언급은 두 곳 모두 신뢰도가 낮아 뺐다.
"""

import random
import sys
from pathlib import Path
from statistics import mean

import burst
import score

BASE = Path(__file__).parent
LETTER = {1: "S", 2: "A", 3: "B", 4: "C"}
EXP_RC = 30
EXP_MIN = 8
GAP = 0.25
TOP = 0.10


def exp_delta(rows):
    xs = [r["delta"] for r in rows if r["delta"] is not None and r["others"] < score.CEILING and r["rc"] >= EXP_RC]
    return mean(xs) if len(xs) >= EXP_MIN else None


def pct(values):
    """값 -> 0(최저)에서 1(최고) 사이 백분위."""
    order = sorted(values, key=lambda k: values[k])
    n = len(order) - 1 or 1
    return {k: i / n for i, k in enumerate(order)}


def burst_share(rows):
    hot, _, _ = burst.bursts(rows)
    return sum(burst.week(r["registered_at"]) in hot for r in rows) / len(rows)


def text_rate(rows, aspect):
    t = [r for r in rows if r["text"].strip()]
    return sum(r["label"][aspect] == "neg" for r in t) / len(t) if t else 0.0


def main(argv):
    labels = Path(argv[0]) if argv else BASE / "data" / "labels" / "claude.jsonl"
    reviews = Path(argv[1]) if len(argv) > 1 else None
    by = score.load(labels, reviews)
    res = {s: score.summarize(rs, random.Random(0)) for s, rs in by.items()}
    score.tiers(list(res.values()))

    flags = {
        "일회성 계정": {s: sum(r["rc"] == 1 for r in rs) / len(rs) for s, rs in by.items()},
        "급증 주": {s: burst_share(rs) for s, rs in by.items()},
        "가격 불만": {s: text_rate(rs, "price") for s, rs in by.items()},
        "응대 불만": {s: text_rate(rs, "service") for s, rs in by.items()},
        "웨이팅 불만": {s: text_rate(rs, "wait") for s, rs in by.items()},
    }
    cut = {k: sorted(v.values())[int(len(v) * (1 - TOP))] for k, v in flags.items()}

    ranked = [s for s in res if res[s]["tier"] is not None]
    exp = {s: exp_delta(by[s]) for s in ranked}
    exp = {s: v for s, v in exp.items() if v is not None}
    p_taste = pct({s: res[s]["taste_delta"] for s in exp})
    p_exp = pct(exp)

    def check(s):
        if s not in exp:
            return "-"
        d = p_exp[s] - p_taste[s]
        if d <= -GAP:
            return f"낮게 봄 ({exp[s]:+.2f})"
        if d >= GAP:
            return f"높게 봄 ({exp[s]:+.2f})"
        return f"일치 ({exp[s]:+.2f})"

    def badges(s):
        return " · ".join(f"{k} {flags[k][s]:.0%}" for k in flags if flags[k][s] >= cut[k] and flags[k][s] > 0) or ""

    print("| 티어 | 가게 | 맛 편차 | 95% 구간 | 맛 후기 | 경험 많은 손님 | 표시 | 카카오 평균 |")
    print("|---|---|---|---|---|---|---|---|")
    for s in sorted(ranked, key=lambda s: (res[s]["tier"], -res[s]["taste_delta"])):
        r = res[s]
        lo, hi = r["taste_delta_ci"]
        print(f"| {LETTER.get(r['tier'], 'D')} | {s} | {r['taste_delta']:+.2f} | {lo:+.2f} ~ {hi:+.2f} | {r['n_clean']} "
              f"| {check(s)} | {badges(s)} | {r['raw_mean']:.1f} ({r['n']}) |")
    print()
    print("판단 보류 (맛 후기 15건 미만)")
    print()
    print("| 가게 | 맛 후기 | 맛 편차 | 표시 | 카카오 평균 |")
    print("|---|---|---|---|---|")
    for s in sorted((s for s in res if res[s]["tier"] is None), key=lambda s: -res[s]["n_clean"]):
        r = res[s]
        d = f"{r['taste_delta']:+.2f}" if r["taste_delta"] is not None else "-"
        print(f"| {s} | {r['n_clean']} | {d} | {badges(s)} | {r['raw_mean']:.1f} ({r['n']}) |")
    print()
    print("표시 기준(상위 10퍼센트): " + ", ".join(f"{k} {v:.0%} 이상" for k, v in cut.items()))


if __name__ == "__main__":
    main(sys.argv[1:])
