import json
import tempfile
import unittest
from pathlib import Path

from app.cli import build_parser, main


class CliBuildSiteTests(unittest.TestCase):
    def test_build_site_command_renders_existing_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            data_dir = root / "data"
            site_dir = root / "site"
            data_dir.mkdir()
            site_dir.mkdir()
            (data_dir / "papers.json").write_text(
                json.dumps(
                    [
                        {
                            "canonical_id": "nurse",
                            "canonical_name": "護理師",
                            "year_roc": 115,
                            "exam_name_raw": "115年第一次專門職業及技術人員高等考試護理師考試",
                            "category_raw": "高等考試_護理師",
                            "subject_name_raw": "基礎醫學",
                            "paper_code": "101-0101-question",
                            "file_type": "question",
                            "download_url_source": "https://source.example/question.pdf",
                            "download_url_mirror": "https://mirror.example/question.pdf",
                            "checksum": "abc123",
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            exit_code = main(["build-site", "--data-dir", str(data_dir), "--site-dir", str(site_dir)])

            self.assertEqual(exit_code, 0)
            html = (site_dir / "index.html").read_text(encoding="utf-8")
            self.assertIn("護理師", html)
            self.assertIn("https://mirror.example/question.pdf", html)

    def test_sync_incremental_years_flag_is_a_window_size(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["sync-incremental", "--years", "3"])
        self.assertEqual(args.year_window, 3)


if __name__ == "__main__":
    unittest.main()
