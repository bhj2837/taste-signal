"""규칙 분류기 v0. CODEBOOK.md 만 보고 만들었다. 실제 후기로 고치기 전이다.

후기를 절로 나눈 뒤, 절마다 다음 순서로 본다.
  1. 덮어쓰기 규칙   "가격 대비 품질이 별로" 처럼 코드북이 따로 판정한 표현
  2. 극성을 품은 단서  "맛있", "불친절", "비싸" 처럼 측면과 극성을 함께 정하는 표현
  3. 측면만 정하는 단서 "직원", "웨이팅", "분위기"
  4. 일반 극성 단서    "좋", "별로", "최고". 그 절에서 언급된 측면에 붙는다.
                    언급된 측면이 없으면 맛에 붙는다(코드북 2절 규칙 2)
매칭된 구간은 지운 뒤 다음 단계로 넘어간다. "불친절" 이 "친절" 로 다시 잡히지 않게 하려는 것이다.

한 측면에 긍정과 부정이 함께 나오거나 중립 표현이 나오면 엇갈림이다.

실행: python3 label_rules.py  ->  data/labels/rules.jsonl
"""

import json
import re
from pathlib import Path

ASPECTS = ("taste", "service", "wait", "price", "other")

SPLIT = re.compile(r"\n+|[.!?~]+|는데|은데|지만|다만|근데|그런데|하지만|그러나|,")

# 1. 덮어쓰기: (측면, 극성, 정규식)
OVERRIDE = [
    ("taste", "neg", r"가격\s*대비\s*(품질|맛|퀄리티|고기)?\s*(이|가|은|는)?\s*(별로|그닥|떨어|아쉽|글쎄|모르)"),
    ("taste", "neg", r"(품질|퀄리티)\s*(이|가|은|는)?\s*(가격|값)\s*(에)?\s*(비해|대비)\s*(별로|떨어|아쉽)"),
    ("taste", "neg", r"(웨이팅|기다|줄\s*서).{0,10}(만큼|정도)[은는]?\s*(아니|아님|아닌|모르)"),
    ("taste", "pos", r"(기다린|웨이팅한|줄\s*선)\s*보람"),
    ("price", "pos", r"가격\s*대비\s*(괜찮|좋|훌륭|만족|최고|굿)"),
]

# 2. 극성을 품은 단서. 부정을 먼저 둔다
POLAR = [
    ("taste", "neg", r"맛\s*(이|은|도)?\s*없|맛없|안\s*맛있|맛있지\s*않|맛있진\s*않|맛\s*(이|은)?\s*(별로|그닥|떨어)|"
                     r"질기|질겼|퍽퍽|느끼|잡내|누린내|비린|싱거|싱겁|(?<!진)짜(요|다|고|서|네|더|웠|운|ㅠ)|짰|"
                     r"비계\s*(만|가\s*많|덩어리|투성)|딱딱"),
    ("taste", "pos", r"맛있|맛나|존맛|꿀맛|JMT|jmt|맛집|부드럽|부드러|쫄깃|쫀득|고소|담백|육즙|신선|감칠맛"),
    ("taste", "mixed", r"먹을\s*만|평범한\s*맛|맛\s*(은|이)?\s*(무난|평범|보통)"),
    ("service", "neg", r"불친절|불쾌|퉁명|쾅쾅|무시|짜증|싸가지|알아서\s*구워|구워\s*주지\s*않|안\s*구워|늦게\s*나|매너\s*(가\s*)?(없|별로|꽝)"),
    ("service", "pos", r"친절|구워\s*주|구워주|챙겨\s*주|서비스\s*(로|도)?\s*(주|줬|준|챙)"),
    ("wait", "neg", r"(웨이팅|대기|기다|줄)\s*(이|가|은|도)?\s*.{0,6}(길|오래|힘들|너무|엄청|한\s*시간|시간\s*넘|지옥)"),
    ("wait", "pos", r"(웨이팅|대기)\s*(없|짧|금방)|바로\s*(입장|들어)|예약\s*(이|하면)?\s*편"),
    ("price", "neg", r"비싸|비쌈|비쌌|비싼|사악|양\s*(이|은|도)?\s*(적|작|부족)|가성비\s*(가|는|도)?\s*(별로|안|떨어|나쁘|꽝)"),
    ("price", "pos", r"저렴|착한\s*가격|가성비\s*(가|는|도)?\s*(좋|최고|굿|짱|갑|훌륭)|가성비갑|푸짐|양\s*(이|도)?\s*(많|넉넉)|(?<!비)싸(고|요|서|다)|(?<!비)싼\s"),
    ("other", "neg", r"더럽|지저분|시끄|좁|냄새\s*(가|가\s*옷에)?\s*(배|밴|베)|연기|환기\s*(가|가\s*안)?\s*(안|별로)|주차\s*(가|는)?\s*(어렵|불편|안\s*됨|불가)"),
    ("other", "pos", r"분위기\s*(가|도|는)?\s*(좋|최고|굿|짱|예쁘|이쁘)|깨끗|청결|쾌적|넓|주차\s*(가|도)?\s*(편|가능|돼)"),
]

