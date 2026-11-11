from __future__ import annotations

from contextlib import closing
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageOps, UnidentifiedImageError

from obscura_ocr.domain.errors import OcrError
from obscura_ocr.domain.models import OcrErrorCode


def prepare_document(document: Path, max_image_side: int) -> None:
    """Validate input and normalize large raster images before native OCR inference."""
    if document.suffix.lower() == ".pdf":
        _validate_pdf(document)
        return
    _validate_and_normalize_image(document, max_image_side)


def _validate_pdf(document: Path) -> None:
    try:
        with closing(pdfium.PdfDocument(document)) as pdf:
            if len(pdf) == 0:
                raise OcrError(OcrErrorCode.FILE_UNSUPPORTED, "PDF 没有可识别页面")
            with closing(pdf[0]):
                pass
    except OcrError:
        raise
    except (pdfium.PdfiumError, RuntimeError, ValueError) as error:
        raise OcrError(
            OcrErrorCode.FILE_UNSUPPORTED,
            "PDF 文件已损坏或无法读取，请重新上传",
        ) from error


def _validate_and_normalize_image(document: Path, max_image_side: int) -> None:
    try:
        with Image.open(document) as image:
            image.verify()
        with Image.open(document) as image:
            normalized = ImageOps.exif_transpose(image).convert("RGB")
            if max(normalized.size) > max_image_side:
                normalized.thumbnail((max_image_side, max_image_side), Image.Resampling.LANCZOS)
            save_format = "PNG" if document.suffix.lower() == ".png" else "JPEG"
            save_options = {} if save_format == "PNG" else {"quality": 92}
            normalized.save(document, format=save_format, **save_options)
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise OcrError(
            OcrErrorCode.FILE_UNSUPPORTED,
            "图片文件已损坏或无法读取，请重新上传",
        ) from error
