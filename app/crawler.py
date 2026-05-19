from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, urlencode, urljoin, urlparse
from urllib.request import Request, urlopen

from app.models import ExamAttachment, ExamOption, ParsedPaper, SearchPageData, SourceExamPage

BASE_URL = "https://wwwq.moex.gov.tw/exam/"
SEARCH_PATH = "wFrmExamQandASearch.aspx"
DOWNLOAD_PATH = "wHandExamQandA_File.ashx"
USER_AGENT = "Mozilla/5.0 (compatible; moex-mirror/1.0)"

FILE_TYPE_MAP = {
    "Q": "question",
    "S": "answer",
    "M": "corrected_answer",
    "A": "all_answers",
    "B": "accessible_bundle",
}
SUBJECT_LABEL_TO_TYPE = {
    "試題": "question",
    "答案": "answer",
    "更正答案": "corrected_answer",
}


def make_result_url(exam_code: str, year_ad: int) -> str:
    return f"{urljoin(BASE_URL, SEARCH_PATH)}?{urlencode({'e': exam_code, 'y': str(year_ad)})}"


def make_download_url(href: str) -> str:
    return urljoin(BASE_URL, href)


def _year_roc(year_ad: int) -> int:
    return year_ad - 1911


class _SearchPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._current_select_name: str | None = None
        self._capture_years = False
        self._capture_exams = False
        self._option_value = ""
        self._option_text = ""
        self.available_years: list[int] = []
        self.exams: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "select":
            self._current_select_name = attrs_dict.get("name")
            self._capture_years = self._current_select_name == "ctl00$holderContent$wUctlExamYearStart$ddlExamYear"
            self._capture_exams = self._current_select_name == "ctl00$holderContent$ddlExamCode"
            return
        if tag == "option" and (self._capture_years or self._capture_exams):
            self._option_value = attrs_dict.get("value", "")
            self._option_text = ""

    def handle_data(self, data: str) -> None:
        if self._capture_years or self._capture_exams:
            self._option_text += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "select":
            self._current_select_name = None
            self._capture_years = False
            self._capture_exams = False
            return
        if tag == "option" and (self._capture_years or self._capture_exams):
            text = " ".join(self._option_text.split())
            if self._capture_years and self._option_value:
                self.available_years.append(int(self._option_value))
            elif self._capture_exams and self._option_value:
                self.exams.append((self._option_value, text))
            self._option_value = ""
            self._option_text = ""


@dataclass
class _Cell:
    text: str
    hrefs: list[str]


