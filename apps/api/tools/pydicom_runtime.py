"""Deterministic, code-only repack of one separately hash-reviewed input wheel.

This module never installs packages or opens an excluded sample-data entry.
The upstream byte hash is checked before ZIP inspection. Runtime installation
additionally requires the derived hash and rights inventory gate.
"""

import base64
import csv
from email.parser import BytesParser
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
from zipfile import ZIP_STORED, BadZipFile, ZipFile, ZipInfo


NAME = "pydicom"
VERSION = "3.0.2"
BUILD = "1oi1"
TRANSFORMATION = "oi-pydicom-code-only-v1"
UPSTREAM_FILENAME = "pydicom-3.0.2-py3-none-any.whl"
FILENAME = "pydicom-3.0.2-1oi1-py3-none-any.whl"
DIST = "pydicom-3.0.2.dist-info"
RECORD = f"{DIST}/RECORD"
FIXED_TIME = (1980, 1, 1, 0, 0, 0)
EXCLUDED_PREFIXES = (
    "pydicom/data/test_files/", "pydicom/data/charset_files/",
    "pydicom/data/palettes/", "pydicom/examples/",
)
EXCLUDED_FILES = {"pydicom/examples.py"}
METADATA_FILES = {
    f"{DIST}/METADATA", f"{DIST}/WHEEL", f"{DIST}/entry_points.txt",
    f"{DIST}/licenses/LICENSE",
}
REQUIRED_FILES = {
    "pydicom/__init__.py", "pydicom/filereader.py", "pydicom/_private_dict.py",
    "pydicom/_dicom_dict.py", f"{DIST}/METADATA", f"{DIST}/WHEEL",
    f"{DIST}/licenses/LICENSE",
}


class PackagingError(ValueError):
    pass


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def reviewed_manifest(root: Path, package: dict) -> dict:
    """Bind both artifact pins and the exact transform record to the inventory."""
    derivation = package.get("derivation", {})
    path = root / "tools/pydicom-runtime.json"
    if (derivation.get("manifest") != "tools/pydicom-runtime.json" or
            derivation.get("manifest_sha256") != sha256(path)):
        raise PackagingError("Missing or changed code-only derivation review")
    manifest = json.loads(path.read_text())
    if (manifest.get("schema_version") != 1 or manifest.get("name") != NAME or
            manifest.get("version") != VERSION or manifest.get("build") != BUILD or
            manifest.get("transformation") != TRANSFORMATION or
            manifest.get("approved_scope") != "local-synthetic-h1-development"):
        raise PackagingError("Unreviewed transformation or use scope")
    source, derived = manifest["source"], manifest["derived"]
    patch = manifest["patch"]
    if (source["filename"] != UPSTREAM_FILENAME or derived["filename"] != FILENAME or
            not re.fullmatch(r"[a-f0-9]{64}", source["sha256"]) or
            not re.fullmatch(r"[a-f0-9]{64}", derived["sha256"]) or
            package.get("filename") != FILENAME or package.get("version") != VERSION or
            package.get("sha256") != derived["sha256"] or
            package.get("selected_license_expression") != "MIT AND BSD-3-Clause" or
            derivation.get("source_filename") != UPSTREAM_FILENAME or
            derivation.get("source_sha256") != source["sha256"] or
            derivation.get("transformation") != TRANSFORMATION):
        raise PackagingError("Derivation does not match the reviewed package")
    if (patch.get("path") != "pydicom/__init__.py" or
            patch.get("operation") != "remove-one-examples-import" or
            not re.fullmatch(r"[a-f0-9]{64}", patch.get("source_sha256", "")) or
            not re.fullmatch(r"[a-f0-9]{64}", patch.get("derived_sha256", ""))):
        raise PackagingError("Unreviewed eager-example import patch")
    pins = [line.strip() for line in (root / "tools/pydicom-upstream.lock").read_text().splitlines()
            if line.strip() and not line.startswith("#")]
    if pins != [f"pydicom==3.0.2 --hash=sha256:{source['sha256']}"]:
        raise PackagingError("Upstream lock does not match the derivation input")
    return manifest


def _members(archive: ZipFile) -> dict[str, ZipInfo]:
    members = {}
    for item in archive.infolist():
        name = item.filename
        parts = PurePosixPath(name).parts
        if (not name or name.startswith("/") or "\\" in name or
                any(part in (".", "..") for part in name.split("/")) or
                ":" in name or not parts or item.flag_bits & 1):
            raise PackagingError("Unsafe wheel member")
        if name in members:
            raise PackagingError("Duplicate wheel member")
        mode = stat.S_IFMT(item.external_attr >> 16)
        if mode not in (0, stat.S_IFREG, stat.S_IFDIR):
            raise PackagingError("Non-regular wheel member")
        members[name] = item
    return members


def _retained(name: str) -> bool:
    if name in EXCLUDED_FILES or name.startswith(EXCLUDED_PREFIXES):
        return False
    if name in METADATA_FILES:
        return True
    # Default-deny every non-code package asset, including extensionless files,
    # JSON URL/hash manifests and samples with unfamiliar suffixes.
    return name == "pydicom/py.typed" or (name.startswith("pydicom/") and name.endswith(".py"))


