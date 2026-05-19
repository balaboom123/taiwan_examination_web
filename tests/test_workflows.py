import unittest
from pathlib import Path


class WorkflowTests(unittest.TestCase):
    def test_incremental_workflow_does_not_ignore_bundle_download_failures(self) -> None:
        workflow_path = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "sync-incremental.yml"
        workflow = workflow_path.read_text(encoding="utf-8")

        self.assertIn('gh release download "$MOEX_RELEASE_TAG" --pattern "*.zip" --dir bundles', workflow)
        self.assertNotIn('gh release download "$MOEX_RELEASE_TAG" --pattern "*.zip" --dir bundles || true', workflow)

    def test_incremental_workflow_checks_for_existing_release_assets_before_download(self) -> None:
        workflow_path = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "sync-incremental.yml"
        workflow = workflow_path.read_text(encoding="utf-8")

        self.assertIn('gh release view "$MOEX_RELEASE_TAG" --json assets', workflow)
        self.assertIn('if [ "$asset_count" -gt 0 ]', workflow)

    def test_incremental_workflow_runs_weekly_for_latest_year(self) -> None:
        workflow_path = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "sync-incremental.yml"
        workflow = workflow_path.read_text(encoding="utf-8")

        self.assertIn('- cron: "15 3 * * 1"', workflow)
        self.assertIn("python -m app sync-incremental --years 1", workflow)


if __name__ == "__main__":
    unittest.main()
