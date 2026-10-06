"""도착률 급증 검정. METHOD.md 9절.

가게마다 후기를 주 단위로 센다. 후기가 1건 이상인 주(활동 주)의 중앙값에 MAD 의 세 배를 더한 값을 넘고,
그 주 후기가 5건 이상인 주를 급증 주로 본다.

기준선을 활동 주로만 잡는 이유: 첫 판은 후기가 0건인 주도 넣었는데, 휴업(화재로 6개월 쉰 가게가 있다)이나
개업 전 공백이 0으로 들어가 기준선이 0이 되고, 거의 모든 주가 급증으로 잡혔다. 급증 주의 후기와 나머지 후기를 비교한다.

  별점      원래 별점
  편차      후기 5개 이상 리뷰어의 편차 (본인 평소 대비)
  일회성    후기 1개짜리 계정의 비율

차이의 유의성은 Welch t 통계량을 쓰되, p 값은 t 분포 대신 순열 검정으로 낸다(10,000번 섞기).
표준 라이브러리만 쓰기 위해서이고, 급증 주 표본이 작아 정규 근사를 믿기 어렵기도 하다.

급증은 판정이 아니다. 개업, 방송 출연, 계절, 리뷰 이벤트 모두 급증을 만든다. 이 스크립트는
"그 기간의 후기가 평소와 달랐나"만 말한다.

  python3 burst.py
"""

import json
import random
from collections import defaultdict
from datetime import date
from pathlib import Path
from statistics import mean, median, variance

BASE = Path(__file__).parent
MIN_BURST = 5
PERM = 10000
SEED = 0


def week(ts):
    y, w, _ = date.fromisoformat(ts[:10]).isocalendar()
    return y, w


def welch_t(a, b):
    if len(a) < 2 or len(b) < 2:
        return None
    va, vb = variance(a) / len(a), variance(b) / len(b)
    if va + vb == 0:
        return 0.0
    return (mean(a) - mean(b)) / (va + vb) ** 0.5


def perm_p(a, b, rng, n=PERM):
    """두쪽 순열 검정. 섞어서 나눴을 때 |t| 가 관측값 이상인 비율."""
    t0 = welch_t(a, b)
    if t0 is None:
        return None
    pool, k, hit = a + b, len(a), 0
    for _ in range(n):
        rng.shuffle(pool)
        t = welch_t(pool[:k], pool[k:])
        if t is not None and abs(t) >= abs(t0) - 1e-12:
            hit += 1
    return (hit + 1) / (n + 1)


def bursts(rows):
    counts = defaultdict(int)
    for r in rows:
        counts[week(r["registered_at"])] += 1
    active = list(counts.values())
    med = median(active)
    mad = median(abs(x - med) for x in active)
    threshold = med + 3 * mad
    hot = {w for w, c in counts.items() if c > threshold and c >= MIN_BURST}
    return hot, threshold, len(active)


def main():
    rng = random.Random(SEED)
    by_shop = defaultdict(list)
    for line in (BASE / "data" / "reviews.jsonl").open(encoding="utf-8"):
        r = json.loads(line)
        by_shop[r["shop"]].append(r)

    print(f"{'가게':<20}{'활동주':>5}{'기준':>6}{'급증주':>6}{'급증후기':>8}  {'별점 급증/평시':>16}{'p':>7}  {'편차 급증/평시':>16}{'p':>7}  {'일회성 급증/평시':>14}")
    for shop, rows in sorted(by_shop.items(), key=lambda x: -len(x[1])):
        hot, threshold, n_weeks = bursts(rows)
        inn = [r for r in rows if week(r["registered_at"]) in hot]
        out = [r for r in rows if week(r["registered_at"]) not in hot]
        line = f"{shop:<20}{n_weeks:>5}{threshold:>6.1f}{len(hot):>6}{len(inn):>8}"
        if len(inn) < 2:
            print(line + "  급증 없음")
            continue
        s_in, s_out = [r["star"] for r in inn], [r["star"] for r in out]
        d_in = [r["delta"] for r in inn if r["delta"] is not None]
        d_out = [r["delta"] for r in out if r["delta"] is not None]
        p_s = perm_p(s_in, s_out, rng)
        p_d = perm_p(d_in, d_out, rng) if len(d_in) >= 2 else None
        one_in = sum(1 for r in inn if (r["rc"] or 0) <= 1) / len(inn)
        one_out = sum(1 for r in out if (r["rc"] or 0) <= 1) / len(out)
        dd = f"{mean(d_in):+.2f}/{mean(d_out):+.2f}" if len(d_in) >= 2 else "-"
        print(
            line
            + f"  {mean(s_in):>7.2f}/{mean(s_out):<7.2f}{p_s:>7.3f}"
            + f"  {dd:>16}{(f'{p_d:.3f}' if p_d is not None else '-'):>7}"
            + f"  {one_in:>6.0%}/{one_out:<6.0%}"
        )
        months = sorted({f"{r['registered_at'][:7]}" for r in inn})
        print(f"{'':<20}급증 주가 걸친 달: {', '.join(months[:12])}{' ...' if len(months) > 12 else ''}")


if __name__ == "__main__":
    main()
