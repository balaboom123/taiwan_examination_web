from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote

from app.crawler import MoexClient
from app.models import AliasRule, ExamAttachment, NormalizedCatalog, ParsedPaper, SourceExamPage, SyncFailure
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


def _mirror_prefix_for_attachment(page: SourceExamPage, attachment: ExamAttachment) -> str:
    return f"{page.year_roc}/{page.source_exam_id}/exam/{attachment.file_type}"


def _mirror_prefix_for_paper(page: SourceExamPage, paper: ParsedPaper, file_type: str) -> str:
    return f"{page.year_roc}/{page.source_exam_id}/{paper.category_code}/{paper.subject_code}/{file_type}"


def sync_exam_pages(
    client: MoexClient,
    exam_codes: list[tuple[str, int]],
    mirror_store: MirrorStore,
    alias_rules: list[AliasRule],
    mirror_base_url: str,
) -> tuple[list[SourceExamPage], NormalizedCatalog, list[SyncFailure]]:
    raw_pages: list[SourceExamPage] = []
    normalized_papers = []
    review_queue = []
    failures: list[SyncFailure] = []

    for exam_code, year_ad in exam_codes:
        page = client.fetch_exam_page(exam_code, year_ad)
        mirror_metadata: dict[tuple[str, str, str], dict[str, str]] = {}

        for attachment in page.attachments:
            try:
                stored = mirror_store.find_existing(_mirror_prefix_for_attachment(page, attachment))
                if stored is None:
                    downloaded = client.download_file(attachment.download_url_source)
                    storage_key = f"{_mirror_prefix_for_attachment(page, attachment)}{_extension_for(downloaded.content_type, downloaded.file_name)}"
                    stored = mirror_store.write_bytes(storage_key, downloaded.data)
                attachment.storage_key = stored.storage_key
                attachment.asset_name = _asset_name_for(stored.storage_key)
                attachment.checksum = stored.checksum
                attachment.download_url_mirror = f"{mirror_base_url.rstrip('/')}/{attachment.asset_name}" if mirror_base_url else ""
            except Exception as exc:
                failures.append(
                    SyncFailure(
                        stage="download",
                        source_exam_id=page.source_exam_id,
                        year_roc=page.year_roc,
                        paper_code=f"exam-{attachment.file_type}",
                        file_type=attachment.file_type,
                        url=attachment.download_url_source,
                        message=str(exc),
                    )
                )

        for paper in page.papers:
            for file_type, download_url in paper.files.items():
                try:
                    stored = mirror_store.find_existing(_mirror_prefix_for_paper(page, paper, file_type))
                    if stored is None:
                        downloaded = client.download_file(download_url)
                        storage_key = f"{_mirror_prefix_for_paper(page, paper, file_type)}{_extension_for(downloaded.content_type, downloaded.file_name)}"
                        stored = mirror_store.write_bytes(storage_key, downloaded.data)
                    paper.mirror_files[file_type] = {
                        "storage_key": stored.storage_key,
                        "asset_name": _asset_name_for(stored.storage_key),
                        "checksum": stored.checksum,
                    }
                    mirror_metadata[(paper.category_code, paper.subject_code, file_type)] = paper.mirror_files[file_type]
                except Exception as exc:
                    failures.append(
                        SyncFailure(
                            stage="download",
                            source_exam_id=page.source_exam_id,
                            year_roc=page.year_roc,
                            paper_code=f"{paper.category_code}-{paper.subject_code}-{file_type}",
                            file_type=file_type,
                            url=download_url,
                            message=str(exc),
                        )
                    )

        normalized_input_papers = [
            ParsedPaper(
                category_raw=paper.category_raw,
                category_code=paper.category_code,
                subject_code=paper.subject_code,
                subject_name_raw=paper.subject_name_raw,
                files={file_type: paper.files[file_type] for file_type in paper.mirror_files},
                mirror_files=paper.mirror_files,
            )
            for paper in page.papers
            if paper.mirror_files
        ]

        normalized = normalize_papers(
            source_exam_id=page.source_exam_id,
            year_ad=page.year_ad,
            exam_name_raw=page.exam_name_raw,
            papers=normalized_input_papers,
            alias_rules=alias_rules,
            mirror_base_url=mirror_base_url,
            mirror_metadata=mirror_metadata,
        )
        raw_pages.append(page)
        normalized_papers.extend(normalized.papers)
        review_queue.extend(normalized.review_queue)

    return raw_pages, NormalizedCatalog(papers=normalized_papers, review_queue=review_queue), failures
