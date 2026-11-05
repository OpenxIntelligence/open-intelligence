#!/usr/bin/env python3
"""Check H1 import ownership without importing or executing application code.

This is a static maintenance gate, not a runtime security boundary. It deliberately
does not infer SQL ownership, object calls, external traffic or clinical authority.
"""

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re


SCHEMA = "oi.engine-boundaries/1"
SCOPE = {"package": "oi_api", "path": "apps/api/src/oi_api"}
MODULE_IMPORT = "<module>"
MAX_MANIFEST_BYTES = 1_048_576
MAX_SOURCE_BYTES = 2_097_152


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate manifest member: {key}")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError(f"Non-finite JSON number: {value}")


def load_manifest(path: Path) -> dict:
    with path.open("rb") as stream:
        data = stream.read(MAX_MANIFEST_BYTES + 1)
    if len(data) > MAX_MANIFEST_BYTES:
        raise ValueError("Manifest exceeds its size limit")
    return json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object,
                      parse_constant=_reject_constant)


def _shape(value, fields, label):
    if type(value) is not dict or set(value) != set(fields):
        raise ValueError(f"{label} requires exactly: {', '.join(sorted(fields))}")


def _text(value, label):
    if type(value) is not str or not value.strip() or len(value) > 2000:
        raise ValueError(f"{label} must be a bounded nonempty string")


def _list(value, label):
    if type(value) is not list or len(value) > 2048:
        raise ValueError(f"{label} must be a bounded list")


def _names(value, label, *, modules=False, whole_module=False):
    _list(value, label)
    for item in value:
        if type(item) is not str:
            raise ValueError(f"Invalid {label} entry")
        valid = re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", item,
                             flags=re.ASCII) if modules else item.isidentifier()
        if not valid and not (whole_module and item == MODULE_IMPORT):
            raise ValueError(f"Invalid {label} entry: {item}")
    if len(set(value)) != len(value):
        raise ValueError(f"Duplicate {label} entry")


