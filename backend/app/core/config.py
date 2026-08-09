"""Application settings. All values come from environment variables.

Pydantic-settings v2 with strict typing. The single source of truth for the
process-wide configuration. Never read os.environ directly elsewhere — go
through `settings`.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
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
    RUN_MIGRATIONS_ON_STARTUP: bool = True

    # --- Database ---
    POSTGRES_USER: str = "erp_admin"
    POSTGRES_PASSWORD: str = "change_me"
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

    # --- Redis (optional) ---
    REDIS_URL: str | None = None

    # --- Media / Cloudinary ---
    UPLOADS_DIR: str = "/app/uploads"
    CLOUDINARY_CLOUD_NAME: str | None = None
    CLOUDINARY_API_KEY: str | None = None
    CLOUDINARY_API_SECRET: str | None = Field(default=None, repr=False)
    CLOUDINARY_UPLOAD_FOLDER: str = "erp-system"
    MEDIA_MAX_IMAGE_BYTES: int = 10 * 1024 * 1024
    MEDIA_SIGNATURE_TTL_SECONDS: int = 300

    # --- Convenient computed fields ---

    @computed_field  # type: ignore[misc]
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @computed_field  # type: ignore[misc]
    @property
    def is_test(self) -> bool:
        return self.ENVIRONMENT == "test"

    @computed_field  # type: ignore[misc]
    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def _secret_not_default(cls, v: str) -> str:
        if v in {"CHANGE_ME", "", "CHANGE_ME_USE_openssl_rand_hex_64"} and cls.model_fields.get(
            "ENVIRONMENT"
        ) is None:
            return v
        return v

    @field_validator("LOG_LEVEL")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


# Eager singleton — imported widely.
settings = get_settings()
