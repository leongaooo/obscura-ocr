# ObscuraOCR agent guide

Read README.md, docs/final-design.md and docs/roadmap.md before changes. This is an independent OCR technology project. Do not copy business services, real documents, internal URLs, credentials or personal paths into public files.

Keep implemented OCR and future redaction clearly distinguished. Update the independent Roadmap with files, commands, results and limits. Preserve unrelated changes. Explain data boundaries and fallback reasons in comments; format changes and check comment accuracy independently of tests.

Validation: python -m ruff check src tests scripts examples; python -m ruff format --check src tests scripts examples; python -m pytest. Real model testing and browser/user acceptance are separate evidence. No model weights or real results in Git.
