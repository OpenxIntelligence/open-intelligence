"""Check exact reviewed artifacts; this is not an automatic legal reviewer.

No network, package installation, SPDX inference or patient data is involved.
Changing the lock, rights inventory, policy or notices requires a fresh review.
"""

import argparse
from datetime import datetime, timezone
from email.parser import BytesParser
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
from zipfile import ZipFile

SCOPE = "local-synthetic-h1-development"
APPROVED = "approved_for_specified_use"
LOCK_LINE = re.compile(r"([A-Za-z0-9_.-]+)==([^\s]+) --hash=sha256:([a-f0-9]{64})")
# Guard known policy exclusions even if a manifest edit labels them approved.
# This is not a general SPDX parser; unlisted expressions still need exact review.
PROHIBITED = re.compile(r"(?:^|[\s(])(?:AGPL|GPL|LGPL|MPL|EPL|CDDL|SSPL|BUSL)-|Commons-Clause|CC-BY-NC|CC-BY-ND")


class GateError(ValueError):
    pass


def canonical(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def read_lock(path):
    found = {}
    for line in path.read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        match = LOCK_LINE.fullmatch(line)
        if not match:
            raise GateError("Lock must contain only exact versions and SHA-256 wheel hashes")
        name, version, wheel_hash = match.groups()
        name = canonical(name)
        if name in found:
            raise GateError("Duplicate locked package")
        found[name] = (version, wheel_hash)
    return found


def verify(root: Path, wheel_dir: Path):
    inventory = json.loads((root / "dependency-license-inventory.json").read_text())
    if inventory.get("schema_version") != 1 or inventory.get("status") != APPROVED:
        raise GateError("Artifact review has not approved the specified use")
    if inventory.get("approved_scope") != SCOPE or inventory.get("open_items"):
        raise GateError("Review scope mismatch or unresolved blocking rights item")
    notices = inventory["notices"]
    if notices["path"] != "THIRD_PARTY_NOTICES.md" or digest(root / notices["path"]) != notices["sha256"]:
        raise GateError("Required notices changed or are missing")
    expressions = set(inventory["license_policy"]["approved_selected_expressions"])
    if any(PROHIBITED.search(expression) for expression in expressions):
        raise GateError("A policy-excluded license cannot be approved through this inventory")
    packages = inventory["packages"]
    native = inventory.get("native_components", [])
    embedded = inventory.get("embedded_runtime_components", [])
    for artifact in packages + native + embedded:
        if artifact.get("rights_state") != APPROVED:
            raise GateError(f"Artifact has unresolved rights: {artifact['name']}")
        if artifact.get("selected_license_expression") not in expressions or not artifact.get("license_evidence"):
            raise GateError(f"Artifact lacks reviewed grant/evidence: {artifact['name']}")
    locked = read_lock(root / "requirements.lock")
    reviewed = {canonical(p["name"]): (p["version"], p["sha256"]) for p in packages}
    if not reviewed or len(reviewed) != len(packages) or locked != reviewed:
        raise GateError("Lock does not exactly match the reviewed artifact inventory")
    filenames = {p["filename"] for p in packages}
    if {p.name for p in wheel_dir.iterdir() if p.is_file()} != filenames:
        raise GateError("Downloaded artifacts differ from the reviewed wheel set")
    for package in packages:
        path = wheel_dir / package["filename"]
        if path.name != package["filename"] or digest(path) != package["sha256"]:
            raise GateError(f"Wheel integrity failure: {package['name']}")
        if canonical(package["name"]) == "pydicom":
            if not package.get("derivation"):
                raise GateError("pydicom requires the reviewed code-only derivation")
            spec = importlib.util.spec_from_file_location(
                "oi_pydicom_runtime", Path(__file__).with_name("pydicom_runtime.py"))
            runtime = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(runtime)
            manifest = runtime.reviewed_manifest(root, package)
            runtime.verify_code_only(path, expected_init_sha256=manifest["patch"]["derived_sha256"])
        elif package.get("derivation"):
            raise GateError("Unreviewed package transformation")
        with ZipFile(path) as archive:
            metadata_files = [n for n in archive.namelist() if n.endswith(".dist-info/METADATA")]
            if len(metadata_files) != 1:
                raise GateError("Wheel has ambiguous package metadata")
            metadata = BytesParser().parsebytes(archive.read(metadata_files[0]))
            if canonical(metadata["Name"]) != canonical(package["name"]) or metadata["Version"] != package["version"]:
                raise GateError("Wheel package identity differs from review")
            for evidence in package["license_evidence"]:
                if "path_in_wheel" in evidence:
                    if hashlib.sha256(archive.read(evidence["path_in_wheel"])).hexdigest() != evidence["sha256"]:
                        raise GateError("Bundled license/notice evidence differs from review")
    return {"scope": SCOPE, "package_count": len(packages), "supplier_native_component_count": len(native),
            "embedded_runtime_component_count": len(embedded),
            "inventory": inventory}


def cyclonedx(report):
    inventory = report["inventory"]
    components = []
    for ecosystem, origin, items in (
        ("pypi", "wheel", inventory["packages"]),
        ("cargo", "supplier-all-targets-sbom", inventory.get("native_components", [])),
        ("generic", "embedded-runtime-source-review", inventory.get("embedded_runtime_components", [])),
    ):
        for artifact in items:
            purl = artifact.get("purl") or f"pkg:{ecosystem}/{canonical(artifact['name'])}@{artifact['version']}"
            component = {
                "type": "library", "bom-ref": purl, "name": artifact["name"], "version": artifact["version"],
                "purl": purl,
                "licenses": [{"expression": artifact["selected_license_expression"]}],
                "properties": [
                    {"name": "oi:review-scope", "value": SCOPE},
                    {"name": "oi:rights-state", "value": artifact["rights_state"]},
                    {"name": "oi:inventory-source", "value": origin},
                ],
            }
            if artifact.get("sha256"):
                component["hashes"] = [{"alg": "SHA-256", "content": artifact["sha256"]}]
            if artifact.get("derivation"):
                component["properties"].extend([
                    {"name": "oi:transformation", "value": artifact["derivation"]["transformation"]},
                    {"name": "oi:upstream-wheel-sha256", "value": artifact["derivation"]["source_sha256"]},
                ])
            components.append(component)
    return {
        "bomFormat": "CycloneDX", "specVersion": "1.6", "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "component": {"type": "application", "name": "Open Intelligence H1 API", "version": "0.1.0"},
            "properties": [
                {"name": "oi:scope", "value": SCOPE},
                {"name": "oi:limits", "value": "Python wheels plus supplier-declared all-target Rust inventory; not a complete container, model, data, or commercial distribution clearance. Exact edges and embedded-runtime caveats remain in the rights inventory."},
            ],
        },
        "components": components,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel-dir", type=Path, required=True)
    parser.add_argument("--sbom", type=Path)
    args = parser.parse_args(argv)
    try:
        report = verify(Path(__file__).resolve().parents[1], args.wheel_dir)
        if args.sbom:
            args.sbom.write_text(json.dumps(cyclonedx(report), indent=2) + "\n")
    except (GateError, OSError, ValueError, KeyError) as exc:
        print(f"Dependency gate failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({k: v for k, v in report.items() if k != "inventory"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
