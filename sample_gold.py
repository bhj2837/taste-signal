"""손 레이블용 표본 300건을 뽑아 개발용 100건과 시험용 200건으로 나눈다.

- 본문이 있는 후기만
- 별점 3 이하 180건, 4 이상 120건. 걸러 내는 판단이 낮은 별점에서 일어나서 과대 표집한다
- 별점 4 이상은 가게마다 고르게 뽑는다. 그냥 뽑으면 후기가 가장 많은 한 가게가 절반을 넘는다
- 개발용과 시험용은 별점 구간 비율을 같게 나눈다
- 자기 일치도용 50건(개발용 25, 시험용 25)을 따로 표시한다
- 시드를 고정했다. 같은 reviews.jsonl 이면 같은 표본이 나온다

출력: data/gold/dev.jsonl, data/gold/test.jsonl, data/gold/recheck.jsonl (review_id 와 본문만. 별점과 가게는 넣지 않는다)
"""

import json
import random
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).parent
SRC = BASE / "data" / "reviews.jsonl"
OUT = BASE / "data" / "gold"
SEED = 20261006
LOW, HIGH = 180, 120
DEV_LOW, DEV_HIGH = 60, 40
RECHECK_PER_SPLIT = 25


def even_by_shop(rows, k, rng):
    """가게별로 돌아가며 하나씩 뽑는다. 다 쓴 가게는 건너뛴다."""
    pools = defaultdict(list)
    for r in rows:
        pools[r["shop"]].append(r)
    for pool in pools.values():
        rng.shuffle(pool)
    shops = sorted(pools)
    out = []
    while len(out) < k and any(pools.values()):
        for s in shops:
            if pools[s] and len(out) < k:
                out.append(pools[s].pop())
    return out


def main():
    rng = random.Random(SEED)
    rows = [json.loads(line) for line in SRC.open(encoding="utf-8")]
    rows = [r for r in rows if r["text"].strip()]
    low = [r for r in rows if r["star"] <= 3]
    high = [r for r in rows if r["star"] >= 4]
    if len(low) < LOW:
        raise SystemExit(f"별점 3 이하 본문 후기가 {len(low)}건뿐이다. {LOW}건이 필요하다")

    low = sorted(low, key=lambda r: r["review_id"])
    rng.shuffle(low)
    low = low[:LOW]
    high = even_by_shop(sorted(high, key=lambda r: r["review_id"]), HIGH, rng)

    dev = low[:DEV_LOW] + high[:DEV_HIGH]
    test = low[DEV_LOW:] + high[DEV_HIGH:]
    rng.shuffle(dev)
    rng.shuffle(test)
    recheck = rng.sample(dev, RECHECK_PER_SPLIT) + rng.sample(test, RECHECK_PER_SPLIT)
    rng.shuffle(recheck)

    OUT.mkdir(parents=True, exist_ok=True)
    for name, items in (("dev", dev), ("test", test), ("recheck", recheck)):
        with (OUT / f"{name}.jsonl").open("w", encoding="utf-8") as fh:
            for r in items:
                fh.write(json.dumps({"review_id": r["review_id"], "text": r["text"]}, ensure_ascii=False) + "\n")

    shops = defaultdict(int)
    for r in dev + test:
        shops[r["shop"]] += 1
    print(f"dev {len(dev)} / test {len(test)} / recheck {len(recheck)} -> {OUT}")
    print("가게별:", ", ".join(f"{s} {n}" for s, n in sorted(shops.items(), key=lambda x: -x[1])))


if __name__ == "__main__":
    main()
