"""raw_compact.txt -> reviews.csv

한 줄이 가게 하나다. `가게이름|rc,avg,star[,P] rc,avg,star ...`
rc   그 리뷰를 쓴 사람의 카카오맵 총 후기 수
avg  그 사람의 평균 별점 (이 리뷰를 포함한 값, 소수 1자리로 반올림되어 노출된다)
star 그 사람이 이 가게에 준 별점
P    결제인증 배지가 붙은 리뷰
"""

import csv
import pathlib

BASE = pathlib.Path(__file__).parent
SRC = BASE / "data" / "raw_compact.txt"
OUT = BASE / "data" / "reviews.csv"


def parse(path):
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        shop, blob = line.split("|", 1)
        for token in blob.split():
            parts = token.split(",")
            rc, avg, star = int(parts[0]), float(parts[1]), float(parts[2])
            paid = len(parts) > 3 and parts[3] == "P"
            yield shop, rc, avg, star, paid


def main():
    rows = list(parse(SRC))
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["shop", "reviewer_count", "reviewer_avg", "star", "paid"])
        w.writerows(rows)
    shops = {r[0] for r in rows}
    print(f"{len(rows)} reviews / {len(shops)} shops -> {OUT}")


if __name__ == "__main__":
    main()
