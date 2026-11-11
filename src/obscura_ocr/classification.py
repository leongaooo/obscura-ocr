from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from decimal import Decimal

from obscura_ocr.contracts.document import DocumentSubtype, DocumentType
from obscura_ocr.domain.models import OcrToken


def normalize_text(value: str) -> str:
    return unicodedata.normalize("NFKC", value).replace(" ", "").strip()


@dataclass(frozen=True)
class Classification:
    document_type: DocumentType
    subtype: DocumentSubtype
    confidence: Decimal | None


def classify_document(tokens: tuple[OcrToken, ...]) -> Classification:
    normalized = [(token, normalize_text(token.text)) for token in tokens]
    invoice = _matching(normalized, ("发票",))
    if invoice:
        # 印章中的“专用”描述印章用途，不是专票票种。票号标签也不能
        # 为标题的分类置信背书；仅以非印章标题证据决定普专与电子属性。
        titles = [
            (token, text)
            for token, text in normalized
            if "发票" in text
            and "章" not in text
            and not any(label in text for label in ("号码", "代码", "校验", "开具"))
        ]
        combined = "".join(text for _, text in titles)
        electronic = "电子" in combined or "数电" in combined
        special = "专用发票" in combined or "专票" in combined
        ordinary = "普通" in combined or "普票" in combined
        if special and ordinary:
            return Classification(DocumentType.INVOICE, DocumentSubtype.OTHER_INVOICE, None)
        if not special and not ordinary:
            special = _is_split_special_invoice_title(normalized)
        if electronic and special:
            subtype = DocumentSubtype.ELECTRONIC_VAT_SPECIAL_INVOICE
        elif electronic and ordinary:
            subtype = DocumentSubtype.ELECTRONIC_ORDINARY_INVOICE
        elif special:
            subtype = DocumentSubtype.VAT_SPECIAL_INVOICE
        elif ordinary:
            subtype = DocumentSubtype.VAT_ORDINARY_INVOICE
        else:
            subtype = DocumentSubtype.OTHER_INVOICE
        evidence = [token for token, _ in titles]
        if special and not any("专用发票" in text or "专票" in text for _, text in titles):
            evidence.extend(token for token, text in normalized if "增值税" in text)
        confidence = min((token.confidence for token in evidence), default=None)
        return Classification(
            DocumentType.INVOICE,
            subtype,
            Decimal(str(confidence)).quantize(Decimal("0.0001"))
            if confidence is not None
            else None,
        )

    bank_receipt = _matching(normalized, ("银行回单", "电子回单", "客户回单", "付款回单"))
    if bank_receipt:
        return Classification(
            DocumentType.PAYMENT_VOUCHER,
            DocumentSubtype.BANK_RECEIPT,
            _confidence(bank_receipt),
        )

    payment = _matching(normalized, ("付款凭证", "支付凭证", "付款通知单"))
    if payment:
        return Classification(
            DocumentType.PAYMENT_VOUCHER,
            DocumentSubtype.PAYMENT_VOUCHER,
            _confidence(payment),
        )

    transaction = _matching(normalized, ("交易凭证", "转账凭证", "支付成功", "交易成功"))
    if transaction:
        return Classification(
            DocumentType.PAYMENT_VOUCHER,
            DocumentSubtype.TRANSACTION_VOUCHER,
            _confidence(transaction),
        )

    other = _matching(normalized, ("报销单", "收据", "结算单", "对账单"))
    if other:
        return Classification(DocumentType.OTHER, DocumentSubtype.OTHER, _confidence(other))

    return Classification(DocumentType.UNKNOWN, DocumentSubtype.UNKNOWN, None)


def _matching(tokens: list[tuple[OcrToken, str]], labels: tuple[str, ...]) -> list[OcrToken]:
    return [token for token, text in tokens if any(label in text for label in labels)]


def _confidence(tokens: list[OcrToken]) -> Decimal:
    return Decimal(str(max(token.confidence for token in tokens))).quantize(Decimal("0.0001"))


def _is_split_special_invoice_title(tokens: list[tuple[OcrToken, str]]) -> bool:
    electronic = [token for token, text in tokens if "电子发票" in text or "数电发票" in text]
    vat = [token for token, text in tokens if "增值税" in text]
    suffix = [token for token, text in tokens if "用发票" in text]
    if not electronic or not vat or not suffix:
        return False
    title_tokens = electronic + vat + suffix
    centers = [token.center_y for token in title_tokens]
    heights = [max(token.box[3] - token.box[1], 1) for token in title_tokens]
    return max(centers) - min(centers) <= max(heights) * 1.5
