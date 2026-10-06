"""data/raw/*.json -> data/reviews.jsonl

후기 한 줄에 한 객체. 같은 가게를 여러 번 수집했으면 가장 최근 스냅샷만 쓴다.

파생 값
  others    이 후기를 뺀 리뷰어 본인 평균. 후기 2개 이상일 때만
  delta     star - others, -4 에서 +4 로 자른다. 후기 5개 이상일 때만 (metrics.loo_delta 와 같은 규칙)
  headroom  5 - others. 평소 후한 리뷰어일수록 작다. 천장 때문에 편차가 눌린 정도를 읽는 데 쓴다
  edited    updated_at 이 registered_at 과 다르면 수정된 후기

rc 와 avg 는 수집 시점의 값이다. 후기를 쓴 시점의 값이 아니다.
"""

import json
from pathlib import Path

BASE = Path(__file__).parent
RAW = BASE / "data" / "raw"
OUT = BASE / "data" / "reviews.jsonl"
MIN_COUNT = 5


def latest_snapshots():
    by_place = {}
    for path in sorted(RAW.glob("*_*.json")):
        place_id = path.name.split("_")[0]
        by_place[place_id] = path  # 파일 이름의 시각 순으로 정렬되어 있어 마지막이 최신
    return [json.loads(p.read_text(encoding="utf-8")) for p in by_place.values()]


def derive(r):
    rc, avg, star = r["rc"], r["avg"], r["star"]
    others = (avg * rc - star) / (rc - 1) if rc and rc >= 2 and avg is not None else None
    delta = None
    if others is not None and rc >= MIN_COUNT:
        delta = max(-4.0, min(4.0, star - others))
    return {
        "others": round(others, 4) if others is not None else None,
        "delta": round(delta, 4) if delta is not None else None,
        "headroom": round(5 - others, 4) if others is not None else None,
        "edited": r["updated_at"] != r["registered_at"],
    }


def main():
    snaps = latest_snapshots()
    n = 0
    with OUT.open("w", encoding="utf-8") as fh:
        for snap in snaps:
            for r in snap["reviews"]:
                row = {
                    "review_id": r["review_id"],
                    "place_id": snap["place_id"],
                    "shop": snap["shop"],
                    "collected_at": snap["collected_at"],
                    **{k: r[k] for k in ("star", "text", "registered_at", "tags", "rc", "avg", "reviewer_key")},
                    **derive(r),
                }
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                n += 1
    print(f"{n} reviews / {len(snaps)} shops -> {OUT}")


if __name__ == "__main__":
    main()
