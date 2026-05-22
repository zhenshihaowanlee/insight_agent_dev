from __future__ import annotations

import re
import zlib
from pathlib import Path
from typing import Any, Dict


SECTION_PATTERNS = {
    "abstract": r"\babstract\b",
    "method_or_design": r"\b(method|design|architecture|implementation)\b",
    "evaluation_or_experiments": r"\b(evaluation|experiment|measurement|results?)\b",
    "limitations_or_discussion": r"\b(limitation|discussion|future work)\b",
    "references": r"\breferences\b",
}


def _decode_pdf_literal(value: bytes) -> str:
    out = bytearray()
    i = 0
    while i < len(value):
        ch = value[i]
        if ch == 92 and i + 1 < len(value):  # backslash
            nxt = value[i + 1]
            escapes = {ord("n"): 10, ord("r"): 13, ord("t"): 9, ord("b"): 8, ord("f"): 12, ord("("): 40, ord(")"): 41, ord("\\"): 92}
            if nxt in escapes:
                out.append(escapes[nxt])
                i += 2
                continue
            if 48 <= nxt <= 55:
                octal = bytes([nxt])
                j = i + 2
                while j < min(i + 4, len(value)) and 48 <= value[j] <= 55:
                    octal += bytes([value[j]])
                    j += 1
                out.append(int(octal, 8))
                i = j
                continue
            i += 1
            ch = nxt
        out.append(ch)
        i += 1
    return out.decode("utf-8", errors="replace")


def _decode_pdf_hex(value: bytes) -> str:
    cleaned = re.sub(rb"\s+", b"", value)
    if len(cleaned) % 2:
        cleaned += b"0"
    try:
        raw = bytes.fromhex(cleaned.decode("ascii"))
    except ValueError:
        return ""
    if b"\x00" in raw:
        return raw.decode("utf-16-be", errors="ignore")
    return raw.decode("utf-8", errors="replace")


def _extract_pdf_string_tokens(content: bytes) -> list[str]:
    chunks: list[str] = []
    i = 0
    while i < len(content):
        ch = content[i]
        if ch == 40:  # literal string
            depth = 1
            j = i + 1
            escaped = False
            buf = bytearray()
            while j < len(content):
                cur = content[j]
                if escaped:
                    buf.append(92)
                    buf.append(cur)
                    escaped = False
                elif cur == 92:
                    escaped = True
                elif cur == 40:
                    depth += 1
                    buf.append(cur)
                elif cur == 41:
                    depth -= 1
                    if depth == 0:
                        break
                    buf.append(cur)
                else:
                    buf.append(cur)
                j += 1
            if j < len(content):
                text = _decode_pdf_literal(bytes(buf)).strip()
                if text:
                    chunks.append(text)
                i = j + 1
                continue
        elif ch == 60 and i + 1 < len(content) and content[i + 1] != 60:  # hex string
            j = content.find(b">", i + 1)
            if j != -1:
                text = _decode_pdf_hex(content[i + 1 : j]).strip()
                if text:
                    chunks.append(text)
                i = j + 1
                continue
        i += 1
    return chunks


def _decompressed_streams(raw: bytes) -> list[bytes]:
    streams: list[bytes] = []
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", raw, flags=re.DOTALL):
        dictionary = raw[max(0, match.start() - 1000) : match.start()]
        data = match.group(1)
        if b"FlateDecode" in dictionary:
            try:
                data = zlib.decompress(data)
            except zlib.error:
                continue
        streams.append(data)
    return streams


def _stream_extract(pdf_path: Path, max_chars: int) -> tuple[str, int]:
    raw = pdf_path.read_bytes()
    parts: list[str] = []
    text_showing_stream_count = 0
    for stream in _decompressed_streams(raw):
        if b"Tj" not in stream and b"TJ" not in stream and b"BT" not in stream:
            continue
        text_showing_stream_count += 1
        tokens = _extract_pdf_string_tokens(stream)
        if not tokens:
            continue
        page_text = " ".join(tokens)
        page_text = re.sub(r"\s+", " ", page_text)
        parts.append(page_text)
        if sum(len(part) for part in parts) >= max_chars:
            break
    text = "\n\n".join(parts)
    text = re.sub(r"(\w)-\s+(\w)", r"\1\2", text)
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars], text_showing_stream_count


def _fallback_extract(pdf_path: Path, max_chars: int) -> tuple[str, int]:
    stream_text, stream_count = _stream_extract(pdf_path, max_chars)
    if stream_text:
        return stream_text, stream_count
    raw = pdf_path.read_bytes()
    text = raw.decode("latin-1", errors="ignore")
    text = re.sub(r"[^ -~\n\t]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    if len(raw) > 100_000 and "%PDF" in text[:20]:
        return "", 0
    return text[:max_chars], 0


def extract_pdf_text(pdf_path: str | Path, max_pages: int, max_chars: int) -> Dict[str, Any]:
    path = Path(pdf_path)
    text = ""
    page_count = 0
    extractor = "pdf_streams"
    try:
        from PyPDF2 import PdfReader  # type: ignore

        reader = PdfReader(str(path))
        page_count = min(len(reader.pages), int(max_pages))
        parts = []
        for page in reader.pages[:page_count]:
            if len(text) >= max_chars:
                break
            parts.append(page.extract_text() or "")
            text = "\n".join(parts)
        text = text[:max_chars]
        extractor = "pypdf2"
    except Exception:
        text, page_count = _fallback_extract(path, max_chars)
        extractor = "pdf_streams" if text else "unavailable"

    section_hints = {name: bool(re.search(pattern, text, flags=re.IGNORECASE)) for name, pattern in SECTION_PATTERNS.items()}
    sufficient = bool(section_hints["abstract"] and section_hints["method_or_design"] and section_hints["evaluation_or_experiments"])
    return {
        "text": text[:max_chars],
        "page_count": page_count,
        "section_hints": section_hints,
        "extraction_sufficient": sufficient,
        "extractor": extractor,
        "ocr_used": False,
        "loop_count": 1,
    }
