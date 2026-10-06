"""손 레이블 도구. 터미널에서 후기를 하나씩 보여 주고 측면 극성을 입력받는다.

  python3 label_tool.py dev        개발용 100건
  python3 label_tool.py test       시험용 200건 (코드북을 고정한 뒤에)
  python3 label_tool.py recheck    자기 일치도용 50건 (첫 레이블에서 일주일 뒤)

별점, 가게, 태그는 보여 주지 않는다. 코드북 2절 규칙 3.
입력은 다섯 글자, 측면 순서는 맛 응대 웨이팅 가격 기타. 공백 뒤는 메모.
  + 긍정   - 부정   ~ 엇갈림   . 언급 없음
명령: ? 도움말   b 직전 것 지우고 다시   q 저장하고 끝내기

한 건 입력할 때마다 바로 저장한다. 끝낸 자리에서 다시 시작한다.
"""

import json
import sys
import textwrap
from datetime import datetime
from pathlib import Path

ASPECTS = ("taste", "service", "wait", "price", "other")
NAMES = ("맛", "응대", "웨이팅", "가격", "기타")
CODES = {"+": "pos", "-": "neg", "~": "mixed", ".": "none"}
HELP = """
  다섯 글자: 맛 응대 웨이팅 가격 기타 순서
  + 긍정   - 부정   ~ 엇갈림(또는 무난함)   . 언급 없음
  예) +-...   맛 긍정, 응대 부정
      -..-. 대상불명    공백 뒤는 메모
  경계: 가격 대비 품질은 맛 / 양은 가격 / 앉은 뒤 음식 기다림은 응대
  b 직전 것 지우기   q 끝내기   자세한 기준은 CODEBOOK.md
"""


def parse(line):
    code, _, note = line.strip().partition(" ")
    if len(code) != 5 or any(c not in CODES for c in code):
        return None
    label = {a: CODES[c] for a, c in zip(ASPECTS, code)}
    label["note"] = note.strip()
    return label


def load_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def save_jsonl(path, items):
    with path.open("w", encoding="utf-8") as fh:
        for it in items:
            fh.write(json.dumps(it, ensure_ascii=False) + "\n")


def show(i, total, text):
    print("\n" + "=" * 60)
    print(f"[{i}/{total}]")
    for para in text.splitlines() or [""]:
        print(textwrap.fill(para, width=58) if para.strip() else "")
    print("-" * 60)


def run(split, gold_dir, stdin=sys.stdin):
    items = load_jsonl(gold_dir / f"{split}.jsonl")
    if not items:
        raise SystemExit(f"{gold_dir / (split + '.jsonl')} 이 없다. sample_gold.py 를 먼저 돌린다")
    out_path = gold_dir / f"labels_{split}.jsonl"
    labels = load_jsonl(out_path)
    done = {l["review_id"] for l in labels}
    print(f"{split}: {len(done)}/{len(items)} 완료. ? 도움말")

    queue = [it for it in items if it["review_id"] not in done]
    i = 0
    while i < len(queue):
        it = queue[i]
        show(len(labels) + 1, len(items), it["text"])
        print("맛 응대 웨이팅 가격 기타 > ", end="", flush=True)
        line = stdin.readline()
        if not line:  # 입력 끝
            break
        cmd = line.strip()
        if cmd == "q":
            break
        if cmd == "?":
            print(HELP)
            continue
        if cmd == "b":
            if labels:
                last = labels.pop()
                save_jsonl(out_path, labels)
                prev = next(x for x in items if x["review_id"] == last["review_id"])
                queue.insert(i, prev)
                print("직전 레이블을 지웠다")
            continue
        label = parse(cmd)
        if label is None:
            print("다섯 글자(+ - ~ .)로 입력한다. ? 도움말")
            continue
        labels.append({"review_id": it["review_id"], **label, "labeled_at": datetime.now().isoformat(timespec="seconds")})
        save_jsonl(out_path, labels)
        i += 1
    print(f"\n{split}: {len(labels)}/{len(items)} 저장 -> {out_path}")
    return labels


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("dev", "test", "recheck"):
        raise SystemExit(__doc__)
    run(sys.argv[1], Path(__file__).parent / "data" / "gold")
