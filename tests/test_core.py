"""Synthetic-only regression checks for source isolation and field evidence boundaries."""

from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from obscura_ocr.app import create_app
from obscura_ocr.config import Settings
from obscura_ocr.domain.models import EngineOutput, OcrToken
from obscura_ocr.extraction import extract_candidates


def token(text, y=0, page=1):
    return OcrToken(text, 0.99, (0, y, 500, y + 20), page)


class Engine:
    name = "SYNTHETIC_TEST_ONLY"
    calls = 0
    paths = []

    def load(self):
        pass

    def recognize(self, path):
        self.calls += 1
        self.paths.append(path)
        return EngineOutput((token("价税合计：￥0.00"),), 1000, 1000)


def png():
    buffer = BytesIO()
    Image.new("RGB", (100, 100), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def test_amount_zero_and_leading_zeroes_are_preserved():
    fields = extract_candidates(
        EngineOutput(
            (
                token("发票号码：00123456789012345678"),
                token("价税合计：￥0.00", 50),
                token("开票日期：2026年2月30日", 100),
            ),
            1000,
            1000,
        )
    )
    assert fields.totalAmount.value == "0.00"
    assert fields.invoiceNumber.value.startswith("00")
    assert fields.issueDate.value is None
    assert "INVALID_DATE" in fields.issueDate.reviewReasons


def test_conflicting_fields_and_multiple_pages_are_not_silently_merged():
    fields = extract_candidates(
        EngineOutput(
            (
                token("发票号码：00123456789012345678"),
                token("发票号码：99123456789012345678", 50),
            ),
            1000,
            1000,
        )
    )
    assert fields.invoiceNumber.value is None
    assert "FIELD_CONFLICT" in fields.invoiceNumber.reviewReasons
    fields = extract_candidates(
        EngineOutput((token("票价：￥42.00"), token("姓名", page=2)), 1000, 1000)
    )
    assert all(field.value is None for _, field in fields)


def test_http_upload_cleanup_errors_and_exactly_one_inference():
    engine = Engine()
    with TestClient(create_app(Settings(), engine)) as client:
        assert client.get("/health/ready").status_code == 200
        assert client.get("/").status_code == 200
        response = client.post("/api/recognize", files={"file": ("sample.png", png(), "image/png")})
        assert response.status_code == 200
        assert response.json()["candidates"]["totalAmount"]["value"] == "0.00"
        assert len(response.json()["tokens"]) == 1
        assert engine.calls == 1
        assert not engine.paths[-1].exists()
        for bad in [b"bad", b"%PDF-1.4 invalid"]:
            response = client.post("/api/recognize", files={"file": ("sample.pdf", bad)})
            assert response.status_code == 422
            assert response.json()["message"]
        assert engine.calls == 1


def test_failed_load_is_not_ready():
    class Failed(Engine):
        def load(self):
            raise RuntimeError("private native engine error")

    with TestClient(create_app(Settings(), Failed())) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 503
        response = client.post("/api/recognize", files={"file": ("sample.png", png())})
        assert response.status_code == 503
        assert "private native" not in response.text


def test_size_limit_rejects_before_inference():
    engine = Engine()
    with TestClient(create_app(Settings(max_file_bytes=1024), engine)) as client:
        response = client.post("/api/recognize", files={"file": ("bad.png", b"x" * 1025)})
        assert response.status_code == 422
        assert engine.calls == 0


def test_valid_pdf_and_page_limit_close_handles():
    buffer = BytesIO()
    Image.new("RGB", (80, 80), "white").save(
        buffer, format="PDF", save_all=True, append_images=[Image.new("RGB", (80, 80))]
    )
    engine = Engine()
    with TestClient(create_app(Settings(max_pdf_pages=1), engine)) as client:
        response = client.post("/api/recognize", files={"file": ("sample.pdf", buffer.getvalue())})
        assert response.status_code == 422
        assert "page limit" in response.json()["message"]
        assert engine.calls == 0
    buffer = BytesIO()
    Image.new("RGB", (80, 80), "white").save(buffer, format="PDF")
    with TestClient(create_app(Settings(), engine)) as client:
        response = client.post("/api/recognize", files={"file": ("sample.pdf", buffer.getvalue())})
        assert response.status_code == 200
        assert not engine.paths[-1].exists()
