from pathlib import Path
from typing import Literal, Self

from pydantic import EmailStr, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Local ONNX paraphrase-multilingual-MiniLM-L12-v2
LOCAL_EMBEDDING_DIM = 384
# Fixed pgvector column size for memories.embedding_remote.
# Changing this requires a new Alembic migration.
REMOTE_EMBEDDING_DIM = 1024


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MEMLORD_", env_file=".env", extra="ignore")

    db_url: str = "postgresql+asyncpg://postgres:postgres@localhost/memlord"
    db_echo: bool = False

    model_dir: Path = Path("src/memlord/onnx")
    host: str = "0.0.0.0"
    port: int = 8000
    base_url: str = "http://localhost:8000"
    rrf_k: int = 60
    default_limit: int = 10
    sim_threshold: float = Field(0.25, ge=0.0, le=1.0)
    dedup_threshold: float = Field(0.85, ge=0.0, le=1.0)
    oauth_jwt_secret: str = "memlord-dev-secret-please-change"
    # Self-registration (web UI + OAuth register form). Disabled by default;
    # set MEMLORD_ALLOW_REGISTRATION=true to enable.
    allow_registration: bool = False

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: EmailStr | None = None
    smtp_tls: bool = True

    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # ── Optional remote embeddings (OpenAI-compatible /v1/embeddings) ─────────
    # Default is local-only (identical to upstream). Set provider to
    # openai_compatible and fill base_url / api_key / model to enable remote.
    # Local 384-d vectors are always written; remote is best-effort with fallback.
    embedding_provider: Literal["local", "openai_compatible"] = "local"
    embedding_base_url: str | None = None  # e.g. https://api.siliconflow.cn/v1
    embedding_api_key: str | None = None
    embedding_model: str | None = None  # e.g. BAAI/bge-m3
    embedding_dim: int = REMOTE_EMBEDDING_DIM
    embedding_timeout: float = Field(10.0, gt=0)
    embedding_retries: int = Field(2, ge=0)
    # Use remote column for vector search only when this fraction of candidate
    # memories already have embedding_remote populated.
    embedding_remote_min_coverage: float = Field(0.5, ge=0.0, le=1.0)

    @property
    def remote_embedding_configured(self) -> bool:
        return (
            self.embedding_provider == "openai_compatible"
            and bool(self.embedding_base_url)
            and bool(self.embedding_api_key)
            and bool(self.embedding_model)
        )

    @model_validator(mode="after")
    def _validate_remote_embedding(self) -> Self:
        if self.embedding_provider != "openai_compatible":
            return self
        missing: list[str] = []
        if not self.embedding_base_url:
            missing.append("MEMLORD_EMBEDDING_BASE_URL")
        if not self.embedding_api_key:
            missing.append("MEMLORD_EMBEDDING_API_KEY")
        if not self.embedding_model:
            missing.append("MEMLORD_EMBEDDING_MODEL")
        if missing:
            raise ValueError("embedding_provider=openai_compatible requires: " + ", ".join(missing))
        if self.embedding_dim != REMOTE_EMBEDDING_DIM:
            raise ValueError(
                f"MEMLORD_EMBEDDING_DIM must be {REMOTE_EMBEDDING_DIM} "
                f"(matches memories.embedding_remote); got {self.embedding_dim}"
            )
        return self


settings = Settings()
