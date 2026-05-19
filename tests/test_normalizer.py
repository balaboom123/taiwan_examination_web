import unittest

from app.models import AliasRule, ParsedPaper, NormalizedPaper
from app.normalizer import normalize_papers


class NormalizePapersTests(unittest.TestCase):
    def test_alias_rules_override_general_canonicalization(self) -> None:
        papers = [
            ParsedPaper(
                category_raw="高等考試_護理師",
                category_code="101",
                subject_code="0101",
                subject_name_raw="基礎醫學",
                files={
                    "question": "https://example.test/q.pdf",
                    "answer": "https://example.test/a.pdf",
                },
            ),
        ]
        aliases = [
            AliasRule(
                match_type="exact",
                raw_pattern="高等考試_護理師",
                canonical_id="nurse",
                canonical_name="護理師",
            )
        ]

        normalized = normalize_papers(
            source_exam_id="115030",
            year_ad=2026,
            exam_name_raw="115年第一次專門職業及技術人員高等考試營養師、護理師、社會工作師考試",
            papers=papers,
            alias_rules=aliases,
            mirror_base_url="https://mirror.example/releases/download/moex",
            mirror_metadata={
                ("101", "0101", "question"): {"checksum": "abc123", "storage_key": "115/115030/101/0101/question.pdf"},
                ("101", "0101", "answer"): {"checksum": "def456", "storage_key": "115/115030/101/0101/answer.pdf"},
            },
        )

        self.assertEqual(len(normalized.papers), 2)
        self.assertEqual(normalized.review_queue, [])
        self.assertEqual(normalized.papers[0].canonical_id, "nurse")
        self.assertEqual(normalized.papers[0].canonical_name, "護理師")
        self.assertTrue(normalized.papers[0].download_url_mirror.endswith("/115/115030/101/0101/question.pdf"))

    def test_general_rules_reduce_known_exam_prefixes_without_aliases(self) -> None:
        papers = [
            ParsedPaper(
                category_raw="專技高考_社會工作師",
                category_code="103",
                subject_code="0301",
                subject_name_raw="社會工作",
                files={"question": "https://example.test/q.pdf"},
            )
        ]

        normalized = normalize_papers(
            source_exam_id="115030",
            year_ad=2026,
            exam_name_raw="115年第一次專門職業及技術人員高等考試營養師、護理師、社會工作師考試",
            papers=papers,
            alias_rules=[],
            mirror_base_url="",
            mirror_metadata={("103", "0301", "question"): {"checksum": "abc123", "storage_key": "115/115030/103/0301/question.pdf"}},
        )

        self.assertEqual(normalized.papers[0].canonical_name, "社會工作師")
        self.assertEqual(normalized.papers[0].canonical_id, "social-worker")
        self.assertEqual(normalized.review_queue, [])

    def test_ambiguous_categories_are_queued_for_review(self) -> None:
        papers = [
            ParsedPaper(
                category_raw="專門職業及技術人員高等考試護理師、心理師考試",
                category_code="999",
                subject_code="0001",
                subject_name_raw="綜合科目",
                files={"question": "https://example.test/q.pdf"},
            )
        ]

        normalized = normalize_papers(
            source_exam_id="114170",
            year_ad=2025,
            exam_name_raw="114年專門職業及技術人員高等考試護理師、心理師考試",
            papers=papers,
            alias_rules=[],
            mirror_base_url="",
            mirror_metadata={("999", "0001", "question"): {"checksum": "abc123", "storage_key": "114/114170/999/0001/question.pdf"}},
        )

        self.assertEqual(normalized.papers[0].canonical_name, "專門職業及技術人員高等考試護理師、心理師考試")
        self.assertEqual(len(normalized.review_queue), 1)
        self.assertEqual(normalized.review_queue[0]["raw_category"], "專門職業及技術人員高等考試護理師、心理師考試")


if __name__ == "__main__":
    unittest.main()
