from __future__ import annotations

from obscura_ocr.domain.models import OcrErrorCode


class OcrError(Exception):
    def __init__(self, code: OcrErrorCode, message: str, http_status: int = 422):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
