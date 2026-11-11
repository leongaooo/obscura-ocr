"""Deployment configuration; model downloads require an explicit preparation step."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OBSCURA_OCR_", extra="ignore")

    model_home: Path = Path("models")
    allow_model_download: bool = False
    device: str = "cpu"
    cpu_threads: int = Field(default=2, ge=1, le=16)
    enable_mkldnn: bool = False
    candidate_pdf_max_side: int = Field(default=1800, ge=1000, le=4000)
    max_file_bytes: int = Field(default=20 * 1024 * 1024, ge=1024)
    max_image_side: int = Field(default=2500, ge=1000, le=4000)
    max_pdf_pages: int = Field(default=10, ge=1, le=100)
    concurrency: int = Field(default=1, ge=1, le=4)

    @property
    def model_ready_marker(self) -> Path:
        return self.model_home / ".prepared"
