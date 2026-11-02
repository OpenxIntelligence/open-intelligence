#!/usr/bin/env python3
"""Create a deterministic, incomplete CycloneDX source/declaration inventory.

This standard-library tool reads repository text and observes its own Python/
SQLite versions. It never imports application/research modules, installs a
package, contacts a service, or resolves a deployed dependency graph.
"""
from __future__ import annotations

import argparse
import ast
from collections import defaultdict
from datetime import date
import hashlib
import json
from pathlib import Path
import platform
import re
import sqlite3
import subprocess
import sys


PREFIX = "open-intelligence:"
GENERATOR_VERSION = "1"
APP_REF = "application:open-intelligence-source-candidate"
TOOL_REF = "tool:generate-source-sbom"
LOCK_PATH = "tools/research/requirements.lock"
GENERATOR_PATH = "tools/generate_source_sbom.py"
PIN = re.compile(r"([A-Za-z0-9][A-Za-z0-9_.-]*)==([A-Za-z0-9][A-Za-z0-9.!+_-]*)")


def properties(**values: object) -> list[dict]:
    return [{"name": PREFIX + name.replace("_", "-"),
             "value": value if isinstance(value, str) else json.dumps(value, sort_keys=True)}
            for name, value in sorted(values.items())]


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def file_component(root: Path, path: str, category: str) -> dict:
    return {"type": "file", "bom-ref": "file:" + path, "name": path,
            "scope": "required" if category == "production-source" else "excluded",
            "hashes": [{"alg": "SHA-256", "content": digest((root / path).read_bytes())}],
            "properties": properties(category=category, source_path=path,
                                     license_status="UNSELECTED", origin="first-party repository file")}


def imports(root: Path, paths: list[str]) -> dict:
    names: set[str] = set()
    for path in paths:
        if not path.endswith(".py"):
            continue
        for node in ast.walk(ast.parse((root / path).read_text(encoding="utf-8"), filename=path)):
            if isinstance(node, ast.Import):
                names.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
                names.add(node.module.split(".")[0])
    first_party = {"open_intelligence", "tools"}
    return {"stdlib_roots": sorted(names & sys.stdlib_module_names),
            "first_party_absolute_roots": sorted(names & first_party),
            "unresolved_third_party_roots": sorted(names - sys.stdlib_module_names - first_party),
            "python_file_count": sum(path.endswith(".py") for path in paths),
            "method": "AST Import/ImportFrom roots only; relative imports are first-party; no module execution"}


def constant(root: Path, path: str, name: str) -> str:
    tree = ast.parse((root / path).read_text(encoding="utf-8"), filename=path)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            value = ast.literal_eval(node.value)
            if isinstance(value, str):
                return value
    raise ValueError(f"Required literal declaration is missing: {path}:{name}")


def declared_package(name: str, version: str, declarations: list[str], category: str) -> dict:
    normalized = re.sub(r"[-_.]+", "-", name).lower()
    return {"type": "library", "bom-ref": f"research-package:{normalized}@{version}",
            "name": name, "version": version, "scope": "excluded",
            "purl": f"pkg:pypi/{normalized}@{version}",
            "properties": properties(category=category, declarations=declarations,
                                     license_status="UNVERIFIED", installation="not inspected or performed",
                                     resolution="declaration only; artifacts, hashes and transitive graph unresolved")}


def workflow_inventory(root: Path, paths: list[str]) -> tuple[list[dict], dict]:
    actions: dict[str, list[str]] = defaultdict(list)
    selectors: dict[tuple[str, str], list[str]] = defaultdict(list)
    packages: dict[tuple[str, str], list[str]] = defaultdict(list)
    unresolved_installs: list[str] = []
    for path in paths:
        for line_number, line in enumerate((root / path).read_text(encoding="utf-8").splitlines(), 1):
            anchor = f"{path}:{line_number}"
            field = re.match(r"\s*(?:-\s*)?(uses|runs-on|python-version):\s*(\S+)", line)
            if field:
                key, value = field.groups()
                value = value.strip("\"'")
                if key == "uses":
                    actions[value].append(anchor)
                else:
                    selectors[key, value].append(anchor)
            if re.search(r"\bnode\s+--(?:check|test)\b", line):
                selectors["test-runtime", "Node.js"].append(anchor)
            if "headless Chromium" in line:
                selectors["test-runtime", "Chrome/Chromium"].append(anchor)
            if "pip install" in line:
                pins = PIN.findall(line)
                for name, version in pins:
                    packages[name, version].append(anchor)
                if not pins and "-r " + LOCK_PATH not in line:
                    unresolved_installs.append(anchor + " " + line.strip())
    components = []
    for reference, anchors in sorted(actions.items()):
        name, separator, version = reference.partition("@")
        component = {"type": "application", "bom-ref": "ci-action:" + reference,
                     "name": name, "scope": "excluded",
                     "properties": properties(category="ci-action-declaration", declared_reference=reference,
                                              declarations=anchors, license_status="UNVERIFIED",
                                              pin_kind="commit SHA" if re.fullmatch(r"[0-9a-f]{40}", version)
                                              else "mutable label or unresolved reference",
                                              resolution="action source, bundled dependencies and transitive graph unresolved")}
        if separator:
            component["version"] = version
        components.append(component)
    for (kind, value), anchors in sorted(selectors.items()):
        name = {"python-version": "Python (CI selector)", "runs-on": "GitHub-hosted runner"}.get(kind, value)
        component = {"type": "operating-system" if kind == "runs-on" else "platform",
                     "bom-ref": f"ci-runtime:{kind}:{value}", "name": name, "scope": "excluded",
                     "properties": properties(category="ci-test-runtime-declaration", declarations=anchors,
                                              declared_selector=value, license_status="UNVERIFIED",
                                              resolution="exact runner/binary version and bundled dependencies unverified")}
        if kind != "test-runtime":
            component["version"] = value
        components.append(component)
    components.extend(declared_package(name, version, anchors, "research-workflow-pin")
                      for (name, version), anchors in sorted(packages.items()))
    return components, {"workflow_count": len(paths), "action_reference_count": len(actions),
                        "action_occurrence_count": sum(map(len, actions.values())),
                        "ci_test_runtime_declaration_count": len(selectors),
                        "inline_research_package_count": len(packages),
                        "unresolved_install_declarations": unresolved_installs}


