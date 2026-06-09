import re
import hashlib
from pathlib import Path
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter


class Chunker:
    # Default heading patterns for plain-text headings (non-# format).
    # Each entry: (compiled_regex, markdown_heading_level)
    # The regex should match the entire heading line.
    # Applied in order; first match wins. Override via heading_rules in __init__.
    DEFAULT_HEADING_RULES: list[tuple[re.Pattern, int]] = [
        # Chinese chapter/section: 第N章, 第N节, 第N部分, 第N篇
        (re.compile(r"^第[一二三四五六七八九十百千\d]+[章节部篇讲].*$"), 1),
        # English chapter/section: Chapter N, Section N
        (re.compile(r"^(?:Chapter|Section)\s+\d+.*$", re.IGNORECASE), 1),
        # Appendix
        (re.compile(r"^Appendix\s+[A-Za-z].*$", re.IGNORECASE), 1),
        # Numbered section/sub-section: 9.5.2 重点说明
        (re.compile(r"^\d+(?:\.\d+)+\s+\S.*$"), 2),
        # Instruction definition in Chinese manuals: 指令 205 GTN_FuncName
        (re.compile(r"^指令\s+\d+\s+[A-Za-z_]\w*.*$"), 2),
        # Numbered list as heading: 1. Introduction, 2.3 Overview
        (re.compile(r"^\d+\.\s+\S.*$"), 2),
        # ALL-CAPS short lines (likely headings)
        (re.compile(r"^[A-Z][A-Z\s]+[A-Z]$"), 1),
        # Chinese numbered: 一、 二、 (一) (二)
        (re.compile(r"^[（(]?[一二三四五六七八九十百千]+[）)、、]"), 2),
    ]

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        heading_rules: list[tuple[re.Pattern | str, int]] | None = None,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # Compile heading rules
        rules = heading_rules if heading_rules is not None else self.DEFAULT_HEADING_RULES
        self._heading_rules: list[tuple[re.Pattern, int]] = []
        for pattern, level in rules:
            if isinstance(pattern, str):
                pattern = re.compile(pattern)
            self._heading_rules.append((pattern, level))

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=[
                "\n## ", "\n### ", "\n#### ", "\n##### ", "\n###### ",
                "\n\n", "\n",
                "。", "？", "！", ".",
                ". ", "? ", "! ", " ",
            ],
            length_function=len,
        )

    def _normalize_headings(self, text: str) -> str:
        """Convert plain-text headings to # markdown format.

        Detects lines matching any configured heading pattern and prepends
        the appropriate number of # markers so that _extract_sections can
        build proper heading paths and section boundaries.
        Lines already starting with # are left untouched.
        """
        lines = text.split("\n")
        result: list[str] = []

        def _is_toc_dotted_line(s: str) -> bool:
            """True if the line is a table-of-contents leader-dot line."""
            stripped = s.strip()
            if not stripped:
                return False
            dot_count = stripped.count(".") + stripped.count("·")
            return dot_count / len(stripped) > 0.30

        def _is_version_date_line(s: str) -> bool:
            """True if the line looks like a version history entry (e.g. 1.8 2021年08月09日)."""
            return bool(re.match(r"^\d+\.\d+\s+\d{4}年", s))

        for line in lines:
            stripped = line.lstrip()
            # Skip if already a markdown heading or inside a code block marker
            if stripped.startswith("#") or stripped.startswith("```"):
                result.append(line)
                continue
            # Skip TOC dotted-filler lines and version-date lines
            if _is_toc_dotted_line(stripped) or _is_version_date_line(stripped):
                result.append(line)
                continue
            matched = False
            for pattern, level in self._heading_rules:
                if pattern.match(stripped):
                    indent = line[: len(line) - len(stripped)]  # preserve indentation
                    result.append(f"{indent}{'#' * level} {stripped}")
                    matched = True
                    break
            if not matched:
                result.append(line)
        return "\n".join(result)

    def chunk_file(self, md_path: str, source: str | None = None) -> list[dict[str, Any]]:
        text = Path(md_path).read_text(encoding="utf-8")
        source = source or Path(md_path).stem
        return self.chunk_text(text, source=source)

    def chunk_text(self, text: str, source: str = "") -> list[dict[str, Any]]:
        text = self._normalize_headings(text)
        sections = self._extract_sections(text)
        chunks: list[dict[str, Any]] = []

        # Track section occurrence count per heading_path to avoid duplicate IDs
        # when the same heading text appears multiple times in a document.
        section_count: dict[str, int] = {}

        for heading_path, section_text in sections:
            path_str = " > ".join(heading_path) if heading_path else ""
            section_count[path_str] = section_count.get(path_str, 0) + 1
            section_seq = section_count[path_str]

            sub_chunks = self.text_splitter.split_text(section_text)
            for i, chunk_text in enumerate(sub_chunks):
                chunk_text = chunk_text.strip()
                if not chunk_text:
                    continue
                chunks.append({
                    "id": self._make_id(source, heading_path, i, section_seq),
                    "text": chunk_text,
                    "metadata": {
                        "source": source,
                        "heading_path": path_str,
                        "chunk_index": i,
                    },
                })
        return chunks

    def _extract_sections(self, text: str) -> list[tuple[list[str], str]]:
        lines = text.split("\n")
        sections: list[tuple[list[str], str]] = []
        heading_stack: list[tuple[int, str]] = []
        current_lines: list[str] = []

        def flush():
            if current_lines:
                path = [h[1] for h in heading_stack]
                sections.append((path, "\n".join(current_lines)))

        for line in lines:
            m = re.match(r"^(#{1,6})\s+(.+)$", line)
            if m:
                flush()
                level = len(m.group(1))
                text_content = m.group(2).strip()
                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()
                heading_stack.append((level, text_content))
                current_lines = [line]
            else:
                current_lines.append(line)

        flush()
        if not sections:
            sections = [([""], text)]
        return sections

    @staticmethod
    def _make_id(source: str, heading_path: list[str], idx: int, section_seq: int = 1) -> str:
        raw = f"{source}::{'>'.join(heading_path)}::{section_seq}::{idx}"
        return hashlib.md5(raw.encode()).hexdigest()[:16]