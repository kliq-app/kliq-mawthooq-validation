from app.infrastructure.parsing.fields import extract_fields_from_text, extract_owner_name, normalize_text, parse_date


def test_normalize_digits() -> None:
    text = "رقم الرخصة ١٢٣٤٥"
    normalized = normalize_text(text)
    assert "12345" in normalized


def test_normalize_nfkc_presentation_forms() -> None:
    text = "ﺭﻗﻢ ﺍﻟﺮﺧﺼﺔ"
    normalized = normalize_text(text)
    assert "رقم الرخصة" in normalized


def test_parse_date_formats() -> None:
    assert parse_date("15/09/2024") == "2024-09-15"
    assert parse_date("2024/09/15") == "2024-09-15"
    assert parse_date("15-09-2024") == "2024-09-15"


def test_extract_license_number() -> None:
    text = "ترخيص إعلامي\nرقم الرخصة: 98765\n"
    fields = extract_fields_from_text(text)
    assert fields.license_number == "98765"


def test_extract_license_number_from_url() -> None:
    text = "تحقق من الترخيص https://elaam.gmedia.gov.sa/gcam-licenses/gcam-celebrity-check/ABC-12345"
    fields = extract_fields_from_text(text)
    assert fields.license_number == "ABC-12345"


def test_extract_license_number_before_label() -> None:
    text = "162995 :ﺭﻗﻢ ﺍﻟﺮﺧﺼﺔ"
    fields = extract_fields_from_text(text)
    assert fields.license_number == "162995"


def test_extract_address_from_combined_line() -> None:
    text = "العنوان الوطني الرياض - النخيل - شارع الملك"
    fields = extract_fields_from_text(text)
    assert fields.city == "الرياض"
    assert fields.district == "النخيل"
    assert fields.street == "شارع الملك"


def test_extract_accounts_from_text() -> None:
    text = "الحسابات الرسمية\nX - @example\nInstagram – @insta_example\n"
    fields = extract_fields_from_text(text)
    assert {"platform": "twitter", "handle": "@example"} in [a.__dict__ for a in fields.accounts]
    assert {"platform": "instagram", "handle": "@insta_example"} in [a.__dict__ for a in fields.accounts]


def test_extract_accounts_swapped_order() -> None:
    text = "الحسابات الرسمية\n@handle - X\n"
    fields = extract_fields_from_text(text)
    assert {"platform": "twitter", "handle": "@handle"} in [a.__dict__ for a in fields.accounts]


def test_extract_accounts_platform_mapping() -> None:
    text = "الحسابات الرسمية\nسناب شات - Mousaday\nMousaday - سناب شات\nInstagram - Mousa.day\nيوتيوب - Heemfit7275\n"
    accounts = [a.__dict__ for a in extract_fields_from_text(text).accounts]
    assert {"platform": "snapchat", "handle": "Mousaday"} in accounts
    assert {"platform": "instagram", "handle": "Mousa.day"} in accounts
    assert {"platform": "youtube", "handle": "Heemfit7275"} in accounts


def test_extract_owner_name_mawthooq_label() -> None:
    text = "Mawthooq_87_Name / الاسم زايد ساير زايد الشهري"
    assert extract_owner_name(text) == "زايد ساير زايد الشهري"


def test_extract_owner_name_gcam_label() -> None:
    text = "اسم المالك: موسى ابراهيم موسى آل جوير"
    assert extract_owner_name(text) == "موسى ابراهيم موسى آل جوير"


def test_extract_gcam_sample_text() -> None:
    text = (
        "الهيئة العامة لتنظيم الإعلام\n"
        "ترخيص إعلامي\n"
        "رقم الرخصة 456789\n"
        "اسم المالك شركة مثال\n"
        "تاريخ الإصدار 2024/01/20\n"
        "تاريخ الانتهاء 20/01/2025\n"
        "المدينة الرياض\n"
    )
    fields = extract_fields_from_text(text)
    assert fields.license_number == "456789"
    assert fields.owner_name == "شركة مثال"
    assert fields.issue_date == "2024-01-20"
    assert fields.expiry_date == "2025-01-20"
    assert fields.city == "الرياض"


def test_extract_unlabeled_dates_after_license() -> None:
    text = "رقم الرخصة 162995\n2024/01/20\n2025/01/20\n"
    fields = extract_fields_from_text(text)
    assert fields.issue_date == "2024-01-20"
    assert fields.expiry_date == "2025-01-20"