class _ResultTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_table = False
        self.table_depth = 0
        self.in_tr = False
        self.in_td = False
        self._cell_text: list[str] = []
        self._cell_hrefs: list[str] = []
        self.current_row: list[_Cell] = []
        self.rows: list[list[_Cell]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "table" and attrs_dict.get("id") == "ctl00_holderContent_tblExamQand":
            self.in_table = True
            self.table_depth = 1
            return
        if not self.in_table:
            return
        if tag == "table":
            self.table_depth += 1
        elif tag == "tr":
            self.in_tr = True
            self.current_row = []
        elif tag == "td":
            self.in_td = True
            self._cell_text = []
            self._cell_hrefs = []
        elif self.in_td and tag == "a":
            href = attrs_dict.get("href")
            if href:
                self._cell_hrefs.append(unescape(href))

    def handle_data(self, data: str) -> None:
        if self.in_td:
            self._cell_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "table" and self.in_table:
            self.table_depth -= 1
            if self.table_depth == 0:
                self.in_table = False
            return
        if not self.in_table:
            return
        if tag == "td" and self.in_td:
            text = " ".join("".join(self._cell_text).split())
            self.current_row.append(_Cell(text=text, hrefs=list(self._cell_hrefs)))
            self.in_td = False
            self._cell_text = []
            self._cell_hrefs = []
        elif tag == "tr" and self.in_tr:
            if self.current_row:
                self.rows.append(self.current_row)
            self.in_tr = False


def parse_search_page(html: str) -> SearchPageData:
    parser = _SearchPageParser()
    parser.feed(html)
    year_ad = parser.available_years[0] if parser.available_years else 0
    exams = [
        ExamOption(code=code, year_ad=year_ad_from_code(code, default_year_ad=year_ad), year_roc=roc_year_from_code(code), label=label)
        for code, label in parser.exams
    ]
    return SearchPageData(available_years=parser.available_years, exams=exams)


def roc_year_from_code(exam_code: str) -> int:
    return int(exam_code[:3])


def year_ad_from_code(exam_code: str, default_year_ad: int | None = None) -> int:
    roc = roc_year_from_code(exam_code)
    return roc + 1911 if roc else (default_year_ad or 0)


def _clean_subject_name(raw_text: str) -> str:
    text = raw_text
    for suffix in ("試題答案更正答案", "試題答案", "試題", "答案", "更正答案"):
        if text.endswith(suffix):
            text = text[: -len(suffix)]
            break
    return text.strip(" _-")


def _extract_type_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    key = query.get("t", [""])[0]
    return FILE_TYPE_MAP.get(key)


def _extract_codes(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    return query.get("c", [""])[0], query.get("s", [""])[0]


def parse_result_page(html: str, exam_code: str, year_ad: int) -> SourceExamPage:
    parser = _ResultTableParser()
    parser.feed(html)
    if not parser.rows:
        raise ValueError(f"No result table rows found for {exam_code}")

    header = parser.rows[0]
    exam_name_raw = next((cell.text for cell in header if cell.text), "")
    attachments: list[ExamAttachment] = []
    for cell in header[2:]:
        for href in cell.hrefs:
            file_type = _extract_type_from_url(href)
            if file_type:
                attachments.append(
                    ExamAttachment(title=cell.text or file_type, file_type=file_type, download_url_source=make_download_url(href))
                )

    papers: list[ParsedPaper] = []
    current_category = ""
    for row in parser.rows[1:]:
        non_empty = [cell for cell in row if cell.text]
        if len(non_empty) == 1 and not non_empty[0].hrefs:
            current_category = non_empty[0].text
            continue
        subject_cells = [cell for cell in row if cell.hrefs and cell.text not in SUBJECT_LABEL_TO_TYPE]
        if not subject_cells:
            continue
        subject_cell = subject_cells[0]
        category_code, subject_code = _extract_codes(subject_cell.hrefs[0])
        files: dict[str, str] = {}
        for cell in row:
            file_type = SUBJECT_LABEL_TO_TYPE.get(cell.text)
            if file_type and cell.hrefs:
                files[file_type] = make_download_url(cell.hrefs[0])
        if files:
            papers.append(
                ParsedPaper(
                    category_raw=current_category,
                    category_code=category_code,
                    subject_code=subject_code,
                    subject_name_raw=_clean_subject_name(subject_cell.text),
                    files=files,
                )
            )

    return SourceExamPage(
        source_exam_id=exam_code,
        year_ad=year_ad,
        year_roc=_year_roc(year_ad),
        exam_name_raw=exam_name_raw,
        attachments=attachments,
        papers=papers,
    )


@dataclass
class DownloadedFile:
    data: bytes
    content_type: str
    file_name: str


class MoexClient:
    def __init__(self, user_agent: str = USER_AGENT) -> None:
        self.user_agent = user_agent

    def _fetch_text(self, url: str) -> str:
        request = Request(url, headers={"User-Agent": self.user_agent})
        with urlopen(request, timeout=60) as response:
            return response.read().decode("utf-8", "ignore")

    def discover_available_years(self) -> list[int]:
        return parse_search_page(self._fetch_text(urljoin(BASE_URL, SEARCH_PATH))).available_years

    def discover_exams(self, year_ad: int) -> list[ExamOption]:
        url = f"{urljoin(BASE_URL, SEARCH_PATH)}?{urlencode({'y': str(year_ad)})}"
        return parse_search_page(self._fetch_text(url)).exams

    def fetch_exam_page(self, exam_code: str, year_ad: int) -> SourceExamPage:
        return parse_result_page(self._fetch_text(make_result_url(exam_code, year_ad)), exam_code=exam_code, year_ad=year_ad)

    def download_file(self, url: str) -> DownloadedFile:
        request = Request(url, headers={"User-Agent": self.user_agent})
        with urlopen(request, timeout=120) as response:
            content_disposition = response.headers.get("Content-Disposition", "")
            file_name_match = re.search(r'filename="?([^"]+)"?', content_disposition)
            file_name = unescape(file_name_match.group(1)) if file_name_match else Path(urlparse(url).path).name
            return DownloadedFile(
                data=response.read(),
                content_type=response.headers.get("Content-Type", "application/octet-stream"),
                file_name=file_name,
            )

