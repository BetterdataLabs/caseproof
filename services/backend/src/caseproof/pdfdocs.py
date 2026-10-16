"""Fictional document rendering and the strict CPL-1 layout parser.

Rendering belongs to the fixture adapter only. Parsing reads nothing but the stored PDF bytes: every fact
is taken from the document text and carries the exact line it was read from, so a fixture's intended values
can never stand in for a failed extraction.
"""

from __future__ import annotations

import io
import re
import threading
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

import pypdfium2 as pdfium
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

PARSER_VERSION = "cpl1-parser/1.0"
_PDFIUM = threading.Lock()  # PDFium is not thread-safe: serialise every call in this process
LAYOUT = "CPL-1"

NAVY = colors.HexColor("#112d3c")
TEAL = colors.HexColor("#00675f")
MUTED = colors.HexColor("#52656c")
RULE = colors.HexColor("#d8e2e0")


def _money(value: str) -> str:
    return f"SGD {Decimal(value):,.2f}"


# rendering


def render_document(role: str, spec: dict[str, Any], parties: dict[str, dict[str, str]]) -> bytes:
    """Render the published demo form; all parser fields remain visible on the page."""
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4, invariant=1, pageCompression=0)
    width, height = A4
    left, right = 42, width - 42
    invoice = role == "invoice"
    issuer = parties[spec["seller"] if invoice else spec["issued_by"]]
    colour = NAVY if invoice else TEAL
    pdf.setTitle(f"{spec['number']} - version {spec['version']} (fictional)")
    pdf.setAuthor(issuer["name"])
    pdf.setSubject("Fictional business document for CaseProof testing")

    def text(x, y, value, size=9, bold=False, colour=NAVY, max_width=None):
        font = "Helvetica-Bold" if bold else "Helvetica"
        while max_width and pdf.stringWidth(value, font, size) > max_width and size > 6:
            size -= 0.25
        pdf.setFillColor(colour)
        pdf.setFont(font, size)
        pdf.drawString(x, y, value)

    def rect(x, y, w, h, fill):
        pdf.setFillColor(fill)
        pdf.rect(x, y, w, h, stroke=0, fill=1)

    def field(label, value, x, y, max_width=width - 84, size=9):
        text(x, y, f"{label}: {value}", size, max_width=max_width)

    def section(title, y):
        rect(left, y - 8, right - left, 27, colour)
        text(left + 12, y + 1, title, 9, True, colors.white)

    rect(0, height - 7, width, 7, colour)
    rect(left, 754, 37, 38, colour)
    mark = "".join(word[0] for word in issuer["name"].split()[:2])
    text(left + 6, 766, mark, 16, True, colors.white)
    text(92, 783, issuer["name"], 13, True, colour, 281)
    text(92, 765, issuer["address"], 8, max_width=281)
    text(92, 750, f"UEN {issuer['uen']}", 8, colour=MUTED)
    text(
        92,
        736,
        issuer.get("contact", "Issued by the accounts / receiving office"),
        7.5,
        colour=MUTED,
        max_width=281,
    )
    text(395, 783, "INVOICE" if invoice else "GOODS RECEIVED", 20 if invoice else 12, True, colour)
    if not invoice:
        text(395, 764, "NOTE", 16, True, colour)
    text(395, 741, spec["number"], 11, True, max_width=158)
    pdf.setStrokeColor(RULE)
    pdf.line(left, 710, right, 710)

    if invoice:
        field("Buyer", parties[spec["buyer"]]["name"], left, 685, size=10)
        text(left, 666, parties[spec["buyer"]]["address"], 8, colour=MUTED, max_width=right - left)
        field("Seller", issuer["name"], left, 646)
        field("Seller UEN", issuer["uen"], left, 628)
        rect(left, 528, right - left, 83, colors.HexColor("#f2f6f5"))
        for label, value, x, y in [
            ("Invoice number", spec["number"], left + 12, 591),
            ("Invoice version", str(spec["version"]), 325, 591),
            ("Issue date", spec["issue_date"], left + 12, 568),
            ("Replaces version", str(spec.get("replaces_version", "none")), 325, 568),
            ("Payment terms", spec["payment_terms"], left + 12, 545),
        ]:
            field(label, value, x, y, 245 if label != "Payment terms" else 475, 8.5)
        section("GOODS / COMMERCIAL DETAILS", 495)
        rows = [
            {
                "item": spec["item"],
                "quantity": spec["quantity"],
                "unit": spec["unit"],
                "unit_price": spec["unit_price"],
            }
        ] + spec.get("extra_lines", [])
        y = 463
        for index, row in enumerate(rows, 1):
            field(f"Line {index} item", row["item"], left + 12, y, size=10)
            field(f"Line {index} quantity", row["quantity"], left + 12, y - 24, 150, 9)
            field(f"Line {index} unit", row["unit"], 238, y - 24, 118, 9)
            field(f"Line {index} unit price", _money(row["unit_price"]), 370, y - 24, 175, 9)
            pdf.line(left, y - 36, right, y - 36)
            y -= 70
        field("Tax", spec.get("tax", "none"), left + 12, y - 2, size=9)
        field("Other charges", spec.get("other_charges", "none"), left + 12, y - 23, size=9)
        rect(309, y - 44, right - 309, 61, colour)
        text(322, y - 3, "AMOUNT PAYABLE", 8, True, colors.white)
        text(322, y - 28, f"Total amount: {_money(spec['total'])}", 12, True, colors.white, 218)
        text(left, 207, "PAYMENT AND DOCUMENT CONTROL", 8, True, colour)
        text(
            left,
            188,
            f"Please quote {spec['number']} on remittance advice and correspondence.",
            8.5,
            max_width=right - left,
        )
        note = spec.get("revision_note") or (
            f"This invoice replaces version {spec['replaces_version']}. Refer to the revised fields above."
            if spec.get("replaces_version")
            else "Retain this invoice with its purchase order and delivery records."
        )
        text(left, 171, note, 8, max_width=right - left)
        text(left, 132, "Prepared by the Accounts Receivable department", 9, True)
    else:
        field("Issued by", issuer["name"], left, 685, size=10)
        field("Supplier", parties[spec["supplier"]]["name"], left, 665)
        rect(left, 531, right - left, 115, colors.HexColor("#f2f6f5"))
        for label, value, x, y in [
            ("Receipt number", spec["number"], left + 12, 625),
            ("Receipt version", str(spec["version"]), 325, 625),
            ("Invoice reference", spec["invoice_ref"], left + 12, 601),
            ("Replaces version", str(spec.get("replaces_version", "none")), 325, 601),
            ("Delivery reference", spec["delivery_ref"], left + 12, 577),
            ("Received at", spec["received_at"], left + 12, 553),
        ]:
            field(label, value, x, y, 470 if label == "Received at" else 248, 8.5)
        section("GOODS RECEIVED", 495)
        field("Item", spec["item"], left + 12, 461, size=10)
        field("Quantity received", spec["quantity"], left + 12, 430, 220, 12)
        field("Unit", spec["unit"], 325, 430, 180, 10)
        field("Condition", spec["condition"], left + 12, 401)
        pdf.line(left, 383, right, 383)
        field("Quantity basis", spec["basis"], left + 12, 360, size=10)
        rect(left, 250, right - left, 80, colors.HexColor("#edf5f1"))
        text(left + 12, 309, "RECEIPT ACKNOWLEDGEMENT", 8, True, colour)
        text(
            left + 12,
            288,
            "The receiving organisation acknowledges the goods described above.",
            9,
            max_width=right - left - 24,
        )
        text(
            left + 12,
            272,
            "Quantities and delivery references must be read with the stated quantity basis.",
            8.5,
            max_width=right - left - 24,
        )
        if spec.get("replaces_version"):
            text(left, 222, f"This receipt replaces {spec['number']} version {spec['replaces_version']}.", 9)
        text(left, 177, "Authorised receiving officer", 11, True, colour)
        pdf.line(left, 164, 278, 164)
        text(
            left, 147, "Acknowledged electronically on behalf of the receiving organisation", 8, colour=MUTED
        )

    pdf.line(left, 96, right, 96)
    field("Document type", "Commercial invoice" if invoice else "Delivery receipt", left, 80, 390, 7.5)
    field("Layout", LAYOUT, 440, 80, 110, 7.5)
    text(left, 58, "Fictional sample for CaseProof testing. No goods or payment are due.", 7.5, colour=MUTED)
    text(left, 42, f"Document reference: {spec['number']} | Version: {spec['version']}", 7, colour=MUTED)
    text(497, 42, "Page 1 of 1", 7, colour=MUTED)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


