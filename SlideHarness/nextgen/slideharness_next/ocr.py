from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Protocol
import csv
import io
import json
import os
import re
import shutil
import subprocess

from PIL import Image, ImageOps


@dataclass(frozen=True)
class OCRConfig:
    enabled: bool = True
    languages: str = "jpn+eng"
    dpi: int = 220
    native_text_min_chars: int = 24
    review_confidence: float = 55.0
    blocking_confidence: float = 25.0
    cache_dir: Path | None = None

    @classmethod
    def from_environment(cls, **overrides: Any) -> "OCRConfig":
        cache_value = overrides.pop("cache_dir", None) or os.environ.get("NEXTGEN_CACHE") or (Path.home() / ".cache" / "slideharness-next")
        cache_dir = Path(cache_value).expanduser().resolve() / "ocr"
        return cls(cache_dir=cache_dir, **overrides)


@dataclass(frozen=True)
class OCRBlock:
    text: str
    confidence: float
    left: int
    top: int
    width: int
    height: int
    line_number: int


@dataclass(frozen=True)
class OCRPage:
    page_number: int
    text: str
    confidence: float
    blocks: list[OCRBlock] = field(default_factory=list)
    backend: str = ""
    languages: str = ""
    image_sha256: str = ""
    source_sha256: str = ""
    preprocessing: list[str] = field(default_factory=list)
    cache_hit: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class OCRBackend(Protocol):
    @property
    def available(self) -> bool: ...

    @property
    def identity(self) -> str: ...

    def recognize(self, image_path: Path, *, page_number: int, languages: str) -> OCRPage: ...


def meaningful_character_count(text: str) -> int:
    return len(re.findall(r"[\w\u3040-\u30ff\u3400-\u9fff]", text, flags=re.UNICODE))


def native_text_is_sufficient(text: str, minimum: int) -> bool:
    return meaningful_character_count(text) >= minimum


