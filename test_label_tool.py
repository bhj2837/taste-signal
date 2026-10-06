"""label_tool.py 입력 처리. 실행: python3 -m unittest"""

import io
import json
import tempfile
import unittest
from pathlib import Path

from label_tool import parse, run


class Parse(unittest.TestCase):
    def test_five_codes(self):
        label = parse("+-...")
        self.assertEqual(
            (label["taste"], label["service"], label["wait"], label["price"], label["other"]),
            ("pos", "neg", "none", "none", "none"),
        )
        self.assertEqual(label["note"], "")

    def test_note_after_space(self):
        self.assertEqual(parse("~.... 대상 불명")["note"], "대상 불명")

    def test_rejects_wrong_length_or_symbol(self):
        self.assertIsNone(parse("+-.."))
        self.assertIsNone(parse("+-..x"))


class Run(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        with (self.dir / "dev.jsonl").open("w", encoding="utf-8") as fh:
            for i, text in enumerate(["가", "나", "다"], start=1):
                fh.write(json.dumps({"review_id": i, "text": text}, ensure_ascii=False) + "\n")

    def tearDown(self):
        self.tmp.cleanup()

    def labels(self):
        path = self.dir / "labels_dev.jsonl"
        return [json.loads(line) for line in path.open(encoding="utf-8")]

    def test_invalid_input_is_asked_again(self):
        run("dev", self.dir, io.StringIO("xx\n+....\nq\n"))
        self.assertEqual([l["review_id"] for l in self.labels()], [1])

    def test_back_relabels_previous(self):
        run("dev", self.dir, io.StringIO("+....\nb\n-....\n.....\nq\n"))
        got = {l["review_id"]: l["taste"] for l in self.labels()}
        self.assertEqual(got, {1: "neg", 2: "none"})

    def test_resumes_where_it_stopped(self):
        run("dev", self.dir, io.StringIO("+....\nq\n"))
        run("dev", self.dir, io.StringIO("-....\n~....\n"))
        self.assertEqual([l["review_id"] for l in self.labels()], [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