# parsing


@dataclass
class ParsedFact:
    field: str
    value: str
    quote: str
    page: int


@dataclass
class ParseResult:
    ok: bool
    doc_type: str | None
    facts: list[ParsedFact] = field(default_factory=list)
    text: str = ""
    page_count: int = 0
    reject_code: str | None = None
    reject_detail: str = ""
    structured: dict[str, Any] = field(default_factory=dict)

    def value(self, name: str) -> str | None:
        for fact in self.facts:
            if fact.field == name:
                return fact.value
        return None


INVOICE_FIELDS = {
    "Invoice number": "invoice_number",
    "Invoice version": "version",
    "Replaces version": "replaces_version",
    "Issue date": "issue_date",
    "Seller": "seller",
    "Seller UEN": "seller_uen",
    "Buyer": "buyer",
    "Payment terms": "payment_terms",
    "Line 1 item": "item",
    "Line 1 quantity": "quantity",
    "Line 1 unit": "unit",
    "Line 1 unit price": "unit_price",
    "Tax": "tax",
    "Other charges": "other_charges",
    "Total amount": "total_amount",
}
RECEIPT_FIELDS = {
    "Receipt number": "receipt_number",
    "Receipt version": "version",
    "Replaces version": "replaces_version",
    "Delivery reference": "delivery_ref",
    "Invoice reference": "invoice_ref",
    "Issued by": "issued_by",
    "Supplier": "supplier",
    "Item": "item",
    "Quantity received": "quantity",
    "Unit": "unit",
    "Received at": "received_at",
    "Quantity basis": "basis",
    "Condition": "condition",
}
MONEY_RE = re.compile(r"^SGD ([0-9]{1,3}(?:,[0-9]{3})*|[0-9]+)\.([0-9]{2})$")


