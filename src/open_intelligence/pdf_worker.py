"""Fresh-process, bounded pypdf text extraction for the synthetic prototype.

Executed by absolute path with Python -I -B; imports no application state. This
is not a PDF renderer, OCR engine, malware scanner, or clinical interpreter.
Python audit restrictions reduce accidental side effects; they are not an OS
sandbox or permission to process real patient data.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sys
import unicodedata

PINNED_VERSION = "6.21.4"
WHEEL_SHA256 = "33e4fb41ca352810eb4e9838aa0d82d6888a5f8bf682f43e99cce5faa666255c"
MAX_SOURCE_BYTES = 65536
MAX_TEXT_BYTES = 65536
MAX_LINES = 512
MAX_PAGES = 20
MAX_OUTPUT_BYTES = 524288
CPU_SECONDS = 5
ADDRESS_SPACE_BYTES = 512 * 1024 * 1024
WALL_SECONDS = 10.0

# Per-operation limits supplement the process-wide limits; none is unlimited.
PARSER_CONFIGURATION = {
    "maximum_declared_stream_length": 1048576,
    "array_based_stream_maximum_output_length": 1048576,
    "array_maximum_element_count": 8192,
    "dictionary_maximum_element_count": 4096,
    "jbig2_maximum_output_length": 1048576,
    "lzw_maximum_output_length": 1048576,
    "run_length_maximum_output_length": 1048576,
    "zlib_maximum_output_length": 1048576,
    "brotli_maximum_output_length": 1048576,
    "zlib_maximum_recovery_input_length": 65536,
    "flate_maximum_columns": 8192,
    "flate_maximum_row_length": 65536,
    "image_maximum_buffer_size": 1048576,
    "stream_filters_maximum_length": 4,
    "stream_decoding_work_maximum_length": 4194304,
    "stream_parsing_work_maximum_count": 100000,
    "page_tree_maximum_entries": 128,
    "page_tree_maximum_depth": 16,
    "page_tree_maximum_page_entries": 8192,
    "xform_maximum_invocations_per_extraction": 128,
    "jbig2dec_binary": None,
}


class PdfRejected(ValueError):
    """A bounded machine-readable failure, never a document-derived message."""


def extractor_descriptor() -> dict:
    return {
        "name": "pypdf", "version": PINNED_VERSION, "wheel_sha256": WHEEL_SHA256,
        "configuration": {
            "profile": "bounded-born-digital-v1",
            "strict": True, "extraction_mode": "plain",
            "orientations": [0, 90, 180, 270],
            "root_object_recovery_limit": 1024,
            "xref_stream_maximum_entries": 8192,
            "parser_limits": dict(PARSER_CONFIGURATION),
            "maximum_original_bytes": MAX_SOURCE_BYTES,
            "maximum_extracted_utf8_bytes": MAX_TEXT_BYTES,
            "maximum_pages": MAX_PAGES, "maximum_lines": MAX_LINES,
            "maximum_worker_output_bytes": MAX_OUTPUT_BYTES,
            "cpu_seconds": CPU_SECONDS, "address_space_bytes": ADDRESS_SPACE_BYTES,
            "wall_seconds": WALL_SECONDS,
            "line_handling": "Per-page Python str.splitlines(); global text is those lines joined with LF, without a terminal separator; original per-page extracted strings remain unchanged.",
            "empty_pages": "Retained in pages; no invented global lines.",
            "unsupported_features": ["encryption", "forms", "annotations", "embedded_files", "document_actions"],
            "visual_completeness": "Unverified: text plus images, invisible text, reading order, tables and visible-text fidelity require original-document review.",
            "clinical_assertions": "None; extraction is not clinical interpretation or review.",
        },
    }


def canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def make_rendition(page_texts: list[str]) -> dict:
    """Build the immutable display rendition; preserve raw extraction per page."""
    if not page_texts or len(page_texts) > MAX_PAGES:
        raise PdfRejected("limits")
    pages, lines = [], []
    total_bytes = 0
    visible = False
    for number, text in enumerate(page_texts, 1):
        if not isinstance(text, str):
            raise PdfRejected("invalid")
        try:
            encoded = text.encode("utf-8", errors="strict")
        except UnicodeError:
            raise PdfRejected("unextractable") from None
        total_bytes += len(encoded)
        if total_bytes > MAX_TEXT_BYTES:
            raise PdfRejected("limits")
        # Preserve printable characters, tabs and splitlines separators. Reject
        # invisible formatting/bidi controls rather than silently deleting them.
        for character in text:
            if character in "\t\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029":
                continue
            if unicodedata.category(character) in {"Cc", "Cf", "Cs"}:
                raise PdfRejected("unextractable")
        visible = visible or bool(text.strip())
        pages.append({"page": number, "text": text,
                      "sha256": hashlib.sha256(encoded).hexdigest()})
        for page_line, line in enumerate(text.splitlines(), 1):
            lines.append({"line": len(lines) + 1, "text": line,
                          "page": number, "page_line": page_line})
            if len(lines) > MAX_LINES:
                raise PdfRejected("limits")
    if not visible:
        raise PdfRejected("unextractable")
    text = "\n".join(line["text"] for line in lines)
    if len(text.encode("utf-8")) > MAX_TEXT_BYTES:
        raise PdfRejected("limits")
    result = {"text": text, "lines": lines, "pages": pages,
              "page_count": len(pages), "extractor": extractor_descriptor()}
    result["extraction_sha256"] = hashlib.sha256(canonical_json(result)).hexdigest()
    return result


def validate_input(raw: bytes) -> None:
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_SOURCE_BYTES:
        raise PdfRejected("input")
    if not re.match(rb"%PDF-(?:1\.[0-7]|2\.0)[\r\n]", raw):
        raise PdfRejected("invalid")
    if not raw.rstrip(b" \t\r\n\f").endswith(b"%%EOF"):
        raise PdfRejected("invalid")


def _set_resource_limits() -> None:
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (CPU_SECONDS, CPU_SECONDS))
        resource.setrlimit(resource.RLIMIT_AS, (ADDRESS_SPACE_BYTES, ADDRESS_SPACE_BYTES))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
        resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    except (ImportError, AttributeError, OSError, ValueError):
        raise PdfRejected("unavailable") from None


def _deny_side_effects(event: str, args: tuple) -> None:
    if (event.startswith("socket.") or event.startswith("subprocess.")
            or event in {"os.system", "os.posix_spawn", "os.spawn", "os.fork", "os.forkpty",
                         "os.exec", "os.remove", "os.rename", "os.mkdir", "os.rmdir",
                         "os.link", "os.symlink", "os.truncate"}):
        raise PdfRejected("unsupported")
    if event == "open":
        _, mode, flags = args
        if ((isinstance(mode, str) and any(flag in mode for flag in "wax+"))
                or (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))):
            raise PdfRejected("unsupported")
    if event == "import" and args[0].split(".", 1)[0] in {
            "PIL", "cryptography", "Crypto", "fontTools", "brotli", "arabic_reshaper", "bidi"}:
        raise ImportError("Optional PDF extras are disabled in this worker")


class _RejectParserWarning(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        # A parser repair or skipped-content warning must not become partial
        # success. Never relay the original log text (it can contain content).
        if record.levelno >= logging.WARNING:
            raise PdfRejected("invalid")


def _has_image_resources(resources: object, seen: set[int] | None = None) -> bool:
    """Inspect references only; never decode images or invoke image helpers."""
    if resources is None:
        return False
    seen = set() if seen is None else seen
    resources = resources.get_object()
    identity = id(resources)
    if identity in seen:
        return False
    seen.add(identity)
    if len(seen) > 128:
        raise PdfRejected("limits")
    xobjects = resources.get("/XObject")
    if xobjects is None:
        return False
    xobjects = xobjects.get_object()
    for reference in xobjects.values():
        item = reference.get_object()
        if item.get("/Subtype") == "/Image":
            return True
        if item.get("/Subtype") == "/Form" and _has_image_resources(item.get("/Resources"), seen):
            return True
    return False


def extract_in_worker(raw: bytes) -> dict:
    validate_input(raw)
    from importlib import metadata
    try:
        if metadata.version("pypdf") != PINNED_VERSION:
            raise PdfRejected("version")
    except metadata.PackageNotFoundError:
        raise PdfRejected("version") from None
    from io import BytesIO
    from pypdf import PdfReader, apply_configuration
    from pypdf.errors import DependencyError, LimitReachedError

    logger = logging.getLogger("pypdf")
    logger.handlers = [_RejectParserWarning()]
    logger.setLevel(logging.WARNING)
    logger.propagate = False
    try:
        with apply_configuration(**PARSER_CONFIGURATION):
            with PdfReader(BytesIO(raw), strict=True, root_object_recovery_limit=1024,
                           xref_stream_maximum_entries=8192) as reader:
                if reader.is_encrypted:
                    raise PdfRejected("encrypted")
                root = reader.trailer["/Root"].get_object()
                if any(key in root for key in ("/AcroForm", "/OpenAction", "/AA", "/AF")):
                    raise PdfRejected("unsupported")
                names = root.get("/Names")
                if names is not None and any(key in names.get_object() for key in ("/EmbeddedFiles", "/JavaScript")):
                    raise PdfRejected("unsupported")
                count = len(reader.pages)
                if not 1 <= count <= MAX_PAGES:
                    raise PdfRejected("limits")
                texts = []
                text_bytes = line_count = 0
                for page in reader.pages:
                    if any(key in page for key in ("/Annots", "/AA", "/AF")):
                        raise PdfRejected("unsupported")
                    text = page.extract_text(extraction_mode="plain", orientations=(0, 90, 180, 270))
                    if not isinstance(text, str):
                        raise PdfRejected("unextractable")
                    if not text.strip():
                        contents = page.get_contents()
                        if ((contents is not None and contents.get_data().strip())
                                or _has_image_resources(page.get("/Resources"))):
                            raise PdfRejected("unextractable")
                    text_bytes += len(text.encode("utf-8"))
                    line_count += len(text.splitlines())
                    if text_bytes > MAX_TEXT_BYTES or line_count > MAX_LINES:
                        raise PdfRejected("limits")
                    texts.append(text)
                return make_rendition(texts)
    except DependencyError:
        raise PdfRejected("unsupported") from None
    except LimitReachedError:
        raise PdfRejected("limits") from None


def main() -> int:
    code = 0
    try:
        _set_resource_limits()
        sys.addaudithook(_deny_side_effects)
        raw = sys.stdin.buffer.read(MAX_SOURCE_BYTES + 1)
        result = extract_in_worker(raw)
    except PdfRejected as error:
        result, code = {"error": str(error)}, 2
    except MemoryError:
        result, code = {"error": "limits"}, 2
    except Exception:
        result, code = {"error": "invalid"}, 2
    output = canonical_json(result)
    if len(output) > MAX_OUTPUT_BYTES:
        output, code = b'{"error":"limits"}', 2
    sys.stdout.buffer.write(output)
    sys.stdout.buffer.flush()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
