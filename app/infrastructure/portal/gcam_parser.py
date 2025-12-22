from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import List, Optional

from app.infrastructure.parsing.fields import normalize_text, parse_account_entry, parse_date


_LABELS = {
    "license_number": ["رقم الرخصة", "رقم الترخيص", "license number", "license no"],
    "owner_name": ["اسم المرخص له", "اسم المالك", "اسم صاحب الرخصة", "owner name"],
    "license_title": ["نوع الترخيص", "نوع الرخصة", "نوع النشاط", "مسمي الرخصة", "license type"],
    "issue_date": ["تاريخ الاصدار", "تاريخ الإصدار", "تاريخ إصدار", "issue date"],
    "expiry_date": ["تاريخ الانتهاء", "تاريخ الإنتهاء", "تاريخ انتهاء", "expiry date"],
    "status": ["الحالة", "حالة الترخيص", "حالة الرخصة", "status"],
    "accounts": [
        "الحسابات",
        "حسابات التواصل",
        "منصات التواصل",
        "منصات التواصل الاجتماعي",
        "الحسابات الرسمية",
    ],
}

_ALL_LABELS = {label for labels in _LABELS.values() for label in labels}
_PLATFORM_LABELS = [
    "سناب شات",
    "تيك توك",
    "يوتيوب",
    "انستقرام",
    "تويتر",
    "Snapchat",
    "TikTok",
    "YouTube",
    "Instagram",
    "Twitter",
    "X",
]
_PLATFORM_LABEL_REGEX = re.compile(
    r"(سناب\s*شات|تيك\s*توك|يوتيوب|انستقرام|تويتر|snapchat|tiktok|youtube|instagram|twitter|\bx\b)",
    re.IGNORECASE,
)


def parse_gcam_html(html_text: str) -> dict:
    parser = _GcamHtmlParser()
    parser.feed(html_text)

    pairs = _extract_pairs_from_tables(parser.rows)
    text_block = "\n".join(parser.text_chunks)
    normalized = normalize_text(text_block)
    lines = normalized.split("\n")

    license_number = _extract_value(pairs, lines, _LABELS["license_number"])
    owner_name = _extract_value(pairs, lines, _LABELS["owner_name"])
    license_title = _extract_value(pairs, lines, _LABELS["license_title"])
    issue_date = _extract_date(pairs, lines, _LABELS["issue_date"])
    expiry_date = _extract_date(pairs, lines, _LABELS["expiry_date"])
    status = _extract_value(pairs, lines, _LABELS["status"])
    accounts = _extract_accounts(parser.rows, normalized, parser.list_items)

    return {
        "license_number": license_number,
        "owner_name": owner_name,
        "license_title": license_title,
        "issue_date": issue_date,
        "expiry_date": expiry_date,
        "status": status,
        "accounts": accounts,
    }


class _GcamHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self.text_chunks: list[str] = []
        self.list_items: list[str] = []
        self._current_row: list[str] = []
        self._current_cell: list[str] = []
        self._current_li: list[str] = []
        self._in_cell = False
        self._in_li = False
        self._skip = False

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip = True
            return
        if tag in {"td", "th"}:
            self._in_cell = True
            self._current_cell = []
        if tag == "li":
            self._in_li = True
            self._current_li = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip = False
            return
        if tag in {"td", "th"}:
            self._in_cell = False
            value = "".join(self._current_cell).strip()
            self._current_row.append(value)
        if tag == "li":
            self._in_li = False
            value = "".join(self._current_li).strip()
            if value:
                self.list_items.append(value)
        if tag == "tr":
            if len(self._current_row) >= 2:
                self.rows.append(self._current_row[:])
            self._current_row = []

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        if data.strip():
            self.text_chunks.append(data)
        if self._in_cell:
            self._current_cell.append(data)
        if self._in_li:
            self._current_li.append(data)


