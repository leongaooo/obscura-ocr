# ObscuraOCR

**Self-host freely. Integrate with one HTTP request.**

[简体中文](README.md) · [Deployment](docs/deployment-modes.md) · [Integration](docs/integration.md)

A standalone OCR service turning images and PDFs into text tokens and evidence-backed Chinese receipt fields. No cloud account, business database or reimbursement application required. Your infrastructure, your document boundary.

## Available today

- Real local PaddleOCR inference with text, page provenance, bounding boxes and confidence.
- Chinese receipt classification and candidate fields: identifiers, dates, parties, totals, tax and supported journey details.
- One inference pipeline feeds raw tokens and field evidence. Unknowns remain null and conflicts require review.
- PNG, JPEG and PDF upload, temporary file cleanup, browser workbench and OpenAPI.
- No real company documents, invoices, credentials or internal business services included.

Automatic file redaction, Office formats and enterprise governance are future extensions, not current capabilities.

## Native deployment

Python 3.11–3.13. CPU by default. Model preparation requires network access; subsequent serving can run offline with the prepared cache.

```bash
python -m venv .venv
# Linux / macOS
.venv/bin/python -m pip install -e ".[paddle]"
.venv/bin/obscura-ocr prepare
.venv/bin/obscura-ocr serve
```

Windows PowerShell: replace `.venv/bin/python` with `.venv/Scripts/python.exe` and `.venv/bin/obscura-ocr` with `.venv/Scripts/obscura-ocr.exe`.

Open http://127.0.0.1:18083 for acceptance testing; `/docs` for OpenAPI; `/health/ready` returns 503 until the real engine is loaded.

## Docker Compose

```bash
docker compose build
docker compose run --rm ocr obscura-ocr prepare
docker compose up -d
```

Loopback binding by default; persistent model cache in the `models` volume. The CPU container recipe requires validation on the target Linux Docker host. GPU packaging is not included. Air-gapped deployments must prepare the image and model volume beforehand.

## Integration

```bash
curl -F "file=@examples/synthetic-invoice.png" http://127.0.0.1:18083/api/recognize
python examples/client.py examples/synthetic-invoice.png
```

On Windows use `curl.exe`. The Python example uses only the standard library. Response fields include `tokens`, `candidates`, input SHA-256, latency and review warnings. Amounts are decimal strings; identifier leading zeroes are preserved. Multi-page tokens are returned, but receipt fields are not merged across pages.

## Operational limits

Default limits: 20 MB, 10 PDF pages, one inference at a time. No built-in authentication, TLS or tenant isolation. Put authentication, upload limits and network isolation in front of internet-facing deployments. OCR results contain original text: handle them as sensitive data. File deletion is not secure erasure; a process crash may leave temporary files requiring operator cleanup.

## Development

```bash
python -m pip install -e ".[test]"
python -m pytest
python -m ruff check src tests scripts examples
python -m ruff format --check src tests scripts examples
```

Project-authored code: [Apache-2.0](LICENSE). Engines, model weights, PDFium and transitive dependencies retain their own licenses. Models are not distributed in this repository. See [third-party notices](THIRD_PARTY_NOTICES.md).
