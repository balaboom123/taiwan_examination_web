from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote

from app.crawler import MoexClient
from app.models import AliasRule, NormalizedCatalog, SourceExamPage
from app.normalizer import normalize_papers
from app.storage import MirrorStore

EXTENSION_OVERRIDES = {
    "application/pdf": ".pdf",
    "application/zip": ".zip",
}


def _extension_for(content_type: str, file_name: str) -> str:
    suffix = Path(unquote(file_name)).suffix
    if suffix:
        return suffix
    return EXTENSION_OVERRIDES.get(content_type.split(";")[0].strip(), ".bin")


def _asset_name_for(storage_key: str) -> str:
    return storage_key.replace("/", "__")


def sync_exam_pages(
    client: MoexClient,
    exam_codes: list[tuple[str, int]],
    mirror_store: MirrorStore,
    alias_rules: list[AliasRule],
    mirror_base_url: str,
) -> tuple[list[SourceExamPage], NormalizedCatalog]:
    raw_pages: list[SourceExamPage] = []
    normalized_papers = []
    review_queue = []

    for exam_code, year_ad in exam_codes:
        page = client.fetch_exam_page(exam_code, year_ad)
        mirror_metadata: dict[tuple[str, str, str], dict[str, str]] = {}

        for attachment in page.attachments:
            downloaded = client.download_file(attachment.download_url_source)
            storage_key = f"{page.year_roc}/{page.source_exam_id}/exam/{attachment.file_type}{_extension_for(downloaded.content_type, downloaded.file_name)}"
            stored = mirror_store.write_bytes(storage_key, downloaded.data)
            attachment.storage_key = stored.storage_key
            attachment.asset_name = _asset_name_for(stored.storage_key)
            attachment.checksum = stored.checksum
            attachment.download_url_mirror = f"{mirror_base_url.rstrip('/')}/{attachment.asset_name}" if mirror_base_url else ""

        for paper in page.papers:
            for file_type, download_url in paper.files.items():
                downloaded = client.download_file(download_url)
                storage_key = (
                    f"{page.year_roc}/{page.source_exam_id}/{paper.category_code}/{paper.subject_code}/"
                    f"{file_type}{_extension_for(downloaded.content_type, downloaded.file_name)}"
                )
                stored = mirror_store.write_bytes(storage_key, downloaded.data)
                paper.mirror_files[file_type] = {
                    "storage_key": stored.storage_key,
                    "asset_name": _asset_name_for(stored.storage_key),
                    "checksum": stored.checksum,
                }
                mirror_metadata[(paper.category_code, paper.subject_code, file_type)] = paper.mirror_files[file_type]

        normalized = normalize_papers(
            source_exam_id=page.source_exam_id,
            year_ad=page.year_ad,
            exam_name_raw=page.exam_name_raw,
            papers=page.papers,
            alias_rules=alias_rules,
            mirror_base_url=mirror_base_url,
            mirror_metadata=mirror_metadata,
        )
        raw_pages.append(page)
        normalized_papers.extend(normalized.papers)
        review_queue.extend(normalized.review_queue)

    return raw_pages, NormalizedCatalog(papers=normalized_papers, review_queue=review_queue)
