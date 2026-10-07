"""시간 예측력. 날짜 T 에서 후기를 잘라, T 이전 후기로 낸 지표가 T 이후 후기의 편차를 맞히는지 본다.

  python3 backtest.py [T]      기본 T = 2025-04-06

앞으로 받아서 채점하려면 쓸 수 있는 새 후기가 가게당 한 달에 0.5건(중앙값)이라 너무 느리다.
그래서 이미 받은 데이터를 과거 시점에서 자른다. 사전 등록은 2026-10-06, 결과를 보기 전에 했다.

대상 가게  T 이전 맛 후기(LLM 레이블 clean, 천장 제외) 15건 이상, T 이후 쓸 수 있는 후기 8건 이상
예측 변수  T 이전 후기만: 맛 편차(LLM), 맛 편차(규칙 v2), 전체 편차, 원평균 별점, 후기 30개 이상 리뷰어 편차
맞힐 것    Y1 T 이후 쓸 수 있는 후기의 편차 평균(본문으로 거르지 않음), Y2 T 이후 맛 후기만의 편차 평균
척도      가게 간 스피어만 상관과, 가게를 다시 뽑는 부트스트랩 95% 구간

알려진 누수: 리뷰어 후기 수와 평균은 수집 시점 값이라, T 이전 후기의 편차에도 T 이후 활동이 섞인다.
원평균 별점에는 이 누수가 없다.
"""

import json
import random
import sys
from datetime import datetime
from pathlib import Path
from statistics import mean

import score
from validate import spearman

BASE = Path(__file__).parent
SETS = [
    ("data/reviews.jsonl", "data/labels/claude.jsonl", "data/labels/rules_mapo_v2.jsonl"),
    ("data/reviews_seongsu.jsonl", "data/labels/claude_seongsu.jsonl", "data/labels/rules_seongsu_v2.jsonl"),
]
MIN_PRE = 15
MIN_POST = 8
EXP_RC = 30
BOOT = 2000


def read(path):
    return [json.loads(l) for l in (BASE / path).open(encoding="utf-8")]


def usable(r):
    return r["delta"] is not None and r["others"] < score.CEILING


def avg(xs):
    return mean(xs) if xs else None


def load():
    shops = []
    for rp, cp, vp in SETS:
        claude = {x["review_id"]: x for x in read(cp)}
        rules = {x["review_id"]: x for x in read(vp)}
        by = {}
        for r in read(rp):
            r["claude"], r["rules"] = claude[r["review_id"]], rules[r["review_id"]]
            by.setdefault(r["place_id"], []).append(r)
        shops.extend(by.values())
    return shops


def measure(shops, t):
    rows = []
    for rs in shops:
        pre = [r for r in rs if datetime.fromisoformat(r["registered_at"]) < t]
        post = [r for r in rs if datetime.fromisoformat(r["registered_at"]) >= t and usable(r)]
        pre_clean = [r["delta"] for r in pre if usable(r) and score.is_clean(r["claude"])]
        if len(pre_clean) < MIN_PRE or len(post) < MIN_POST:
            continue
        rows.append({
            "맛 편차 (LLM)": avg(pre_clean),
            "맛 편차 (규칙 v2)": avg([r["delta"] for r in pre if usable(r) and score.is_clean(r["rules"])]),
            "전체 편차": avg([r["delta"] for r in pre if usable(r)]),
            "원평균 별점": avg([r["star"] for r in pre]),
            "경험 많은 손님 편차": avg([r["delta"] for r in pre if usable(r) and r["rc"] >= EXP_RC]),
            "Y1": avg([r["delta"] for r in post]),
            "Y2": avg([r["delta"] for r in post if score.is_clean(r["claude"])]),
        })
    return rows


def rho(rows, x, y, rng=None):
    rs = [r for r in rows if r[x] is not None and r[y] is not None]
    if rng:
        rs = rng.choices(rs, k=len(rs))
    return spearman([r[x] for r in rs], [r[y] for r in rs]), len(rs)


def main(argv):
    t = datetime.fromisoformat(argv[0] if argv else "2025-04-06")
    rows = measure(load(), t)
    print(f"T = {t.date()}, 가게 {len(rows)}곳")
    preds = ["맛 편차 (LLM)", "맛 편차 (규칙 v2)", "전체 편차", "원평균 별점", "경험 많은 손님 편차"]
    for y in ("Y1", "Y2"):
        print(f"\n{y}")
        for x in preds:
            r, n = rho(rows, x, y)
            rng = random.Random(0)
            bs = sorted(rho(rows, x, y, rng)[0] for _ in range(BOOT))
            print(f"  {x:<14} {r:+.2f}  [{bs[int(.025 * BOOT)]:+.2f}, {bs[int(.975 * BOOT) - 1]:+.2f}]  {n}곳")
    # 예측 1: 맛 편차(LLM)와 원평균의 차이, 같은 재표본에서
    rng = random.Random(1)
    both = [r for r in rows if r["Y1"] is not None]
    diffs = []
    for _ in range(BOOT):
        s = rng.choices(both, k=len(both))
        diffs.append(spearman([r["맛 편차 (LLM)"] for r in s], [r["Y1"] for r in s])
                     - spearman([r["원평균 별점"] for r in s], [r["Y1"] for r in s]))
    diffs.sort()
    d0 = rho(rows, "맛 편차 (LLM)", "Y1")[0] - rho(rows, "원평균 별점", "Y1")[0]
    print(f"\n맛 편차(LLM) - 원평균, Y1 상관 차이 {d0:+.2f}  [{diffs[int(.025 * BOOT)]:+.2f}, {diffs[int(.975 * BOOT) - 1]:+.2f}]")


