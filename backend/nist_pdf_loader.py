"""Loader for the full NIST SP 800-61 PDF."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import List, Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.config import settings
from backend.logger import get_logger
from backend.models import Chunk, SourceType

logger = get_logger(__name__)

_HEADING_RE = re.compile(r"^\s*(\d+(?:\.\d+)*)\s+([A-Z][A-Za-z0-9 ,/\-()]{3,80})\s*$")


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _make_splitter() -> RecursiveCharacterTextSplitter:
    chunk_size_chars = settings.chunk_size_tokens * 4
    overlap_chars = settings.chunk_overlap_tokens * 4
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size_chars,
        chunk_overlap=overlap_chars,
        separators=["\n\n", "\n", ". ", " ", ""],
    )


def _extract_pages_with_headings(pdf_path: Path) -> List[tuple[str, List[tuple[int, str]]]]:
    import pdfplumber

    pages: List[tuple[str, List[tuple[int, str]]]] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            headings_in_page: List[tuple[int, str]] = []
            offset = 0
            for line in text.splitlines(keepends=True):
                match = _HEADING_RE.match(line.strip())
                if match:
                    headings_in_page.append((offset, f"{match.group(1)} {match.group(2)}".strip()))
                offset += len(line)
            pages.append((text, headings_in_page))

    return pages


def _heading_at_offset(headings_in_page: List[tuple[int, str]], offset: int, carry_in: Optional[str]) -> Optional[str]:
    active = carry_in
    for h_offset, heading in headings_in_page:
        if h_offset <= offset:
            active = heading
        else:
            break
    return active


def load_nist_pdf_chunks(pdf_path: Path) -> List[Chunk]:
    if not pdf_path.exists():
        logger.warning("NIST PDF not found at %s; skipping", pdf_path)
        return []

    try:
        pages = _extract_pages_with_headings(pdf_path)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to extract text from NIST PDF %s: %s", pdf_path, exc)
        return []

    splitter = _make_splitter()
    chunks: List[Chunk] = []
    carried_heading: Optional[str] = None

    for page_num, (page_text, headings_in_page) in enumerate(pages, start=1):
        if not page_text.strip():
            continue

        splits = splitter.split_text(page_text)
        search_cursor = 0
        for i, split_text in enumerate(splits):
            if len(split_text.strip()) < 40:
                continue

            start_offset = page_text.find(split_text[:60], search_cursor)
            if start_offset == -1:
                start_offset = search_cursor
            search_cursor = max(search_cursor, start_offset)

            section_label = _heading_at_offset(headings_in_page, start_offset, carried_heading) or "General"
            annotated_text = f"[NIST SP 800-61 | Section: {section_label} | Page {page_num}]\n{split_text}"
            chunk_hash = _content_hash(annotated_text)

            chunks.append(
                Chunk(
                    chunk_id=f"nist_p{page_num}_{i}_{chunk_hash}",
                    text=annotated_text,
                    source_type=SourceType.NIST,
                    source_name=f"NIST SP 800-61 — {section_label}",
                    file_path=str(pdf_path),
                    metadata={
                        "page": page_num,
                        "section": section_label,
                        "content_hash": chunk_hash,
                    },
                )
            )

        if headings_in_page:
            carried_heading = headings_in_page[-1][1]

    logger.info(
        "Loaded %d chunks from NIST SP 800-61 PDF (%s, %d pages)",
        len(chunks), pdf_path.name, len(pages),
    )
    return chunks