def _validate_metadata(content: bytes):
    metadata = BytesParser().parsebytes(content)
    if metadata.get_all("Name") != [NAME] or metadata.get_all("Version") != [VERSION]:
        raise PackagingError("Unexpected upstream package identity")
    for requirement in metadata.get_all("Requires-Dist", []):
        if not re.search(r';\s*extra\s*==\s*[\"\'][a-z-]+[\"\']\s*$', requirement):
            raise PackagingError("Core wheel gained an unreviewed runtime dependency")


def _validate_wheel(content: bytes, *, derived: bool):
    wheel = BytesParser().parsebytes(content)
    if (wheel.get_all("Wheel-Version") != ["1.0"] or
            wheel.get_all("Root-Is-Purelib") != ["true"] or
            wheel.get_all("Tag") != ["py3-none-any"] or
            wheel.get_all("Build", []) != ([BUILD] if derived else [])):
        raise PackagingError("Unexpected wheel platform, format or build tag")


def _record(contents: dict[str, bytes]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    for name in sorted(set(contents) | {RECORD}):
        if name == RECORD:
            writer.writerow((name, "", ""))
        else:
            content = contents[name]
            digest = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b"=").decode("ascii")
            writer.writerow((name, "sha256=" + digest, len(content)))
    return stream.getvalue().encode("utf-8")


def build_code_only(source: Path, output: Path, expected_source_hash: str) -> dict:
    """Build candidate bytes; the independent final-artifact gate must pass next."""
    if (source.name != UPSTREAM_FILENAME or output.name != FILENAME or
            not re.fullmatch(r"[a-f0-9]{64}", expected_source_hash) or
            sha256(source) != expected_source_hash):
        raise PackagingError("Upstream wheel identity or SHA-256 mismatch")
    try:
        with ZipFile(source) as archive:
            members = _members(archive)
            selected = {name for name, item in members.items() if not item.is_dir() and _retained(name)}
            if not REQUIRED_FILES <= selected:
                raise PackagingError("Required runtime code or complete license is missing")
            # Crucially, discarded entries are never passed to read(), open(),
            # extract() or testzip(). The whole input hash already pins them.
            contents = {name: archive.read(name) for name in sorted(selected)}
        _validate_metadata(contents[f"{DIST}/METADATA"])
        _validate_wheel(contents[f"{DIST}/WHEEL"], derived=False)
        original_init = contents["pydicom/__init__.py"]
        lines = original_init.splitlines(keepends=True)
        eager_import = b"import pydicom.examples\n"
        if lines.count(eager_import) != 1:
            raise PackagingError("Expected single eager-example import is absent or ambiguous")
        contents["pydicom/__init__.py"] = b"".join(line for line in lines if line != eager_import)
        patch = {
            "path": "pydicom/__init__.py", "operation": "remove-one-examples-import",
            "source_sha256": hashlib.sha256(original_init).hexdigest(),
            "derived_sha256": hashlib.sha256(contents["pydicom/__init__.py"]).hexdigest(),
        }
        contents[f"{DIST}/WHEEL"] = contents[f"{DIST}/WHEEL"].rstrip(b"\r\n") + b"\nBuild: 1oi1\n"
        contents[RECORD] = _record(contents)
        with ZipFile(output, "x", compression=ZIP_STORED, allowZip64=False) as archive:
            for name in sorted(contents):
                info = ZipInfo(name, date_time=FIXED_TIME)
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                info.compress_type = ZIP_STORED
                archive.writestr(info, contents[name])
        verify_code_only(output)
    except (BadZipFile, KeyError, UnicodeError) as exc:
        raise PackagingError("Invalid reviewed wheel structure") from exc
    return {
        "transformation": TRANSFORMATION, "source_sha256": expected_source_hash,
        "sha256": sha256(output), "retained_file_count": len(contents),
        "excluded_file_count": sum(not item.is_dir() and name not in selected and name != RECORD
                                   for name, item in members.items()),
        "patch": patch,
    }


def verify_code_only(path: Path, *, expected_init_sha256: str | None = None):
    """Reject assets and inconsistent wheel metadata independently of the hash."""
    if path.name != FILENAME:
        raise PackagingError("Derived runtime wheel filename/build is required")
    try:
        with ZipFile(path) as archive:
            members = _members(archive)
            if not REQUIRED_FILES | {RECORD} <= set(members):
                raise PackagingError("Incomplete code-only runtime wheel")
            if any(name != RECORD and not _retained(name) for name in members):
                raise PackagingError("Unapproved asset in code-only runtime wheel")
            if list(members) != sorted(members) or any(
                    item.date_time != FIXED_TIME or item.compress_type != ZIP_STORED or
                    item.create_system != 3 or item.external_attr != 0o100644 << 16 or
                    item.extra or item.comment or item.is_dir() for item in members.values()):
                raise PackagingError("Noncanonical derived wheel metadata")
            contents = {name: archive.read(name) for name in members}
        _validate_metadata(contents[f"{DIST}/METADATA"])
        _validate_wheel(contents[f"{DIST}/WHEEL"], derived=True)
        init = contents["pydicom/__init__.py"]
        if (b"import pydicom.examples\n" in init.splitlines(keepends=True) or
                expected_init_sha256 is not None and hashlib.sha256(init).hexdigest() != expected_init_sha256):
            raise PackagingError("Unreviewed or missing eager-example import removal")
        if contents[RECORD] != _record({name: data for name, data in contents.items() if name != RECORD}):
            raise PackagingError("Derived wheel RECORD does not match its contents")
    except (BadZipFile, KeyError, UnicodeError) as exc:
        raise PackagingError("Invalid derived wheel structure") from exc
