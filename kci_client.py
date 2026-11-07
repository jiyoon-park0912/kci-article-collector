"""KCI Open API client. No credentials are logged or serialized."""
from __future__ import annotations
import math
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Callable
import requests

API_URL = "https://open.kci.go.kr/po/openapi/openApiSearch.kci"
MAX_PAGE_SIZE = 100

class KCIError(Exception):
    pass

@dataclass
class Collection:
    rows: list[dict]
    total_reported: int
    pages_fetched: int
    complete: bool
    messages: list[str]


def korean_present(value: str) -> bool:
    return bool(re.search(r"[가-힣]", value or ""))


def pick_lang(parent: ET.Element | None, tag: str, lang: str) -> str:
    if parent is None:
        return ""
    for element in parent.findall(tag):
        if element.get("lang", "").casefold() == lang:
            return "".join(element.itertext()).strip()
    return ""


def parse_response(content: bytes) -> tuple[int | None, str | None, list[dict]]:
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise KCIError("API 응답이 올바른 XML이 아닙니다.") from exc
    message = (root.findtext("./outputData/result/resultMsg") or "").strip() or None
    raw_total = root.findtext("./outputData/result/total")
    try:
        total = int(raw_total) if raw_total is not None else None
    except ValueError:
        total = None
    rows = []
    for record in root.findall("./outputData/record"):
        journal_info = record.find("journalInfo")
        article_info = record.find("articleInfo")
        if article_info is None:
            continue
        group = article_info.find("abstract-group")
        titles = article_info.find("title-group")
        original = pick_lang(group, "abstract", "original")
        english = pick_lang(group, "abstract", "english")
        # A Korean abstract must contain Hangul; no fallback from English.
        korean = original if korean_present(original) else ""
        rows.append({
            "article_id": article_info.get("article-id", "").strip(),
            "journal": journal_info.findtext("journal-name", default="").strip() if journal_info is not None else "",
            "publisher": journal_info.findtext("publisher-name", default="").strip() if journal_info is not None else "",
            "year": journal_info.findtext("pub-year", default="").strip() if journal_info is not None else "",
            "month": journal_info.findtext("pub-mon", default="").strip() if journal_info is not None else "",
            "field": article_info.findtext("article-categories", default="").strip(),
            "regularity": article_info.findtext("article-regularity", default="").strip(),
            "title": pick_lang(titles, "article-title", "original"),
            "abstract_ko": korean,
            "abstract_en": english,
            "abstract_original": original,
            "doi": article_info.findtext("doi", default="").strip(),
            "url": article_info.findtext("url", default="").strip(),
        })
    return total, message, rows


def _fetch(session: requests.Session, key: str, journal: str, start_year: int, end_year: int, page: int, page_size: int) -> tuple[int | None, str | None, list[dict]]:
    # Credentials are placed only in the HTTPS request, never in log output.
    params = {
        "key": key, "apiCode": "articleSearch", "journal": journal,
        "dateFrom": f"{start_year}01", "dateTo": f"{end_year}12",
        "page": page, "displayCount": page_size,
    }
    try:
        response = session.get(API_URL, params=params, timeout=35)
        response.raise_for_status()
        return parse_response(response.content)
    except requests.RequestException as exc:
        # Avoid logging exception details: requests exceptions may contain a URL with the key.
        raise KCIError(f"{page}페이지에서 네트워크 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.") from None


def collect(
    *, key: str, journal: str, start_year: int, end_year: int,
    page_limit: int = 10, pause: float = 0.5, page_size: int = MAX_PAGE_SIZE,
    progress: Callable[[int, int, int], None] | None = None,
    session: requests.Session | None = None,
) -> Collection:
    if not key or not key.strip():
        raise KCIError("API 인증키가 필요합니다.")
    if not journal or not journal.strip():
        raise KCIError("학술지명을 입력하세요.")
    if start_year > end_year:
        raise KCIError("시작 연도가 종료 연도보다 늦습니다.")
    if not 1 <= page_limit <= 200 or not 1 <= page_size <= 100:
        raise KCIError("페이지 및 페이지당 수집 건수를 확인하세요.")
    session = session or requests.Session()
    raw_rows = []
    total_reported = None
    page_count = 0
    messages = []
    complete = False
    for page in range(1, page_limit + 1):
        total, msg, page_rows = _fetch(session, key, journal.strip(), start_year, end_year, page, page_size)
        if msg:
            if msg.casefold() == "no data" and page == 1:
                return Collection([], 0, 1, True, ["검색 결과가 없습니다."])
            if page == 1:
                raise KCIError(f"KCI API 메시지: {msg}")
            messages.append(f"{page}페이지에서 API 메시지({msg})가 반환되어 수집을 중단했습니다.")
            break
        if total_reported is None:
            if total is None:
                raise KCIError("API 응답에서 전체 검색 건수를 확인할 수 없습니다.")
            total_reported = total
        raw_rows.extend(page_rows)
        page_count += 1
        if progress:
            progress(page_count, max(1, math.ceil(total_reported / page_size)), len(raw_rows))
        if not page_rows or len(raw_rows) >= total_reported:
            complete = len(raw_rows) >= total_reported
            break
        if page < page_limit:
            time.sleep(pause)
    if total_reported is None:
        total_reported = 0
    if not complete and total_reported > 0:
        messages.append("전체 검색 결과를 끝까지 조회하지 못했습니다. 페이지 제한 또는 API 응답을 확인하세요.")
    # Deduplicate by article ID; fallback to stable tuple for missing IDs.
    seen = set()
    rows = []
    for row in raw_rows:
        key_id = row["article_id"] or (row["journal"], row["year"], row["title"])
        if key_id in seen:
            continue
        seen.add(key_id)
        rows.append(row)
    if len(rows) != len(raw_rows):
        messages.append(f"중복 논문 {len(raw_rows)-len(rows)}건을 제거했습니다. 검색 결과의 페이지 중복 여부를 확인하세요.")
    return Collection(rows, total_reported, page_count, complete, messages)
