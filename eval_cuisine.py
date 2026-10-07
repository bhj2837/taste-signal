"""다른 업종에서 규칙 분류기 v2 를 채점한다. 사전 등록 2026-10-07(레이블 전).

  python3 eval_cuisine.py sample <업종>      본문 있는 후기 300건을 시드로 뽑아 레이블할 목록을 쓴다
  python3 eval_cuisine.py grade <업종>       LLM 레이블과 규칙 v2 를 대어 채점한다
  python3 eval_cuisine.py label <업종>       규칙 v2 로 그 업종 후기 전부에 레이블을 단다(티어표용)

업종은 jp(일식) 또는 cn(중식). 후기는 data/reviews_<업종>.jsonl(normalize.py 로 만든다).
레이블할 목록에는 본문만 있다. 별점, 가게, 분류기 출력은 넣지 않는다.
LLM 레이블은 data/labels/claude_codes_<업종>.txt 에 「번호 코드」 줄로 쌓는다. 코드는 맛, 응대, 웨이팅, 가격, 기타
순서의 다섯 글자이고 + 긍정, - 부정, ~ 엇갈림, . 언급 없음이다(CODEBOOK.md v1).

합격 기준(업종마다): 잘못 걸러짐 15.0퍼센트 이하, 맛 극성 일치 80퍼센트 이상. 둘 다 넘어야 그 업종에서 맛 티어를 쓴다.
규칙은 채점 뒤에 고치지 않는다.
"""

import json
import random
import sys
from pathlib import Path

import score

BASE = Path(__file__).parent
N = 300
SEED = 20261007
CODE = {"+": "pos", "-": "neg", "~": "mixed", ".": "none"}
ASPECTS = ("taste", "service", "wait", "price", "other")
MAX_LOST = 0.15
MIN_AGREE = 0.80


def paths(g):
    return (BASE / "data" / f"reviews_{g}.jsonl", BASE / "data" / "labels" / f"claude_todo_{g}.jsonl",
            BASE / "data" / "labels" / f"claude_codes_{g}.txt")


def sample(g):
    reviews, todo, _ = paths(g)
    rows = [json.loads(l) for l in reviews.open(encoding="utf-8")]
    rows = sorted((r for r in rows if r["text"].strip()), key=lambda r: r["review_id"])
    pick = random.Random(SEED).sample(rows, N)
    with todo.open("w", encoding="utf-8") as fh:
        for r in pick:
            fh.write(json.dumps({"review_id": r["review_id"], "text": r["text"]}, ensure_ascii=False) + "\n")
    print(f"{g}: 본문 있는 후기 {len(rows)}건 중 {N}건 -> {todo}")


def grade(g):
    _, todo, codes = paths(g)
    sys.path.insert(0, str(BASE / "extension"))
    from gen_rules import load_v2
    v2 = load_v2()
    items = [json.loads(l) for l in todo.open(encoding="utf-8")]
    got = [l.split() for l in codes.read_text().splitlines()]
    assert [int(i) for i, _ in got] == list(range(len(items))), "레이블 번호가 이어지지 않는다"
    ref = [dict(zip(ASPECTS, (CODE[c] for c in code))) for _, code in got]
    rule = [v2.classify(x["text"]) for x in items]
    agree = sum(a["taste"] == b["taste"] for a, b in zip(ref, rule)) / len(ref)
    clean = [(a, b) for a, b in zip(ref, rule) if score.is_clean(a)]
    unclean = [(a, b) for a, b in zip(ref, rule) if not score.is_clean(a)]
    lost = sum(not score.is_clean(b) for _, b in clean)
    kept = sum(score.is_clean(b) for _, b in unclean)
    print(f"{g}: {len(ref)}건")
    print(f"  맛 극성 일치   {agree:.1%}  (기준 {MIN_AGREE:.0%} 이상)  {'넘음' if agree >= MIN_AGREE else '못 넘음'}")
    print(f"  잘못 걸러짐    {lost / len(clean):.1%} ({lost}/{len(clean)})  (기준 {MAX_LOST:.0%} 이하)  {'넘음' if lost / len(clean) <= MAX_LOST else '못 넘음'}")
    print(f"  잘못 남김      {kept / len(unclean):.1%} ({kept}/{len(unclean)})  참고")


def label(g):
    reviews, _, _ = paths(g)
    sys.path.insert(0, str(BASE / "extension"))
    from gen_rules import load_v2
    v2 = load_v2()
    out = BASE / "data" / "labels" / f"rules_{g}_v2.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for l in reviews.open(encoding="utf-8"):
            r = json.loads(l)
            fh.write(json.dumps({"review_id": r["review_id"], **v2.classify(r["text"])}, ensure_ascii=False) + "\n")
    print(f"-> {out}")


if __name__ == "__main__":
    {"sample": sample, "grade": grade, "label": label}[sys.argv[1]](sys.argv[2])
