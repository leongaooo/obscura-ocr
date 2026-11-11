from __future__ import annotations

from pathlib import Path
from typing import Protocol

from obscura_ocr.domain.models import EngineOutput


class OcrEngine(Protocol):
    name: str

    def load(self) -> None: ...

    def recognize(self, document: Path) -> EngineOutput: ...