def _validate_manifest(manifest):
    _shape(manifest, {"schema_version", "baseline_commit", "scope", "owners",
                      "reference_bridges", "legacy_imports"}, "Manifest")
    if manifest["schema_version"] != SCHEMA or manifest["scope"] != SCOPE:
        raise ValueError("Unsupported schema or narrowed H1 package scope")
    if type(manifest["baseline_commit"]) is not str or not re.fullmatch(
            r"[0-9a-f]{40}", manifest["baseline_commit"]):
        raise ValueError("A full baseline commit is required")

    owners, module_owner, exports = {}, {}, {}
    _list(manifest["owners"], "Owners")
    if not manifest["owners"]:
        raise ValueError("At least one owner is required")
    for owner in manifest["owners"]:
        _shape(owner, {"id", "responsibility", "modules", "exports", "depends_on"}, "Owner")
        identity = owner["id"]
        if type(identity) is not str or not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", identity):
            raise ValueError("Invalid owner identifier")
        if identity in owners:
            raise ValueError(f"Duplicate owner: {identity}")
        _text(owner["responsibility"], "Owner responsibility")
        _names(owner["modules"], "Module", modules=True)
        if not owner["modules"]:
            raise ValueError("An existing owner must own an existing module")
        for module in owner["modules"]:
            if module != "oi_api" and not module.startswith("oi_api."):
                raise ValueError(f"Module outside H1 scope: {module}")
            if module in module_owner:
                raise ValueError(f"Duplicate module owner: {module}")
            module_owner[module] = identity
        if type(owner["exports"]) is not dict:
            raise ValueError("Exports must map owned modules to explicit symbols")
        for module, names in owner["exports"].items():
            if module not in owner["modules"]:
                raise ValueError(f"Owner cannot export another owner's module: {module}")
            _names(names, "Export")
            exports[module] = set(names)
        _list(owner["depends_on"], "Dependencies")
        if any(type(item) is not str for item in owner["depends_on"]):
            raise ValueError("Dependency identifiers must be strings")
        if len(set(owner["depends_on"])) != len(owner["depends_on"]):
            raise ValueError("Duplicate dependency")
        owners[identity] = owner

    for identity, owner in owners.items():
        if any(dependency not in owners or dependency == identity for dependency in owner["depends_on"]):
            raise ValueError(f"Unknown or self dependency: {identity}")
    pending = {identity: set(owner["depends_on"]) for identity, owner in owners.items()}
    while pending:
        ready = {identity for identity, dependencies in pending.items() if not dependencies}
        if not ready:
            raise ValueError("Declared public dependency graph contains a cycle")
        pending = {identity: dependencies - ready for identity, dependencies in pending.items()
                   if identity not in ready}

    bridges = {}
    _list(manifest["reference_bridges"], "Reference bridges")
    for bridge in manifest["reference_bridges"]:
        _shape(bridge, {"module", "path", "symbols", "reason"}, "Reference bridge")
        module = bridge["module"]
        _names([module], "Reference module", modules=True)
        if not module.startswith("open_intelligence.") or module in bridges:
            raise ValueError("Unknown or duplicate canonical reference bridge")
        if bridge["path"] != "src/" + module.replace(".", "/") + ".py":
            raise ValueError("Reference path must match its canonical module inside the repository")
        _names(bridge["symbols"], "Reference symbol")
        _text(bridge["reason"], "Reference reason")
        bridges[module] = bridge

    legacy = {}
    _list(manifest["legacy_imports"], "Legacy imports")
    for entry in manifest["legacy_imports"]:
        _shape(entry, {"consumer", "provider", "symbols", "reason", "backlog"}, "Legacy import")
        consumer, provider = entry["consumer"], entry["provider"]
        if type(consumer) is not str or type(provider) is not str:
            raise ValueError("Legacy endpoints must be module names")
        if consumer not in module_owner or provider not in module_owner:
            raise ValueError("Legacy endpoints must have declared owners")
        if module_owner[consumer] == module_owner[provider]:
            raise ValueError("An internal import cannot be cross-owner debt")
        _names(entry["symbols"], "Legacy symbol", whole_module=True)
        if not entry["symbols"]:
            raise ValueError("A legacy exception must name its imported symbols")
        _text(entry["reason"], "Legacy reason")
        if type(entry["backlog"]) is not str or not re.fullmatch(r"OI-\d{3}", entry["backlog"]):
            raise ValueError("Legacy imports require an existing-style backlog reference")
        for name in entry["symbols"]:
            key = consumer, provider, name
            if key in legacy:
                raise ValueError("Duplicate legacy import exception")
            legacy[key] = entry
    return owners, module_owner, exports, bridges, legacy


def _violation(code, detail, *, module="", provider="", symbol="", line=0):
    return {"code": code, "detail": detail, "module": module,
            "provider": provider, "symbol": symbol, "line": line}


def _has_symlink(root, path):
    relative = path.relative_to(root)
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def _scan_sources(root, violations):
    package = root / SCOPE["path"]
    if _has_symlink(root, package):
        violations.append(_violation("source_symlink", "H1 package path contains a symlink"))
        return {}, {}, {}
    if not package.is_dir():
        violations.append(_violation("missing_module", "H1 package directory is missing"))
        return {}, {}, {}
    paths, trees, hashes = {}, {}, {}

    def walk_error(error):
        violations.append(_violation("invalid_source", f"Cannot scan H1 package: {error.strerror}"))

    for directory, directories, files in os.walk(package, followlinks=False, onerror=walk_error):
        for name in sorted(directories):
            path = Path(directory) / name
            if path.is_symlink():
                violations.append(_violation("source_symlink", str(path.relative_to(root))))
                directories.remove(name)
        for name in sorted(files):
            path = Path(directory) / name
            if path.suffix != ".py":
                continue
            if path.is_symlink():
                violations.append(_violation("source_symlink", str(path.relative_to(root))))
                continue
            parts = list(path.relative_to(package).with_suffix("").parts)
            if parts[-1] == "__init__":
                parts.pop()
            module = ".".join([SCOPE["package"], *parts])
            if module in paths:
                violations.append(_violation("invalid_source", "Ambiguous module and package paths", module=module))
                continue
            paths[module] = path
            try:
                with path.open("rb") as stream:
                    data = stream.read(MAX_SOURCE_BYTES + 1)
                if len(data) > MAX_SOURCE_BYTES:
                    raise ValueError("Source exceeds its size limit")
                trees[module] = ast.parse(data, filename=str(path.relative_to(root)))
                hashes[str(path.relative_to(root))] = hashlib.sha256(data).hexdigest()
            except (OSError, SyntaxError, ValueError, RecursionError) as error:
                violations.append(_violation("invalid_source", f"Cannot parse source: {type(error).__name__}", module=module))
    for module in sorted(paths):
        parent = module.rpartition(".")[0]
        while parent:
            if parent in paths and paths[parent].name != "__init__.py":
                violations.append(_violation("invalid_source", "A regular module cannot be a package parent",
                                             module=module, provider=parent))
            parent = parent.rpartition(".")[0]
    return paths, trees, hashes


