import json
import tempfile
import unittest
from pathlib import Path

from app.models import AliasRule, NormalizedCatalog, NormalizedPaper, ReviewItem, SourceExamPage
from app.publisher import build_site, write_data_files


class PublisherTests(unittest.TestCase):
    def test_write_data_files_and_site(self) -> None:
        normalized = NormalizedCatalog(
            papers=[
                NormalizedPaper(
                    canonical_id="nurse",
                    canonical_name="護理師",
                    year_roc=115,
                    exam_name_raw="115年第一次專門職業及技術人員高等考試營養師、護理師、社會工作師考試",
                    category_raw="高等考試_護理師",
                    subject_name_raw="基礎醫學",
                    paper_code="101-0101-question",
                    file_type="question",
                    download_url_source="https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx?t=Q&code=115030&c=101&s=0101&q=1",
                    download_url_mirror="https://mirror.example/115/115030/101/0101/question.pdf",
                    checksum="abc123",
                )
            ],
            review_queue=[ReviewItem(raw_category="高等考試_護理師", normalized_candidate="護理師", source_exam_id="115030", year_roc=115)],
        )
        raw_pages = [
            SourceExamPage(
                source_exam_id="115030",
                year_ad=2026,
                year_roc=115,
                exam_name_raw="115年第一次專門職業及技術人員高等考試營養師、護理師、社會工作師考試",
                attachments=[],
                papers=[],
            )
        ]
        aliases = [AliasRule(match_type="exact", raw_pattern="高等考試_護理師", canonical_id="nurse", canonical_name="護理師")]

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            write_data_files(root / "data", raw_pages, normalized, aliases)
            build_site(root / "site", normalized)

            papers = json.loads((root / "data" / "papers.json").read_text(encoding="utf-8"))
            self.assertEqual(papers[0]["canonical_name"], "護理師")

            review = json.loads((root / "data" / "review-queue.json").read_text(encoding="utf-8"))
            self.assertEqual(review[0]["normalized_candidate"], "護理師")

            html = (root / "site" / "index.html").read_text(encoding="utf-8")
            self.assertIn("護理師", html)
            self.assertIn("基礎醫學", html)
            self.assertIn("https://mirror.example/115/115030/101/0101/question.pdf", html)


if __name__ == "__main__":
    unittest.main()
