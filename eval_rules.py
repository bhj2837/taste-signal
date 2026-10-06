"""규칙 분류기를 LLM 레이블에 대어 채점한다. METHOD.md 5절 「v2」.

시험용 200건(사람 검수)은 v0, v1 채점에 이미 두 번 썼다. v2 는 가게 단위로 새로 떼어 낸 시험용 가게로 채점한다.
처음 11곳은 v1 을 만들 때 본 가게라 전부 개발용에 둔다. 나머지에서 TEST_SHARE 만큼을 시드로 뽑아 시험용에 둔다.
분할은 data/gold/shop_split.json 에 한 번 쓰고, 이후에는 읽기만 한다.

  python3 eval_rules.py split                 분할을 만든다(이미 있으면 그대로 둔다)
  python3 eval_rules.py dev  <규칙 레이블>     개발용 가게로 채점
  python3 eval_rules.py test <규칙 레이블>     시험용 가게로 채점. 판마다 한 번만 쓴다

기준 레이블은 data/labels/claude.jsonl 이다. 사람이 처음부터 단 정답이 아니라 LLM 레이블이고,
검수로 추정한 오류율은 5퍼센트 안팎이다(METHOD.md 6절).
"""

import json
import random
import sys
from pathlib import Path
from statistics import mean

import score
from validate import spearman

BASE = Path(__file__).parent
SPLIT = BASE / "data" / "gold" / "shop_split.json"
REF = BASE / "data" / "labels" / "claude.jsonl"
SEED = 20261007
TEST_SHARE = 1 / 3
FIRST_ROUND = 11
TOP_SHIFT = 8


def make_split():
    if SPLIT.exists():
        print(f"이미 있다: {SPLIT}")
        return
    shops = {}
    for line in (BASE / "data" / "reviews.jsonl").open(encoding="utf-8"):
        r = json.loads(line)
        shops.setdefault(r["shop"], r["place_id"])
    # 처음 11곳은 원본 파일 이름(<place_id>_<수집 시각>.json)의 수집 시각이 가장 이른 11개다
    raw = sorted((BASE / "data" / "raw").glob("*.json"), key=lambda p: p.stem.split("_")[1])
    first = {p.stem.split("_")[0] for p in raw[:FIRST_ROUND]}
    rest = sorted(s for s, pid in shops.items() if str(pid) not in first)
    rng = random.Random(SEED)
    test = sorted(rng.sample(rest, round(len(rest) * TEST_SHARE)))
    dev = sorted(s for s in shops if s not in test)
    SPLIT.write_text(json.dumps({"seed": SEED, "dev": dev, "test": test}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"개발용 {len(dev)}곳, 시험용 {len(test)}곳 -> {SPLIT}")


def plain(rows):
    xs = [r["delta"] for r in rows if r["delta"] is not None and r["others"] < score.CEILING]
    return mean(xs) if xs else None


def grade(part, rules_path):
    split = json.loads(SPLIT.read_text(encoding="utf-8"))
    shops = set(split[part])
    ref = {s: rows for s, rows in score.load(REF).items() if s in shops}
    got = {s: rows for s, rows in score.load(Path(rules_path)).items() if s in shops}

    rows = [r for rs in ref.values() for r in rs if r["text"].strip()]
    lab = {r["review_id"]: r["label"] for rs in got.values() for r in rs}
    clean = [r for r in rows if score.is_clean(r["label"])]
    unclean = [r for r in rows if not score.is_clean(r["label"])]
    lost = sum(not score.is_clean(lab[r["review_id"]]) for r in clean)
    kept = sum(score.is_clean(lab[r["review_id"]]) for r in unclean)
    agree = sum(lab[r["review_id"]]["taste"] == r["label"]["taste"] for r in rows)

    rc = {s: score.summarize(r, random.Random(0)) for s, r in ref.items()}
    rg = {s: score.summarize(r, random.Random(0)) for s, r in got.items()}
    both = [s for s in shops if not rc[s]["hold"] and not rg[s]["hold"]]
    rho = spearman([rc[s]["taste_delta"] for s in both], [rg[s]["taste_delta"] for s in both]) if len(both) > 2 else None
    shifted = sorted((s for s in both if plain(ref[s]) is not None),
                     key=lambda s: -(rc[s]["taste_delta"] - plain(ref[s])))[:TOP_SHIFT]
    err = mean(abs(rc[s]["taste_delta"] - rg[s]["taste_delta"]) for s in shifted) if shifted else None
    err0 = mean(abs(rc[s]["taste_delta"] - plain(ref[s])) for s in shifted) if shifted else None

    print(f"{part}: 가게 {len(shops)}곳, 본문 {len(rows)}건")
    print(f"  맛 극성 일치          {agree / len(rows):.0%}")
    print(f"  잘못 걸러짐           {lost / len(clean):.1%}  ({lost}/{len(clean)})")
    print(f"  잘못 남김             {kept / len(unclean):.1%}  ({kept}/{len(unclean)})")
    print(f"  가게 순위상관          {rho:.2f}  (둘 다 보류 아닌 {len(both)}곳)" if rho is not None else "  가게 순위상관  -")
    if err is not None:
        print(f"  거르기 효과 큰 {len(shifted)}곳 평균 오차  {err:.2f}  (거르지 않으면 {err0:.2f})")


def main(argv):
    if argv[:1] == ["split"]:
        make_split()
    elif len(argv) == 2 and argv[0] in ("dev", "test"):
        grade(argv[0], argv[1])
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