def _package_bindings(tree):
    """Conservatively collect module-level bindings without evaluating a package."""
    names, pending = set(), list(tree.body)
    while pending:
        node = pending.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
            continue
        if isinstance(node, ast.Lambda):
            continue
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
        elif isinstance(node, (ast.MatchAs, ast.MatchStar, ast.ExceptHandler)) and node.name:
            names.add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            names.add(node.rest)
        elif isinstance(node, ast.Import):
            names.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names)
        pending.extend(ast.iter_child_nodes(node))
    return names


def _imports(module, path, tree, known_modules, package_bindings, violations):
    package = module if path.name == "__init__.py" else module.rpartition(".")[0]
    result = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Name) and node.id in {"__import__", "exec", "eval"}) or (
                isinstance(node, ast.Attribute) and node.attr in {"__import__", "exec", "eval"}):
            violations.append(_violation("dynamic_import", "Executable import indirection requires an explicit static boundary",
                                         module=module, line=node.lineno))
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == "importlib":
                    violations.append(_violation("dynamic_import", "importlib is outside the static boundary contract",
                                                 module=module, line=node.lineno))
                result.append((alias.name, MODULE_IMPORT, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = package.split(".")
                if node.level > len(parts):
                    violations.append(_violation("unknown_internal_import", "Relative import escapes the H1 package",
                                                 module=module, line=node.lineno))
                    continue
                base = ".".join(parts[:len(parts) - node.level + 1])
                if node.module:
                    base += "." + node.module
            else:
                base = node.module or ""
            if base.split(".")[0] == "importlib":
                violations.append(_violation("dynamic_import", "importlib is outside the static boundary contract",
                                             module=module, line=node.lineno))
            for alias in node.names:
                if alias.name == "*":
                    violations.append(_violation("wildcard_import", "Name every imported symbol explicitly",
                                                 module=module, provider=base, line=node.lineno))
                    continue
                candidate = base + "." + alias.name
                bindings = package_bindings.get(base, set())
                if candidate in known_modules and (alias.name in bindings or "__getattr__" in bindings):
                    violations.append(_violation("ambiguous_import", "Package attribute and child module cannot be distinguished statically; use an explicit interface",
                                                 module=module, provider=base, symbol=alias.name, line=node.lineno))
                    continue
                result.append((candidate, MODULE_IMPORT, node.lineno) if candidate in known_modules
                              else (base, alias.name, node.lineno))
    return result


def check_repository(root: Path, manifest: dict) -> dict:
    report = {"ok": False, "module_count": 0, "owner_count": 0,
              "legacy_import_count": 0, "reference_bridge_count": 0,
              "violations": []}
    violations = report["violations"]
    try:
        owners, module_owner, exports, bridges, legacy = _validate_manifest(manifest)
    except (ValueError, TypeError, RecursionError) as error:
        violations.append(_violation("invalid_manifest", str(error)))
        return report
    root = Path(root).resolve()
    paths, trees, hashes = _scan_sources(root, violations)
    report.update(module_count=len(paths), owner_count=len(owners), reference_bridge_count=len(bridges))
    for module in sorted(set(paths) - set(module_owner)):
        violations.append(_violation("unowned_module", "Register an owner before adding a module", module=module))
    for module in sorted(set(module_owner) - set(paths)):
        violations.append(_violation("missing_module", "Registered module is missing", module=module))
    for module, bridge in bridges.items():
        path = root / bridge["path"]
        if _has_symlink(root, path):
            violations.append(_violation("source_symlink", bridge["path"], module=module))
        elif not path.is_file():
            violations.append(_violation("missing_reference", "Canonical reference bridge is missing", module=module))

    seen, used_legacy, owner_edges = set(), set(), set()
    known_modules = set(paths) | set(module_owner) | set(bridges)
    package_bindings = {module: _package_bindings(tree) for module, tree in trees.items()
                        if paths[module].name == "__init__.py"}
    for consumer, tree in sorted(trees.items()):
        if consumer not in module_owner:
            continue
        for provider, symbol, line in _imports(consumer, paths[consumer], tree, known_modules, package_bindings, violations):
            namespace = provider.split(".")[0]
            if namespace not in {"oi_api", "open_intelligence"}:
                continue
            key = consumer, provider, symbol
            seen.add(key)
            if namespace == "open_intelligence":
                if provider not in bridges or symbol not in bridges[provider]["symbols"]:
                    violations.append(_violation("undeclared_reference_import", "Canonical reference bridge does not declare this symbol",
                                                 module=consumer, provider=provider, symbol=symbol, line=line))
                continue
            if provider not in module_owner or provider not in paths:
                violations.append(_violation("unknown_internal_import", "Imported H1 module has no existing declared owner",
                                             module=consumer, provider=provider, symbol=symbol, line=line))
                continue
            source_owner, target_owner = module_owner[consumer], module_owner[provider]
            if source_owner == target_owner:
                continue
            owner_edges.add((source_owner, target_owner))
            exported = symbol in exports.get(provider, set())
            dependency = target_owner in owners[source_owner]["depends_on"]
            if key in legacy:
                used_legacy.add(key)
                if exported and dependency:
                    violations.append(_violation("redundant_legacy_import", "Remove debt now covered by an approved public interface",
                                                 module=consumer, provider=provider, symbol=symbol, line=line))
            elif not exported or not dependency:
                code = "private_import" if not exported else "undeclared_dependency"
                violations.append(_violation(code, "Cross-owner import requires an exported symbol and declared dependency",
                                             module=consumer, provider=provider, symbol=symbol, line=line))
    for consumer, provider, symbol in sorted(set(legacy) - used_legacy):
        violations.append(_violation("stale_legacy_import", "Remove an exception whose import no longer exists",
                                     module=consumer, provider=provider, symbol=symbol))
    violations.sort(key=lambda item: (item["module"], item["line"], item["code"], item["provider"], item["symbol"]))
    report.update(
        ok=not violations, legacy_import_count=len(used_legacy), import_count=len(seen),
        observed_owner_dependencies=[list(edge) for edge in sorted(owner_edges)],
        manifest_sha256=hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        source_sha256=hashlib.sha256(json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        source_files=dict(sorted(hashes.items())),
        legacy_debt=[{"consumer": consumer, "provider": provider, "symbol": symbol,
                      "reason": legacy[(consumer, provider, symbol)]["reason"],
                      "backlog": legacy[(consumer, provider, symbol)]["backlog"]}
                     for consumer, provider, symbol in sorted(used_legacy)],
    )
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--manifest", type=Path, default=Path("docs/architecture/engine_boundaries.json"))
    parser.add_argument("--json", action="store_true", help="Print a deterministic machine-readable result")
    args = parser.parse_args(argv)
    path = args.manifest if args.manifest.is_absolute() else args.root / args.manifest
    try:
        report = check_repository(args.root, load_manifest(path))
    except (OSError, ValueError, RecursionError) as error:
        report = {"ok": False, "violations": [_violation("invalid_manifest", str(error))]}
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        state = "PASS" if report["ok"] else "FAIL"
        print(f"{state}: {report.get('module_count', 0)} H1 modules, {report.get('owner_count', 0)} owners, "
              f"{report.get('legacy_import_count', 0)} explicit legacy symbol imports remain")
        for violation in report["violations"]:
            print(f"{violation['code']}: {violation['module']}:{violation['line']} "
                  f"{violation['provider']} {violation['symbol']} — {violation['detail']}")
        print("Static import policy only; runtime authority and independent deployment are not established.")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
