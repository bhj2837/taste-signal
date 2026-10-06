"""분류기를 손 레이블로 채점한다. METHOD.md 6절.

  python3 grade.py dev                         규칙 분류기를 개발용으로
  python3 grade.py test data/labels/llm.jsonl  다른 분류기를 시험용으로
  python3 grade.py recheck                     자기 일치도 (코헨 카파)

시험용은 분류기 판마다 한 번만 채점한다. 결과를 보고 규칙을 고치면 시험용이 개발용이 된다.
"""

import json
import sys
from collections import Counter
from pathlib import Path

BASE = Path(__file__).parent
GOLD = BASE / "data" / "gold"
ASPECTS = ("taste", "service", "wait", "price", "other")
CLASSES = ("pos", "neg", "mixed", "none")


def load(path):
    return {json.loads(l)["review_id"]: json.loads(l) for l in path.open(encoding="utf-8") if l.strip()}


def macro_f1(gold, pred):
    """gold 나 pred 에 한 번이라도 나온 클래스만 평균한다."""
    f1s = []
    for c in CLASSES:
        tp = sum(1 for g, p in zip(gold, pred) if g == c and p == c)
        fp = sum(1 for g, p in zip(gold, pred) if g != c and p == c)
        fn = sum(1 for g, p in zip(gold, pred) if g == c and p != c)
        if tp + fp + fn == 0:
            continue
        f1s.append(2 * tp / (2 * tp + fp + fn))
    return sum(f1s) / len(f1s) if f1s else None


def kappa(a, b):
    n = len(a)
    if n == 0:
        return None
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[c] * cb[c] for c in set(a) | set(b)) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def grade(split, pred_path):
    gold = load(GOLD / f"labels_{split}.jsonl")
    pred = load(pred_path)
    reviews = load(BASE / "data" / "reviews.jsonl")
    ids = sorted(gold)
    print(f"{split} {len(ids)}건 / 분류기 {pred_path.name}\n")
    print(f"{'측면':<8}{'정확도':>8}{'매크로F1':>10}")
    for a in ASPECTS:
        g = [gold[i][a] for i in ids]
        p = [pred[i][a] for i in ids]
        acc = sum(1 for x, y in zip(g, p) if x == y) / len(ids)
        print(f"{a:<8}{acc:>8.0%}{macro_f1(g, p):>10.2f}")

    low_taste = [i for i in ids if gold[i]["taste"] != "none" and (reviews[i]["delta"] or 0) < 0]
    wrong_drop = [i for i in low_taste if pred[i]["taste"] == "none"]
    no_taste = [i for i in ids if gold[i]["taste"] == "none"]
    wrong_keep = [i for i in no_taste if pred[i]["taste"] != "none"]
    print(f"\n잘못 걸러짐  {len(wrong_drop)}/{len(low_taste)}"
          + (f" = {len(wrong_drop) / len(low_taste):.0%}" if low_taste else "") + "   (기준 10% 이하)")
    print(f"잘못 남김    {len(wrong_keep)}/{len(no_taste)}"
          + (f" = {len(wrong_keep) / len(no_taste):.0%}" if no_taste else ""))

    tagged = [i for i, r in reviews.items() if "맛" in r["tags"] and r["text"].strip()]
    agree = [i for i in tagged if pred[i]["taste"] in ("pos", "mixed")]
    print(f"태그 일치    {len(agree)}/{len(tagged)} = {len(agree) / len(tagged):.0%}   (맛 태그가 붙은 본문 후기 전체, 손 레이블 무관)")

    print("\n맛 혼동표 (행 정답, 열 분류기)")
    print(" " * 8 + "".join(f"{c:>7}" for c in CLASSES))
    for gc in CLASSES:
        row = [sum(1 for i in ids if gold[i]["taste"] == gc and pred[i]["taste"] == pc) for pc in CLASSES]
        print(f"{gc:<8}" + "".join(f"{x:>7}" for x in row))


def recheck():
    again = load(GOLD / "labels_recheck.jsonl")
    first = {}
    for split in ("dev", "test"):
        path = GOLD / f"labels_{split}.jsonl"
        if path.exists():
            first.update(load(path))
    ids = sorted(i for i in again if i in first)
    print(f"자기 일치도 {len(ids)}건\n")
    for a in ASPECTS:
        k = kappa([first[i][a] for i in ids], [again[i][a] for i in ids])
        print(f"{a:<8} 카파 {k:.2f}" if k is not None else f"{a:<8} -")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] not in ("dev", "test", "recheck"):
        raise SystemExit(__doc__)
    if args[0] == "recheck":
        recheck()
    else:
        grade(args[0], Path(args[1]) if len(args) > 1 else BASE / "data" / "labels" / "rules.jsonl")