def services(root: Path) -> list[dict]:
    declarations = (
        ("europe-pmc", "Europe PMC bibliographic metadata", "src/open_intelligence/literature.py", "ENDPOINT", False,
         "Optional public human-authored terms with explicit attestations; metadata only; no automatic case query"),
        ("crossref", "Crossref DOI metadata", "tools/crossref_metadata.py", "API_ROOT", False,
         "Optional explicitly entered public DOI; metadata only"),
        ("meta-model-api", "Meta Model API", "src/open_intelligence/investigation.py", "META_API_URL", True,
         "Optional operator-key live mode for bounded synthetic investigation; no model weights supplied"),
    )
    result = []
    for identifier, name, path, key, authenticated, boundary in declarations:
        attributes = {"category": "external-service-declaration", "source_ref": "file:" + path,
                      "constant": key, "activation": boundary, "rights_status": "UNVERIFIED",
                      "live_verification_by_inventory": "not performed", "provider_dependency_graph": "unresolved"}
        if identifier == "meta-model-api":
            attributes["declared_model_identifier"] = constant(root, path, "META_MODEL")
        result.append({"bom-ref": "service:" + identifier, "name": name,
                       "endpoints": [constant(root, path, key)], "authenticated": authenticated,
                       "description": "Source declaration only; not a deployment, live-provider verification or rights grant.",
                       "properties": properties(**attributes)})
    return result


