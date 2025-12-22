from app.application.use_cases.extract_document import _calculate_confidence, _merge_fields
from app.domain.models import AccountHandle, ExtractionFields, OfficialData


def test_merge_official_overwrites_extracted() -> None:
    extracted = ExtractionFields(
        license_number="123",
        owner_name="Extracted Owner",
        license_title="Extracted Title",
        issue_date="2024-01-01",
        expiry_date="2025-01-01",
        status="pending",
    )
    official = OfficialData(
        license_number="456",
        owner_name="Official Owner",
        license_title=None,
        issue_date="2024-02-01",
        expiry_date=None,
        status="active",
    )

    merged = _merge_fields(extracted, official)

    assert merged.license_number == "456"
    assert merged.owner_name == "Official Owner"
    assert merged.license_title == "Extracted Title"
    assert merged.issue_date == "2024-02-01"
    assert merged.expiry_date == "2025-01-01"
    assert merged.status == "active"


def test_confidence_increases_with_fields() -> None:
    base = _calculate_confidence(ExtractionFields(), False)
    with_license = _calculate_confidence(ExtractionFields(license_number="123"), False)
    with_more = _calculate_confidence(
        ExtractionFields(
            license_number="123",
            status="active",
            issue_date="2024-01-01",
            expiry_date="2025-01-01",
            owner_name="Example Owner",
            accounts=[AccountHandle(platform="twitter", handle="@example")],
        ),
        False,
    )

    assert base < with_license < with_more


def test_confidence_increases_with_official_lookup() -> None:
    fields = ExtractionFields(license_number="123")
    without_lookup = _calculate_confidence(fields, False)
    with_lookup = _calculate_confidence(fields, True)

    assert with_lookup > without_lookup
