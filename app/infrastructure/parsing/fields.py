from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Iterable, Optional

from app.domain.models import AccountHandle, ExtractionFields


_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

_DATE_PATTERN = re.compile(
    r"(?P<first>\d{1,4})[\-/](?P<second>\d{1,2})[\-/](?P<third>\d{2,4})"
)
_LICENSE_REGEX = re.compile(
    r"(?:رقم الرخصة|رقم الترخيص|license number|licnumber|license no)\s*[:：\-]?\s*([A-Za-z0-9/\-]{3,})",
    re.IGNORECASE,
)
_LICENSE_LABEL_PATTERN = (
    r"(?:رقم\s*الرخصة|رقم\s*الترخيص|license\s*number|licnumber|license\s*no)"
)
_LICENSE_NUMBER_AFTER_LABEL_RE = re.compile(
    rf"{_LICENSE_LABEL_PATTERN}\s*[:：]?\s*(\d{{3,}})",
    re.IGNORECASE,
)
_LICENSE_NUMBER_BEFORE_LABEL_RE = re.compile(
    rf"(\d{{3,}})\s*[:：]?\s*{_LICENSE_LABEL_PATTERN}",
    re.IGNORECASE,
)
_LICENSE_URL_REGEX = re.compile(r"gcam-licenses/gcam-celebrity-check/([A-Za-z0-9\-]+)", re.IGNORECASE)
_PLATFORM_ALIASES = {
    "سنابشات": "snapchat",
    "snapchat": "snapchat",
    "تيكتوك": "tiktok",
    "tiktok": "tiktok",
    "يوتيوب": "youtube",
    "youtube": "youtube",
    "انستقرام": "instagram",
    "instagram": "instagram",
    "تويتر": "twitter",
    "twitter": "twitter",
    "x": "twitter",
}
_OWNER_LABELS = [
    "اسم المالك",
    "اسم صاحب الترخيص",
    "الاسم",
    "Owner Name",
]
_MAWTHOOQ_OWNER_LABEL = re.compile(r"Mawthooq_\d+_Name\s*/\s*الاسم", re.IGNORECASE)
_OWNER_LABEL_PATTERNS = [
    re.compile(r"اسم المالك\s*[:：]?\s*(?P<value>.*)$", re.IGNORECASE),
    re.compile(r"اسم صاحب الترخيص\s*[:：]?\s*(?P<value>.*)$", re.IGNORECASE),
    re.compile(r"Owner Name\s*[:：]?\s*(?P<value>.*)$", re.IGNORECASE),
    re.compile(r"الاسم\s*[:：]?\s*(?P<value>.*)$", re.IGNORECASE),
]


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.translate(_ARABIC_DIGITS)
    text = text.replace("،", ",").replace("؛", ";")
    text = text.replace("\u200f", " ").replace("\u200e", " ")
    text = text.replace("ـ", "")
    lines = []
    for line in text.split("\n"):
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def arabic_ratio(text: str) -> float:
    if not text:
        return 0.0
    arabic_chars = re.findall(r"[\u0600-\u06FF]", text)
    letters = re.findall(r"[A-Za-z\u0600-\u06FF]", text)
    if not letters:
        return 0.0
    return len(arabic_chars) / len(letters)


