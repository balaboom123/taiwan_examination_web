from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.crawler import MoexClient
from app.models import NormalizedCatalog, NormalizedPaper
from app.normalizer import load_alias_rules
from app.publisher import build_site, write_data_files
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
    catalog = NormalizedCatalog(papers=[NormalizedPaper(**paper) for paper in papers], review_queue=[])
    build_site(args.site_dir, catalog)
    return 0


def command_sync(args: argparse.Namespace) -> int:
    client = MoexClient()
    if getattr(args, "year_window", None):
        years = _latest_years(client, args.year_window)
    else:
        years = _discover_years(client, args.years)
    exam_codes = _collect_exam_codes(client, years)
    aliases = load_alias_rules(args.aliases)
    raw_pages, normalized = sync_exam_pages(
        client=client,
        exam_codes=exam_codes,
        mirror_store=MirrorStore(args.mirror_dir),
        alias_rules=aliases,
        mirror_base_url=args.mirror_base_url,
    )
    write_data_files(args.data_dir, raw_pages, normalized, aliases)
    build_site(args.site_dir, normalized)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app")
    subparsers = parser.add_subparsers(dest="command", required=True)
    repo_root = _default_repo_root()

    discover = subparsers.add_parser("discover", help="Discover available exams grouped by year.")
    discover.add_argument("--years", nargs="*", type=int, default=None)
    discover.set_defaults(handler=command_discover)

    for name in ("sync-full", "sync-incremental"):
        sync = subparsers.add_parser(name, help=f"{name} against the live MOEX site.")
        sync.add_argument("--data-dir", type=Path, default=repo_root / "data")
        sync.add_argument("--site-dir", type=Path, default=repo_root / "site")
        sync.add_argument("--mirror-dir", type=Path, default=repo_root / "mirror")
        sync.add_argument("--aliases", type=Path, default=repo_root / "data" / "aliases.json")
        sync.add_argument("--mirror-base-url", default="")
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
