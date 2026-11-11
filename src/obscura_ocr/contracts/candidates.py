"""字段候选边界模型；缺失值与有据的零严格分开。"""

from __future__ import annotations

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field

from obscura_ocr.contracts.document import DocumentRecognitionResponse

Value = TypeVar("Value")


class Evidence(BaseModel):
    page: int | None = Field(default=None, ge=1)
    box: tuple[float, float, float, float] | None = None
    text: str
    ruleId: str


class Candidate(BaseModel, Generic[Value]):
    value: Value | None = None
    rawText: str | None = None
    confidence: str | None = None
    confidenceSource: Literal["OCR_TOKEN_MIN", "RULE_EVIDENCE", "UNAVAILABLE"] = "UNAVAILABLE"
    evidence: list[Evidence] = Field(default_factory=list)
    reviewReasons: list[str] = Field(default_factory=list)


class JourneySegment(BaseModel):
    passengerName: Candidate[str]
    departure: Candidate[str]
    destination: Candidate[str]
    departureDate: Candidate[str]
    serviceNumber: Candidate[str]
    seat: Candidate[str]


class Journey(JourneySegment):
    segments: list[JourneySegment] = Field(default_factory=list)


class ReceiptCandidates(BaseModel):
    receiptType: Candidate[
        Literal[
            "VAT_SPECIAL",
            "VAT_ORDINARY",
            "TRAIN",
            "AIR_ITINERARY",
            "TAXI",
            "COACH",
            "TOLL",
            "OTHER_INVOICE",
            "CONSUMPTION_PROOF",
            "PAYMENT_PROOF",
        ]
    ]
    taxInvoiceType: Candidate[Literal["SPECIAL", "ORDINARY", "OTHER"]]
    documentForm: Candidate[Literal["ELECTRONIC", "PAPER"]]
    invoiceNumber: Candidate[str]
    invoiceCode: Candidate[str]
    ticketNumber: Candidate[str]
    issueDate: Candidate[str]
    transactionDate: Candidate[str]
    buyerName: Candidate[str]
    buyerTaxId: Candidate[str]
    sellerName: Candidate[str]
    sellerTaxId: Candidate[str]
    totalAmount: Candidate[str]
    netAmount: Candidate[str]
    taxAmount: Candidate[str]
    taxRate: Candidate[str]
    currency: Candidate[str]
    journey: Candidate[Journey]


class CandidateRecognitionResponse(DocumentRecognitionResponse):
    candidateSchemaVersion: Literal["OCR-CANDIDATE-1.0.0"] = "OCR-CANDIDATE-1.0.0"
    documentSha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidates: ReceiptCandidates
