"""One inference supplies both raw OCR and evidence-backed field candidates."""

import hashlib
from pathlib import Path
from time import perf_counter

from obscura_ocr.classification import classify_document
from obscura_ocr.config import Settings
from obscura_ocr.engines.base import OcrEngine
from obscura_ocr.extraction import extract_candidates
from obscura_ocr.validation import prepare_document


def recognize(document: Path, settings: Settings, engine: OcrEngine, request_id: str) -> dict:
    """Normalize only the temporary copy; never derive fields from a filename or sample answer."""
    started = perf_counter()
    digest = hashlib.sha256(document.read_bytes()).hexdigest()
    prepare_document(document, settings.max_image_side)
    infer = getattr(engine, "recognize_detailed", engine.recognize)
    output = infer(document)
    classification = classify_document(output.tokens)
    fields = extract_candidates(output)
    warnings = sorted({reason for _, field in fields for reason in field.reviewReasons})
    return {
        "requestId": request_id,
        "documentSha256": digest,
        "engine": engine.name,
        "durationMs": round((perf_counter() - started) * 1000),
        "documentType": classification.document_type.value,
        "documentSubtype": classification.subtype.value,
        "classificationConfidence": (
            str(classification.confidence) if classification.confidence is not None else None
        ),
        "reviewRequired": bool(warnings),
        "warnings": warnings,
        "tokens": [
            {"text": t.text, "confidence": t.confidence, "box": t.box, "page": t.page}
            for t in output.tokens
        ],
        "candidates": fields.model_dump(mode="json"),
        "message": "Recognition complete; confirm extracted fields before use.",
    }
