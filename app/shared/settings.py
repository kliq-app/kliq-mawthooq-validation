from __future__ import annotations

from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _split_csv(value: str) -> List[str]:
    return [item.strip().lower() for item in value.split(",") if item.strip()]


def _split_csv_raw(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        env_ignore_empty=True,
    )

    app_env: str = Field("dev", alias="APP_ENV")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    max_download_mb: int = Field(25, alias="MAX_DOWNLOAD_MB")
    request_timeout_sec: int = Field(20, alias="REQUEST_TIMEOUT_SEC")
    allowed_domains: List[str] | str = Field(default_factory=list, alias="ALLOWED_DOMAINS")
    api_keys: List[str] | str = Field(default_factory=list, alias="API_KEYS")
    rate_limit_per_min: int = Field(60, alias="RATE_LIMIT_PER_MIN")
    redis_url: str | None = Field(None, alias="REDIS_URL")
    metrics_enabled: bool = Field(False, alias="METRICS_ENABLED")
    extract_debug: bool = Field(False, alias="EXTRACT_DEBUG")
    ocr_enabled: bool = Field(True, alias="OCR_ENABLED")
    ocr_language: str = Field("ara+eng", alias="OCR_LANGUAGE")
    max_ocr_pages: int = Field(2, alias="MAX_OCR_PAGES")
    min_arabic_ratio: float = Field(0.05, alias="MIN_ARABIC_RATIO")
    min_text_length: int = Field(50, alias="MIN_TEXT_LENGTH")
    gcam_lookup_enabled: bool = Field(True, alias="GCAM_LOOKUP_ENABLED")
    gcam_base_url: str = Field("https://elaam.gmedia.gov.sa", alias="GCAM_BASE_URL")
    gcam_lookup_timeout_sec: int = Field(15, alias="GCAM_LOOKUP_TIMEOUT_SEC")
    gcam_lookup_retry_count: int = Field(2, alias="GCAM_LOOKUP_RETRY_COUNT")
    gcam_cb_failure_threshold: int = Field(5, alias="GCAM_CB_FAILURE_THRESHOLD")
    gcam_cb_reset_sec: int = Field(60, alias="GCAM_CB_RESET_SEC")

    @field_validator("allowed_domains", mode="before")
    @classmethod
    def parse_allowed_domains(cls, value: object) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return _split_csv(value)
        if isinstance(value, list):
            return [str(item).lower() for item in value]
        return []

    @field_validator("api_keys", mode="before")
    @classmethod
    def parse_api_keys(cls, value: object) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return _split_csv_raw(value)
        if isinstance(value, list):
            return [str(item) for item in value]
        return []

    @field_validator("redis_url", mode="before")
    @classmethod
    def parse_redis_url(cls, value: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return str(value)


settings = Settings()
