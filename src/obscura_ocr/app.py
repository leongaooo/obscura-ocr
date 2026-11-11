"""Loopback-first HTTP boundary with bounded upload and single-engine inference."""

import asyncio
import logging
from contextlib import asynccontextmanager, closing
from pathlib import Path
from uuid import uuid4

import pypdfium2 as pdfium
from fastapi import FastAPI, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from obscura_ocr.config import Settings
from obscura_ocr.domain.errors import OcrError
from obscura_ocr.domain.models import OcrErrorCode
from obscura_ocr.engines.base import OcrEngine
from obscura_ocr.engines.paddle import PaddleOcrEngine
from obscura_ocr.service import recognize
from obscura_ocr.upload import read_validated_upload, temporary_document


def create_app(settings: Settings | None = None, engine: OcrEngine | None = None) -> FastAPI:
    """Inject an engine for contract tests; production always defaults to real PaddleOCR."""
    settings = settings or Settings()
    engine = engine or PaddleOcrEngine(settings)
    ready = {"ready": False}
    gate = asyncio.Semaphore(settings.concurrency)

    @asynccontextmanager
    async def lifespan(app):
        try:
            await asyncio.to_thread(engine.load)
            ready["ready"] = True
        except Exception:
            # Never log native exception contents: they may contain OCR text or local paths.
            logging.getLogger("obscura_ocr").error(
                "Engine initialization failed; readiness stays false. Check model configuration."
            )
        yield

    app = FastAPI(title="ObscuraOCR", version="0.1.0", lifespan=lifespan)

    @app.exception_handler(OcrError)
    async def handle_error(request: Request, error: OcrError):
        return JSONResponse(
            status_code=error.http_status,
            content={"errorCode": error.code, "message": error.message},
        )

    @app.get("/health/live")
    async def live():
        return {"status": "UP"}

    @app.get("/health/ready")
    async def readiness():
        return JSONResponse(ready, status_code=200 if ready["ready"] else 503)

    @app.post("/api/recognize")
    async def recognize_file(file: UploadFile):
        if not ready["ready"]:
            raise OcrError(OcrErrorCode.CONFIGURATION_ERROR, "OCR engine is not ready.", 503)
        try:
            await asyncio.wait_for(gate.acquire(), timeout=0.05)
        except TimeoutError as error:
            raise OcrError(OcrErrorCode.RATE_LIMITED, "OCR is busy; retry later.", 429) from error
        try:
            suffix, data = await read_validated_upload(file, settings.max_file_bytes)
            with temporary_document(suffix, data) as document:
                if suffix == ".pdf":
                    try:
                        with closing(pdfium.PdfDocument(document)) as pdf:
                            if len(pdf) > settings.max_pdf_pages:
                                raise OcrError(
                                    OcrErrorCode.FILE_UNSUPPORTED, "PDF page limit exceeded."
                                )
                    except (pdfium.PdfiumError, RuntimeError) as error:
                        raise OcrError(OcrErrorCode.FILE_UNSUPPORTED, "Invalid PDF.") from error
                inference = asyncio.create_task(
                    asyncio.to_thread(recognize, document, settings, engine, uuid4().hex)
                )
                try:
                    return await asyncio.shield(inference)
                except asyncio.CancelledError:
                    # Native inference cannot be interrupted safely. Retain the file and slot
                    # until the worker exits, even if the HTTP caller has disconnected.
                    await inference
                    raise
        finally:
            await file.close()
            gate.release()

    assets = Path(__file__).parent / "web"
    app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(assets / "index.html", headers={"Cache-Control": "no-store"})

    return app
