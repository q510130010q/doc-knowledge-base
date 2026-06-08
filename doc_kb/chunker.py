import re
import hashlib
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter


class Chunker:
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=[
                "\n## ", "\n### ", "\n#### ", "\n##### ", "\n###### ",
                "\n\n", "\n", ". ", "? ", "! ", " ",
            ],
            length_function=len,
        )

    def chunk_file(self, md_path: str, source: str | None = None) -> list[dict[str, Any]]:
        text = Path(md_path).read_text(encoding="utf-8")
        source = source or Path(md_path).stem
        return self.chunk_text(text, source=source)

    def chunk_text(self, text: str, source: str = "") -> list[dict[str, Any]]:
        sections = self._extract_sections(text)
        chunks: list[dict[str, Any]] = []

        for heading_path, section_text in sections:
            sub_chunks = self.text_splitter.split_text(section_text)
            for i, chunk_text in enumerate(sub_chunks):
                chunk_text = chunk_text.strip()
                if not chunk_text:
                    continue
                chunks.append({
                    "id": self._make_id(source, heading_path, i),
                    "text": chunk_text,
                    "metadata": {
                        "source": source,
                        "heading_path": " > ".join(heading_path) if heading_path else "",
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
    def _make_id(source: str, heading_path: list[str], idx: int) -> str:
        raw = f"{source}::{'>'.join(heading_path)}::{idx}"
        return hashlib.md5(raw.encode()).hexdigest()[:16]


from pathlib import Path
