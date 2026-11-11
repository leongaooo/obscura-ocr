from __future__ import annotations

import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from fastapi import UploadFile

from obscura_ocr.domain.errors import OcrError
from obscura_ocr.domain.models import OcrErrorCode


async def read_validated_upload(file: UploadFile, max_file_bytes: int) -> tuple[str, bytes]:
    data = bytearray()
    while chunk := await file.read(1024 * 1024):
        data.extend(chunk)
        if len(data) > max_file_bytes:
            raise OcrError(OcrErrorCode.FILE_UNSUPPORTED, "文件超过 OCR 识别大小限制")
    if not data:
        raise OcrError(OcrErrorCode.FILE_REQUIRED, "请选择需要识别的文件")
    header = bytes(data[:16])
    if header.startswith(b"%PDF-"):
        return ".pdf", bytes(data)
    if header.startswith(b"\xff\xd8\xff"):
        return ".jpg", bytes(data)
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png", bytes(data)
    raise OcrError(OcrErrorCode.FILE_UNSUPPORTED, "文件内容与声明类型不一致")


@contextmanager
def temporary_document(suffix: str, data: bytes) -> Iterator[Path]:
    path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temporary:
            temporary.write(data)
            path = Path(temporary.name)
        yield path
    finally:
        if path:
            path.unlink(missing_ok=True)
