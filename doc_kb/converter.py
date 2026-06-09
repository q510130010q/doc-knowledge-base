from pathlib import Path

from markitdown import MarkItDown


class ConversionError(Exception):
    pass


class Converter:
    SUPPORTED_EXTENSIONS = {
        ".pdf", ".docx", ".pptx", ".xlsx",
        ".html", ".htm", ".csv", ".json", ".xml", ".txt",
    }

    def __init__(self, output_dir: str | Path = "data/md"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._converter = MarkItDown()

    def convert(self, file_path: str | Path) -> Path:
        file_path = Path(file_path)
        if file_path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            raise ConversionError(f"Unsupported file type: {file_path.suffix}")

        try:
            result = self._converter.convert(str(file_path))
        except Exception as e:
            raise ConversionError(f"Failed to convert {file_path.name}: {e}")

        stem = self._sanitize_stem(file_path.stem)
        output_path = self.output_dir / f"{stem}.md"
        output_path.write_text(result.text_content, encoding="utf-8")
        return output_path

    def convert_all(self, input_dir: str | Path) -> list[Path]:
        input_dir = Path(input_dir)
        paths: list[Path] = []
        for ext in self.SUPPORTED_EXTENSIONS:
            paths.extend(input_dir.glob(f"*{ext}"))
            paths.extend(input_dir.glob(f"*{ext.upper()}"))
        return [self.convert(p) for p in sorted(set(paths))]

    @staticmethod
    def _sanitize_stem(stem: str) -> str:
        safe = stem.replace("：", "-").replace(":", "-")
        safe = "".join(c for c in safe if c.isalnum() or c in " _-")
        return safe.strip() or "untitled"
