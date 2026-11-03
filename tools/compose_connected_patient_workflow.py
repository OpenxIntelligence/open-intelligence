"""Reproduce the reviewed source-owner composition; never publish or fetch data.

Only the four pinned source trees are accepted. Build every result and verify its
aggregate hash before changing files. Original source-owner histories and tests
are preserved; this is a synthetic reference-application integration recipe.
"""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile

SOURCES = {
    "base": ("24519839aa8ac1ea3aff88a956349ba72798a72a", "e06c9824f2af36d83999a1e5a0f072dd0446cc2e"),
    "clinical": ("1d5cd0502b5789371165539149dcecad8df5e551", "8ef8eec918753d224d4d57d6ae1af4ae0585c5ab"),
    "report": ("ad9713a443d2fe98e74f7d83605db776571e9929", "fb67de5ca9184754bf49c3e27210394099eb2d3e"),
    "record": ("3df25cc417f308f7ea1247962656ffa2afc62d5d", "4b72319efecd7d43eb41ed8ec6bdf736b1850aff"),
}
EXPECTED = "d97b838688c447f29fec035f363dfb5ba72d2bec9830a3c9f7fb10aa11364453"


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args])


def read_tree(ref: str, expected: str) -> dict[str, tuple[str, bytes]]:
    if git("rev-parse", ref + "^{tree}").decode().strip() != expected:
        raise ValueError("Source tree differs from inspected input: " + ref)
    result = {}
    for entry in git("ls-tree", "-rz", ref).split(b"\0"):
        if not entry:
            continue
        metadata, raw_path = entry.split(b"\t", 1)
        mode, kind, sha = metadata.decode().split()
        path = raw_path.decode("utf-8")
        parts = PurePosixPath(path).parts
        if kind != "blob" or mode not in {"100644", "100755"}:
            raise ValueError("Unsupported input entry: " + path)
        if path.startswith("/") or ".." in parts or ".git" in parts:
            raise ValueError("Unsafe input path: " + path)
        result[path] = (mode, git("cat-file", "blob", sha))
    return result


def resolve(path: str, stage: str, text: str) -> str:
    pattern = re.compile(r"<<<<<<< ours\n(.*?)=======\n(.*?)>>>>>>> incoming\n", re.S)
    blocks = list(pattern.finditer(text))
    expected = ({"src/open_intelligence/store.py": 1} if stage == "report" else {
        "src/open_intelligence/__main__.py": 1,
        "src/open_intelligence/store.py": 3,
        "web/app.js": 2, "web/index.html": 1, "web/style.css": 1,
    })
    if len(blocks) != expected.get(path):
        raise ValueError(f"Unexpected {stage} conflict: {path}, {len(blocks)}")
    index = 0
    def replacement(match):
        nonlocal index
        i = index
        index += 1
        ours, incoming = match.group(1, 2)
        if stage == "report":
            return ours + "\n" + incoming
        if path == "src/open_intelligence/store.py":
            if i == 0:
                return ours + incoming[incoming.index('        """'):]
            if i == 1:
                anchor = "            facts = self.investigation_facts(case_id, question_id)\n"
                if ours.count(anchor) != 1:
                    raise ValueError("Expected exact investigation guard anchor")
                return ours.replace(anchor, incoming + anchor)
            return ours
        if path == "web/index.html":
            return incoming + '        <p><a class="button secondary" href="#patient-report">Open the printable plain-language report</a></p>\n'
        if path == "web/style.css":
            return ours + "}\n" + incoming
        return ours + incoming
    return pattern.sub(replacement, text)


def merge(base, ours, incoming, stage):
    output = {}
    for path in sorted(set(base) | set(ours) | set(incoming)):
        b, a, c = base.get(path), ours.get(path), incoming.get(path)
        if a == c or c == b:
            value = a
        elif a == b:
            value = c
        else:
            if a is None or c is None or a[0] != c[0]:
                raise ValueError("Unreviewed delete/mode conflict: " + path)
            with tempfile.TemporaryDirectory() as tmp:
                files = [Path(tmp) / name for name in ("ours", "base", "incoming")]
                for file, entry in zip(files, (a, b, c)):
                    file.write_bytes(entry[1] if entry else b"")
                proc = subprocess.run(["git", "merge-file", "-p", "-L", "ours", "-L", "base", "-L", "incoming", *map(str, files)], capture_output=True)
                if proc.returncode < 0 or proc.returncode > 127:
                    raise ValueError("Cannot text-merge " + path)
                data = proc.stdout
                if proc.returncode:
                    data = resolve(path, stage, data.decode("utf-8")).encode("utf-8")
                value = (a[0], data)
        if value is not None:
            output[path] = value
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name, (ref, _) in SOURCES.items():
        parser.add_argument("--" + name, default=ref)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    trees = {name: read_tree(getattr(args, name), expected)
             for name, (_, expected) in SOURCES.items()}
    result = merge(trees["base"], trees["clinical"], trees["report"], "report")
    result = merge(trees["base"], result, trees["record"], "record")
    paths = sorted(set().union(*(set(tree) for tree in trees.values())))
    digest = hashlib.sha256()
    for path in paths:
        entry = result.get(path)
        suffix = (entry[0].encode() + b"\0" + hashlib.sha256(entry[1]).hexdigest().encode()
                  if entry else b"deleted")
        digest.update(path.encode() + b"\0" + suffix + b"\n")
    if digest.hexdigest() != EXPECTED:
        raise ValueError("Composed sources do not match locally tested tree: " + digest.hexdigest())
    root = Path(git("rev-parse", "--show-toplevel").decode().strip())
    for path in paths:
        target = root / path
        if target.is_symlink() or any(parent.is_symlink() for parent in target.parents if parent != root.parent):
            raise ValueError("Refusing symlink destination: " + path)
        if target.exists() and not target.is_file():
            raise ValueError("Refusing non-file destination: " + path)
        if not args.check_only:
            current = target.read_bytes() if target.is_file() else None
            clinical = trees["clinical"].get(path)
            final = result.get(path)
            permitted = {clinical[1] if clinical else None, final[1] if final else None}
            if current not in permitted:
                raise ValueError("Refusing to overwrite unrelated work: " + path)
    if not args.check_only:
        for path in paths:
            target = root / path
            if path not in result:
                target.unlink(missing_ok=True)
            else:
                mode, data = result[path]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                target.chmod(0o755 if mode == "100755" else 0o644)
    print(f"Verified {len(result)} source files; aggregate SHA-256 {EXPECTED}")


if __name__ == "__main__":
    main()
