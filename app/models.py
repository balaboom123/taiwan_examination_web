from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ExamOption:
    code: str
    year_ad: int
    year_roc: int
    label: str


@dataclass
class SearchPageData:
    available_years: list[int]
    exams: list[ExamOption]


@dataclass
class ExamAttachment:
    title: str
    file_type: str
    download_url_source: str
    storage_key: str = ""
    asset_name: str = ""
    checksum: str = ""
    download_url_mirror: str = ""


@dataclass
class ParsedPaper:
    category_raw: str
    category_code: str
    subject_code: str
    subject_name_raw: str
    files: dict[str, str]
    mirror_files: dict[str, dict[str, str]] = field(default_factory=dict)


@dataclass
class SourceExamPage:
    source_exam_id: str
    year_ad: int
    year_roc: int
    exam_name_raw: str
    attachments: list[ExamAttachment]
    papers: list[ParsedPaper]


@dataclass
class AliasRule:
    match_type: str
    raw_pattern: str
    canonical_id: str
    canonical_name: str
    year_from: int | None = None
    year_to: int | None = None


@dataclass
class ReviewItem:
    raw_category: str
    normalized_candidate: str
    source_exam_id: str
    year_roc: int

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


@dataclass
class NormalizedPaper:
    canonical_id: str
    canonical_name: str
    year_roc: int
    exam_name_raw: str
    category_raw: str
    subject_name_raw: str
    paper_code: str
    file_type: str
    download_url_source: str
    download_url_mirror: str
    checksum: str


@dataclass
class NormalizedCatalog:
    papers: list[NormalizedPaper]
    review_queue: list[ReviewItem]


@dataclass
class StoredFile:
    storage_key: str
    path: Path
    checksum: str
    created: bool
    size: int


def to_plain_data(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return {key: to_plain_data(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {key: to_plain_data(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_plain_data(item) for item in value]
    return value
