"""규칙 분류기 v1. v0 은 CODEBOOK.md 만 보고 만들었고, v1 은 개발용 100건의 오류만 보고 고쳤다.
시험용 200건은 판마다 한 번만 채점한다(grade.py).

후기를 절로 나눈 뒤, 절마다 다음 순서로 본다.
  1. 덮어쓰기 규칙   "가격 대비 품질이 별로" 처럼 코드북이 따로 판정한 표현
  2. 극성을 품은 단서  "맛있", "불친절", "비싸" 처럼 측면과 극성을 함께 정하는 표현
  3. 측면만 정하는 단서 "직원", "웨이팅", "분위기"
  4. 일반 극성 단서    "좋", "별로", "최고". 그 절에서 언급된 측면에 붙는다.
                    언급된 측면이 없으면 맛에 붙는다(코드북 2절 규칙 2)
매칭된 구간은 지운 뒤 다음 단계로 넘어간다. "불친절" 이 "친절" 로 다시 잡히지 않게 하려는 것이다.

측면마다 절 단위로 표를 센다. 한쪽이 다른 쪽(엇갈림 표 포함)의 두 배 이상이면 그 극성이고,
아니면 엇갈림이다(v1). v0 은 긍정과 부정이 하나씩만 있어도 엇갈림이라 엇갈림이 과하게 나왔다.

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
    # v1: 「웨이팅 할 맛 아님」, 「그 맛이 아님」, 「맛집이 맞나」 류
    ("taste", "neg", r"할\s*맛\s*(이\s*)?(아니|아님|안)|(옛날|예전|그)\s*(그\s*)?맛\s*(이|은)?\s*(아니|아님|안\s*나)|예전에?가?\s*더\s*맛있"),
    ("taste", "neg", r"맛집\s*(이)?\s*(맞나|아님|아닌|인지\s*모르)|왜\s*(여기가\s*)?맛집|무한리필.{0,12}(수준|동일|보다\s*못)"),
    ("taste", "mixed", r"맛있(는지|을지)\s*(는\s*)?(잘\s*)?모르|그\s*정도\s*(로\s*)?(는\s*)?(아니|모르)"),
    # v1: 반어. 「고기가 맛없을 수 있나」는 칭찬이거나 일반론이다. 극성 없이 지우기만 한다
    (None, None, r"맛없(을\s*수|기가|기\s*힘)"),
    # v1: 「불친절함을 느끼지 못했다」 는 응대 긍정
    ("service", "pos", r"불친절\s*(함|한\s*거)?\s*(을|은)?\s*(전혀\s*|한\s*번도\s*)?(느끼지|못\s*느|없었)"),
    ("price", "pos", r"가격\s*대비\s*(괜찮|좋|훌륭|만족|최고|굿)"),
]

# 2. 극성을 품은 단서. 부정을 먼저 둔다
POLAR = [
    ("taste", "neg", r"맛\s*(이|은|도)?\s*없|맛없|안\s*맛있|맛있지\s*않|맛있진\s*않|맛\s*(이|은)?\s*(별로|그닥|떨어)|"
                     r"질기|질겼|퍽퍽|느끼|잡내|누린내|비린|싱거|싱겁|(?<!진)짜(요|다|고|서|네|더|웠|운|ㅠ)|짰|"
                     r"비계\s*(만|가\s*많|덩어리|투성)|딱딱|"
                     r"무맛|아무\s*맛|고무\s*씹|밍밍|슴슴|짜기만|짠\s*(감|편|맛)|"
                     r"(?<!옷에\s)냄새\s*(나|가\s*나|가\s*심|심)|안\s*익|설익|덜\s*익"),
    ("taste", "pos", r"맛있|맛나|존맛|꿀맛|JMT|jmt|맛집|부드럽|부드러|쫄깃|쫀득|고소|담백|육즙|신선|감칠맛|"
                     r"극락|살살\s*녹|녹아|윤기|고퀄|퀄리티\s*(가|는|도)?\s*(좋|최고|클래스|대박|훌륭)"),
    ("taste", "mixed", r"먹을\s*만|평범한\s*맛|맛\s*(은|이)?\s*(무난|평범|보통)"),
    ("service", "neg", r"불친절|불쾌|퉁명|쾅쾅|무시|짜증|싸가지|알아서\s*구워|구워\s*주지\s*않|안\s*구워|늦게\s*나|매너\s*(가\s*)?(없|별로|꽝)|"
                       r"(직원|응대|서비스)\s*교육|대답\s*(도|을)?\s*(안|없)|사과\s*(도|를)?\s*(안|없)|불러도|재촉|설렁설렁|개판|"
                       r"성격\s*(이\s*)?별로|직접\s*구워\s*먹|구워\s*먹으라|구우라|굽지\s*마|어리둥절|말\s*(을\s*)?걸|붙여\s*(주|줬)|"
                       r"(서비스|응대)\s*(가|는|와|도)?\s*.{0,8}(별로|개판|최악|아까|떨어|아쉽|부족|엉망)"),
    ("service", "pos", r"친절|구워\s*주|구워주|챙겨\s*주|서비스\s*(로|도)?\s*(주|줬|준|챙)|"
                       r"(아이스크림|음료|후식|계란찜|디저트)\s*(도|을|를)?\s*(주심|주셨|줬|서비스)|눈치\s*(를\s*)?안|최선"),
    ("wait", "neg", r"(웨이팅|대기|기다|줄)\s*(이|가|은|도)?\s*.{0,6}(길|오래|힘들|너무|엄청|한\s*시간|시간\s*넘|지옥)|"
                    r"먼저\s*(들여|들어|입장|번호)|(웨이팅|대기|줄)\s*(도|을|이)?\s*.{0,10}(꼬이|아깝|추워|추운|안내\s*(가\s*)?(전혀\s*)?없)|"
                    r"\d+\s*시간\s*(넘게|이상)?\s*(대기|기다|웨이팅)|(테이블|자리)\s*(이|가)?\s*.{0,6}비어\s*있.{0,30}(대기|기다|웨이팅|치우)|"
                    r"치우지\s*않|안\s*치우|원격\s*줄서기\s*필수"),
    ("wait", "pos", r"(웨이팅|대기)\s*(도|는|가|이)?\s*(없|짧|금방)|바로\s*(입장|들어)|예약\s*(이|하면)?\s*편"),
    ("price", "neg", r"비싸|비쌈|비쌌|비싼|사악|양\s*(이|은|도)?\s*(적|작|부족)|가성비\s*(가|는|도)?\s*(별로|안|떨어|나쁘|꽝)"),
    ("price", "pos", r"저렴|착한\s*가격|가성비\s*(가|는|도)?\s*(좋|최고|굿|짱|갑|훌륭)|가성비갑|푸짐|양\s*(이|도)?\s*(많|넉넉)|(?<!비)싸(고|요|서|다)|(?<!비)싼\s"),
    ("other", "neg", r"더럽|더러|지저분|시끄|좁|날파리|벌레|불결|청결\s*(무슨|문제|불량|별로)|수세미|안\s*씻|제대로\s*씻|"
                     r"불판.{0,12}(때|찌꺼기|찌든|기름|더러|세척)|덥|더웠|더워|침\s*뱉|냄새\s*(가|가\s*옷에)?\s*(배|밴|베)|연기|환기\s*(가|가\s*안)?\s*(안|별로)|주차\s*(가|는)?\s*(어렵|불편|안\s*됨|불가)"),
    ("other", "pos", r"분위기\s*(가|도|는)?\s*(좋|최고|굿|짱|예쁘|이쁘)|(매장|가게|내부|인테리어|테이블|식당)\s*(도|이|가|은|는)?\s*(엄청\s*|너무\s*)?(깔끔|깨끗|쾌적)|"
                     r"늦게까지\s*영업|에어컨|accessible|깨끗|청결|쾌적|넓|주차\s*(가|도)?\s*(편|가능|돼)"),
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
    ("mixed", r"나쁘지\s*않|나쁘진\s*않|나쁘지는\s*않|무난|평범|그럭저럭|쏘쏘|보통|그저\s*그|그냥\s*그(래|럼|렇)|"
              r"괜찮은\s*(편|정도)|편차|들쭉날쭉|일정하지\s*않"),
    ("neg", r"안\s*좋(?!아하)|좋지\s*않|좋진\s*않|별로|ㅂㄹ|최악|실망|아쉽|아쉬|비추|다시는|안\s*갈|그닥|글쎄|후회|"
            r"속았|시간\s*(이\s*)?아깝|내\s*시간|👎"),
    ("pos", r"좋|최고|굿|대박|짱|훌륭|만족|추천|감동|강추|미쳤|재방문|또\s*(오|올|갈|방문|가고)|자주\s*(와|가|옵)|"
            r"괜찮|👍"),
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
        if hit and aspect:
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


def merge(votes):
    """절 단위 표를 모아 극성 하나로. 한쪽이 나머지의 두 배 이상이면 그 극성, 아니면 엇갈림."""
    pos, neg, mixed = votes.count("pos"), votes.count("neg"), votes.count("mixed")
    if not votes:
        return "none"
    if pos and pos >= 2 * (neg + mixed):
        return "pos"
    if neg and neg >= 2 * (pos + mixed):
        return "neg"
    return "mixed"


def classify(text):
    per = {a: [] for a in ASPECTS}
    for clause in SPLIT.split(text or ""):
        if clause.strip():
            for aspect, pol in set(classify_clause(clause)):
                per[aspect].append(pol)
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
