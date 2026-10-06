"""Claude 레이블 검수 페이지를 만든다 -> data/review/review.html (로컬 전용, 본문 포함)

맛 극성을 일부러 틀리게 바꾼 함정 항목을 섞는다. 검수자가 그중 몇 개를 잡는지가
「검수가 실제로 오류를 잡았다」는 근거가 된다. 함정 목록은 data/gold/decoys.json.
함정의 위치는 출력하지 않는다.

  python3 review_page.py <시드>
"""

import html
import json
import random
import sys
from pathlib import Path

BASE = Path(__file__).parent
GOLD = BASE / "data" / "gold"
OUT = BASE / "data" / "review" / "review.html"
N_DECOY = 15
A = ("taste", "service", "wait", "price", "other")
KO = ("맛", "응대", "웨이팅", "가격", "기타")
SYM = {"pos": "+", "neg": "−", "mixed": "~", "none": ""}
FLIP = {"pos": "neg", "neg": "pos", "mixed": "pos", "none": "neg"}

CSS = """
:root{--bg:#fff;--fg:#1a1a1a;--mute:#666;--line:#e3e3e3;--pos:#1a7f37;--neg:#c4302b;--mix:#9a6700;--card:#fafafa}
@media (prefers-color-scheme:dark){:root{--bg:#151515;--fg:#eee;--mute:#999;--line:#333;--pos:#4ac26b;--neg:#ff6b61;--mix:#d4a72c;--card:#1d1d1d}}
body{background:var(--bg);color:var(--fg);font:15px/1.6 -apple-system,"Apple SD Gothic Neo",sans-serif;margin:0 auto;max-width:860px;padding:0 16px 120px}
header{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);padding:12px 0;z-index:2}
h1{font-size:18px;margin:4px 0}.guide{color:var(--mute);font-size:13px}
.item{border:1px solid var(--line);background:var(--card);border-radius:8px;padding:12px 14px;margin:12px 0}
.item.flag{border-color:var(--neg);box-shadow:0 0 0 1px var(--neg)}
.head{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.chip{border:1px solid var(--line);border-radius:12px;padding:0 9px;font-size:13px}.chip.taste{font-weight:700;font-size:14px}
.chip.pos{color:var(--pos);border-color:var(--pos)}.chip.neg{color:var(--neg);border-color:var(--neg)}
.chip.mixed{color:var(--mix);border-color:var(--mix)}.chip.none{color:var(--mute)}
.note{color:var(--mute);font-size:12px;margin-top:4px}.text{margin:8px 0}
.wrong{font-size:13px;margin-right:8px}
.fix{width:min(420px,90%);font-size:13px;padding:3px 6px;background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:4px}
footer{position:fixed;bottom:0;left:0;right:0;background:var(--bg);border-top:1px solid var(--line);padding:8px 16px}
footer textarea{width:100%;max-width:860px;height:56px;font-size:12px;background:var(--card);color:var(--fg);border:1px solid var(--line)}
"""

JS = """
const KEY="taste-signal-review-"+document.body.dataset.seed;let st={};
try{st=JSON.parse(localStorage.getItem(KEY)||"{}")}catch(e){}
const items=[...document.querySelectorAll(".item")];
function save(){try{localStorage.setItem(KEY,JSON.stringify(st))}catch(e){};render()}
function render(){const f=items.filter(i=>st[i.dataset.key]?.w);
 document.getElementById("count").textContent=` 체크 ${f.length}건`;
 document.getElementById("out").value=f.map(i=>i.dataset.key+(st[i.dataset.key].fix?" "+st[i.dataset.key].fix:"")).join("\\n");
 const v=document.getElementById("view").value;
 items.forEach(i=>{const w=!!st[i.dataset.key]?.w;i.classList.toggle("flag",w);
  i.style.display=(v=="all"||(v=="note"&&i.dataset.note=="1")||(v=="flag"&&w))?"":"none"})}
items.forEach(i=>{const k=i.dataset.key,cb=i.querySelector("input[type=checkbox]"),fx=i.querySelector(".fix");
 const s=st[k]||{};cb.checked=!!s.w;fx.value=s.fix||"";
 cb.onchange=()=>{st[k]={...(st[k]||{}),w:cb.checked};save()};
 fx.oninput=()=>{st[k]={...(st[k]||{}),fix:fx.value,w:true};cb.checked=true;save()}});
document.getElementById("view").onchange=render;
document.getElementById("copy").onclick=()=>{const t=document.getElementById("out");t.select();
 try{navigator.clipboard.writeText(t.value)}catch(e){document.execCommand("copy")}};
render();
"""