# --- 2차: 서울 고깃집(마포, 성동 제외). 사전 등록 2026-10-06, 수집 전 -------------------------------------
# LLM 레이블 없이 규칙 v2 고정본(커밋 41666b4)만 쓴다. 1차에서 규칙 v2 와 LLM 레이블의 미래 예측력이 같았다.
# 결과(10월 7일): 대상 125곳, H1 H2 H3 모두 서지 않았다(METHOD.md 7절).
#   python3 backtest.py --seoul [T]
SEOUL = ("data/reviews_seoul.jsonl", "data/labels/rules_seoul_v2.jsonl")


def label_seoul():
    out = BASE / SEOUL[1]
    if out.exists():
        return
    sys.path.insert(0, str(BASE / "extension"))
    from gen_rules import load_v2
    v2 = load_v2()
    with out.open("w", encoding="utf-8") as fh:
        for r in read(SEOUL[0]):
            fh.write(json.dumps({"review_id": r["review_id"], **v2.classify(r["text"])}, ensure_ascii=False) + "\n")


def load_seoul():
    label_seoul()
    rules = {x["review_id"]: x for x in read(SEOUL[1])}
    by = {}
    for r in read(SEOUL[0]):
        r["rules"] = rules[r["review_id"]]
        by.setdefault(r["place_id"], []).append(r)
    return list(by.values())


def measure_seoul(shops, t):
    rows = []
    for rs in shops:
        pre = [r for r in rs if datetime.fromisoformat(r["registered_at"]) < t]
        post = [r for r in rs if datetime.fromisoformat(r["registered_at"]) >= t and usable(r)]
        pre_clean = [r["delta"] for r in pre if usable(r) and score.is_clean(r["rules"])]
        if len(pre_clean) < MIN_PRE or len(post) < MIN_POST:
            continue
        exp = [r["delta"] for r in pre if usable(r) and r["rc"] >= EXP_RC]
        rows.append({
            "맛 편차 (규칙 v2)": avg(pre_clean),
            "전체 편차": avg([r["delta"] for r in pre if usable(r)]),
            "원평균 별점": avg([r["star"] for r in pre]),
            "경험 많은 손님 편차": avg(exp) if len(exp) >= 8 else None,
            "Y1": avg([r["delta"] for r in post]),
        })
    return rows


def diff_ci(rows, x, base="원평균 별점", y="Y1"):
    """같은 가게 재표본에서 잰 상관 차이. x 가 정의된 가게만 쓴다."""
    rs = [r for r in rows if r[x] is not None]
    d0 = spearman([r[x] for r in rs], [r[y] for r in rs]) - spearman([r[base] for r in rs], [r[y] for r in rs])
    rng, ds = random.Random(2), []
    for _ in range(BOOT):
        s = rng.choices(rs, k=len(rs))
        ds.append(spearman([r[x] for r in s], [r[y] for r in s]) - spearman([r[base] for r in s], [r[y] for r in s]))
    ds.sort()
    return d0, ds[int(.025 * BOOT)], ds[int(.975 * BOOT) - 1], len(rs)


def main_seoul(argv):
    t = datetime.fromisoformat(argv[0] if argv else "2025-04-06")
    rows = measure_seoul(load_seoul(), t)
    print(f"서울(마포, 성동 제외) T = {t.date()}, 가게 {len(rows)}곳")
    for x in ("맛 편차 (규칙 v2)", "전체 편차", "원평균 별점", "경험 많은 손님 편차"):
        r, n = rho(rows, x, "Y1")
        print(f"  {x:<14} {r:+.2f}  {n}곳")
    for h, x in (("H1", "경험 많은 손님 편차"), ("H2", "전체 편차"), ("H3", "맛 편차 (규칙 v2)")):
        d, lo, hi, n = diff_ci(rows, x)
        print(f"{h} {x} - 원평균: {d:+.2f}  [{lo:+.2f}, {hi:+.2f}]  {n}곳  {'선다' if lo > 0 else '서지 않는다'}")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--seoul"]:
        main_seoul(sys.argv[2:])
    else:
        main(sys.argv[1:])
