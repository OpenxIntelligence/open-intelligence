"""Inventory *declared* repository dependencies without network access.

This is not an SBOM, license audit, installed-package scan, or commercial
clearance. It discovers application/research manifests and package installs in
CI workflows; resolution, source rights and deployed artifact analysis remain
separate mandatory OI-17 gates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import tomllib
from pathlib import Path

SKIP_PARTS = frozenset({
    ".git", ".venv", "venv", "node_modules", "dist", "build", "__pycache__",
    ".tox", ".mypy_cache", ".pytest_cache", "site-packages",
})
PYREQ = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_.-]*(?:\[[A-Za-z0-9_.,-]+\])?)\s*(==|>=|~=|<=|>|<|!=)?\s*([A-Za-z0-9_.+!-]*)")
PIP = re.compile(r"\bpip(?:3)?\s+install\s+([^\n#]+)")
USES = re.compile(r"^\s*(?:-\s*)?uses:\s*(\S+)")
SHA40 = re.compile(r"[0-9a-fA-F]{40}\Z")


def scope(path: Path) -> str:
    p = path.as_posix()
    if p.startswith("tools/research/"):
        return "isolated_research"
    if p.startswith(".github/workflows/"):
        return "ci_workflow"
    return "application_or_tool"


def _declaration(raw: str, source: str, line: int, kind: str) -> dict | None:
    raw = raw.strip()
    if not raw or raw.startswith("#") or raw in {"-e", "."}:
        return None
    match = PYREQ.match(raw)
    if not match:
        return {"source": source, "line": line, "raw": raw, "kind": kind,
                "status": "unparsed", "rights": "not_reviewed"}
    name, operator, version = match.groups()
    if not name:
        return None
    pinned = operator == "==" and bool(version)
    return {"source": source, "line": line, "name": name, "specifier": (operator or "") + version,
            "kind": kind, "pin_status": "pinned" if pinned else "not_exactly_pinned",
            "rights": "not_reviewed"}


def inspect(root: Path) -> dict:
    root = root.resolve()
    dependencies: list[dict] = []
    files: list[dict] = []
    workflows: list[dict] = []
    problems: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in SKIP_PARTS for part in rel.parts):
            continue
        if "tests" in rel.parts or "examples" in rel.parts:
            continue
        identifier = rel.as_posix()
        low = path.name.lower()
        is_pyreq = (low.startswith("requirements") and low.endswith((".txt", ".lock")))
        is_pyproject = low == "pyproject.toml"
        is_js = low == "package.json"
        is_lock_unknown = low in {"poetry.lock", "uv.lock", "pnpm-lock.yaml", "yarn.lock", "package-lock.json"}
        is_workflow = rel.parts[:2] == (".github", "workflows") and low.endswith((".yml", ".yaml"))
        if not any((is_pyreq, is_pyproject, is_js, is_lock_unknown, is_workflow)):
            continue
        data = path.read_bytes()
        files.append({"path": identifier, "sha256": hashlib.sha256(data).hexdigest(),
                      "declared_scope": scope(rel), "size_bytes": len(data)})
        try:
            content = data.decode("utf-8")
        except UnicodeDecodeError:
            problems.append(f"{identifier}: non-UTF8 manifest; manual inspection required")
            continue
        if is_pyreq:
            for n, line in enumerate(content.splitlines(), 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith(("-", "git+", "http:", "https:")):
                    problems.append(f"{identifier}:{n}: directive or remote requirement requires manual resolution")
                    continue
                record = _declaration(line, identifier, n, "python_requirements")
                if record:
                    dependencies.append(record)
        if is_pyproject:
            try:
                parsed = tomllib.loads(content)
                items = parsed.get("project", {}).get("dependencies", [])
                groups = parsed.get("project", {}).get("optional-dependencies", {})
                for item in items:
                    result = _declaration(item, identifier, 0, "python_project")
                    if result:
                        dependencies.append(result)
                for group, entries in groups.items():
                    for item in entries:
                        result = _declaration(item, identifier, 0, f"python_optional:{group}")
                        if result:
                            dependencies.append(result)
            except (ValueError, TypeError, AttributeError) as exc:
                problems.append(f"{identifier}: pyproject could not be parsed: {type(exc).__name__}")
        if is_js:
            try:
                parsed = json.loads(content)
                for section in ("dependencies", "devDependencies", "optionalDependencies"):
                    for name, declared in sorted(parsed.get(section, {}).items()):
                        dependencies.append({
                            "source": identifier, "line": 0, "name": name, "specifier": str(declared),
                            "kind": f"javascript_{section}",
                            "pin_status": "range_or_reference_needs_lockfile_review",
                            "rights": "not_reviewed",
                        })
            except (ValueError, TypeError, AttributeError):
                problems.append(f"{identifier}: package manifest unreadable")
        if is_lock_unknown:
            problems.append(f"{identifier}: lockfile detected but resolved dependency graph not inspected")
        if is_workflow:
            for n, line in enumerate(content.splitlines(), 1):
                action = USES.match(line)
                if action:
                    target = action.group(1)
                    if not target.startswith("./"):
                        workflows.append({
                            "source": identifier, "line": n, "action": target,
                            "pin_status": "full_sha" if SHA40.fullmatch(target.rsplit("@", 1)[-1])
                                          else "tag_or_nonsha", "rights": "not_reviewed",
                        })
                command = PIP.search(line)
                if not command:
                    continue
                try:
                    # YAML single-quoted 'run:' values end with a closing quote
                    # outside the matched command. Remove only that wrapper.
                    fragment = command.group(1).strip().rstrip("'\"")
                    args = shlex.split(fragment)
                except ValueError:
                    problems.append(f"{identifier}:{n}: unparseable pip command")
                    continue
                position = 0
                while position < len(args):
                    arg = args[position]
                    if arg in {"-r", "--requirement", "-c", "--constraint"}:
                        if position + 1 < len(args):
                            workflows.append({"source": identifier, "line": n,
                                              "requirement_ref": args[position + 1],
                                              "rights": "not_reviewed"})
                            position += 2
                            continue
                    if arg.startswith(("-", "$", "{")) or arg in {"&&", "||", "\\"}:
                        position += 1
                        continue
                    record = _declaration(arg, identifier, n, "ci_pip_install")
                    if record:
                        dependencies.append(record)
                    position += 1
    dependencies.sort(key=lambda d: (d["source"], d["line"], d.get("name", ""), d["kind"]))
    workflows.sort(key=lambda d: (d["source"], d["line"], d.get("action", d.get("requirement_ref", ""))))
    files.sort(key=lambda f: f["path"])
    return {
        "schema": "oi.static-dependency-declarations/1",
        "assessment": "declaration_only_not_sbom_not_license_clearance",
        "files": files,
        "dependency_declarations": dependencies,
        "workflow_references": workflows,
        "warnings": sorted(problems),
        "rights_verified": False,
        "resolved_build_inventory": False,
        "external_downloads_performed": False,
        "patient_data_used": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    report = inspect(args.repo)
    content = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    print(f"Manifest files: {len(report['files'])}; dependency declarations: "
          f"{len(report['dependency_declarations'])}; workflow references: "
          f"{len(report['workflow_references'])}; warnings: {len(report['warnings'])}")
    print("DECLARATIONS ONLY. Not a resolved SBOM, model/data rights audit, or clinical/security clearance.")
    if not args.output:
        print(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