def build(root: Path, as_of: str) -> dict:
    if date.fromisoformat(as_of).isoformat() != as_of:
        raise ValueError("--as-of must use YYYY-MM-DD")
    production = sorted({str(path.relative_to(root)) for directory in ("src", "web")
                         for path in (root / directory).rglob("*") if path.is_file()
                         and "__pycache__" not in path.parts and path.suffix not in {".pyc", ".pyo"}}
                        | {"tools/crossref_metadata.py", "tools/__init__.py"})
    workflows = sorted(str(path.relative_to(root)) for path in (root / ".github/workflows").glob("*.y*ml"))
    declaration_paths = workflows + [LOCK_PATH, GENERATOR_PATH]
    files = [file_component(root, path, "production-source") for path in production]
    files.extend(file_component(root, path, "inventory-tool" if path == GENERATOR_PATH else "declaration-input")
                 for path in declaration_paths)
    packages = []
    for number, line in enumerate((root / LOCK_PATH).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.startswith("#"):
            continue
        match = PIN.fullmatch(line.strip())
        if not match:
            raise ValueError(f"Unsupported research lock declaration at {LOCK_PATH}:{number}")
        packages.append(declared_package(*match.groups(), [f"{LOCK_PATH}:{number}"], "research-lock-pin"))
    ci_components, counts = workflow_inventory(root, workflows)
    runtime = [
        {"type": "platform", "bom-ref": "observed-runtime:python", "name": "Python",
         "version": platform.python_version(), "scope": "required",
         "properties": properties(category="observed-local-runtime", implementation=platform.python_implementation(),
                                  observation="platform.python_version(); generator interpreter only",
                                  license_status="UNVERIFIED", resolution="not a deployment runtime or binary SBOM")},
        {"type": "library", "bom-ref": "observed-runtime:sqlite", "name": "SQLite",
         "version": sqlite3.sqlite_version, "scope": "required",
         "properties": properties(category="observed-local-runtime", observation="sqlite3.sqlite_version",
                                  license_status="UNVERIFIED", resolution="local Python binding; native build/transitives unresolved")},
    ]
    input_hashes = {component["name"]: component["hashes"][0]["content"] for component in files}
    ast_imports = imports(root, production)
    other_production_files = [path for path in production
                              if Path(path).suffix not in {".py", ".js", ".css", ".html"}]
    counts.update(production_file_count=len(production), file_component_count=len(files),
                  research_lock_package_count=len(packages), observed_runtime_count=len(runtime),
                  third_party_production_import_root_count=len(ast_imports["unresolved_third_party_roots"]))
    root_properties = properties(
        category="first-party-source-candidate", license_status="UNSELECTED",
        revision=git(root, "rev-parse", "HEAD"), branch=git(root, "branch", "--show-current"),
        working_tree_inputs_modified=bool(git(root, "status", "--porcelain", "--untracked-files=normal", "--",
                                             *production, *declaration_paths)))
    result = {
        "$schema": "https://cyclonedx.org/schema/bom-1.6.schema.json", "bomFormat": "CycloneDX",
        "specVersion": "1.6", "version": 1,
        "metadata": {
            "lifecycles": [{"phase": "pre-build"}],
            "component": {"type": "application", "bom-ref": APP_REF, "name": "Open Intelligence synthetic demo source candidate",
                          "description": "Incomplete first-party source and declaration inventory; not a built, resolved or deployed SBOM.",
                          "properties": root_properties},
            "tools": {"components": [{"type": "application", "bom-ref": TOOL_REF,
                                       "name": "Open Intelligence source inventory generator", "version": GENERATOR_VERSION,
                                       "scope": "excluded", "properties": properties(source_ref="file:" + GENERATOR_PATH,
                                                                                       license_status="UNSELECTED")}]},
            "properties": properties(
                inventory_date=as_of, inventory_counts=counts, production_ast_imports=ast_imports,
                input_manifest_sha256=digest(json.dumps(input_hashes, sort_keys=True, separators=(",", ":")).encode()),
                completeness="INCOMPLETE: source/declarations only; no binary, installed-package, container, OS, vulnerability or license scan",
                licenses="UNSELECTED first-party project; UNVERIFIED external components; no SPDX license or clearance inferred",
                dependency_graph="Only local Python/SQLite runtime relationships recorded; action/package/native/service transitives unresolved",
                runtime_separation="Research lock and workflow packages are excluded; accepted H1 design candidates are not implemented runtime dependencies",
                data_and_weights={"other_production_files": other_production_files,
                                  "status": "Additional asset review required" if other_production_files else
                                  "Enumerated production roots contain only Python/JavaScript/HTML/CSS source files",
                                  "limits": "No weight/dataset contents fetched or inspected; synthetic fixtures excluded; no installation performed"},
                safety_reconciliation="Combined candidate includes the reviewed 20-file safety reconciliation from baseline 24519839 and selected PR #123 changes, with synthetic-fixture corrections and the offline guard harness; scoped research code remains excluded from the application runtime/dependency graph; historical artifact retention is not cleared",
                exclusions="Research probe source, test/fixture contents, downloaded data, host/site packages, models, images and deployed artifacts are not inventoried",
                schema_validation="Generation checks JSON and references; independent formal schema validation is recorded in SBOM.md")},
        "components": sorted(files + runtime + packages + ci_components, key=lambda item: item["bom-ref"]),
        "services": services(root),
        "dependencies": [{"ref": APP_REF, "dependsOn": ["observed-runtime:python", "observed-runtime:sqlite"]},
                         {"ref": TOOL_REF, "dependsOn": ["observed-runtime:python"]}],
        "compositions": [{"aggregate": "incomplete", "assemblies": [APP_REF], "dependencies": [APP_REF, TOOL_REF]}],
    }
    verify_references(result)
    return result


def verify_references(inventory: dict) -> None:
    components = [inventory["metadata"]["component"], *inventory["metadata"]["tools"]["components"],
                  *inventory["components"], *inventory["services"]]
    references = [component["bom-ref"] for component in components]
    if len(references) != len(set(references)):
        raise ValueError("Duplicate BOM reference; review overlapping declaration identities")
    targets = set(references)
    for dependency in inventory["dependencies"]:
        if not {dependency["ref"], *dependency["dependsOn"]} <= targets:
            raise ValueError("Unresolved dependency reference")
    for composition in inventory["compositions"]:
        if not set(composition["assemblies"] + composition["dependencies"]) <= targets:
            raise ValueError("Unresolved composition reference")
    for component in components:
        for prop in component.get("properties", []):
            if prop["name"] == PREFIX + "source-ref" and prop["value"] not in targets:
                raise ValueError("Unresolved source-file reference")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", required=True, help="Inventory date, YYYY-MM-DD; explicit for reproducibility")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true", help="Compare with existing output without writing")
    args = parser.parse_args()
    try:
        root = args.repo.resolve()
        output = args.output or root / "docs/safety-packet" / f"SBOM_SOURCE_{args.as_of}.cdx.json"
        inventory = build(root, args.as_of)
        raw = (json.dumps(inventory, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()
        if args.check:
            if not output.is_file() or output.read_bytes() != raw:
                raise ValueError("Inventory differs from current source/declarations/runtime; regenerate before use")
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(raw)
        print(json.dumps({"result": "current" if args.check else "written", "path": str(output),
                          "sha256": digest(raw), "component_count": len(inventory["components"]),
                          "service_count": len(inventory["services"]), "completeness": "incomplete"}, sort_keys=True))
        return 0
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"Source SBOM inventory failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
