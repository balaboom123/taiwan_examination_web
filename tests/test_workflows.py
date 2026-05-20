import unittest
from pathlib import Path


class WorkflowTests(unittest.TestCase):
    def test_incremental_workflow_probes_before_syncing(self) -> None:
        workflow_path = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "sync-incremental.yml"
        workflow = workflow_path.read_text(encoding="utf-8")

        self.assertIn("python -m app probe-latest --years 2", workflow)
        self.assertIn("python -m app sync-targeted", workflow)
        self.assertLess(workflow.index("python -m app probe-latest"), workflow.index("python -m app sync-targeted"))

    def test_incremental_workflow_can_exit_before_heavy_steps_when_unchanged(self) -> None:
        workflow_path = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "sync-incremental.yml"
        workflow = workflow_path.read_text(encoding="utf-8")

        self.assertIn("steps.probe.outputs.should_sync == 'true'", workflow)
        self.assertIn(".tmp/source-probe.json", workflow)
        self.assertIn("steps.probe.outputs.should_sync != 'true'", workflow)
        self.assertIn("git add data/source-manifest.json", workflow)

    def test_incremental_workflow_does_not_download_release_bundles_before_probe(self) -> None:
        workflow_path = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "sync-incremental.yml"
        workflow = workflow_path.read_text(encoding="utf-8")

        self.assertNotIn('gh release download "$MOEX_RELEASE_TAG" --pattern "*.zip" --dir bundles', workflow)
        self.assertIn("--download-affected-bundles", workflow)

    def test_monthly_audit_workflow_exists(self) -> None:
        workflow_path = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "audit-recent.yml"
        workflow = workflow_path.read_text(encoding="utf-8")

        self.assertIn('- cron: "45 3 1 * *"', workflow)
        self.assertIn("python -m app sync-incremental --years 2", workflow)
        self.assertIn("--write-manifest", workflow)

    def test_incremental_workflow_only_deletes_stale_zip_assets(self) -> None:
        workflow_path = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "sync-incremental.yml"
        workflow = workflow_path.read_text(encoding="utf-8")

        self.assertIn('asset["name"].endswith(".zip")', workflow)


if __name__ == "__main__":
    unittest.main()
