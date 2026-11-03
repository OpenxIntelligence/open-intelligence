"""Reproduce the inspected #210/#203 source reconciliation, without publishing.

The compressed patch is a transport receipt for the readable changes in the final
PR. Inputs, patch paths and complete output digest are pinned. Build and validate
in a temporary directory before touching the checkout; refuse unrelated work.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
from compose_connected_patient_workflow import git, read_tree

SOURCES = {
    'base': ('1d5cd0502b5789371165539149dcecad8df5e551', '8ef8eec918753d224d4d57d6ae1af4ae0585c5ab'),
    'connected': ('9735414c947c211ab20154638179d0be8ff2db32', '9553a486c3811599368cf31212df030e37b72511'),
    'intake': ('f9ba8d66b56a7d6669ef0ffce902af6565e1b477', 'b06fd49b7fd10181065a87b58a0ae6580b126bef'),
}
PATCH_SHA = '947205946115e9680f61e266ffc40db540399f52d7b9352b0e582c57a086c507'
COMPOSED = '08d8fc7ab6b8da872d097e8a4f3ed7ef125da1e8cc1106a47a7b9df58dae0815'
FINAL = '2a52abe4bbbd537d681672f9b10d2c597da7b6e4a49b3472aa899bcb768ed61f'
PATCH_PATHS = {
    'README_WORKSPACE.md', 'docs/engineering/CONNECTED_PATIENT_WORKFLOW.md',
    'docs/superpowers/plans/2026-11-03-connected-intake-report.md',
    'docs/superpowers/specs/2026-11-03-connected-intake-report-design.md',
    'tests/clinical_workspace_browser_journey.py', 'tests/test_composer_intake_freshness.js',
    'tests/test_connected_intake_entry.py', 'tests/test_intake_report_integration.js',
    'tests/test_workspace_entry_integration.js', 'web/app.js', 'web/composer.js',
    'web/intake.js', 'web/workspace-entry.js',
}


def digest(tree):
    checksum = hashlib.sha256()
    for path, (mode, data) in sorted(tree.items()):
        checksum.update(path.encode() + b'\0' + mode.encode() + b'\0' +
                        hashlib.sha256(data).hexdigest().encode() + b'\n')
    return checksum.hexdigest()


def compose(base, connected, intake):
    result = {}
    conflicts = []
    for path in sorted(base.keys() | connected.keys() | intake.keys()):
        b, a, c = base.get(path), connected.get(path), intake.get(path)
        if a == c or c == b:
            value = a
        elif a == b:
            value = c
        else:
            if not a or not b or not c or not a[0] == b[0] == c[0]:
                raise ValueError('Unreviewed ownership conflict: ' + path)
            with tempfile.TemporaryDirectory() as tmp:
                files = [Path(tmp) / name for name in ('ours', 'base', 'incoming')]
                for file, entry in zip(files, (a, b, c)):
                    file.write_bytes(entry[1])
                process = subprocess.run(['git', 'merge-file', '-p', '-L', 'connected',
                    '-L', 'base', '-L', 'intake', *map(str, files)], capture_output=True)
                if process.returncode not in (0, 1):
                    raise ValueError('Cannot merge: ' + path)
                text = process.stdout.decode('utf-8')
                if process.returncode:
                    conflicts.append(path)
                    if path != 'web/app.js':
                        raise ValueError('Unexpected overlap: ' + path)
                    # Intermediate incoming guard; the pinned patch replaces it
                    # with the tested shared superset including follow-through.
                    text, count = re.subn(
                        r'<<<<<<< connected\n(.*?)=======\n(.*?)>>>>>>> intake\n',
                        lambda match: match.group(2), text, flags=re.S)
                    if count != 1:
                        raise ValueError('Unexpected case-switch conflict count')
                value = (a[0], text.encode('utf-8'))
        if value:
            result[path] = value
    if conflicts != ['web/app.js'] or digest(result) != COMPOSED:
        raise ValueError('Source composition differs from locally inspected inputs')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name, (sha, _) in SOURCES.items():
        parser.add_argument('--' + name, default=sha)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    root = Path(git('rev-parse', '--show-toplevel').decode().strip())
    trees = {name: read_tree(getattr(args, name), tree)
             for name, (_, tree) in SOURCES.items()}
    result = compose(trees['base'], trees['connected'], trees['intake'])
    with gzip.open(root / 'tools/connected_intake_reviewed.patch.gz', 'rb') as file:
        patch = file.read(131073)
    if len(patch) > 131072 or hashlib.sha256(patch).hexdigest() != PATCH_SHA:
        raise ValueError('Reviewed patch differs from verified local changes')
    paths = re.findall(r'^diff --git a/(\S+) b/(\S+)$', patch.decode(), re.M)
    if {a for a, b in paths} != PATCH_PATHS or any(a != b for a, b in paths):
        raise ValueError('Unreviewed patch path')
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp)
        subprocess.run(['git', 'init', '-q', str(stage)], check=True)
        for path, (mode, data) in result.items():
            target = stage / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            target.chmod(0o755 if mode == '100755' else 0o644)
        patchfile = stage / 'reviewed.patch'
        patchfile.write_bytes(patch)
        subprocess.run(['git', 'apply', '--check', str(patchfile)], cwd=stage, check=True)
        subprocess.run(['git', 'apply', str(patchfile)], cwd=stage, check=True)
        for path in PATCH_PATHS:
            target = stage / path
            result[path] = ('100755' if target.stat().st_mode & 0o111 else '100644', target.read_bytes())
    if digest(result) != FINAL:
        raise ValueError('Final source does not match locally tested source')
    for path, (_, data) in result.items():
        target = root / path
        if '..' in PurePosixPath(path).parts or target.is_symlink() or any(
                parent.is_symlink() for parent in target.parents if parent != root.parent):
            raise ValueError('Unsafe output: ' + path)
        original = trees['connected'].get(path)
        allowed = {original[1] if original else None, data}
        if (target.read_bytes() if target.is_file() else None) not in allowed:
            raise ValueError('Refusing to overwrite unrelated work: ' + path)
        if target.exists() and not target.is_file():
            raise ValueError('Non-file output: ' + path)
    if not args.check_only:
        for path, (mode, data) in result.items():
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            target.chmod(0o755 if mode == '100755' else 0o644)
    print(f'Verified {len(result)} application/source files; aggregate SHA-256 {FINAL}')


if __name__ == '__main__':
    main()
