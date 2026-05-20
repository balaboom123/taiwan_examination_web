from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path

from app.bundler import build_bundles
from app.crawler import MoexClient, year_ad_from_code
from app.manifest import load_source_manifest, source_manifest_from_data, write_source_manifest
from app.models import BundleAsset, NormalizedCatalog, NormalizedPaper
from app.normalizer import load_alias_rules
from app.publisher import build_site, write_data_files
from app.probe import probe_latest
from app.state import filter_catalog_by_canonical_ids, load_existing_state, merge_incremental_state, merge_targeted_state
from app.sync import sync_exam_pages
from app.storage import MirrorStore


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _discover_years(client: MoexClient, years: list[int] | None) -> list[int]:
    if years:
        return years
    return client.discover_available_years()


def _latest_years(client: MoexClient, count: int) -> list[int]:
    years = sorted(client.discover_available_years(), reverse=True)
    return sorted(years[:count], reverse=True)


def _collect_exam_codes(client: MoexClient, years: list[int]) -> list[tuple[str, int]]:
    exam_codes: list[tuple[str, int]] = []
    for year in years:
        exam_codes.extend((exam.code, exam.year_ad) for exam in client.discover_exams(year))
    return exam_codes


def command_discover(args: argparse.Namespace) -> int:
    client = MoexClient()
    years = _discover_years(client, args.years)
    payload = []
    for year in years:
        payload.append(
            {
                "year_ad": year,
                "year_roc": year - 1911,
                "exams": [exam.__dict__ for exam in client.discover_exams(year)],
            }
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def command_build_site(args: argparse.Namespace) -> int:
    papers = json.loads((args.data_dir / "papers.json").read_text(encoding="utf-8"))
    bundles_path = args.data_dir / "bundles.json"
    bundles_data = json.loads(bundles_path.read_text(encoding="utf-8")) if bundles_path.exists() else []
    catalog = NormalizedCatalog(papers=[NormalizedPaper(**paper) for paper in papers], review_queue=[])
    bundles = [BundleAsset(**bundle) for bundle in bundles_data]
    build_site(args.site_dir, catalog, bundles)
    return 0


def run_probe_latest(args: argparse.Namespace, client: MoexClient | None = None, now: str | None = None) -> int:
    probe_client = client or MoexClient()
    generated_at = now or datetime.now().astimezone().isoformat()
    manifest = load_source_manifest(args.manifest)
    result = probe_latest(client=probe_client, manifest=manifest, year_window=args.years, now=generated_at)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result.to_output_data(), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.write_manifest:
        write_source_manifest(args.manifest, result.updated_manifest)
    return 0


def command_probe_latest(args: argparse.Namespace) -> int:
    return run_probe_latest(args)


def _download_affected_bundles(bundle_dir: Path, existing_bundles: list[BundleAsset], affected_canonical_ids: set[str], release_tag: str) -> None:
    asset_names = [
        bundle.asset_name
        for bundle in existing_bundles
        if bundle.canonical_id in affected_canonical_ids and bundle.asset_name
    ]
    if not asset_names:
        return
    bundle_dir.mkdir(parents=True, exist_ok=True)
    for asset_name in sorted(set(asset_names)):
        if (bundle_dir / asset_name).exists():
            continue
        subprocess.run(["gh", "release", "download", release_tag, "--pattern", asset_name, "--dir", str(bundle_dir)], check=True)


def _write_probe_manifest_if_present(probe: dict[str, object], manifest_path: Path) -> None:
    updated_manifest = probe.get("updated_manifest")
    if isinstance(updated_manifest, dict):
        write_source_manifest(manifest_path, source_manifest_from_data(updated_manifest))


def run_sync_targeted(args: argparse.Namespace, client: MoexClient | None = None) -> int:
    probe = json.loads(args.probe.read_text(encoding="utf-8"))
    if not probe.get("should_sync", False):
        return 0

    changed_exam_codes = list(probe.get("changed_exam_codes", []))
    removed_exam_ids = set(probe.get("removed_exam_codes", []))
    exam_years = {code: int(year) for code, year in probe.get("exam_years", {}).items()}
    exam_codes = [(code, exam_years.get(code, year_ad_from_code(code))) for code in changed_exam_codes]
    aliases = load_alias_rules(args.aliases)
    sync_client = client or MoexClient()
    refreshed_raw_pages, refreshed_catalog, sync_failures = sync_exam_pages(
        client=sync_client,
        exam_codes=exam_codes,
        mirror_store=MirrorStore(args.mirror_dir),
        alias_rules=aliases,
        mirror_base_url="",
        download_attachments=args.download_attachments,
    )
    if sync_failures:
        return 1
    existing_raw_pages, existing_catalog, existing_bundles, existing_failures = load_existing_state(args.data_dir)
    refreshed_exam_ids = {page.source_exam_id for page in refreshed_raw_pages}
    raw_pages, normalized, preserved_bundles, affected_canonical_ids = merge_targeted_state(
        existing_raw_pages=existing_raw_pages,
        existing_catalog=existing_catalog,
        existing_bundles=existing_bundles,
        refreshed_raw_pages=refreshed_raw_pages,
        refreshed_catalog=refreshed_catalog,
        removed_exam_ids=removed_exam_ids,
    )
    if args.download_affected_bundles:
        _download_affected_bundles(args.bundle_dir, existing_bundles, affected_canonical_ids, args.release_tag)
    rebuild_result = build_bundles(
        bundle_dir=args.bundle_dir,
        mirror_dir=args.mirror_dir,
        normalized=filter_catalog_by_canonical_ids(normalized, affected_canonical_ids),
        bundle_base_url=args.bundle_base_url or args.mirror_base_url,
    )
    if rebuild_result.failures:
        return 1
    canonical_order = {bundle.canonical_id: bundle for bundle in preserved_bundles}
    for bundle in rebuild_result.bundles:
        canonical_order[bundle.canonical_id] = bundle
    bundles = sorted(canonical_order.values(), key=lambda bundle: bundle.canonical_id)
    replaced_exam_ids = refreshed_exam_ids | removed_exam_ids
    failures = [failure for failure in existing_failures if failure.source_exam_id not in replaced_exam_ids]
    failures.extend(sync_failures)
    failures.extend(rebuild_result.failures)

    write_data_files(args.data_dir, raw_pages, normalized, aliases, bundles, failures)
    build_site(args.site_dir, normalized, bundles)
    _write_probe_manifest_if_present(probe, args.manifest)
    return 0


def command_sync_targeted(args: argparse.Namespace) -> int:
    return run_sync_targeted(args)


def command_sync(args: argparse.Namespace) -> int:
    client = MoexClient()
    if getattr(args, "year_window", None):
        years = _latest_years(client, args.year_window)
    else:
        years = _discover_years(client, args.years)
    exam_codes = _collect_exam_codes(client, years)
    aliases = load_alias_rules(args.aliases)
    refreshed_raw_pages, refreshed_catalog, sync_failures = sync_exam_pages(
        client=client,
        exam_codes=exam_codes,
        mirror_store=MirrorStore(args.mirror_dir),
        alias_rules=aliases,
        mirror_base_url="",
        download_attachments=args.download_attachments,
    )
    incremental_mode = getattr(args, "year_window", None) is not None
    if incremental_mode:
        existing_raw_pages, existing_catalog, existing_bundles, existing_failures = load_existing_state(args.data_dir)
        refreshed_exam_ids = {page.source_exam_id for page in refreshed_raw_pages}
        raw_pages, normalized, preserved_bundles, affected_canonical_ids = merge_incremental_state(
            existing_raw_pages=existing_raw_pages,
            existing_catalog=existing_catalog,
            existing_bundles=existing_bundles,
            refreshed_raw_pages=refreshed_raw_pages,
            refreshed_catalog=refreshed_catalog,
            refreshed_year_rocs={year - 1911 for year in years},
        )
        rebuild_result = build_bundles(
            bundle_dir=args.bundle_dir,
            mirror_dir=args.mirror_dir,
            normalized=filter_catalog_by_canonical_ids(normalized, affected_canonical_ids),
            bundle_base_url=args.bundle_base_url or args.mirror_base_url,
        )
        canonical_order = {bundle.canonical_id: bundle for bundle in preserved_bundles}
        for bundle in rebuild_result.bundles:
            canonical_order[bundle.canonical_id] = bundle
        bundles = sorted(canonical_order.values(), key=lambda bundle: bundle.canonical_id)
        failures = [failure for failure in existing_failures if failure.source_exam_id not in refreshed_exam_ids]
        failures.extend(sync_failures)
        failures.extend(rebuild_result.failures)
    else:
        raw_pages = refreshed_raw_pages
        normalized = refreshed_catalog
        rebuild_result = build_bundles(
            bundle_dir=args.bundle_dir,
            mirror_dir=args.mirror_dir,
            normalized=normalized,
            bundle_base_url=args.bundle_base_url or args.mirror_base_url,
        )
        bundles = rebuild_result.bundles
        failures = sync_failures + rebuild_result.failures

    write_data_files(args.data_dir, raw_pages, normalized, aliases, bundles, failures)
    build_site(args.site_dir, normalized, bundles)
    if getattr(args, "write_manifest", False) and not failures:
        manifest = load_source_manifest(args.manifest)
        result = probe_latest(client=client, manifest=manifest, year_window=len(years), now=datetime.now().astimezone().isoformat())
        write_source_manifest(args.manifest, result.updated_manifest)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app")
    subparsers = parser.add_subparsers(dest="command", required=True)
    repo_root = _default_repo_root()

    discover = subparsers.add_parser("discover", help="Discover available exams grouped by year.")
    discover.add_argument("--years", nargs="*", type=int, default=None)
    discover.set_defaults(handler=command_discover)

    probe_parser = subparsers.add_parser("probe-latest", help="Probe recent MOEX source changes without downloading files.")
    probe_parser.add_argument("--years", type=int, default=2)
    probe_parser.add_argument("--manifest", type=Path, default=repo_root / "data" / "source-manifest.json")
    probe_parser.add_argument("--output", type=Path, default=repo_root / ".tmp" / "source-probe.json")
    probe_parser.add_argument("--write-manifest", action="store_true")
    probe_parser.set_defaults(handler=command_probe_latest)

    targeted = subparsers.add_parser("sync-targeted", help="Sync only changed exams from a probe output file.")
    targeted.add_argument("--probe", type=Path, default=repo_root / ".tmp" / "source-probe.json")
    targeted.add_argument("--data-dir", type=Path, default=repo_root / "data")
    targeted.add_argument("--site-dir", type=Path, default=repo_root / "site")
    targeted.add_argument("--mirror-dir", type=Path, default=repo_root / "mirror")
    targeted.add_argument("--bundle-dir", type=Path, default=repo_root / "bundles")
    targeted.add_argument("--aliases", type=Path, default=repo_root / "data" / "aliases.json")
    targeted.add_argument("--manifest", type=Path, default=repo_root / "data" / "source-manifest.json")
    targeted.add_argument("--bundle-base-url", default="")
    targeted.add_argument("--mirror-base-url", default="")
    targeted.add_argument("--download-attachments", action="store_true", default=False)
    targeted.add_argument("--download-affected-bundles", action="store_true", default=False)
    targeted.add_argument("--release-tag", default="moex-bundles")
    targeted.set_defaults(handler=command_sync_targeted)

    for name in ("sync-full", "sync-incremental"):
        sync = subparsers.add_parser(name, help=f"{name} against the live MOEX site.")
        sync.add_argument("--data-dir", type=Path, default=repo_root / "data")
        sync.add_argument("--site-dir", type=Path, default=repo_root / "site")
        sync.add_argument("--mirror-dir", type=Path, default=repo_root / "mirror")
        sync.add_argument("--bundle-dir", type=Path, default=repo_root / "bundles")
        sync.add_argument("--aliases", type=Path, default=repo_root / "data" / "aliases.json")
        sync.add_argument("--manifest", type=Path, default=repo_root / "data" / "source-manifest.json")
        sync.add_argument("--bundle-base-url", default="")
        sync.add_argument("--mirror-base-url", default="")
        sync.add_argument("--download-attachments", action="store_true", default=name == "sync-full")
        sync.add_argument("--write-manifest", action="store_true", default=False)
        if name == "sync-full":
            sync.add_argument("--years", nargs="*", type=int, default=None)
        else:
            sync.add_argument("--years", dest="year_window", type=int, default=3)
        sync.set_defaults(handler=command_sync)

    build_site_parser = subparsers.add_parser("build-site", help="Build static HTML from data/papers.json.")
    build_site_parser.add_argument("--data-dir", type=Path, default=repo_root / "data")
    build_site_parser.add_argument("--site-dir", type=Path, default=repo_root / "site")
    build_site_parser.set_defaults(handler=command_build_site)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)