class TesseractOCRBackend:
    def __init__(self, executable: str | None = None) -> None:
        self.executable = executable or shutil.which("tesseract") or ""
        self._identity: str | None = None

    @property
    def available(self) -> bool:
        return bool(self.executable and Path(self.executable).is_file())

    @property
    def identity(self) -> str:
        if self._identity is not None:
            return self._identity
        if not self.available:
            self._identity = "tesseract:unavailable"
            return self._identity
        result = subprocess.run([self.executable, "--version"], capture_output=True, text=True, timeout=15)
        first_line = (result.stdout or result.stderr or "unknown").splitlines()[0].strip()
        self._identity = f"tesseract:{first_line}"
        return self._identity

    def recognize(self, image_path: Path, *, page_number: int, languages: str) -> OCRPage:
        if not self.available:
            raise RuntimeError("tesseract is unavailable")
        result = subprocess.run(
            [self.executable, str(image_path), "stdout", "-l", languages, "--psm", "6", "tsv"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "tesseract failed")
        rows = csv.DictReader(io.StringIO(result.stdout), delimiter="\t")
        grouped: dict[tuple[int, int, int], list[dict[str, str]]] = {}
        confidences: list[float] = []
        for row in rows:
            text = str(row.get("text") or "").strip()
            if not text:
                continue
            try:
                confidence = float(row.get("conf") or -1)
            except ValueError:
                confidence = -1
            if confidence >= 0:
                confidences.append(confidence)
            key = (int(row.get("block_num") or 0), int(row.get("par_num") or 0), int(row.get("line_num") or 0))
            grouped.setdefault(key, []).append(row)
        blocks: list[OCRBlock] = []
        for line_number, (_, words) in enumerate(sorted(grouped.items()), start=1):
            text = " ".join(str(word.get("text") or "").strip() for word in words).strip()
            values = []
            for word in words:
                try:
                    value = float(word.get("conf") or -1)
                except ValueError:
                    value = -1
                if value >= 0:
                    values.append(value)
            left = min(int(word.get("left") or 0) for word in words)
            top = min(int(word.get("top") or 0) for word in words)
            right = max(int(word.get("left") or 0) + int(word.get("width") or 0) for word in words)
            bottom = max(int(word.get("top") or 0) + int(word.get("height") or 0) for word in words)
            blocks.append(
                OCRBlock(
                    text=text,
                    confidence=sum(values) / max(1, len(values)),
                    left=left,
                    top=top,
                    width=max(0, right - left),
                    height=max(0, bottom - top),
                    line_number=line_number,
                )
            )
        image_hash = sha256(image_path.read_bytes()).hexdigest()
        return OCRPage(
            page_number=page_number,
            text="\n".join(block.text for block in blocks if block.text),
            confidence=sum(confidences) / max(1, len(confidences)),
            blocks=blocks,
            backend=self.identity,
            languages=languages,
            image_sha256=image_hash,
        )


def _rasterizer() -> str | None:
    return shutil.which("pdftoppm") or shutil.which("pdftocairo")


def _rasterize_page(pdf_path: Path, page_number: int, target: Path, dpi: int) -> Path:
    executable = _rasterizer()
    if not executable:
        raise RuntimeError("pdftoppm or pdftocairo is unavailable")
    command = [
        executable, "-f", str(page_number), "-l", str(page_number), "-r", str(dpi),
        "-png", "-singlefile", str(pdf_path), str(target),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    output = target.with_suffix(".png")
    if result.returncode != 0 or not output.is_file():
        raise RuntimeError(result.stderr.strip() or "PDF page rasterization failed")
    with Image.open(output) as image:
        prepared = ImageOps.autocontrast(ImageOps.exif_transpose(image).convert("L"))
        prepared.save(output, format="PNG", optimize=True)
    return output


def _cache_key(image_hash: str, backend: str, config: OCRConfig) -> str:
    payload = json.dumps(
        {"image_sha256": image_hash, "backend": backend, "languages": config.languages, "dpi": config.dpi, "preprocessing": "rasterize-grayscale-autocontrast-v1"},
        sort_keys=True,
    ).encode("utf-8")
    return sha256(payload).hexdigest()


def _read_cached_page(path: Path, page_number: int) -> OCRPage | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return OCRPage(
            page_number=page_number,
            text=str(payload.get("text") or ""),
            confidence=float(payload.get("confidence") or 0),
            blocks=[OCRBlock(**item) for item in payload.get("blocks", [])],
            backend=str(payload.get("backend") or ""),
            languages=str(payload.get("languages") or ""),
            image_sha256=str(payload.get("image_sha256") or ""),
            source_sha256=str(payload.get("source_sha256") or ""),
            preprocessing=list(payload.get("preprocessing") or []),
            cache_hit=True,
        )
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def _write_cached_page(path: Path, page: OCRPage) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(page.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def ocr_pdf_pages(
    pdf_path: str | Path,
    native_texts: list[str],
    *,
    config: OCRConfig | None = None,
    backend: OCRBackend | None = None,
) -> tuple[dict[int, OCRPage], dict[str, Any]]:
    source = Path(pdf_path).resolve()
    source_hash = sha256(source.read_bytes()).hexdigest()
    config = config or OCRConfig.from_environment()
    backend = backend or TesseractOCRBackend()
    pages: dict[int, OCRPage] = {}
    findings: list[dict[str, Any]] = []
    page_reports: list[dict[str, Any]] = []
    candidates = [index for index, text in enumerate(native_texts, start=1) if not native_text_is_sufficient(text, config.native_text_min_chars)]
    if not config.enabled:
        for page_number in candidates:
            findings.append({"code": "ocr_disabled_for_low_text_page", "severity": "blocking", "page_number": page_number, "message": "PDF page has insufficient extractable text and OCR is disabled"})
    elif candidates and (not backend.available or not _rasterizer()):
        missing = "OCR backend" if not backend.available else "PDF rasterizer"
        for page_number in candidates:
            findings.append({"code": "ocr_dependency_unavailable", "severity": "blocking", "page_number": page_number, "message": f"{missing} is unavailable for a low-text PDF page"})
    elif candidates:
        with TemporaryDirectory(prefix="slideharness-ocr-") as directory:
            temporary_root = Path(directory)
            for page_number in candidates:
                try:
                    image_path = _rasterize_page(source, page_number, temporary_root / f"page-{page_number}", config.dpi)
                    image_hash = sha256(image_path.read_bytes()).hexdigest()
                    cache_path = None
                    page = None
                    if config.cache_dir is not None:
                        cache_path = config.cache_dir / f"{_cache_key(image_hash, backend.identity, config)}.json"
                        page = _read_cached_page(cache_path, page_number)
                    if page is None:
                        page = backend.recognize(image_path, page_number=page_number, languages=config.languages)
                        page = replace(
                            page,
                            source_sha256=source_hash,
                            preprocessing=[f"rasterize:{config.dpi}dpi", "grayscale", "autocontrast"],
                        )
                        if cache_path is not None:
                            _write_cached_page(cache_path, page)
                    pages[page_number] = page
                    severity = None
                    code = None
                    if not page.text.strip() or page.confidence < config.blocking_confidence:
                        severity = "blocking"
                        code = "ocr_confidence_blocking"
                    elif page.confidence < config.review_confidence:
                        severity = "review"
                        code = "ocr_confidence_review"
                    if severity:
                        findings.append({"code": code, "severity": severity, "page_number": page_number, "message": f"OCR confidence is {page.confidence:.1f}"})
                    page_reports.append(page.to_dict())
                except (OSError, RuntimeError, subprocess.SubprocessError) as error:
                    findings.append({"code": "ocr_page_failed", "severity": "blocking", "page_number": page_number, "message": str(error)})
    blocking = [item for item in findings if item["severity"] == "blocking"]
    review = [item for item in findings if item["severity"] == "review"]
    report = {
        "schema_version": "0.4.0",
        "status": "FAIL" if blocking else "PASS",
        "source": str(source),
        "native_page_count": len(native_texts) - len(candidates),
        "ocr_candidate_count": len(candidates),
        "ocr_page_count": len(pages),
        "cache_hit_count": sum(1 for page in pages.values() if page.cache_hit),
        "blocking_count": len(blocking),
        "review_count": len(review),
        "backend": backend.identity if backend.available else "unavailable",
        "languages": config.languages,
        "pages": page_reports,
        "findings": findings,
    }
    return pages, report
