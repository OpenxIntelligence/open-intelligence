"""Stage the exact, reviewable report/review integration without a remote write.

Requires the two pinned source commits locally. This script makes NO network
request, creates no commit/ref, and never touches a live patient database.
Run in a disposable checkout. The output archive identifies its staged tree,
not a fictitious commit corresponding to uncommitted source.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

REPORT = '5db96198d7ad1b17701f5b772b84a740b4ece768'
QUEUE = '2307d11a0c4504796e3c522086dbbeb21d81a545'
COMMON = '6062293a7cc0152f7863d6c3cd0b9b3cdf31eb4c'
QUEUE_PATHS = (
    '.github/workflows/evidence-review-handoff.yml',
    'docs/engineering/AUTHORIZED_EVIDENCE_REVIEW_QUEUE_HANDOFF.md',
    'src/open_intelligence/authorized_evidence_review.py',
    'src/open_intelligence/store.py',
    'tests/test_authorized_evidence_review_handoff.py',
)
PAYLOADS = {
    'evidence_report_handoff.py': 'src/open_intelligence/evidence_report_handoff.py',
    'test_report_review_handoff.py': 'tests/test_report_review_handoff.py',
}


def git(*args: str, optional: bool = False) -> bytes | None:
    result = subprocess.run(['git', *args], check=False, capture_output=True)
    if result.returncode:
        if optional:
            return None
        raise RuntimeError(f'git {args[0]} failed; no source validation claimed')
    return result.stdout


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    if Path.cwd().resolve() != root:
        raise RuntimeError('Run from the disposable repository root')
    git('cat-file', '-e', REPORT + '^{commit}')
    git('cat-file', '-e', QUEUE + '^{commit}')
    git('cat-file', '-e', COMMON + '^{commit}')
    if git('diff', '--name-only') or git('diff', '--cached', '--name-only'):
        raise RuntimeError('Refuse to overlay an already changed checkout')
    prepared = {}
    for name in QUEUE_PATHS:
        original = git('show', REPORT + ':' + name, optional=True)
        ancestor = git('show', COMMON + ':' + name, optional=True)
        incoming = git('show', QUEUE + ':' + name)
        path = root / name
        current = path.read_bytes() if path.exists() else None
        if original != ancestor or current != original:
            raise RuntimeError('Source-owner overlap requires manual review: ' + name)
        prepared[name] = incoming
    payload_root = root / 'validation/report_review'
    for source, destination in PAYLOADS.items():
        if (root / destination).exists():
            raise RuntimeError('Payload destination already exists: ' + destination)
        prepared[destination] = (payload_root / source).read_bytes()
    for name, data in prepared.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    patch = str(payload_root / 'owner_extensions.patch')
    git('apply', '--check', patch)
    git('apply', patch)
    git('add', '--', *prepared)
    tree = git('write-tree').decode().strip()
    checkout = git('rev-parse', 'HEAD').decode().strip()
    out = root / 'verification-report-handoff'
    out.mkdir(exist_ok=True)
    git('archive', '--format=zip', '--output=' + str(out / 'source-under-test.zip'), tree)
    files = git('ls-tree', '-r', '--name-only', tree).decode().splitlines()
    receipt = {
        'contract': 'oi.synthetic-report-review-composition/1',
        'workflow_checkout': checkout, 'tested_commit': None, 'tested_tree': tree,
        'report_parent': REPORT, 'review_parent': QUEUE, 'common_parent': COMMON,
        'remote_branches_changed': False,
        'clinical_or_release_approved': False,
        'files_sha256': {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                         for name in files},
    }
    (out / 'source-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('Staged review candidate:', tree)
    print('Not a merged commit, authenticated UI, delivery receipt or clinical review.')


if __name__ == '__main__':
    main()
