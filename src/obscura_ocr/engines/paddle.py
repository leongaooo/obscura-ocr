from __future__ import annotations

import json
import logging
import os
from contextlib import closing
from pathlib import Path
from typing import Any

from obscura_ocr.config import Settings
from obscura_ocr.domain.errors import OcrError
from obscura_ocr.domain.models import EngineOutput, OcrErrorCode, OcrToken

LOGGER = logging.getLogger("obscura_ocr.engine.paddle")


class PaddleOcrEngine:
    name = "PADDLEOCR"

    def __init__(self, settings: Settings):
        self.settings = settings
        self._pipeline: Any = None

    def load(self) -> None:
        if not self.settings.allow_model_download and not self.settings.model_ready_marker.exists():
            raise OcrError(
                OcrErrorCode.CONFIGURATION_ERROR,
                "OCR 模型尚未准备，请先执行模型准备脚本",
                503,
            )
        self.settings.model_home.mkdir(parents=True, exist_ok=True)
        # PaddleX reads this variable during import, so set it before importing PaddleOCR.
        os.environ["PADDLE_PDX_CACHE_HOME"] = str(self.settings.model_home.resolve())
        try:
            from paddleocr import PaddleOCR

            self._pipeline = PaddleOCR(
                device=self.settings.device,
                enable_mkldnn=self.settings.enable_mkldnn,
                cpu_threads=self.settings.cpu_threads,
                text_detection_model_name="PP-OCRv5_mobile_det",
                text_recognition_model_name="PP-OCRv5_mobile_rec",
                use_doc_orientation_classify=True,
                use_doc_unwarping=False,
                use_textline_orientation=True,
            )
        except OcrError:
            raise
        except Exception as error:
            LOGGER.error(
                "Engine initialization failed; readiness blocked. Check model configuration."
            )
            raise OcrError(
                OcrErrorCode.CONFIGURATION_ERROR,
                "OCR 引擎初始化失败",
                503,
            ) from error

    def recognize(self, document: Path) -> EngineOutput:
        return self._recognize(document, detailed_pdf=False)

    def recognize_detailed(self, document: Path) -> EngineOutput:
        """Return page-indexed OCR tokens; PDF coordinates use the configured raster size."""
        return self._recognize(document, detailed_pdf=True)

    def _recognize(self, document: Path, *, detailed_pdf: bool) -> EngineOutput:
        if self._pipeline is None:
            raise OcrError(OcrErrorCode.CONFIGURATION_ERROR, "OCR 引擎尚未初始化", 503)
        try:
            import numpy as np
            import pypdfium2 as pdfium

            tokens: list[OcrToken] = []
            width = height = 1.0

            def collect(model_input: Any, page: int) -> None:
                nonlocal width, height
                for result in self._pipeline.predict(model_input):
                    payload = _as_payload(result)
                    texts = payload.get("rec_texts") or []
                    scores = payload.get("rec_scores") or []
                    boxes = payload.get("rec_boxes") or payload.get("dt_polys") or []
                    for text, score, box in zip(texts, scores, boxes, strict=False):
                        normalized_box = _normalize_box(box)
                        width = max(width, normalized_box[2])
                        height = max(height, normalized_box[3])
                        tokens.append(OcrToken(str(text), float(score), normalized_box, page))

            if document.suffix.lower() == ".pdf":
                # Render one page at a time to bound memory. Coordinates refer to rendered pixels.
                with closing(pdfium.PdfDocument(document)) as pdf:
                    for index in range(len(pdf)):
                        with closing(pdf[index]) as page:
                            scale = self.settings.candidate_pdf_max_side / max(page.get_size())
                            bitmap = page.render(scale=scale)
                            try:
                                rgb = np.asarray(bitmap.to_pil().convert("RGB"))
                                collect(rgb[:, :, ::-1].copy(), index + 1)
                            finally:
                                bitmap.close()
            else:
                collect(str(document), 1)
            return EngineOutput(tuple(tokens), width, height)
        except OcrError:
            raise
        except Exception as error:
            LOGGER.error(
                "OCR inference failed; no result returned. Document suffix=%s", document.suffix
            )
            raise OcrError(
                OcrErrorCode.TEMPORARILY_UNAVAILABLE,
                "OCR 服务暂时不可用，请手工录入或稍后重试",
                503,
            ) from error


def _as_payload(result: Any) -> dict[str, Any]:
    payload = getattr(result, "json", result)
    if callable(payload):
        payload = payload()
    if isinstance(payload, str):
        payload = json.loads(payload)
    if isinstance(payload, dict) and isinstance(payload.get("res"), dict):
        return payload["res"]
    return payload if isinstance(payload, dict) else {}


def _normalize_box(box: Any) -> tuple[float, float, float, float]:
    values = box.tolist() if hasattr(box, "tolist") else box
    if len(values) == 4 and not isinstance(values[0], list | tuple):
        left, top, right, bottom = values
        return float(left), float(top), float(right), float(bottom)
    xs = [float(point[0]) for point in values]
    ys = [float(point[1]) for point in values]
    return min(xs), min(ys), max(xs), max(ys)