def _clean_value(value: str) -> str:
    value = value.strip().strip(":-–")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _normalize_for_match(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[\s:،؛,_./\\|\-]+", "", text)
    return text


def _label_pattern(label: str) -> re.Pattern[str]:
    parts = [re.escape(char) for char in label if not char.isspace()]
    pattern = r"[\s:،؛,_./\\|\-]*".join(parts)
    return re.compile(pattern, re.IGNORECASE)


def _extract_labeled_value(lines: list[str], labels: Iterable[str]) -> Optional[str]:
    patterns = [(label, _label_pattern(label)) for label in labels]
    labels_norm = [_normalize_for_match(label) for label in labels]
    for idx, line in enumerate(lines):
        normalized_line = _normalize_for_match(line)
        for (label, pattern), label_norm in zip(patterns, labels_norm):
            if label_norm and label_norm not in normalized_line:
                continue
            match = pattern.search(line)
            if match:
                tail = line[match.end() :].strip()
                candidate = _clean_value(tail)
                if candidate:
                    return candidate
                if idx + 1 < len(lines):
                    candidate = _clean_value(lines[idx + 1])
                    if candidate:
                        return candidate
    return None


def _extract_date_for_labels(lines: list[str], labels: Iterable[str]) -> Optional[str]:
    value = _extract_labeled_value(lines, labels)
    if not value:
        return None
    return parse_date(value)


def has_pdf_text_signal(normalized_text: str) -> bool:
    if not normalized_text:
        return False
    if re.search(r"رقم\s*الرخصة", normalized_text):
        return True
    if _LICENSE_NUMBER_AFTER_LABEL_RE.search(normalized_text):
        return True
    if _LICENSE_NUMBER_BEFORE_LABEL_RE.search(normalized_text):
        return True
    if _DATE_PATTERN.search(normalized_text):
        return True
    return False


def extract_owner_name(text: str) -> Optional[str]:
    normalized = normalize_text(text)
    if not normalized:
        return None

    lines = normalized.split("\n")

    for idx, line in enumerate(lines):
        if _MAWTHOOQ_OWNER_LABEL.search(line):
            candidate = _extract_owner_value_from_line(line, _MAWTHOOQ_OWNER_LABEL)
            owner_name = _normalize_owner_value(candidate)
            if _is_valid_owner_name(owner_name):
                return owner_name
            if idx + 1 < len(lines):
                owner_name = _normalize_owner_value(lines[idx + 1])
                if _is_valid_owner_name(owner_name):
                    return owner_name

    for idx, line in enumerate(lines):
        for pattern in _OWNER_LABEL_PATTERNS:
            match = pattern.search(line)
            if not match:
                continue
            candidate = _normalize_owner_value(match.group("value"))
            if not candidate and idx + 1 < len(lines):
                candidate = _normalize_owner_value(lines[idx + 1])
            if _is_valid_owner_name(candidate):
                return candidate

    fallback = _normalize_owner_value(_extract_labeled_value(lines, _OWNER_LABELS))
    if _is_valid_owner_name(fallback):
        return fallback
    return None


def _extract_owner_value_from_line(line: str, pattern: re.Pattern[str]) -> str:
    match = pattern.search(line)
    if not match:
        return ""
    return line[match.end() :].strip()


def _normalize_owner_value(value: Optional[str]) -> str:
    if not value:
        return ""
    value = re.sub(r"[:：]+", " ", value)
    value = re.sub(r"[\\/|]+", " ", value)
    value = re.sub(r"[-–—]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    value = value.strip(" :：/-–—|")
    return value.strip()


def _is_valid_owner_name(value: str) -> bool:
    if not value:
        return False
    if len(value) < 5:
        return False
    if re.fullmatch(r"\d+", value):
        return False
    if parse_date(value):
        return False
    lowered = value.lower()
    if "license" in lowered or "ترخيص" in value:
        return False
    if not re.search(r"[A-Za-z\u0600-\u06FF]", value):
        return False
    return True


def parse_date(value: str) -> Optional[str]:
    match = _DATE_PATTERN.search(value)
    if not match:
        return None

    first = match.group("first")
    second = match.group("second")
    third = match.group("third")

    if len(first) == 4:
        year = int(first)
        month = int(second)
        day = int(third)
    elif len(third) == 4:
        year = int(third)
        month = int(second)
        day = int(first)
    else:
        return None

    try:
        date = datetime(year, month, day)
    except ValueError:
        return None
    return date.strftime("%Y-%m-%d")


def extract_fields_from_text(text: str) -> ExtractionFields:
    normalized = normalize_text(text)
    lines = normalized.split("\n")

    license_number = _extract_license_number(normalized, lines)
    if not license_number:
        match = _LICENSE_URL_REGEX.search(normalized)
        if match:
            license_number = _clean_value(match.group(1))

    owner_name = extract_owner_name(text)
    if not owner_name:
        owner_name = _extract_labeled_value(
            lines,
            ["اسم المالك", "اسم المرخص له", "اسم صاحب الرخصة", "صاحب الترخيص", "المالك", "owner name"],
        )

    id_number = _extract_labeled_value(
        lines,
        ["رقم الهوية", "هوية", "id number", "id no"],
    )

    issue_date = _extract_date_for_labels(
        lines,
        ["تاريخ الاصدار", "تاريخ الإصدار", "issue date", "تاريخ الاصدار"],
    )

    expiry_date = _extract_date_for_labels(
        lines,
        ["تاريخ الانتهاء", "تاريخ الإنتهاء", "expiry date", "تاريخ الانتهاء"],
    )
    if not issue_date or not expiry_date:
        fallback_issue, fallback_expiry = _extract_unlabeled_dates_after_license(lines)
        if not issue_date:
            issue_date = fallback_issue
        if not expiry_date:
            expiry_date = fallback_expiry

    city = _extract_labeled_value(lines, ["المدينة", "city"])
    district = _extract_labeled_value(lines, ["الحي", "district"])
    street = _extract_labeled_value(lines, ["الشارع", "street"])

    license_title = _extract_labeled_value(
        lines,
        ["نوع الترخيص", "نوع الرخصة", "license type", "license title", "اسم الرخصة"],
    )
    if not license_title:
        for line in lines:
            if "ترخيص" in line and "رقم" not in line and "تاريخ" not in line:
                license_title = _clean_value(line)
                break
            if "بطاقة موثوق" in line:
                license_title = _clean_value(line)
                break

    status = _extract_labeled_value(lines, ["الحالة", "status"])
    accounts = _extract_accounts(lines)

    if not city or not district or not street:
        city, district, street = _fill_address_from_line(lines, city, district, street)

    return ExtractionFields(
        license_number=license_number,
        owner_name=owner_name,
        id_number=id_number,
        issue_date=issue_date,
        expiry_date=expiry_date,
        city=city,
        district=district,
        street=street,
        license_title=license_title,
        status=status,
        accounts=accounts,
    )


def _extract_license_number(normalized: str, lines: list[str]) -> Optional[str]:
    license_number = _extract_labeled_value(
        lines,
        ["رقم الرخصة", "رقم الترخيص", "license number", "licnumber", "license no"],
    )
    if license_number:
        return license_number
    match = _LICENSE_NUMBER_AFTER_LABEL_RE.search(normalized)
    if match:
        return _clean_value(match.group(1))
    match = _LICENSE_NUMBER_BEFORE_LABEL_RE.search(normalized)
    if match:
        return _clean_value(match.group(1))
    match = _LICENSE_REGEX.search(normalized)
    if match:
        return _clean_value(match.group(1))
    return None


def _extract_unlabeled_dates_after_license(
    lines: list[str],
) -> tuple[Optional[str], Optional[str]]:
    license_index = None
    for idx, line in enumerate(lines):
        if re.search(r"رقم\s*الرخصة", line):
            license_index = idx
            break
    if license_index is None:
        return None, None

    dates: list[str] = []
    for line in lines[license_index + 1 : license_index + 5]:
        for match in _DATE_PATTERN.finditer(line):
            parsed = parse_date(match.group(0))
            if parsed:
                dates.append(parsed)
        if len(dates) >= 2:
            break

    if len(dates) >= 2:
        return dates[0], dates[1]
    return None, None


def _fill_address_from_line(
    lines: list[str],
    city: Optional[str],
    district: Optional[str],
    street: Optional[str],
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    address_labels = ["العنوان الوطني", "العنوان", "عنوان"]
    for line in lines:
        for label in address_labels:
            if label in line:
                tail = line.split(label, 1)[-1]
                parts = [part.strip() for part in re.split(r"[-–—/,|،]+", tail) if part.strip()]
                if parts:
                    if not city and len(parts) >= 1:
                        city = parts[0]
                    if not district and len(parts) >= 2:
                        district = parts[1]
                    if not street and len(parts) >= 3:
                        street = parts[2]
                return city, district, street
    return city, district, street


def _extract_accounts(lines: list[str]) -> list[AccountHandle]:
    labels = ["الحسابات", "حسابات التواصل", "منصات التواصل", "الحسابات الرسمية"]
    for idx, line in enumerate(lines):
        if any(label in line for label in labels):
            candidates = [line] + lines[idx + 1 : idx + 5]
            return _parse_account_lines(candidates)
    return []


def _parse_account_lines(lines: list[str]) -> list[AccountHandle]:
    accounts: list[AccountHandle] = []
    for line in lines:
        tokens = re.split(r"[;،,]+", line)
        for token in tokens:
            token = token.strip()
            if not token:
                continue
            account = _split_account_entry(token)
            if account:
                accounts.append(account)
    return _dedupe_accounts(accounts)


def _split_account_entry(value: str) -> Optional[AccountHandle]:
    parsed = parse_account_entry(value)
    if not parsed:
        return None
    platform, handle = parsed
    return AccountHandle(platform=platform, handle=handle)


def _dedupe_accounts(accounts: list[AccountHandle]) -> list[AccountHandle]:
    seen: set[tuple[Optional[str], str]] = set()
    output: list[AccountHandle] = []
    for account in accounts:
        key = (account.platform, account.handle)
        if key in seen:
            continue
        seen.add(key)
        output.append(account)
    return output


def parse_account_entry(value: str) -> Optional[tuple[str, str]]:
    cleaned = _clean_account_value(value)
    if not cleaned:
        return None
    parts = re.split(r"\s*[-–—:]\s*", cleaned, maxsplit=1)
    if len(parts) != 2:
        return None
    left, right = [part.strip() for part in parts]
    if not left or not right:
        return None

    platform_left = _normalize_platform_label(left)
    platform_right = _normalize_platform_label(right)

    if platform_left and not platform_right:
        platform = platform_left
        handle = right
    elif platform_right and not platform_left:
        platform = platform_right
        handle = left
    else:
        return None

    handle = _clean_account_handle(handle)
    if not _is_valid_handle(handle, platform):
        return None
    return platform, handle


def _normalize_platform_label(value: str | None) -> Optional[str]:
    if not value:
        return None
    normalized = _strip_account_noise(value).lower()
    normalized = re.sub(r"[\s_./|]+", "", normalized)
    normalized = re.sub(r"[-–—]+", "", normalized)
    if not normalized:
        return None
    return _PLATFORM_ALIASES.get(normalized)


def _clean_account_value(value: str) -> str:
    value = value.strip()
    value = _strip_account_noise(value)
    value = value.replace("—", "-").replace("–", "-")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _strip_account_noise(value: str) -> str:
    value = re.sub(r"^[\\s•*·-]+", "", value)
    value = re.sub(r"[•*·]+$", "", value)
    return value.strip()


def _clean_account_handle(value: str) -> str:
    value = _strip_account_noise(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _is_valid_handle(handle: str, platform: str) -> bool:
    if not handle:
        return False
    if _normalize_platform_label(handle):
        return False
    return handle.lower() != platform
