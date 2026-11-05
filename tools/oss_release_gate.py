"""Fail-closed *declaration* gate for adopted third-party OSS (OI-17).

This checks receipt structure and local evidence-file presence, NOT legal validity,
installed dependencies, or transitive completeness. A separate SBOM reconciliation,
security, and legal review remains mandatory before release.
"""
import argparse
import json
import re
import sys
from pathlib import Path

PERMISSIVE_SPDX = frozenset({
    "MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause",
    "ISC", "PostgreSQL", "Zlib", "BSL-1.0",
})
# Founder decision independent of whether the upstream license is permissive.
FORBIDDEN_NAMES = frozenset({"next.js", "nextjs", "next"})
REQUIRED_TEXT = (
    "name", "version", "role", "source_url", "source_commit",
    "spdx_license", "intended_commercial_use",
)
EVIDENCE_PATHS = (
    "sbom_path",
    "source_rights_receipt",
    "dependency_rights_receipt",
    "asset_and_content_rights_receipt",
    "patent_and_trademark_review_receipt",
    "security_and_maintenance_receipt",
    "notice_file",
    "human_approval_receipt",
)


def validate_manifest(root: Path, manifest_path: Path) -> list[str]:
    root = root.resolve()
    errors = []
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"manifest unreadable or invalid JSON: {exc}"]

    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        return ["expected manifest object with schema_version=1"]
    entries = payload.get("adopted_components")
    if not isinstance(entries, list):
        return ["adopted_components must be an array"]

    seen = set()
    for index, item in enumerate(entries):
        prefix = f"adopted_components[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix}: entry must be an object")
            continue
        for field in REQUIRED_TEXT + EVIDENCE_PATHS:
            if not isinstance(item.get(field), str) or not item[field].strip():
                errors.append(f"{prefix}: missing/empty {field}")

        name = item.get("name", "")
        version = item.get("version", "")
        if isinstance(name, str) and name.casefold() in FORBIDDEN_NAMES:
            errors.append(f"{prefix}: Next.js excluded by founder decision")
        identity = (str(name).casefold(), str(version))
        if identity in seen:
            errors.append(f"{prefix}: duplicate component/version")
        seen.add(identity)

        license_id = item.get("spdx_license")
        if license_id not in PERMISSIVE_SPDX:
            errors.append(f"{prefix}: SPDX {license_id!r} not Tier-1 allowlisted")
        commit = item.get("source_commit")
        if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-fA-F]{40}", commit):
            errors.append(f"{prefix}: source_commit must be a full 40-hex SHA")

        for field in EVIDENCE_PATHS:
            raw_path = item.get(field)
            if not isinstance(raw_path, str) or not raw_path.strip():
                continue
            evidence = (root / raw_path).resolve()
            if not evidence.is_relative_to(root):
                errors.append(f"{prefix}: {field} escapes repository root")
            elif not evidence.is_file() or evidence.stat().st_size == 0:
                errors.append(f"{prefix}: {field} missing or empty: {raw_path}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", nargs="?", default="docs/OSS_RELEASE_MANIFEST.json")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    errors = validate_manifest(root, root / args.manifest)
    if errors:
        for err in errors:
            print("OSS RELEASE GATE FAIL:", err, file=sys.stderr)
        return 1
    print("OSS declaration gate PASS: records are structurally complete.")
    print("NOT verified: installed/transitive inventory, receipt truth, security, or legal clearance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
