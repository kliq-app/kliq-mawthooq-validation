import pytest

from app.domain.models import AccountHandle, ExtractionFields
from app.shared.utils import calculate_confidence, is_allowed_domain


class TestCalculateConfidence:
    """Tests for calculate_confidence function."""

    def test_empty_fields_returns_minimum(self) -> None:
        fields = ExtractionFields()
        result = calculate_confidence(fields)
        assert result == 0.20

    def test_license_number_adds_weight(self) -> None:
        fields = ExtractionFields(license_number="ABC123")
        result = calculate_confidence(fields)
        assert result == 0.45  # 0.20 base + 0.25

    def test_all_fields_without_official_lookup(self) -> None:
        fields = ExtractionFields(
            license_number="ABC123",
            status="active",
            issue_date="2024-01-01",
            expiry_date="2025-01-01",
            accounts=[AccountHandle(platform="instagram", handle="@test")],
            owner_name="Test User",
        )
        result = calculate_confidence(fields)
        # 0.20 + 0.25 + 0.10 + 0.10 + 0.10 + 0.10 + 0.10 = 0.95
        assert result == 0.95

    def test_all_fields_with_official_lookup(self) -> None:
        fields = ExtractionFields(
            license_number="ABC123",
            status="active",
            issue_date="2024-01-01",
            expiry_date="2025-01-01",
            accounts=[AccountHandle(platform="instagram", handle="@test")],
            owner_name="Test User",
        )
        result = calculate_confidence(fields, official_lookup_ok=True)
        # Would be 1.05 but capped at 0.95
        assert result == 0.95

    def test_partial_fields(self) -> None:
        fields = ExtractionFields(
            license_number="ABC123",
            status="active",
        )
        result = calculate_confidence(fields)
        # 0.20 + 0.25 + 0.10 = 0.55
        assert result == 0.55

    def test_official_lookup_only(self) -> None:
        fields = ExtractionFields()
        result = calculate_confidence(fields, official_lookup_ok=True)
        # 0.20 + 0.10 = 0.30
        assert result == 0.30

    def test_accounts_empty_list_not_counted(self) -> None:
        fields = ExtractionFields(accounts=[])
        result = calculate_confidence(fields)
        assert result == 0.20

    def test_result_is_rounded(self) -> None:
        fields = ExtractionFields(license_number="ABC123")
        result = calculate_confidence(fields)
        assert result == round(result, 2)


class TestIsAllowedDomain:
    """Tests for is_allowed_domain function."""

    def test_exact_match(self) -> None:
        assert is_allowed_domain("example.com", ["example.com"]) is True

    def test_subdomain_match(self) -> None:
        assert is_allowed_domain("sub.example.com", ["example.com"]) is True

    def test_deep_subdomain_match(self) -> None:
        assert is_allowed_domain("deep.sub.example.com", ["example.com"]) is True

    def test_no_match(self) -> None:
        assert is_allowed_domain("other.com", ["example.com"]) is False

    def test_partial_domain_no_match(self) -> None:
        # "notexample.com" should NOT match "example.com"
        assert is_allowed_domain("notexample.com", ["example.com"]) is False

    def test_case_insensitive(self) -> None:
        assert is_allowed_domain("EXAMPLE.COM", ["example.com"]) is True
        assert is_allowed_domain("example.com", ["EXAMPLE.COM"]) is True

    def test_trailing_dots_stripped(self) -> None:
        assert is_allowed_domain("example.com.", ["example.com"]) is True
        assert is_allowed_domain("example.com", ["example.com."]) is True

    def test_multiple_allowed_domains(self) -> None:
        allowed = ["example.com", "allowed.org", "test.net"]
        assert is_allowed_domain("example.com", allowed) is True
        assert is_allowed_domain("allowed.org", allowed) is True
        assert is_allowed_domain("test.net", allowed) is True
        assert is_allowed_domain("other.com", allowed) is False

    def test_empty_allowed_list(self) -> None:
        assert is_allowed_domain("example.com", []) is False

    def test_accepts_iterable(self) -> None:
        # Test with tuple
        assert is_allowed_domain("example.com", ("example.com",)) is True
        # Test with set
        assert is_allowed_domain("example.com", {"example.com"}) is True
        # Test with generator
        assert is_allowed_domain("example.com", (d for d in ["example.com"])) is True
