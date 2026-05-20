import json
import tempfile
import unittest
from pathlib import Path

from app.manifest import SourceManifest, load_source_manifest, write_source_manifest


class SourceManifestTests(unittest.TestCase):
    def test_missing_manifest_loads_as_empty_schema_one_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            manifest = load_source_manifest(Path(tmp_dir) / "source-manifest.json")

        self.assertEqual(manifest.schema_version, 1)
        self.assertEqual(manifest.probe_policy, {})
        self.assertEqual(manifest.years, {})
        self.assertEqual(manifest.exams, {})
        self.assertEqual(manifest.files, {})

    def test_invalid_schema_version_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "source-manifest.json"
            path.write_text(json.dumps({"schema_version": 99}), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Unsupported source manifest schema_version: 99"):
                load_source_manifest(path)

    def test_invalid_top_level_sections_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "source-manifest.json"
            path.write_text(json.dumps({"schema_version": 1, "years": []}), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Invalid source manifest years"):
                load_source_manifest(path)

    def test_invalid_manifest_entries_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "source-manifest.json"
            path.write_text(json.dumps({"schema_version": 1, "exams": {"115030": []}}), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Invalid source manifest exams.115030"):
                load_source_manifest(path)

    def test_write_source_manifest_uses_stable_sorted_json(self) -> None:
        manifest = SourceManifest(
            probe_policy={"year_window": 2, "download_attachments_by_default": False},
            years={
                "2026": {
                    "year_ad": 2026,
                    "exam_codes": ["115040", "115010"],
                }
            },
            exams={
                "115040": {
                    "source_exam_id": "115040",
                    "paper_url_hash": "sha256:abc",
                }
            },
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "source-manifest.json"

            write_source_manifest(path, manifest)
            first = path.read_text(encoding="utf-8")
            write_source_manifest(path, load_source_manifest(path))
            second = path.read_text(encoding="utf-8")

        self.assertEqual(first, second)
        self.assertTrue(first.endswith("\n"))
        self.assertLess(first.index('"exams"'), first.index('"files"'))
        self.assertLess(first.index('"probe_policy"'), first.index('"schema_version"'))


if __name__ == "__main__":
    unittest.main()
