"""Read common business documents without imposing invoice or numeric conventions."""

from __future__ import annotations

import io
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePath
from xml.etree import ElementTree as ET

import pypdfium2 as pdfium
from PIL import Image

from .pdfdocs import _PDFIUM, render_preview

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
EXTENSIONS = {
    "application/pdf": "pdf",
    DOCX: "docx",
    XLSX: "xlsx",
    "text/csv": "csv",
    "text/plain": "txt",
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/tiff": "tiff",
    "image/webp": "webp",
}


@dataclass
class DocumentContent:
    pages: list[str]
    page_count: int
    images: list[tuple[int, bytes]] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    visual_pages: list[int] = field(default_factory=list)
    rendering: str = ""


def render_word(data: bytes) -> bytes:
    """Render the complete Word layout in a private, disposable LibreOffice profile."""
    executable = shutil.which("libreoffice") or shutil.which("soffice")
    if not executable:
        raise ValueError("Word page rendering is unavailable. Install LibreOffice or provide a PDF copy.")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if sum(i.file_size for i in archive.infolist()) > 80 * 1024 * 1024:
            raise ValueError("The expanded document exceeds the processing limit.")
    with tempfile.TemporaryDirectory(prefix="caseproof-word-") as directory:
        root = Path(directory)
        (root / "document.docx").write_bytes(data)
        profile = root / "profile"
        (profile / "user").mkdir(parents=True)
        (profile / "user/registrymodifications.xcu").write_text(
            '<?xml version="1.0"?><oor:items xmlns:oor="http://openoffice.org/2001/registry">'
            '<item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop></item>'
            '<item oor:path="/org.openoffice.Office.Writer/Content/Update"><prop oor:name="Link" oor:op="fuse"><value>2</value></prop></item></oor:items>'
        )
        try:
            subprocess.run(
                [
                    executable,
                    f"-env:UserInstallation={profile.as_uri()}",
                    "--headless",
                    "--nologo",
                    "--nodefault",
                    "--norestore",
                    "--convert-to",
                    "pdf:writer_pdf_Export",
                    "--outdir",
                    directory,
                    str(root / "document.docx"),
                ],
                timeout=25,
                check=True,
                capture_output=True,
            )
            output = root / "document.pdf"
            if not output.is_file() or output.stat().st_size > 40 * 1024 * 1024:
                raise ValueError("Word could not be rendered within the document limit.")
            return output.read_bytes()
        except (subprocess.SubprocessError, OSError) as exc:
            raise ValueError("Word could not be rendered reliably. Supply an unlocked PDF copy.") from exc


def identify_format(data: bytes, filename: str = "") -> str:
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if zipfile.is_zipfile(io.BytesIO(data)):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = set(archive.namelist())
            if "word/document.xml" in names:
                return DOCX
            if "xl/workbook.xml" in names:
                return XLSX
    try:
        with Image.open(io.BytesIO(data)) as image:
            mime = Image.MIME.get(image.format, "")
            if mime in EXTENSIONS:
                return mime
    except (OSError, ValueError):
        pass
    if PurePath(filename).suffix.lower() in {".csv", ".txt"}:
        decode_text(data)
        return "text/csv" if filename.lower().endswith(".csv") else "text/plain"
    raise ValueError("Use a PDF, PNG, JPEG, TIFF, WebP, DOCX, XLSX, CSV or text document.")


def decode_text(data: bytes) -> str:
    encoding = "utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    try:
        text = data.decode(encoding)
    except UnicodeDecodeError:
        text = data.decode("cp1252")
    if "\x00" in text:
        raise ValueError("The text file contains undecodable binary content.")
    return text


def image_preview(data: bytes, page: int = 0) -> bytes:
    with Image.open(io.BytesIO(data)) as image:
        image.seek(page)
        frame = image.convert("RGB")
        frame.thumbnail((1800, 1800))
        output = io.BytesIO()
        frame.save(output, "PNG")
        frame.close()
        return output.getvalue()


def _xml(archive: zipfile.ZipFile, name: str):
    return ET.fromstring(archive.read(name))


def _word_text(node) -> str:
    output = []
    for element in node.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag == "t":
            output.append(element.text or "")
        elif tag == "tab":
            output.append("\t")
        elif tag in {"br", "cr"}:
            output.append("\n")
    return "".join(output)


