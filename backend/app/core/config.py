"""Application settings. All values come from environment variables.

Pydantic-settings v2 with strict typing. The single source of truth for the
process-wide configuration. Never read os.environ directly elsewhere — go
through `settings`.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    ENVIRONMENT: Literal["development", "staging", "production", "test"] = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    APP_NAME: str = "ERP System"
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    BACKEND_WORKERS: int = 1
    RUN_MIGRATIONS_ON_STARTUP: bool = False

    # --- Database ---
    POSTGRES_USER: str = "erp_admin"
    POSTGRES_PASSWORD: str = "change_me"  # noqa: S105 - development-only fallback
    POSTGRES_DB: str = "erp_db"
    POSTGRES_HOST: str = "db"
    POSTGRES_PORT: int = 5432
    POSTGRES_TEST_DB: str = "erp_db_test"
    DATABASE_URL: str = "postgresql+asyncpg://erp_admin:change_me@db:5432/erp_db"
    DATABASE_URL_SYNC: str = "postgresql://erp_admin:change_me@db:5432/erp_db"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800
    DB_ECHO: bool = False

    # --- JWT ---
    JWT_SECRET_KEY: str = Field(default="CHANGE_ME", repr=False)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # --- Argon2 ---
    ARGON2_TIME_COST: int = 3
    ARGON2_MEMORY_COST: int = 65536
    ARGON2_PARALLELISM: int = 4

    # --- Rate limiting (strings consumed by slowapi or custom middleware) ---
    LOGIN_RATE_LIMIT: str = "10/minute"
    REFRESH_RATE_LIMIT: str = "30/minute"
    RESET_RATE_LIMIT: str = "5/minute"

    # --- Cookies / security ---
    SECURE_COOKIES: bool = True
    CORS_ORIGINS: str = (
        "http://localhost:5173,http://127.0.0.1:5173,https://proyecto-erp-one.vercel.app"
    )
    CORS_ORIGIN_REGEX: str | None = r"https://.*\.vercel\.app"

    # --- Redis / background processing ---
    REDIS_ENABLED: bool = False
    REDIS_URL: str | None = None
    REDIS_PASSWORD: str | None = Field(default=None, repr=False)
    REDIS_CONNECT_TIMEOUT_SECONDS: float = Field(default=0.2, ge=0.05, le=5)
    OCR_ENABLED: bool = False
    OCR_LANGUAGES: str = "spa+eng"
    OCR_JOB_TIMEOUT_SECONDS: int = Field(default=900, ge=60, le=3600)
    OCR_TESSERACT_TIMEOUT_SECONDS: int = Field(default=120, ge=10, le=600)
    OCR_MAX_PAGES: int = Field(default=300, ge=1, le=2000)
    OCR_MAX_OUTPUT_BYTES: int = Field(default=100 * 1024 * 1024, ge=1024, le=200 * 1024 * 1024)
    OCR_SKIP_BIG_MPIX: int = Field(default=50, ge=1, le=500)
    OCR_MAX_ATTEMPTS: int = Field(default=3, ge=1, le=10)
    OCR_STALE_MINUTES: int = Field(default=20, ge=5, le=1440)
    OCR_RECONCILE_SECONDS: int = Field(default=15, ge=5, le=60)

    # --- Media / Cloudinary ---
    UPLOADS_DIR: str = "/app/uploads"
    CLOUDINARY_CLOUD_NAME: str | None = None
    CLOUDINARY_API_KEY: str | None = None
    CLOUDINARY_API_SECRET: str | None = Field(default=None, repr=False)
    CLOUDINARY_UPLOAD_FOLDER: str = "erp-system"
    MEDIA_MAX_IMAGE_BYTES: int = 10 * 1024 * 1024
    MEDIA_SIGNATURE_TTL_SECONDS: int = 300
    SUPPLIER_DATA_ENCRYPTION_KEY: str | None = Field(default=None, repr=False)

    # --- Generic documents / S3-compatible object storage ---
    OBJECT_STORAGE_ENABLED: bool = False
    OBJECT_STORAGE_INTERNAL_ENDPOINT: str = "http://rustfs:9000"
    OBJECT_STORAGE_PUBLIC_ENDPOINT: str = "http://localhost:9000"
    OBJECT_STORAGE_REGION: str = "us-east-1"
    OBJECT_STORAGE_BUCKET: str = "erp-documents"
    OBJECT_STORAGE_CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    OBJECT_STORAGE_ACCESS_KEY: str | None = None
    OBJECT_STORAGE_SECRET_KEY: str | None = Field(default=None, repr=False)
    OBJECT_STORAGE_UPLOAD_TTL_SECONDS: int = Field(default=600, ge=60, le=3600)
    OBJECT_STORAGE_DOWNLOAD_TTL_SECONDS: int = Field(default=300, ge=30, le=3600)
    DOCUMENT_MAX_BYTES: int = Field(default=50 * 1024 * 1024, ge=1, le=50 * 1024 * 1024)
    DOCUMENT_MAX_PENDING_PER_USER: int = Field(default=20, ge=1, le=100)
    DOCUMENT_PENDING_RETENTION_HOURS: int = Field(default=24, ge=1, le=168)
    DOCUMENT_QUARANTINE_RETENTION_DAYS: int = Field(default=7, ge=1, le=365)
    DOCUMENT_DELETION_RETENTION_DAYS: int = Field(default=30, ge=1, le=3650)
    DOCUMENT_SCAN_STALE_MINUTES: int = Field(default=15, ge=5, le=1440)
    DOCUMENT_MAINTENANCE_INTERVAL_SECONDS: int = Field(default=3600, ge=60, le=86400)
    CLAMAV_HOST: str = "clamav"
    CLAMAV_PORT: int = Field(default=3310, ge=1, le=65535)
    CLAMAV_TIMEOUT_SECONDS: int = Field(default=120, ge=5, le=600)

    # --- Vendor-neutral observability (OpenTelemetry/OTLP) ---
    OBSERVABILITY_ENABLED: bool = False
    OTEL_EXPORTER_OTLP_ENDPOINT: str | None = None
    OTEL_EXPORTER_OTLP_HEADERS: str | None = Field(default=None, repr=False)
    OTEL_EXPORTER_OTLP_TIMEOUT_SECONDS: float = Field(default=3.0, ge=0.1, le=30)
    OTEL_METRIC_EXPORT_INTERVAL_SECONDS: int = Field(default=15, ge=5, le=300)
    OTEL_SERVICE_NAMESPACE: str = "erp"
    OTEL_TRACE_SAMPLE_RATIO: float | None = Field(default=None, ge=0, le=1)
    OTEL_EXPORTER_OTLP_INSECURE: bool = False
    OBSERVABILITY_HEALTH_URL: str | None = None
    OBSERVABILITY_HEALTH_TIMEOUT_SECONDS: float = Field(default=0.5, ge=0.1, le=5)
    GRAFANA_ADMIN_USER: str = "admin"
    GRAFANA_ADMIN_PASSWORD: str | None = Field(default=None, repr=False)

    # --- Convenient computed fields ---

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_test(self) -> bool:
        return self.ENVIRONMENT == "test"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def object_storage_cors_origin_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.OBJECT_STORAGE_CORS_ORIGINS.split(",")
            if origin.strip()
        ]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def otel_trace_sample_ratio(self) -> float:
        if self.OTEL_TRACE_SAMPLE_RATIO is not None:
            return self.OTEL_TRACE_SAMPLE_RATIO
        return 1.0 if self.ENVIRONMENT in {"development", "test"} else 0.1

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def _secret_not_default(cls, v: str) -> str:
        if (
            v in {"CHANGE_ME", "", "CHANGE_ME_USE_openssl_rand_hex_64"}
            and cls.model_fields.get("ENVIRONMENT") is None
        ):
            return v
        return v

    @field_validator("LOG_LEVEL")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()

    @model_validator(mode="after")
    def _validate_document_storage(self) -> Settings:
        if self.OBJECT_STORAGE_ENABLED and not (
            self.OBJECT_STORAGE_ACCESS_KEY and self.OBJECT_STORAGE_SECRET_KEY
        ):
            raise ValueError(
                "OBJECT_STORAGE_ACCESS_KEY y OBJECT_STORAGE_SECRET_KEY son obligatorios "
                "cuando OBJECT_STORAGE_ENABLED=true."
            )
        if self.REDIS_ENABLED and not self.REDIS_URL:
            raise ValueError("REDIS_URL es obligatorio cuando REDIS_ENABLED=true.")
        if self.OCR_ENABLED and not self.REDIS_ENABLED:
            raise ValueError("OCR_ENABLED requiere REDIS_ENABLED=true.")
        if self.OBSERVABILITY_ENABLED and not self.OTEL_EXPORTER_OTLP_ENDPOINT:
            raise ValueError(
                "OTEL_EXPORTER_OTLP_ENDPOINT es obligatorio cuando OBSERVABILITY_ENABLED=true."
            )
        if self.OBSERVABILITY_ENABLED and self.OTEL_EXPORTER_OTLP_ENDPOINT:
            endpoint = self.OTEL_EXPORTER_OTLP_ENDPOINT.lower()
            if (
                self.ENVIRONMENT in {"staging", "production"}
                and endpoint.startswith("http://")
                and not self.OTEL_EXPORTER_OTLP_INSECURE
            ):
                raise ValueError(
                    "OTLP por HTTP en staging/production requiere "
                    "OTEL_EXPORTER_OTLP_INSECURE=true; se recomienda HTTPS."
                )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


# Eager singleton — imported widely.
settings = get_settings()
