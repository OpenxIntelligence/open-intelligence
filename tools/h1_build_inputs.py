"""Reproduce the connected H1 dependency inputs without installing anything.

--output writes canonical JSON; --verify compares its bytes to this checkout.
Supply both --api-sbom and --web-receipt on verification to reconcile outputs
from the *existing* wheel and installed-notice gates, after those gates pass.
A static inventory alone proves neither installation nor permission.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from apps.api.tools import check_dependencies as wheel_gate, pydicom_runtime

API = "apps/api/"
WEB = "apps/web/"
INPUTS = (
    API + "requirements.lock", API + "dependency-license-inventory.json",
    API + "THIRD_PARTY_NOTICES.md", API + "tools/pydicom-upstream.lock",
    API + "tools/pydicom-runtime.json", API + "tools/pydicom_runtime.py",
    API + "tools/prepare_dependencies.py", API + "tools/check_dependencies.py",
    API + "Dockerfile", API + "compose.yaml", API + "container-image-pins.json",
    WEB + "package.json", WEB + "package-lock.json", WEB + "tools/license-gate.mjs",
)
NPM_NAME = re.compile(r"(?:@[a-zA-Z0-9_][\w.-]*/)?[a-zA-Z0-9_][\w.-]*", re.ASCII)
NPM_VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path):
    return json.loads(path.read_bytes(), object_pairs_hook=unique_object)


def wheel_inputs(root, inventory):
    api = root / API
    locked = wheel_gate.read_lock(api / "requirements.lock")
    reviewed = {wheel_gate.canonical(p["name"]): p for p in inventory["packages"]}
    require(len(reviewed) == len(inventory["packages"]) and set(locked) == set(reviewed),
            "wheel set differs from the reviewed inventory")
    wheels = []
    for name, (version, digest) in sorted(locked.items()):
        row = reviewed[name]
        require((row["version"], row["sha256"]) == (version, digest),
                f"reviewed wheel differs from lock: {name}")
        wheels.append({"name": name, "version": version, "sha256": digest,
                       "filename": row["filename"], "scope": row["scope"]})
    # Use the existing binding of upstream, transform and code-only runtime pins.
    manifest = pydicom_runtime.reviewed_manifest(api, reviewed["pydicom"])
    return {"runtime_wheels": wheels, "preparation_only": [{
        "name": manifest["name"], "version": manifest["version"],
        "filename": manifest["source"]["filename"], "sha256": manifest["source"]["sha256"],
        "transformation": manifest["transformation"], "derived_sha256": manifest["derived"]["sha256"],
    }], "supplier_and_embedded_evidence": API + "dependency-license-inventory.json"}


def npm_inputs(root):
    manifest = read_json(root / WEB / "package.json")
    lock = read_json(root / WEB / "package-lock.json")
    require(lock["lockfileVersion"] == 3, "expected npm lockfile v3")
    packages = lock["packages"]
    direct = {}
    for field in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
        deps = manifest.get(field, {})
        require(deps == packages[""].get(field, {}), f"{field} differs between web manifest and lock")
        direct.update(deps)
    overrides = manifest.get("overrides", {})
    require(all(isinstance(v, str) and v.startswith("npm:") for v in overrides.values()),
            "unrecognized npm override; review this build profile")
    rows = []
    for location, record in sorted(packages.items()):
        if location == "":
            continue
        names = location.removeprefix("node_modules/").split("/node_modules/")
        require(location.startswith("node_modules/") and all(NPM_NAME.fullmatch(n) for n in names),
                f"unexpected npm lock location: {location}")
        install_name = names[-1]
        name, version = record.get("name", install_name), record["version"]
        require(NPM_NAME.fullmatch(name) and NPM_VERSION.fullmatch(version), f"invalid npm pin: {location}")
        selection = ("npm:" + name + "@" if name != install_name else "") + version
        if install_name in overrides:
            require(overrides[install_name] == selection, f"npm override mismatch: {location}")
        elif install_name != name:
            require(len(names) == 1 and direct.get(install_name) == selection, f"unbound alias: {location}")
        if len(names) == 1 and install_name in direct:
            require(direct[install_name] == selection, f"direct npm pin mismatch: {location}")
        resolved = f"https://registry.npmjs.org/{name}/-/{name.rsplit('/', 1)[-1]}-{version}.tgz"
        require(record["resolved"] == resolved and not record.get("link"), f"unexpected tarball: {location}")
        sri = record["integrity"]
        require(sri.startswith("sha512-"), f"missing SHA512 integrity: {location}")
        raw = base64.b64decode(sri[7:], validate=True)
        require(len(raw) == 64 and base64.b64encode(raw).decode() == sri[7:],
                f"invalid SHA512 integrity: {location}")
        for flag in ("dev", "optional", "devOptional", "peer"):
            require(type(record.get(flag, False)) is bool, f"invalid {flag} flag: {location}")
        rows.append({"location": location, "install_name": install_name, "name": name, "version": version,
                     "registry_tarball": resolved, "integrity": sri, "declared_license": record["license"],
                     "dependency_flags": [f for f in ("dev", "optional", "devOptional", "peer") if record.get(f)],
                     "expected_in_omit_optional_install": not record.get("optional", False)})
    require(all("node_modules/" + n in packages for n in direct), "direct npm dependency missing")
    require(set(overrides) <= {r["install_name"] for r in rows}, "npm override target missing")
    require(rows, "empty npm lock")
    return rows


def build(root):
    inputs = {p: wheel_gate.digest(root / p) for p in INPUTS}
    inventory = read_json(root / API / "dependency-license-inventory.json")
    require(inputs[API + "THIRD_PARTY_NOTICES.md"] == inventory["notices"]["sha256"],
            "API notices differ from the reviewed inventory")
    return {
        "schema": "oi.h1-build-inputs/1",
        "scope": "Declared package inputs for local fictional H1 development; no installation or release claim.",
        "inputs_sha256": inputs,
        "api": wheel_inputs(root, inventory),
        "web_lock_locations": npm_inputs(root),
        "outside_package_coverage": {
            "python_base_image_and_os_layers": API + "Dockerfile",
            "postgres_image_and_os_layers": API + "compose.yaml",
            "pinned_image_identities": API + "container-image-pins.json",
            "not_inventoried": ["packages within image layers", "host and CI toolchains",
                                "browser and browser bundle contents", "native linkage", "models, data and services"],
            "commercial_distribution_cleared": False,
        },
    }


def check_web(receipt, expected):
    lock_hash = expected["inputs_sha256"][WEB + "package-lock.json"]
    require(receipt["schema"] == "oi.frontend-dependency-evidence/1"
            and receipt["scope"] == "local-fictional-development-only"
            and receipt["commercial_release_cleared"] is False
            and receipt["native_object_linkage_reviewed"] is False
            and receipt["lock_sha256"] == lock_hash and receipt["errors"] == [],
            "web gate failed, scope differs or lock receipt is stale")
    by_path = {r["location"]: r for r in receipt["records"]}
    rows = expected["web_lock_locations"]
    require(len(by_path) == len(receipt["records"]) and set(by_path) == {r["location"] for r in rows},
            "web gate does not cover exact lock locations")
    for row in rows:
        loc = row["location"]
        got = by_path[loc]
        require(got["version"] == row["version"] and got["integrity"] == row["integrity"]
                and got["license"] == row["declared_license"]
                and got["installed"] is row["expected_in_omit_optional_install"],
                f"web gate differs from lock or omit-optional build: {loc}")
        if not got["installed"]:
            require(got["scope"] == "optional-platform-not-inspected", f"missing optional boundary: {loc}")
            continue
        require(got["name"] == row["name"] and got["resolved"] == row["registry_tarball"],
                f"web receipt identity differs: {loc}")
        notices = got["notice_files"]
        require(isinstance(notices, list) and len(notices) > 0, f"missing notice receipts: {loc}")
        for notice in notices:
            # Current notices round-trip as UTF-8. A future non-UTF-8 notice
            # needs original bytes to compare; fail closed instead of guessing.
            digest = hashlib.sha256(notice["text"].encode("utf-8")).hexdigest()
            require(digest == notice["sha256"], f"notice text/digest mismatch: {loc}")


def check_web_bom(bom, expected, app_name, app_version):
    """Cross-check the build-environment BOM with independently resolved lock inputs."""
    require((bom["bomFormat"], bom["specVersion"], bom["version"]) == ("CycloneDX", "1.6", 1),
            "unexpected web BOM format")
    rows = expected["web_lock_locations"]
    installed = {row["location"]: row for row in rows if row["expected_in_omit_optional_install"]}
    metadata = bom["metadata"]
    require(metadata["component"] == {"type": "application", "name": app_name, "version": app_version},
            "web BOM application mismatch")
    properties = {p["name"]: p["value"] for p in metadata["properties"]}
    require(len(properties) == len(metadata["properties"]) and properties == {
        "oi:scope": "Installed npm build environment for fictional H1 development",
        "oi:package-lock-sha256": expected["inputs_sha256"][WEB + "package-lock.json"],
        "oi:absent-optional-count": str(len(rows) - len(installed)),
        "oi:license-evidence": "inventory.json",
    }, "web BOM scope or lock mismatch")
    parts = {part["bom-ref"]: part for part in bom["components"]}
    require(len(parts) == len(bom["components"]) and parts.keys() == installed.keys(),
            "web BOM installed locations differ")
    for loc, row in installed.items():
        group, _, name = row["name"].rpartition("/")
        digest = base64.b64decode(row["integrity"][7:], validate=True).hex()
        identity = quote(row["name"], safe="/") + "@" + quote(row["version"], safe="")
        wanted = {
            "type": "library", "bom-ref": loc, "name": name, "version": row["version"],
            "purl": "pkg:npm/" + identity, "licenses": [{"expression": row["declared_license"]}],
            "externalReferences": [{"type": "distribution", "url": row["registry_tarball"],
                                    "hashes": [{"alg": "SHA-512", "content": digest}]}],
            "properties": [{"name": "oi:development-dependency",
                            "value": "true" if "dev" in row["dependency_flags"] else "false"}],
        }
        if group:
            wanted["group"] = group
        require(parts[loc] == wanted, f"web BOM identity or archive evidence differs: {loc}")


def check_gates(root, expected, api_sbom, web_receipt, web_sbom=None):
    inventory = read_json(root / API / "dependency-license-inventory.json")
    wanted = wheel_gate.cyclonedx({"inventory": inventory})
    got = read_json(api_sbom)
    # The wheel owner includes a wall-clock time. All other output, including
    # each native/embedded scope, license and wheel hash, must correspond.
    for record in (got, wanted):
        del record["metadata"]["timestamp"]
    require(got == wanted, "API gate SBOM differs from the current reviewed components or scope")
    check_web(read_json(web_receipt), expected)
    if web_sbom is not None:
        package = read_json(root / WEB / "package.json")
        check_web_bom(read_json(web_sbom), expected, package["name"], package["version"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--output", type=Path)
    mode.add_argument("--verify", type=Path)
    parser.add_argument("--api-sbom", type=Path)
    parser.add_argument("--web-receipt", type=Path)
    parser.add_argument("--web-sbom", type=Path, help="also verify the installed-location CycloneDX JSON")
    args = parser.parse_args(argv)
    if (args.api_sbom or args.web_receipt or args.web_sbom) and not (args.verify and args.api_sbom and args.web_receipt):
        parser.error("provide both gate outputs with --verify")
    try:
        expected = build(ROOT)
        data = (json.dumps(expected, indent=2, sort_keys=True) + "\n").encode()
        if args.output:
            args.output.write_bytes(data)
        else:
            require(args.verify.read_bytes() == data, "inventory differs from current build inputs")
            if args.api_sbom:
                check_gates(ROOT, expected, args.api_sbom, args.web_receipt, args.web_sbom)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        print(f"Build input check failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
