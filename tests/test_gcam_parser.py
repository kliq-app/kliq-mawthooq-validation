from pathlib import Path

from app.infrastructure.portal.gcam_parser import parse_gcam_html


def test_parse_gcam_html_fixture() -> None:
    fixture = Path("tests/fixtures/gcam_sample.html").read_text(encoding="utf-8")
    parsed = parse_gcam_html(fixture)

    assert parsed["license_number"] == "12345"
    assert parsed["owner_name"] == "شركة الاختبار"
    assert parsed["license_title"] == "ترخيص إعلامي"
    assert parsed["issue_date"] == "2024-03-01"
    assert parsed["expiry_date"] == "2025-03-01"
    assert parsed["status"] == "ساري"
    assert {"platform": "twitter", "handle": "@test_account"} in parsed["accounts"]
    assert {"platform": "instagram", "handle": "@insta_example"} in parsed["accounts"]
    assert {"platform": "snapchat", "handle": "Mousaday"} in parsed["accounts"]


def test_parse_gcam_html_accounts_from_fixture_162995() -> None:
    fixture = Path("test.html").read_text(encoding="utf-8")
    parsed = parse_gcam_html(fixture)

    assert parsed["accounts"]
    assert {"platform": "snapchat", "handle": "Mousaday"} in parsed["accounts"]
