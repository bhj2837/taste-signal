"""규칙 분류기 v2 의 정규식을 확장용 JS 로 옮긴다. 손으로 옮겨 적지 않으려고 만든 스크립트다.

  python3 extension/gen_rules.py   ->  extension/rules_v2.js

확장은 v3 가 아니라 v2 를 쓴다(METHOD.md 5절). v2 고정본은 커밋 41666b4 의 label_rules.py 이고,
sha1 이 맞지 않으면 멈춘다.
"""

import hashlib
import importlib.util
import json
import subprocess
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
COMMIT = "41666b4"
SHA1 = "7d4944497d5beea2de79faab1218845e764c2662"
OUT = BASE / "extension" / "rules_v2.js"


def load_v2():
    src = subprocess.run(["git", "-C", str(BASE), "show", f"{COMMIT}:label_rules.py"],
                         capture_output=True, check=True).stdout
    assert hashlib.sha1(src).hexdigest() == SHA1, "v2 고정본이 아니다"
    with tempfile.NamedTemporaryFile("wb", suffix=".py", delete=False) as fh:
        fh.write(src)
    spec = importlib.util.spec_from_file_location("label_rules_v2", fh.name)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    m = load_v2()
    rules = {
        "split": m.SPLIT.pattern,
        "hedge": m.HEDGE.pattern,
        "override": [[a, p, rx] for a, p, rx in m.OVERRIDE],
        "polar": [[a, p, rx] for a, p, rx in m.POLAR],
        "mention": [[a, rx] for a, rx in m.MENTION],
        "generic": [[p, rx] for p, rx in m.GENERIC],
    }
    body = json.dumps(rules, ensure_ascii=False, indent=1)
    OUT.write_text(
        "// 생성 파일. 고치지 말 것. python3 extension/gen_rules.py 로 다시 만든다.\n"
        f"// 출처: label_rules.py v2 (커밋 {COMMIT}, sha1 {SHA1})\n"
        f"export const RULES = {body};\n",
        encoding="utf-8",
    )
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