def load(path):
    return [json.loads(l) for l in path.open(encoding="utf-8") if l.strip()]


def chips(lab):
    out = [
        f'<span class="chip {lab[a]}{" taste" if a == "taste" else ""}">{ko} {SYM[lab[a]]}</span>'
        for a, ko in zip(A, KO)
        if lab[a] != "none"
    ]
    if lab["taste"] == "none":
        out.append('<span class="chip none">맛 언급 없음</span>')
    return "".join(out)


def main(seed):
    items = []
    for split, prefix in (("dev", "D"), ("test", "T")):
        for i, (t, l) in enumerate(zip(load(GOLD / f"{split}.jsonl"), load(GOLD / f"claude_{split}.jsonl")), 1):
            assert t["review_id"] == l["review_id"]
            items.append({"key": f"{prefix}{i:03d}", "rid": t["review_id"], "text": t["text"],
                          "lab": {a: l[a] for a in A}, "note": l["note"]})
    rng = random.Random(seed)
    log = []
    for k in rng.sample(range(len(items)), N_DECOY):
        it = items[k]
        log.append({"key": it["key"], "review_id": it["rid"], "true_taste": it["lab"]["taste"]})
        it["lab"]["taste"] = FLIP[it["lab"]["taste"]]
        it["note"] = ""
    (GOLD / "decoys.json").write_text(json.dumps({"seed": seed, "decoys": log}, ensure_ascii=False, indent=1))

    rows = []
    for it in items:
        note = f'<div class="note">메모: {html.escape(it["note"])}</div>' if it["note"] else ""
        rows.append(
            f'<div class="item" data-key="{it["key"]}" data-note="{1 if it["note"] else 0}">'
            f'<div class="head"><b>{it["key"]}</b> {chips(it["lab"])}</div>{note}'
            f'<div class="text">{html.escape(it["text"]).replace(chr(10), "<br>")}</div>'
            '<label class="wrong"><input type="checkbox"> 이건 아니다</label>'
            '<input class="fix" placeholder="맞는 판정이나 이유 (선택)"></div>'
        )
    page = (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"><title>레이블 검수</title>'
        f"<style>{CSS}</style></head><body data-seed=\"{seed}\">"
        '<header><h1>측면 레이블 검수 300건</h1><div class="guide">'
        "+ 긍정, − 부정, ~ 엇갈림(또는 무난함). 굵은 칩이 맛이다. <b>맛이 맞는지가 제일 중요하다.</b> "
        "틀린 것만 「이건 아니다」를 체크한다. 맞는 판정은 적지 않아도 된다. "
        f"일부러 틀리게 바꾼 항목이 {N_DECOY}개 섞여 있다. 체크는 이 브라우저에 저장된다.</div>"
        '<div style="margin-top:6px"><select id="view"><option value="all">전체</option>'
        '<option value="note">메모 있는 것만 (Claude 가 애매했던 것)</option>'
        '<option value="flag">체크한 것만</option></select><span id="count"></span></div></header>'
        + "".join(rows)
        + '<footer><button id="copy">결과 복사</button> <span class="guide">이 칸의 내용을 대화창에 붙여 주면 된다</span>'
        '<textarea id="out" readonly></textarea></footer>'
        f"<script>{JS}</script></body></html>"
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding="utf-8")
    print(f"{len(items)}건, 함정 {N_DECOY}건 -> {OUT}")


if __name__ == "__main__":
    main(int(sys.argv[1]))