def _extract_pairs_from_tables(rows: list[list[str]]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for cells in rows:
        if len(cells) >= 2:
            label = normalize_text(cells[0])
            value = normalize_text(cells[1])
            if label and value:
                pairs.append((label, value))
    return pairs


def _extract_value(pairs: list[tuple[str, str]], lines: list[str], labels: List[str]) -> Optional[str]:
    for label in labels:
        for pair_label, pair_value in pairs:
            if label.lower() in pair_label.lower():
                return _clean_value(pair_value)

    for idx, line in enumerate(lines):
        line_lower = line.lower()
        for label in labels:
            position = line_lower.find(label.lower())
            if position >= 0:
                tail = line[position + len(label) :].strip()
                value = _clean_value(tail)
                if value:
                    return value
                if idx + 1 < len(lines):
                    value = _clean_value(lines[idx + 1])
                    if value:
                        return value
    return None


def _extract_date(pairs: list[tuple[str, str]], lines: list[str], labels: List[str]) -> Optional[str]:
    value = _extract_value(pairs, lines, labels)
    if not value:
        return None
    return parse_date(value)


def _extract_accounts(rows: list[list[str]], normalized_text: str, list_items: list[str]) -> list[dict]:
    candidates: list[str] = []

    for item in list_items:
        if not item or not item.strip():
            continue
        if _PLATFORM_LABEL_REGEX.search(item) and re.search(r"[-–—:]", item):
            candidates.append(item.strip())

    for cells in rows:
        if len(cells) < 2:
            continue
        label = normalize_text(cells[0])
        if "الحسابات" in label:
            value = cells[1]
            candidates.extend(_split_accounts(value))

    if not candidates:
        candidates.extend(_extract_account_lines_from_text(normalized_text))

    return _split_account_entries(candidates)


def _collect_account_lines(lines: list[str]) -> list[str]:
    collected: list[str] = []
    for line in lines:
        if _contains_label(line):
            break
        collected.extend(_split_accounts(line))
    return collected


def _contains_label(text: str) -> bool:
    lowered = text.lower()
    return any(label.lower() in lowered for label in _ALL_LABELS)


def _split_accounts(text: str) -> list[str]:
    text = _clean_value(text)
    if not text:
        return []
    tokens = re.split(r"[\n\r]+|[،,;]+|[•·]+", text)
    return [token.strip() for token in tokens if token and token.strip()]


def _clean_value(value: str) -> str:
    value = value.strip().strip(":-–")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _split_account_entries(items: list[str]) -> list[dict]:
    accounts: list[dict] = []
    for item in items:
        entry = _split_account_entry(item)
        if entry:
            accounts.append(entry)
    return _dedupe_accounts(accounts)


def _split_account_entry(value: str) -> Optional[dict]:
    value = _clean_value(value)
    if not value:
        return None
    parsed = parse_account_entry(value)
    if not parsed:
        return None
    platform, handle = parsed
    return {"platform": platform, "handle": handle}
    return None


def _dedupe_accounts(items: list[dict]) -> list[dict]:
    seen = set()
    ordered: list[dict] = []
    for item in items:
        key = (item.get("platform"), item.get("handle"))
        if key in seen:
            continue
        seen.add(key)
        ordered.append(item)
    return ordered


def _looks_like_handle(value: str | None) -> bool:
    if not value:
        return False
    return "@" in value or value.startswith("http") or value.startswith("www")


def _extract_account_lines_from_text(text: str) -> list[str]:
    lines = text.split("\n")
    candidates: list[str] = []
    for line in lines:
        if not _PLATFORM_LABEL_REGEX.search(line):
            continue
        if not re.search(r"[-–—:]", line):
            continue
        segments = re.split(r"[|/]+|[،;]+", line)
        for segment in segments:
            if _PLATFORM_LABEL_REGEX.search(segment) and re.search(r"[-–—:]", segment):
                candidates.append(segment.strip())
    return candidates