# 3. 측면만 정하는 단서
MENTION = [
    ("taste", r"맛|고기|목살|삼겹|항정|갈비|부위|찌개|된장|냉면|볶음밥|반찬|김치|소스|쌈|숙성|식감|품질|퀄리티|음식"),
    ("service", r"직원|사장|알바|응대|서비스|태도|설명|서빙|주문|매너"),
    ("wait", r"웨이팅|대기|오픈런|예약|회전|줄\s*서"),
    ("price", r"가격|가성비|양이|양은|양도|중량|인분|그램"),
    ("other", r"분위기|인테리어|위생|청결|주차|소음|좌석|자리|환기|화장실|위치|테라스|냄새"),
]

# 4. 일반 극성. 중립을 먼저, 그다음 부정, 마지막 긍정
GENERIC = [
    ("mixed", r"나쁘지\s*않|나쁘진\s*않|나쁘지는\s*않|무난|평범|그럭저럭|쏘쏘|보통"),
    ("neg", r"안\s*좋|좋지\s*않|좋진\s*않|별로|최악|실망|아쉽|아쉬|비추|다시는|안\s*갈|그닥|글쎄|후회"),
    ("pos", r"좋|최고|굿|대박|짱|훌륭|만족|추천|감동|강추|미쳤|재방문|또\s*(오|올|갈|방문|가고)|자주\s*(와|가|옵)"),
]

COMPILED = {
    "override": [(a, p, re.compile(rx)) for a, p, rx in OVERRIDE],
    "polar": [(a, p, re.compile(rx)) for a, p, rx in POLAR],
    "mention": [(a, re.compile(rx)) for a, rx in MENTION],
    "generic": [(p, re.compile(rx)) for p, rx in GENERIC],
}


def _take(rx, text):
    """매칭이 있으면 그 구간을 공백으로 지운 문자열과 True 를 돌려준다."""
    if rx.search(text):
        return rx.sub(" ", text), True
    return text, False


def classify_clause(clause):
    found = []  # (측면, 극성)
    text = clause
    for aspect, pol, rx in COMPILED["override"]:
        text, hit = _take(rx, text)
        if hit:
            found.append((aspect, pol))
    for aspect, pol, rx in COMPILED["polar"]:
        text, hit = _take(rx, text)
        if hit:
            found.append((aspect, pol))
    mentioned = {aspect for aspect, rx in COMPILED["mention"] if rx.search(text)}
    generic = []
    for pol, rx in COMPILED["generic"]:
        text, hit = _take(rx, text)
        if hit:
            generic.append(pol)
    polar_aspects = {a for a, _ in found}
    targets = mentioned - polar_aspects
    if generic:
        if not targets and not found:
            targets = {"taste"}
        for aspect in targets:
            for pol in generic:
                found.append((aspect, pol))
    return found


def merge(pols):
    if not pols:
        return "none"
    if "mixed" in pols or ("pos" in pols and "neg" in pols):
        return "mixed"
    return pols.pop() if len(pols) == 1 else "mixed"


def classify(text):
    per = {a: set() for a in ASPECTS}
    for clause in SPLIT.split(text or ""):
        if clause.strip():
            for aspect, pol in classify_clause(clause):
                per[aspect].add(pol)
    return {a: merge(per[a]) for a in ASPECTS}


def main():
    base = Path(__file__).parent
    src = base / "data" / "reviews.jsonl"
    out = base / "data" / "labels" / "rules.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with out.open("w", encoding="utf-8") as fh:
        for line in src.open(encoding="utf-8"):
            r = json.loads(line)
            fh.write(json.dumps({"review_id": r["review_id"], **classify(r["text"])}, ensure_ascii=False) + "\n")
            n += 1
    print(f"{n} reviews -> {out}")


if __name__ == "__main__":
    main()
