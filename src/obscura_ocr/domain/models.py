from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class OcrStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    FAILED = "FAILED"


class OcrErrorCode(StrEnum):
    FILE_REQUIRED = "OCR_FILE_REQUIRED"
    FILE_NOT_FOUND = "OCR_FILE_NOT_FOUND"
    FILE_UNSUPPORTED = "OCR_FILE_UNSUPPORTED"
    NOT_INVOICE = "OCR_NOT_INVOICE"
    TOTAL_AMOUNT_UNREADABLE = "OCR_TOTAL_AMOUNT_UNREADABLE"
    REVIEW_REQUIRED = "OCR_REVIEW_REQUIRED"
    RATE_LIMITED = "OCR_RATE_LIMITED"
    TEMPORARILY_UNAVAILABLE = "OCR_TEMPORARILY_UNAVAILABLE"
    CONFIGURATION_ERROR = "OCR_CONFIGURATION_ERROR"


@dataclass(frozen=True)
class OcrToken:
    text: str
    confidence: float
    box: tuple[float, float, float, float]
    # 页码由引擎提供；旧适配器缺失时保留未知，候选层不得伪造第一页。
    page: int | None = None

    @property
    def center_x(self) -> float:
        return (self.box[0] + self.box[2]) / 2

    @property
    def center_y(self) -> float:
        return (self.box[1] + self.box[3]) / 2


@dataclass(frozen=True)
class EngineOutput:
    tokens: tuple[OcrToken, ...]
    page_width: float
    page_height: float