def extract_text(data: bytes, max_pages: int = 20) -> tuple[list[str], int]:
    with _PDFIUM:
        return _extract_text(data, max_pages)


def _extract_text(data: bytes, max_pages: int = 20) -> tuple[list[str], int]:
    document = pdfium.PdfDocument(data)
    try:
        if len(document) > max_pages:
            return [], len(document)
        pages = []
        for page in document:
            textpage = page.get_textpage()
            pages.append(textpage.get_text_range())
            textpage.close()
            page.close()
        return pages, len(pages)
    finally:
        document.close()


FIELD_LABEL_RE = re.compile(
    r"(?<!\w)("
    + "|".join(
        re.escape(label)
        for label in sorted(
            set(INVOICE_FIELDS) | set(RECEIPT_FIELDS) | {"Layout", "Document type", "Line 2 item"},
            key=len,
            reverse=True,
        )
    )
    + r"): *"
)


def parse_document(data: bytes, max_pages: int = 20) -> ParseResult:
    try:
        pages, page_count = extract_text(data, max_pages)
    except Exception:
        return ParseResult(
            False, None, reject_code="UNREADABLE_PDF", reject_detail="The file is not a readable PDF."
        )
    text = "\n".join(pages)
    if page_count > max_pages:
        return ParseResult(
            False,
            None,
            text=text,
            page_count=page_count,
            reject_code="TOO_MANY_PAGES",
            reject_detail=f"{page_count} pages exceeds the {max_pages}-page admission limit.",
        )
    if not text.strip():
        return ParseResult(
            False,
            None,
            page_count=page_count,
            reject_code="NO_TEXT_LAYER",
            reject_detail="The PDF has no text layer; scanned images are not supported.",
        )

    found: dict[str, list[tuple[str, str, int]]] = {}
    for page_no, page_text in enumerate(pages, start=1):
        for raw in page_text.replace("\r", "\n").split("\n"):
            line = " ".join(raw.split())
            labels = list(FIELD_LABEL_RE.finditer(line))
            for index, match in enumerate(labels):
                end = labels[index + 1].start() if index + 1 < len(labels) else len(line)
                passage = line[match.start() : end].strip()
                value = line[match.end() : end].strip()
                found.setdefault(match.group(1), []).append((value, passage, page_no))

    def single(label: str) -> tuple[str, str, int] | None:
        values = found.get(label, [])
        return values[0] if len(values) == 1 else None

    layout = single("Layout")
    doc_type = single("Document type")
    if not layout or layout[0] != LAYOUT or not doc_type:
        return ParseResult(
            False,
            None,
            text=text,
            page_count=page_count,
            reject_code="UNSUPPORTED_LAYOUT",
            reject_detail="The document is not in the declared CPL-1 layout.",
        )
    kind = {"Commercial invoice": "invoice", "Delivery receipt": "delivery_receipt"}.get(doc_type[0])
    if kind is None:
        return ParseResult(
            False,
            None,
            text=text,
            page_count=page_count,
            reject_code="UNSUPPORTED_DOCUMENT_TYPE",
            reject_detail=f"Document type '{doc_type[0]}' is not supported.",
        )

    spec = INVOICE_FIELDS if kind == "invoice" else RECEIPT_FIELDS
    result = ParseResult(True, kind, text=text, page_count=page_count)
    missing = []
    for label, name in spec.items():
        entry = single(label)
        if entry is None:
            missing.append(label)
            continue
        value, quote, page_no = entry
        result.facts.append(ParsedFact(name, value, quote, page_no))
    if missing:
        return ParseResult(
            False,
            kind,
            facts=result.facts,
            text=text,
            page_count=page_count,
            reject_code="MISSING_OR_REPEATED_FIELDS",
            reject_detail="Missing or repeated fields: " + ", ".join(missing),
        )

    if kind == "invoice":
        if "Line 2 item" in found:
            return _unsupported(
                result,
                "MULTIPLE_INVOICE_LINES",
                "The invoice has more than one line; only single-line invoices are supported.",
            )
        if result.value("tax") != "none" or result.value("other_charges") != "none":
            return _unsupported(
                result,
                "TAX_OR_CHARGES",
                f"Tax or other charges are present ({result.value('tax')}); not supported.",
            )
        for name in ("unit_price", "total_amount"):
            if not MONEY_RE.match(result.value(name) or ""):
                return _unsupported(
                    result, "UNSUPPORTED_CURRENCY", f"{name} is not an SGD amount with 2 decimals."
                )
    for name in ("quantity",):
        try:
            quantity = Decimal(result.value(name) or "x")
            if quantity <= 0 or quantity != quantity.to_integral_value():
                raise InvalidOperation
        except InvalidOperation:
            return _unsupported(result, "INVALID_QUANTITY", "Quantity must be a positive whole number.")
    if result.value("version") is None or not (result.value("version") or "").isdigit():
        return _unsupported(result, "INVALID_VERSION", "Version must be a whole number.")
    replaces = result.value("replaces_version")
    if replaces not in ("none",) and not (replaces or "").isdigit():
        return _unsupported(
            result, "INVALID_SUPERSESSION", "Replaces version must be 'none' or a version number."
        )
    return result


def _unsupported(result: ParseResult, code: str, detail: str) -> ParseResult:
    result.ok = False
    result.reject_code = code
    result.reject_detail = detail
    return result


def money_value(text: str) -> Decimal:
    match = MONEY_RE.match(text)
    if not match:
        raise ValueError(text)
    return Decimal(match.group(1).replace(",", "") + "." + match.group(2))


def render_preview(data: bytes, page_index: int, scale: float = 1.6) -> bytes:
    """Raster preview: active PDF content is never displayed in the browser."""
    with _PDFIUM:
        return _render_preview(data, page_index, scale)


def _render_preview(data: bytes, page_index: int, scale: float) -> bytes:
    document = pdfium.PdfDocument(data)
    page = bitmap = image = None
    try:
        page = document[page_index]
        scale = min(scale, 2000 / max(page.get_size()))
        bitmap = page.render(scale=scale)
        image = bitmap.to_pil()
        out = io.BytesIO()
        image.save(out, format="PNG", optimize=True)
        return out.getvalue()
    finally:
        if image is not None:
            image.close()
        if bitmap is not None:
            bitmap.close()
        if page is not None:
            page.close()
        document.close()
