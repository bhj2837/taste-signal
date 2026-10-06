"""reviews.csv 를 읽어 표로 찍는다."""

import csv
import pathlib

from metrics import analyze

BASE = pathlib.Path(__file__).parent


def load():
    with (BASE / "data" / "reviews.csv").open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            yield {
                "shop": row["shop"],
                "reviewer_count": int(row["reviewer_count"]),
                "reviewer_avg": float(row["reviewer_avg"]),
                "star": float(row["star"]),
                "paid": row["paid"] == "True",
            }


def main():
    rows = list(load())
    peer_median, results = analyze(rows)

    print(f"리뷰 {len(rows)}건 / 가게 {len(results)}곳 / peer 중앙값 {peer_median:.3f}\n")
    head = f"{'가게':<22}{'n':>5}{'원평균':>8}{'보정':>8}{'하한':>8}{'편차':>8}{'칭찬봇':>8}{'일회성':>8}{'별5':>7}"
    print(head)
    print("-" * 84)
    for r in results:
        delta = f"{r['delta']:+.2f}" if r["delta"] is not None else "  -  "
        print(
            f"{r['shop']:<22}{r['n']:>5}{r['raw_mean']:>8.2f}{r['r_hat']:>8.2f}"
            f"{r['lower']:>8.2f}{delta:>8}{r['bot_rate']*100:>7.0f}%"
            f"{r['one_shot_rate']*100:>7.0f}%{r['five_star_rate']*100:>6.0f}%"
        )


if __name__ == "__main__":
    main()