def _office(data: bytes, mime: str) -> DocumentContent:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if sum(i.file_size for i in archive.infolist()) > 80 * 1024 * 1024:
            raise ValueError("The expanded document exceeds the processing limit.")
        if mime == DOCX:
            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            root = _xml(archive, "word/document.xml")
            # Paragraph order preserves table row/cell order and repeated line items.
            paragraphs = []
            body = root.find("w:body", ns)
            for block in body:
                if block.tag.endswith("}tbl"):
                    for row in block.findall("w:tr", ns):
                        paragraphs.append(
                            " | ".join(
                                "\n".join(_word_text(p) for p in cell.findall(".//w:p", ns))
                                for cell in row.findall("w:tc", ns)
                            )
                        )
                else:
                    paragraphs.append(_word_text(block))
            for name in archive.namelist():
                if name.startswith(("word/header", "word/footer")) and name.endswith(".xml"):
                    paragraphs.extend(_word_text(p) for p in _xml(archive, name).findall(".//w:p", ns))
            content = DocumentContent(["\n".join(paragraphs)], 1)
            for name in archive.namelist():
                if name.startswith("word/media/"):
                    try:
                        content.images.append((len(content.pages) + 1, image_preview(archive.read(name))))
                        content.pages.append(f"Embedded image: {PurePath(name).name}")
                    except (OSError, ValueError):
                        content.limitations.append(f"Embedded image {PurePath(name).name} could not be read.")
            content.page_count = len(content.pages)
            return content
        ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared = [
                "".join(x.itertext()) for x in _xml(archive, "xl/sharedStrings.xml").findall("s:si", ns)
            ]
        rels = {r.attrib["Id"]: r.attrib["Target"] for r in _xml(archive, "xl/_rels/workbook.xml.rels")}
        formats = {0: "General", 1: "0", 2: "0.00", 9: "0%", 10: "0.00%", 14: "mm-dd-yy"}
        styles = []
        if "xl/styles.xml" in archive.namelist():
            style_root = _xml(archive, "xl/styles.xml")
            formats.update(
                {
                    int(f.attrib["numFmtId"]): f.attrib["formatCode"]
                    for f in style_root.findall("s:numFmts/s:numFmt", ns)
                }
            )
            styles = [
                formats.get(int(f.get("numFmtId", "0")), "General")
                for f in style_root.findall("s:cellXfs/s:xf", ns)
            ]
        pages, limitations = [], []
        for sheet in _xml(archive, "xl/workbook.xml").findall("s:sheets/s:sheet", ns):
            rid = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
            target = rels[rid]
            name = target.lstrip("/") if target.startswith("/") else f"xl/{target}"
            rows = [f"Sheet: {sheet.attrib['name']}"]
            for row in _xml(archive, name).findall(".//s:sheetData/s:row", ns):
                cells = []
                for cell in row.findall("s:c", ns):
                    value = cell.findtext("s:v", "", ns)
                    if cell.get("t") == "s":
                        value = shared[int(value)]
                    elif cell.get("t") == "inlineStr":
                        value = "".join(cell.find("s:is", ns).itertext())
                    style = int(cell.get("s", "0"))
                    if style < len(styles) and styles[style] != "General":
                        value += f" [display format: {styles[style]}]"
                    formula = cell.findtext("s:f", "", ns)
                    if formula:
                        value += f" [formula: ={formula}; cached value must be verified]"
                    cells.append(f"{cell.get('r', '')}: {value}")
                rows.append(" | ".join(cells))
            pages.append("\n".join(rows))
        content = DocumentContent(pages, len(pages), limitations=limitations)
        for name in archive.namelist():
            if name.startswith("xl/media/"):
                try:
                    content.images.append((len(content.pages) + 1, image_preview(archive.read(name))))
                    content.pages.append(f"Embedded spreadsheet image: {PurePath(name).name}")
                except (OSError, ValueError):
                    content.limitations.append(f"Embedded image {PurePath(name).name} could not be read.")
        content.page_count = len(content.pages)
        return content


def read_content(
    data: bytes, mime: str, max_pages: int, skip_pages: set[int] | None = None, max_images: int | None = None
) -> DocumentContent:
    skip_pages = skip_pages or set()
    if mime == DOCX:
        try:
            content = read_content(render_word(data), "application/pdf", max_pages, skip_pages, max_images)
            content.rendering = "word_pages"
            return content
        except ValueError as exc:
            content = _office(data, mime)
            content.limitations.append(
                f"Word visual rendering failed; structured text is for manual review only. {exc}"
            )
            return content
    if mime == "application/pdf":
        with _PDFIUM, pdfium.PdfDocument(data) as document:
            count = len(document)
        visual_pages = list(range(1, min(count, max_pages) + 1))
        selected = [p for p in visual_pages if p not in skip_pages][:max_images]
        content = DocumentContent(
            [""] * len(visual_pages), count, visual_pages=visual_pages, rendering="pdf_pages"
        )
        content.images = [(p, render_preview(data, p - 1, scale=2.5)) for p in selected]
    elif mime.startswith("image/"):
        with Image.open(io.BytesIO(data)) as image:
            count = getattr(image, "n_frames", 1)
        visual_pages = list(range(1, min(count, max_pages) + 1))
        content = DocumentContent(
            [""] * len(visual_pages), count, visual_pages=visual_pages, rendering="images"
        )
        content.images = [
            (p, image_preview(data, p - 1))
            for p in [p for p in visual_pages if p not in skip_pages][:max_images]
        ]
    elif mime == XLSX:
        content = _office(data, mime)
    else:
        content = DocumentContent([decode_text(data)], 1)
    if content.page_count > max_pages:
        content.pages = content.pages[:max_pages]
        content.images = [(p, data) for p, data in content.images if p <= max_pages]
        content.limitations.append(
            f"Only {max_pages} of {content.page_count} pages or sheets could be processed."
        )
    if not content.visual_pages:
        content.visual_pages = [p for p, _ in content.images]
        content.images = [(p, image) for p, image in content.images if p not in skip_pages][:max_images]
    return content
