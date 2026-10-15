"""Bounded PDF rendering and structural clues for document appearance review."""

from __future__ import annotations

import ctypes
import io
from dataclasses import dataclass

import pypdfium2 as pdfium
from pypdfium2 import raw

from .document_checks import MAX_VISUAL_PAGES
from .pdfdocs import _PDFIUM


@dataclass
class VisualPDF:
    images: list[bytes]
    page_count: int
    findings: list[dict]
    clues: dict
    limited: bool


def _overlap(a: tuple, b: tuple) -> float:
    area = max(0, a[2] - a[0]) * max(0, a[3] - a[1])
    intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    return intersection / area if area else 0


def _box(bounds: tuple, width: float, height: float) -> list[int]:
    left, bottom, right, top = bounds
    return [
        max(0, min(1000, round(n)))
        for n in (
            left / width * 1000,
            (height - top) / height * 1000,
            right / width * 1000,
            (height - bottom) / height * 1000,
        )
    ]


def _opaque_path(obj) -> bool:
    fill, stroke = ctypes.c_int(), ctypes.c_int()
    channels = [ctypes.c_uint() for _ in range(4)]
    return bool(
        raw.FPDFPath_GetDrawMode(obj, fill, stroke)
        and fill.value
        and raw.FPDFPageObj_GetFillColor(obj, *channels)
        and channels[3].value >= 240
    )


def inspect_pdf(data: bytes, *, tampering: bool) -> VisualPDF:
    """Inspect drawing order without treating editor names or metadata as proof of tampering."""
    images, findings, typography = [], [], []
    limited = False
    with _PDFIUM, pdfium.PdfDocument(data) as document:
        page_count = len(document)
        if page_count < 1:
            raise ValueError("The PDF contains no pages.")
        metadata = {
            k: str(v)[:200]
            for k, v in document.get_metadata_dict().items()
            if k in {"Producer", "Creator", "CreationDate", "ModDate"}
        }
        for page_number in range(min(page_count, MAX_VISUAL_PAGES)):
            page = document[page_number]
            try:
                width, height = page.get_size()
                if not 0 < min(width, height) or max(width, height) > 20000:
                    raise ValueError("Unsupported page dimensions.")
                bitmap = page.render(scale=min(1.8, 1600 / max(width, height)))
                try:
                    image = bitmap.to_pil()
                    buffer = io.BytesIO()
                    image.save(buffer, format="PNG")
                    images.append(buffer.getvalue())
                    image.close()
                finally:
                    bitmap.close()
                if not tampering:
                    continue
                texts, masks = [], []
                textpage = page.get_textpage()
                try:
                    for index, obj in enumerate(page.get_objects(textpage=textpage)):
                        if index >= 2500:
                            limited = True
                            break
                        bounds = obj.get_bounds()
                        if obj.type == raw.FPDF_PAGEOBJ_PATH and _opaque_path(obj):
                            if (bounds[2] - bounds[0]) * (bounds[3] - bounds[1]) < width * height * 0.25:
                                masks.append((index, bounds))
                        elif obj.type == raw.FPDF_PAGEOBJ_TEXT:
                            value = " ".join(obj.extract().split())
                            if len(value) < 2:
                                continue
                            if len(typography) < 80:
                                typography.append(
                                    {
                                        "page": page_number + 1,
                                        "text": value[:100],
                                        "font_size": round(obj.get_font_size(), 2),
                                        "box": _box(bounds, width, height),
                                    }
                                )
                            for old_index, old_bounds, old_value in texts[-100:]:
                                if (
                                    value == old_value
                                    or _overlap(old_bounds, bounds) < 0.55
                                    or _overlap(bounds, old_bounds) < 0.55
                                ):
                                    continue
                                if any(
                                    mask_index > old_index and _overlap(old_bounds, mask_bounds) > 0.8
                                    for mask_index, mask_bounds in masks[-200:]
                                ):
                                    if len(findings) < 8:
                                        findings.append(
                                            {
                                                "kind": "possible_alteration",
                                                "page": page_number + 1,
                                                "box": _box(bounds, width, height),
                                                "title": "Covered text with a different value on top",
                                                "detail": f"The PDF retains “{old_value[:80]}” beneath a covering shape, with “{value[:80]}” printed in the same area. This can occur during legitimate corrections as well as tampering; verify the change with the issuer.",
                                                "origin": "pdf_structure",
                                            }
                                        )
                                    break
                            texts.append((index, bounds, value))
                finally:
                    textpage.close()
            finally:
                page.close()
    return VisualPDF(
        images,
        page_count,
        findings,
        {"metadata": metadata, "end_markers": data.count(b"%%EOF"), "text_objects": typography},
        limited or page_count > MAX_VISUAL_PAGES,
    )
