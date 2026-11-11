from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

from obscura_ocr.domain.models import OcrErrorCode, OcrStatus


class DocumentType(StrEnum):
    INVOICE = "INVOICE"
    PAYMENT_VOUCHER = "PAYMENT_VOUCHER"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class DocumentSubtype(StrEnum):
    ELECTRONIC_VAT_SPECIAL_INVOICE = "ELECTRONIC_VAT_SPECIAL_INVOICE"
    ELECTRONIC_ORDINARY_INVOICE = "ELECTRONIC_ORDINARY_INVOICE"
    VAT_SPECIAL_INVOICE = "VAT_SPECIAL_INVOICE"
    VAT_ORDINARY_INVOICE = "VAT_ORDINARY_INVOICE"
    OTHER_INVOICE = "OTHER_INVOICE"
    BANK_RECEIPT = "BANK_RECEIPT"
    PAYMENT_VOUCHER = "PAYMENT_VOUCHER"
    TRANSACTION_VOUCHER = "TRANSACTION_VOUCHER"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class AmountType(StrEnum):
    TOTAL_WITH_TAX = "TOTAL_WITH_TAX"
    TOTAL_AMOUNT = "TOTAL_AMOUNT"
    PAYMENT_AMOUNT = "PAYMENT_AMOUNT"
    UNKNOWN = "UNKNOWN"


class DocumentRecognitionResponse(BaseModel):
    status: OcrStatus = Field(description="Recognition outcome.")
    isInvoice: bool = Field(description="Whether the document is classified as an invoice.")
    documentType: DocumentType = Field(description="Top-level document classification.")
    documentSubtype: DocumentSubtype = Field(description="China-specific document subtype.")
    totalAmount: Decimal | None = Field(
        default=None,
        description="Best supported total amount. Detail amounts are never returned.",
    )
    amountType: AmountType = Field(description="Business meaning of totalAmount.")
    currency: str = Field(default="CNY", description="ISO 4217 currency code.")
    classificationConfidence: Decimal | None = Field(
        default=None,
        description="Classification confidence from 0 to 1.",
    )
    amountConfidence: Decimal | None = Field(
        default=None,
        description="Selected total amount confidence from 0 to 1.",
    )
    reviewRequired: bool = Field(
        default=False,
        description="Whether a person must confirm the classification or amount.",
    )
    warnings: list[str] = Field(default_factory=list, description="Stable review reasons.")
    engine: str = Field(default="PADDLEOCR", description="OCR engine name.")
    engineVersion: str = Field(description="OCR model and document-rule version.")
    requestId: str = Field(description="Caller-provided or generated trace identifier.")
    durationMs: int = Field(ge=0, description="End-to-end recognition duration in milliseconds.")
    errorCode: OcrErrorCode | None = Field(default=None, description="Stable error code.")
    message: str = Field(description="Human-readable result summary.")
