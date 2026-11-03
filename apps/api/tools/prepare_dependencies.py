"""Prepare exact runtime wheels; the upstream pydicom wheel is never installed.

The default downloads pinned inputs with pip and no extras/dependency resolution.
Both optional input paths support offline verification of already acquired wheels.
Only the complete final set that passes check_dependencies is published.
"""

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from check_dependencies import GateError, canonical, read_lock, verify
from pydicom_runtime import build_code_only, reviewed_manifest


def _download(lock: Path, destination: Path):
    subprocess.run([
        sys.executable, "-m", "pip", "download", "--quiet", "--disable-pip-version-check",
        "--no-cache-dir", "--no-deps", "--require-hashes", "--only-binary=:all:",
        "--dest", str(destination), "-r", str(lock),
    ], check=True)


def prepare(root: Path, destination: Path, *, existing_wheel_dir: Path | None = None,
            upstream_wheel: Path | None = None) -> dict:
    inventory = json.loads((root / "dependency-license-inventory.json").read_text())
    packages = inventory["packages"]
    candidates = [p for p in packages if canonical(p["name"]) == "pydicom"]
    if len(candidates) != 1:
        raise GateError("One reviewed pydicom runtime artifact is required")
    package = candidates[0]
    manifest = reviewed_manifest(root, package)
    locked = read_lock(root / "requirements.lock")
    if locked.pop("pydicom", None) != ("3.0.2", manifest["derived"]["sha256"]):
        raise GateError("Runtime lock does not pin the derived pydicom wheel")
    if destination.is_symlink() or (destination.exists() and (
            not destination.is_dir() or any(destination.iterdir()))):
        raise GateError("Destination must be absent or an empty directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".oi-dependency-preparation-", dir=destination.parent) as temporary:
        work = Path(temporary)
        staged = work / "runtime"
        staged.mkdir()
        if existing_wheel_dir is None:
            baseline_lock = work / "baseline.lock"
            baseline_lock.write_text("".join(
                f"{name}=={version} --hash=sha256:{digest}\n"
                for name, (version, digest) in sorted(locked.items())))
            if locked:
                _download(baseline_lock, staged)
        else:
            for item in packages:
                if canonical(item["name"]) != "pydicom":
                    filename = item["filename"]
                    if Path(filename).name != filename:
                        raise GateError("Unsafe reviewed wheel filename")
                    shutil.copyfile(existing_wheel_dir / filename, staged / filename)
        if upstream_wheel is None:
            source_dir = work / "upstream"
            source_dir.mkdir()
            _download(root / "tools/pydicom-upstream.lock", source_dir)
            if {p.name for p in source_dir.iterdir()} != {manifest["source"]["filename"]}:
                raise GateError("Unexpected upstream preparation artifact")
            upstream_wheel = source_dir / manifest["source"]["filename"]
        transform = build_code_only(upstream_wheel, staged / manifest["derived"]["filename"],
                                    manifest["source"]["sha256"])
        if transform["patch"] != manifest["patch"]:
            raise GateError("Runtime patch provenance differs from its reviewed before/after hashes")
        report = verify(root, staged)
        if destination.exists():
            destination.rmdir()
        staged.rename(destination)
    return {key: value for key, value in report.items() if key != "inventory"} | {"derivation": transform}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--wheel-dir", type=Path, required=True)
    parser.add_argument("--existing-wheel-dir", type=Path, help="Optional already-acquired baseline wheels; still hash-verified")
    parser.add_argument("--upstream-wheel", type=Path, help="Optional pinned preparation input; never installed")
    args = parser.parse_args(argv)
    try:
        report = prepare(args.api_root, args.wheel_dir, existing_wheel_dir=args.existing_wheel_dir,
                         upstream_wheel=args.upstream_wheel)
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        print(f"Dependency preparation failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
