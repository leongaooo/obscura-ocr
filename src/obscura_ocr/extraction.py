"""一次OCR输出上的有据候选：按标签、页内行列提取，不读PDF文本或样本答案。

本模块仅生成技术字段候选，与调用方业务流程无关。它不补算税额，不修写姓名，不按文件名
判票种；多页未分票时保守拒绝拼接，方便后续分票能力明确接管。
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from obscura_ocr.classification import normalize_text
from obscura_ocr.contracts.candidates import (
    Candidate,
    Evidence,
    Journey,
    ReceiptCandidates,
)
from obscura_ocr.domain.models import EngineOutput, OcrToken

DATE_PATTERN = re.compile(r"(?P<year>\d{4})\D+(?P<month>\d{1,2})\D+(?P<day>\d{1,2})")
MONEY_PATTERN = re.compile(r"(?:人民币|RMB|CNY|[¥￥])?(-?\d{1,12}(?:,\d{3})*(?:\.\d+)?)")
NUMBER_PATTERN = re.compile(r"\d{8,30}")
TAX_ID_PATTERN = re.compile(r"[A-Z0-9]{15,20}")


def missing(reason: str = "FIELD_NOT_FOUND") -> Candidate:
    return Candidate(reviewReasons=[reason])


def supported(value: object, tokens: list[OcrToken], rule: str) -> Candidate:
    """置信度仅为OCR证据最小值；缺页来源时坐标也留空，避免误导定位。"""
    reasons = []
    if any(token.page is None for token in tokens):
        reasons.append("PAGE_PROVENANCE_UNAVAILABLE")
    confidence = min(max(0, min(1, token.confidence)) for token in tokens)
    if confidence < 0.85:
        reasons.append("LOW_CONFIDENCE")
    return Candidate(
        value=value,
        rawText="\n".join(token.text for token in tokens),
        confidence=f"{confidence:.4f}",
        confidenceSource="OCR_TOKEN_MIN",
        evidence=[
            Evidence(
                page=token.page,
                box=token.box if token.page is not None else None,
                text=token.text,
                ruleId=rule,
            )
            for token in tokens
        ],
        reviewReasons=reasons,
    )


def unique(matches: list[tuple[str, list[OcrToken]]], rule: str) -> Candidate:
    if not matches:
        return missing()
    values = {value for value, _ in matches}
    evidence = list(dict.fromkeys(token for _, tokens in matches for token in tokens))
    result = supported(next(iter(values)) if len(values) == 1 else None, evidence, rule)
    if len(values) > 1:
        result.reviewReasons.append("FIELD_CONFLICT")
    return result


def height(token: OcrToken) -> float:
    return max(1, token.box[3] - token.box[1])


def same_row(first: OcrToken, second: OcrToken) -> bool:
    return first.page == second.page and abs(first.center_y - second.center_y) <= (
        min(height(first), height(second)) * 0.65
    )


def labelled(
    tokens: list[OcrToken],
    labels: tuple[str, ...],
    pattern: re.Pattern,
    *,
    preserve_raw_value: bool = False,
) -> Candidate:
    """先解析标签后的完整值，再找同页紧邻右侧值；不从备注中截任意数字。"""
    matches = []
    for token in tokens:
        # 只归一标签中的常见异体字；合法名称与号码值仍使用各自原文规则。
        text = normalize_text(token.text).replace("統一社会信用代码", "统一社会信用代码")
        label = next((label for label in labels if text.startswith(label)), None)
        if label is None:
            continue
        suffix = text[len(label) :].lstrip(":：")
        if pattern.fullmatch(suffix):
            value = suffix
            if preserve_raw_value:
                # 名称不能沿用用于匹配标签的NFKC/去空白结果，避免改写合法名称。
                parts = re.split(r"[:：]", token.text, maxsplit=1)
                value = (parts[1] if len(parts) == 2 else token.text[len(label) :]).strip()
            matches.append((value, [token]))
        elif not suffix:
            adjacent = [
                other
                for other in tokens
                if other is not token
                and same_row(token, other)
                and other.box[0] >= token.box[2] - height(token)
            ]
            if adjacent:
                other = min(adjacent, key=lambda item: item.box[0])
                value = normalize_text(other.text).lstrip(":：")
                if pattern.fullmatch(value):
                    if preserve_raw_value:
                        value = other.text.strip()
                    matches.append((value, [token, other]))
    return unique(matches, "LABEL:" + labels[0])


def date_candidate(candidate: Candidate) -> Candidate:
    if candidate.value is None:
        return candidate
    value = date_text(str(candidate.value))
    if value is None:
        candidate.value = None
        candidate.reviewReasons.append("INVALID_DATE")
        return candidate
    candidate.value = value
    return candidate


def date_text(text: str) -> str | None:
    """从带时间后缀或OCR异常分隔符的日期文本中提取真实日历日期。"""
    match = DATE_PATTERN.search(normalize_text(text))
    if match is None:
        return None
    try:
        return date(
            int(match.group("year")),
            int(match.group("month")),
            int(match.group("day")),
        ).isoformat()
    except ValueError:
        return None


def labelled_date(tokens: list[OcrToken], labels: tuple[str, ...]) -> Candidate:
    """按日期标签取值，允许同一OCR token带时间或其他非数字分隔符。"""
    matches = []
    invalid_tokens = []
    for token in tokens:
        text = normalize_text(token.text)
        label = next((label for label in labels if text.startswith(label)), None)
        if label is None:
            continue
        suffix = text[len(label) :].lstrip(":：")
        value = date_text(suffix)
        if value is not None:
            matches.append((value, [token]))
            continue
        if DATE_PATTERN.search(suffix):
            invalid_tokens.append(token)
            continue
        if suffix:
            continue
        adjacent = [
            other
            for other in tokens
            if other is not token
            and same_row(token, other)
            and other.box[0] >= token.box[2] - height(token)
        ]
        if adjacent:
            other = min(adjacent, key=lambda item: item.box[0])
            value = date_text(other.text)
            if value is not None:
                matches.append((value, [token, other]))
            elif DATE_PATTERN.search(other.text):
                invalid_tokens.extend((token, other))
    result = unique(matches, "LABEL:" + labels[0])
    if not matches and invalid_tokens:
        result = supported(None, list(dict.fromkeys(invalid_tokens)), "LABEL:" + labels[0])
        result.reviewReasons.append("INVALID_DATE")
    return result


def unlabelled_date(tokens: list[OcrToken]) -> Candidate:
    """仅在没有明确日期标签时保守保留唯一日期，并要求人工确认来源。"""
    matches = []
    for token in tokens:
        value = date_text(token.text)
        if value is not None:
            matches.append((value, [token]))
    result = unique(matches, "DATE_IN_DOCUMENT")
    if result.value is not None:
        result.reviewReasons.append("DATE_INFERRED_FROM_DOCUMENT")
    return result


def money_text(text: str) -> str | None:
    normalized = normalize_text(text).replace("(小写)", "").strip(":：()")
    # 支出截图可能使用Unicode减号或长横线；仅归一金额单元，原始证据不改写。
    normalized = normalized.translate(str.maketrans({"−": "-", "–": "-", "—": "-", "﹣": "-"}))
    match = MONEY_PATTERN.fullmatch(normalized)
    return match.group(1).replace(",", "") if match else None


def money_candidate(candidate: Candidate) -> Candidate:
    """忽略支出金额前的负号，保留原文证据并拒绝超两位小数。"""
    if candidate.value is None:
        return candidate
    value = candidate.value.lstrip("-")
    if "." in value and len(value.partition(".")[2]) > 2:
        candidate.value = None
        candidate.reviewReasons.append("UNSUPPORTED_PRECISION")
    else:
        candidate.value = f"{Decimal(value):.2f}"
    return candidate


def amount_for_labels(tokens: list[OcrToken], labels: tuple[str, ...]) -> Candidate:
    matches = []
    for anchor in tokens:
        text = normalize_text(anchor.text)
        label = next((label for label in labels if text.startswith(label)), None)
        if label is None:
            continue
        suffix = text[len(label) :].lstrip(":：")
        inline = money_text(suffix)
        if inline is not None:
            matches.append((inline, [anchor]))
            continue
        # 价税合计的大写金额不作为数值来源，只取同一行明确的小写金额。
        values = [
            token
            for token in tokens
            if token is not anchor
            and same_row(anchor, token)
            and token.center_x > anchor.center_x
            and money_text(token.text) is not None
        ]
        if len(values) == 1:
            matches.append((money_text(values[0].text), [anchor, values[0]]))
        elif len(values) > 1:
            matches.extend((money_text(token.text), [anchor, token]) for token in values)
    return money_candidate(unique(matches, "TOTAL_ANCHOR"))


def signed_amount_candidate(tokens: list[OcrToken]) -> Candidate:
    """从无标签凭证中提取唯一负号金额，并按支出金额返回正数。"""
    matches = []
    for token in tokens:
        value = money_text(token.text)
        if value is not None and value.startswith("-"):
            matches.append((value, [token]))
    result = unique(matches, "SIGNED_AMOUNT")
    if result.evidence:
        return money_candidate(result)
    return result


def title_fields(tokens: list[OcrToken]) -> dict[str, Candidate]:
    titles = [
        token
        for token in tokens
        if any(
            word in normalize_text(token.text)
            for word in (
                "电子发",
                "数电发",
                "增值税",
                "铁路电子客票",
                "航空运输电子客票行程单",
                "出租车发票",
                "客运发票",
                "通行费发票",
                "付款凭证",
                "银行回单",
                "消费凭证",
            )
        )
        and not any(word in token.text for word in ("章", "号码", "代码", "备注"))
    ]
    # OCR常将套印标题拆框；只合并同页同一标题行，印章与项目名称不能参与。
    title_row = list(
        dict.fromkeys(
            token
            for token in tokens
            if any(same_row(title, token) for title in titles)
            and not any(word in token.text for word in ("章", "号码", "代码", "日期"))
        )
    )
    combined = "".join(
        normalize_text(token.text) for token in sorted(title_row, key=lambda token: token.center_x)
    )
    receipt, tax, form = missing("DOCUMENT_TYPE_UNCERTAIN"), missing(), missing()
    special = "专用发票" in combined
    ordinary = "普通发票" in combined
    partial = False
    if not special and not ordinary and ("电子发" in combined or "增值税" in combined):
        # 套印遮挡后的“普用/普发票”或“用发票”只提供待确认分类，不改写OCR原文。
        ordinary = bool(re.search(r"普.{0,2}发票", combined))
        special = "用发票" in combined and not ordinary and "普" not in combined
        partial = special or ordinary
    if special and ordinary:
        receipt = supported(None, title_row, "TITLE_CONFLICT")
        tax = supported(None, title_row, "TITLE_CONFLICT")
        receipt.reviewReasons.append("FIELD_CONFLICT")
        tax.reviewReasons.append("FIELD_CONFLICT")
    elif special or ordinary:
        receipt = supported("VAT_SPECIAL" if special else "VAT_ORDINARY", title_row, "VAT_TITLE")
        tax = supported("SPECIAL" if special else "ORDINARY", title_row, "VAT_TITLE")
    for phrase, code in (
        ("铁路电子客票", "TRAIN"),
        ("航空运输电子客票行程单", "AIR_ITINERARY"),
        ("出租车发票", "TAXI"),
        ("客运发票", "COACH"),
        ("通行费发票", "TOLL"),
        ("付款凭证", "PAYMENT_PROOF"),
        ("银行回单", "PAYMENT_PROOF"),
        ("消费凭证", "CONSUMPTION_PROOF"),
    ):
        if phrase in combined:
            receipt = supported(code, title_row, "DOCUMENT_TITLE")
    payment_markers = [
        token
        for token in tokens
        if any(
            marker in normalize_text(token.text)
            for marker in (
                "付款凭证",
                "支付凭证",
                "支付成功",
                "交易成功",
                "账单详情",
                "转账时间",
                "支付时间",
                "付款时间",
                "充值金额",
            )
        )
    ]
    if receipt.value is None and payment_markers:
        receipt = supported("PAYMENT_PROOF", payment_markers, "PAYMENT_PROOF_MARKER")
    if "铁路" in combined and "客票" in combined and "电子" in combined:
        receipt = supported("TRAIN", title_row, "SPLIT_TRAIN_TITLE")
        if "铁路电子客票" not in combined:
            receipt.reviewReasons.append("DOCUMENT_TYPE_UNCERTAIN")
    if receipt.value is None and "发票" in combined and not receipt.evidence:
        receipt = supported("OTHER_INVOICE", title_row, "GENERIC_INVOICE_TITLE")
        receipt.reviewReasons.append("DOCUMENT_TYPE_UNCERTAIN")
    if partial:
        receipt.reviewReasons.append("DOCUMENT_TYPE_UNCERTAIN")
        tax.reviewReasons.append("DOCUMENT_TYPE_UNCERTAIN")
    if "电子" in combined or "数电" in combined:
        form = supported("ELECTRONIC", title_row, "ELECTRONIC_TITLE")
    return {"receiptType": receipt, "taxInvoiceType": tax, "documentForm": form}


def party_fields(tokens: list[OcrToken]) -> dict[str, Candidate]:
    result = {}
    anchors = [
        token
        for token in tokens
        if normalize_text(token.text) in {"购买方信息", "销售方信息", "购买方", "销售方"}
    ]
    for role, label in (("buyer", "购买方"), ("seller", "销售方")):
        for suffix, pattern in (("Name", re.compile(r".+")), ("TaxId", TAX_ID_PATTERN)):
            field_matches = []
            for token in tokens:
                text = normalize_text(token.text)
                prefix = "名称" if suffix == "Name" else "统一社会信用代码/纳税人识别号"
                if suffix == "TaxId":
                    prefixes = (prefix, "纳税人识别号", "统一社会信用代码")
                else:
                    prefixes = (prefix,)
                field_label = next((item for item in prefixes if text.startswith(item + ":")), None)
                if field_label is None:
                    continue
                candidates = [
                    anchor
                    for anchor in anchors
                    if anchor.page == token.page
                    and token.center_x > anchor.center_x
                    and anchor.box[1] - height(token)
                    <= token.center_y
                    <= anchor.box[3] + height(token) * 2
                ]
                if not candidates:
                    continue
                owner = min(candidates, key=lambda anchor: abs(token.box[0] - anchor.box[2]))
                value = text[len(field_label) :].lstrip(":：")
                if label in owner.text and pattern.fullmatch(value):
                    # 名称仅去标签和首尾空白，不用Unicode/空白归一结果修改合法名称。
                    if suffix == "Name":
                        value = re.split(r"[:：]", token.text, maxsplit=1)[-1].strip()
                    field_matches.append((value, [owner, token]))
            explicit = labelled(
                tokens,
                (label + ("名称" if suffix == "Name" else "纳税人识别号"),),
                pattern,
                preserve_raw_value=suffix == "Name",
            )
            result[role + suffix] = (
                explicit if explicit.evidence else unique(field_matches, "PARTY_BLOCK:" + label)
            )
    # 铁路客票的统一信用代码与购买方名称并排，不存在销售方区域，不能套用卖方。
    if result["buyerName"].evidence and not anchors:
        result["buyerTaxId"] = labelled(tokens, ("统一社会信用代码",), TAX_ID_PATTERN)
    return result


def summary_fields(tokens: list[OcrToken]) -> dict[str, Candidate]:
    result = {"netAmount": missing(), "taxAmount": missing(), "taxRate": missing()}
    summaries = [token for token in tokens if normalize_text(token.text) == "合计"]
    summaries += [
        token
        for token in tokens
        if normalize_text(token.text) == "合"
        and any(normalize_text(other.text) == "计" and same_row(token, other) for other in tokens)
    ]
    for key, label in (("netAmount", "金额"), ("taxAmount", "税额")):
        headers = [
            token
            for token in tokens
            if normalize_text(token.text) == label
            or (label == "金额" and normalize_text(token.text).startswith("金额税率"))
        ]
        matches = []
        for anchor in summaries:
            for token in tokens:
                value = money_text(token.text)
                if value is None or not same_row(anchor, token):
                    continue
                if any(
                    header.page == token.page
                    and header.center_y < token.center_y
                    and abs(header.center_x - token.center_x)
                    <= max(header.box[2] - header.box[0], token.box[2] - token.box[0])
                    for header in headers
                ):
                    matches.append((value, [anchor, token]))
        result[key] = money_candidate(unique(matches, "SUMMARY_COLUMN:" + label))
    rate_headers = [
        token for token in tokens if "税率" in normalize_text(token.text).replace("稅", "税")
    ]
    rates = []
    for token in tokens:
        match = re.fullmatch(r"(\d{1,2}(?:\.\d{1,2})?|100)%", normalize_text(token.text))
        if not match:
            continue
        if any(
            header.page == token.page
            and header.center_y < token.center_y
            and abs(header.center_x - token.center_x)
            < max(header.box[2] - header.box[0], height(token) * 3)
            for header in rate_headers
        ):
            rates.append((f"{Decimal(match.group(1)) / 100:.4f}", [token]))
    result["taxRate"] = unique(rates, "TAX_RATE_COLUMN")
    if "FIELD_CONFLICT" in result["taxRate"].reviewReasons:
        result["taxRate"].reviewReasons.remove("FIELD_CONFLICT")
        result["taxRate"].reviewReasons.append("MULTIPLE_TAX_RATES")
    return result


def train_journey(tokens: list[OcrToken]) -> Candidate:
    fields = {key: missing() for key in Journey.model_fields if key != "segments"}
    services = [token for token in tokens if re.fullmatch(r"[GDCZTKYS]\d{1,5}", token.text)]
    fields["serviceNumber"] = unique([(token.text, [token]) for token in services], "TRAIN_SERVICE")
    stations = [token for token in tokens if re.fullmatch(r"[\u4e00-\u9fff]{1,12}站", token.text)]
    for service in services:
        route = sorted(
            [token for token in stations if same_row(service, token)],
            key=lambda token: token.center_x,
        )
        if len(route) == 2 and route[0].center_x < service.center_x < route[1].center_x:
            fields["departure"] = supported(route[0].text, [service, route[0]], "TRAIN_ROUTE")
            fields["destination"] = supported(route[1].text, [service, route[1]], "TRAIN_ROUTE")
    fields["seat"] = unique(
        [
            (token.text, [token])
            for token in tokens
            if re.fullmatch(r"\d{1,2}车\d{1,3}[A-Fa-f]?号", token.text)
        ],
        "TRAIN_SEAT",
    )
    # 发车日期需与“开”时刻同一行，避免误用晚于行程的开票日期。
    dates = [
        (date_text(token.text), [token])
        for token in tokens
        if date_text(token.text) is not None
        and any(
            re.fullmatch(r"\d{1,2}:\d{2}开", normalize_text(other.text)) and same_row(token, other)
            for other in tokens
        )
    ]
    fields["departureDate"] = date_candidate(unique(dates, "TRAIN_DEPARTURE_DATE"))
    identities = [
        token
        for token in tokens
        if re.fullmatch(r"[0-9Xx*]{15,20}", token.text) and "*" in token.text
    ]
    names = [
        (token.text, [token])
        for token in tokens
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,12}", token.text)
        and not any(word in token.text for word in ("座", "站", "票", "开"))
        and any(
            same_row(identity, token) and token.center_x > identity.center_x
            for identity in identities
        )
    ]
    fields["passengerName"] = unique(names, "TRAIN_PASSENGER_ROW")
    if fields["passengerName"].value is not None:
        # 姓名的字形不能用公司名单或答案纠正，即使OCR高分也须逐字人工核对。
        fields["passengerName"].reviewReasons.append("PASSENGER_NAME_REQUIRES_REVIEW")
    evidence = list(
        dict.fromkeys(
            token
            for token in tokens
            if any(item.text == token.text for field in fields.values() for item in field.evidence)
        )
    )
    if not evidence:
        return missing()
    result = supported(Journey(**fields, segments=[]), evidence, "TRAIN_JOURNEY")
    result.reviewReasons = list(
        dict.fromkeys(
            result.reviewReasons
            + [reason for field in fields.values() for reason in field.reviewReasons]
        )
    )
    return result


def extract_candidates(output: EngineOutput) -> ReceiptCandidates:
    """候选始终全键返回；多页未可靠分票前不允许跨页拼成一张票。"""
    tokens = list(output.tokens)
    pages = {token.page for token in tokens if token.page is not None}
    if len(pages) > 1:
        return ReceiptCandidates(
            **{key: missing("MULTIPLE_DOCUMENTS") for key in ReceiptCandidates.model_fields}
        )
    fields = title_fields(tokens)
    fields.update(party_fields(tokens))
    fields.update(summary_fields(tokens))
    for key, labels in (
        ("invoiceNumber", ("发票号码",)),
        ("invoiceCode", ("发票代码",)),
        ("ticketNumber", ("电子客票号", "客票号", "票号")),
    ):
        fields[key] = labelled(tokens, labels, NUMBER_PATTERN)
    fields["issueDate"] = labelled_date(tokens, ("开票日期",))
    fields["transactionDate"] = labelled_date(
        tokens,
        (
            "交易日期",
            "消费日期",
            "支付日期",
            "付款日期",
            "转账日期",
            "支付时间",
            "付款时间",
            "转账时间",
            "交易时间",
        ),
    )
    if not fields["transactionDate"].evidence and not fields["issueDate"].evidence:
        fields["transactionDate"] = unlabelled_date(tokens)
    fields["totalAmount"] = amount_for_labels(
        tokens,
        (
            "价税合计",
            "票价",
            "付款金额",
            "支付金额",
            "交易金额",
            "总金额",
            "合计金额",
            "充值金额",
            "实付",
        ),
    )
    if fields["totalAmount"].value is None and not fields["totalAmount"].evidence:
        fields["totalAmount"] = signed_amount_candidate(tokens)
    currencies = []
    for token in tokens:
        for marker, code in (
            ("人民币", "CNY"),
            ("RMB", "CNY"),
            ("CNY", "CNY"),
            ("￥", "CNY"),
            ("¥", "CNY"),
            ("USD", "USD"),
            ("美元", "USD"),
        ):
            if marker in token.text:
                currencies.append((code, [token]))
    fields["currency"] = unique(currencies, "EXPLICIT_CURRENCY")
    if fields["currency"].value is None:
        fields["currency"].reviewReasons.append("CURRENCY_UNCERTAIN")
    fields["journey"] = (
        train_journey(tokens) if fields["receiptType"].value == "TRAIN" else missing()
    )
    return ReceiptCandidates(**fields)
