from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Iterable

from app.models import AliasRule, NormalizedCatalog, NormalizedPaper, ParsedPaper, ReviewItem

KNOWN_CANONICAL_IDS = {
    "護理師": "nurse",
    "社會工作師": "social-worker",
    "營養師": "dietitian",
    "心理師": "psychologist",
    "諮商心理師": "counseling-psychologist",
    "臨床心理師": "clinical-psychologist",
}

KNOWN_PREFIXES = [
    r"^專門職業及技術人員(?:高等|普通)?考試",
    r"^專技(?:高考|普考)",
    r"^高等考試",
    r"^普通考試",
    r"^特種考試",
]


def load_alias_rules(path: Path) -> list[AliasRule]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [AliasRule(**item) for item in payload.get("rules", [])]


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text or "")
    normalized = normalized.replace("＿", "_")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _match_alias(rule: AliasRule, raw_category: str, year_ad: int) -> bool:
    if rule.year_from is not None and year_ad < rule.year_from:
        return False
    if rule.year_to is not None and year_ad > rule.year_to:
        return False
    if rule.match_type == "exact":
        return normalize_text(raw_category) == normalize_text(rule.raw_pattern)
    if rule.match_type == "contains":
        return normalize_text(rule.raw_pattern) in normalize_text(raw_category)
    raise ValueError(f"Unsupported alias match type: {rule.match_type}")


def _strip_exam_family(text: str) -> str:
    value = normalize_text(text)
    value = re.sub(r"^\d+年", "", value)
    if "_" in value:
        value = value.split("_")[-1]
    for prefix in KNOWN_PREFIXES:
        value = re.sub(prefix, "", value)
    value = re.sub(r"^第[一二三四五六七八九十]+次", "", value)
    value = re.sub(r"考試$", "", value)
    return value.strip(" -_")


def _is_ambiguous(candidate: str) -> bool:
    return any(token in candidate for token in ("、", "暨", "及", "與"))


def _canonical_id(candidate: str) -> str:
    if candidate in KNOWN_CANONICAL_IDS:
        return KNOWN_CANONICAL_IDS[candidate]
    return "canonical-" + candidate.encode("utf-8").hex()[:16]


def normalize_papers(
    source_exam_id: str,
    year_ad: int,
    exam_name_raw: str,
    papers: Iterable[ParsedPaper],
    alias_rules: list[AliasRule],
    mirror_base_url: str,
    mirror_metadata: dict[tuple[str, str, str], dict[str, str]],
) -> NormalizedCatalog:
    year_roc = year_ad - 1911
    normalized_papers: list[NormalizedPaper] = []
    review_queue: list[ReviewItem] = []
    for paper in papers:
        raw_category = paper.category_raw or exam_name_raw
        alias = next((rule for rule in alias_rules if _match_alias(rule, raw_category, year_ad)), None)
        candidate = _strip_exam_family(raw_category or exam_name_raw)
        if alias:
            canonical_id = alias.canonical_id
            canonical_name = alias.canonical_name
        else:
            canonical_name = candidate or normalize_text(raw_category or exam_name_raw)
            canonical_id = _canonical_id(canonical_name)
        if not alias and _is_ambiguous(canonical_name):
            canonical_name = normalize_text(raw_category or exam_name_raw)
            canonical_id = _canonical_id(canonical_name)
            review_queue.append(
                ReviewItem(
                    raw_category=raw_category,
                    normalized_candidate=candidate or canonical_name,
                    source_exam_id=source_exam_id,
                    year_roc=year_roc,
                )
            )
        for file_type, download_url_source in paper.files.items():
            metadata = mirror_metadata.get((paper.category_code, paper.subject_code, file_type), {})
            storage_key = metadata.get("storage_key", "")
            asset_name = metadata.get("asset_name") or storage_key
            download_url_mirror = f"{mirror_base_url.rstrip('/')}/{asset_name}" if mirror_base_url and asset_name else ""
            normalized_papers.append(
                NormalizedPaper(
                    canonical_id=canonical_id,
                    canonical_name=canonical_name,
                    year_roc=year_roc,
                    exam_name_raw=exam_name_raw,
                    category_raw=paper.category_raw,
                    subject_name_raw=paper.subject_name_raw,
                    paper_code=f"{paper.category_code}-{paper.subject_code}-{file_type}",
                    file_type=file_type,
                    download_url_source=download_url_source,
                    download_url_mirror=download_url_mirror,
                    checksum=metadata.get("checksum", ""),
                )
            )
    return NormalizedCatalog(papers=normalized_papers, review_queue=review_queue)
