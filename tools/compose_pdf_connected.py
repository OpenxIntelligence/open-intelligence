"""Reproduce inspected #221/#215 source convergence; no clinical/network action.

Inputs and complete outputs are pinned. All composition and patch validation
finish in a temporary directory before any checkout write. Only a later CI job
may publish a verified new branch; this script never touches remote references.
"""
from __future__ import annotations
import lzma
import hashlib
from pathlib import Path
import re
import subprocess
import tempfile
from compose_connected_patient_workflow import git, read_tree

SOURCES = {
    'base': ('24519839aa8ac1ea3aff88a956349ba72798a72a', 'e06c9824f2af36d83999a1e5a0f072dd0446cc2e'),
    'connected': ('2a246b54bb29cbd844c77f06f8e3a20ddff8dcc7', '85d2b15bba994233d277a94cefd7b8f9e05aa955'),
    'pdf': ('3be1106b5cd34523c4746e2df6f123048beb5659', 'b03dc8a5d14f2bf7ca4c99a4c8b72491812015ee'),
}
INITIAL = 'ef8119f646e7f21db5f1e991dab0b015e5698c2c4e36efca510f500f006d9d0e'
REVIEWED = '680fb9e8ec33d124bc3dfee05be89650151d868bc531c601dc9a0f7d382cdade'
FINAL = '00496db2a2cdf554b62cef9c92c779948cefb1f8a96d25ab89d3ef99661b7950'
PATCH_SHA = '2a736a6d0c6966da1da90ba4d1db93552ee88836c25718c063fd3764ba60744a'
WHOLE = {'tests/test_source_dialogs.js', 'src/open_intelligence/world_model.py', 'tests/test_model_investigation_freshness.js', 'tools/research/test_rna_expression_probe.py', 'tests/test_patient_record.js', 'tools/research/public_case_intake.py', 'docs/EXECUTION_BACKLOG.csv', '.github/workflows/single-cell-analysis.yml', 'src/open_intelligence/composer.py', 'tools/research/single_cell_probe.py', 'web/patient-record.js', 'docs/engineering/SYNTHETIC_WORLD_MODEL_PROJECTION.md', 'tools/research/rna_expression_probe.py', '.github/workflows/rna-analysis.yml', '.github/workflows/public-research.yml', 'tools/research/test_single_cell_probe.py'}
CONFLICTS = {'.github/workflows/public-research.yml': 3, '.github/workflows/rna-analysis.yml': 1, '.github/workflows/single-cell-analysis.yml': 1, 'docs/EXECUTION_BACKLOG.csv': 1, 'docs/engineering/SYNTHETIC_WORLD_MODEL_PROJECTION.md': 1, 'src/open_intelligence/__main__.py': 2, 'src/open_intelligence/composer.py': 8, 'src/open_intelligence/composer_lab.py': 1, 'src/open_intelligence/investigation.py': 2, 'src/open_intelligence/lab_trends.py': 4, 'src/open_intelligence/store.py': 8, 'src/open_intelligence/world_model.py': 15, 'tests/test_investigation_question_lifecycle.py': 2, 'tests/test_model_investigation_freshness.js': 2, 'tests/test_patient_record.js': 1, 'tests/test_source_dialogs.js': 1, 'tools/research/public_case_intake.py': 1, 'tools/research/rna_expression_probe.py': 1, 'tools/research/single_cell_probe.py': 1, 'tools/research/test_rna_expression_probe.py': 1, 'tools/research/test_single_cell_probe.py': 1, 'web/app.js': 7, 'web/composer.js': 9, 'web/index.html': 4, 'web/patient-record.js': 10}
PATCH_PATHS = {'tests/test_patient_record.js', 'docs/superpowers/specs/2026-11-03-pdf-connected-workflow-design.md', '.github/workflows/ui-glance.yml', 'src/open_intelligence/knowledge_context.py', 'README_WORKSPACE.md', 'tests/test_intake_report_integration.js', 'tests/document_intake_browser_journey.py', 'docs/engineering/CONNECTED_PATIENT_WORKFLOW.md', '.github/workflows/synthetic-tests.yml', 'web/workspace-entry.js', 'src/open_intelligence/world_model.py', 'tests/test_pdf_connected_followthrough.py', 'tests/test_workspace_start_http.py', 'docs/superpowers/plans/2026-11-03-pdf-connected-workflow.md', '.github/workflows/report-attribution.yml', 'tests/test_connected_intake_entry.py', 'tests/test_workspace_entry_integration.js', 'web/app.js', 'src/open_intelligence/workspace_host.py', 'src/open_intelligence/__main__.py', 'src/open_intelligence/patient_report.py', 'src/open_intelligence/evidence_review_report.py', 'src/open_intelligence/evidence_review_packet.py'}

def resolve(path, i, a, b):
    if path == 'src/open_intelligence/__main__.py':
        return a + (b if i == 1 else '            if path == "/document-intake.js":\n                return self._static("document-intake.js", "text/javascript; charset=utf-8")\n')
    if path in ('src/open_intelligence/investigation.py', 'src/open_intelligence/lab_trends.py'):
        return b
    if path == 'src/open_intelligence/composer_lab.py':
        return a
    if path == 'src/open_intelligence/store.py':
        if i == 0:
            return b
        if i in (1, 2):
            return ''
        if i == 3:
            return a.replace('"invalidated_snapshots": invalidated, "invalidated_options": invalidated_options,', '"invalidated_snapshots": invalidated, "invalidated_options": invalidated_options,\n                "invalidated_model_investigation_ids": invalidated_models,')
        if i == 4:
            return b
        if i == 5:
            return a + b
        return a
    if path == 'tests/test_investigation_question_lifecycle.py':
        return a + b
    if path == 'web/app.js':
        if i == 0:
            return a
        if i == 1:
            return b
        if i == 2:
            return a
        if i == 3:
            return a + '      active = null;\n'
        return b
    if path == 'web/composer.js':
        return a if i in (0, 5, 6, 7, 8) else b
    if path == 'web/index.html':
        if i == 0:
            return a.replace('<script src="/patient-record.js"', '<script src="/document-intake.js" defer></script>\n  <script src="/patient-record.js"') + '  <script src="/composer.js" defer></script>\n'
        if i == 1:
            return b
        if i == 2:
            return a
        return re.sub('      <footer>.*?</footer>\\n', b, a, flags=re.S)
    raise ValueError((path, i))


def digest(tree):
    h = hashlib.sha256()
    for path, (mode, data) in sorted(tree.items()):
        h.update(path.encode() + b'\0' + mode.encode() + b'\0' +
                 hashlib.sha256(data).hexdigest().encode() + b'\n')
    return h.hexdigest()


def compose(base, connected, pdf):
    result = dict(connected)
    observed = {}
    prefixes = ('src/', 'web/', 'tests/', 'tools/', '.github/',
                'THIRD_PARTY_NOTICES/', 'docs/engineering/', 'docs/safety-packet/')
    names = {'requirements-pdf.lock', 'README_IMPLEMENTATION.md', 'AGENTS.md',
             'docs/EXECUTION_BACKLOG.csv', 'docs/IMPLEMENTATION_STATUS.md'}
    for original in sorted(pdf):
        if not (original.startswith(prefixes) or original in names):
            continue
        path = original
        b, a, c = base.get(path), connected.get(path), pdf[path]
        if path == 'web/intake.js':
            path, value = 'web/document-intake.js', c[1]
        elif path in {'.github/workflows/synthetic-tests.yml', '.github/workflows/ui-glance.yml'}:
            continue
        elif a == c or c == b:
            continue
        elif a == b:
            value = c[1]
        else:
            with tempfile.TemporaryDirectory() as tmp:
                files = [Path(tmp) / name for name in ('ours', 'base', 'incoming')]
                for file, entry in zip(files, (a, b, c)):
                    file.write_bytes(entry[1] if entry else b'')
                p = subprocess.run(['git', 'merge-file', '-p', '-L', 'connected',
                    '-L', 'base', '-L', 'pdf', *map(str, files)], capture_output=True)
                if p.returncode < 0 or p.returncode > 127:
                    raise ValueError('Merge failure: ' + path)
                value = p.stdout
                if p.returncode:
                    observed[path] = p.returncode
        text = value.decode('utf-8')
        if original in WHOLE:
            text = c[1].decode('utf-8')
        elif '<<<<<<< connected' in text:
            pattern = re.compile(r'<<<<<<< connected\n(.*?)=======\n(.*?)>>>>>>> pdf\n', re.S)
            blocks = list(pattern.finditer(text))
            if len(blocks) != CONFLICTS.get(path):
                raise ValueError('Unexpected conflict blocks: ' + path)
            number = [0]
            def replacement(match):
                index = number[0]
                number[0] += 1
                return resolve(path, index, match[1], match[2])
            text = pattern.sub(replacement, text)
        if '<<<<<<< connected' in text:
            raise ValueError('Unresolved conflict: ' + path)
        if path == 'tests/test_document_intake_ui.js':
            text = text.replace('../web/intake.js', '../web/document-intake.js')
        result[path] = (connected.get(path, c)[0], text.encode('utf-8'))
    if observed != CONFLICTS or digest(result) != INITIAL:
        raise ValueError('Composition differs from inspected original owners')
    return result


def apply_reviewed(result, patch):
    if len(patch) > 131072 or hashlib.sha256(patch).hexdigest() != PATCH_SHA:
        raise ValueError('Reviewed patch changed')
    paths = re.findall(r'^diff --git a/(\S+) b/(\S+)$', patch.decode(), re.M)
    if {a for a, b in paths} != PATCH_PATHS or any(a != b for a, b in paths):
        raise ValueError('Unexpected reviewed file path')
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
        subprocess.run(['git', 'apply', '--unidiff-zero', '--check', str(patchfile)], cwd=stage, check=True)
        subprocess.run(['git', 'apply', '--unidiff-zero', str(patchfile)], cwd=stage, check=True)
        for path in PATCH_PATHS:
            target = stage / path
            result[path] = ('100755' if target.stat().st_mode & 0o111 else '100644', target.read_bytes())
    if digest(result) != REVIEWED:
        raise ValueError('Reviewed application differs from inspected source')
    # Run 41569288063 caught the report handoff link inheriting nowrap outside
    # the patient finding cards. Preserve the original browser containment gate.
    path = 'web/style.css'
    mode, data = result[path]
    old = '.patient-record-item .pill, .patient-record-item .button { max-width: 100%; white-space: normal; }\n'
    new = '.patient-record-item .pill, .patient-record-item .button { max-width: 100%; white-space: normal; }\n/* The report handoff is outside the finding cards and must wrap independently. */\n#patient-view > p > .button { max-width: 100%; white-space: normal; overflow-wrap: anywhere; }\n'
    text = data.decode('utf-8')
    if text.count(old) != 1 or new in text:
        raise ValueError('Unexpected report-handoff layout anchor')
    result[path] = (mode, text.replace(old, new).encode('utf-8'))
    if digest(result) != FINAL:
        raise ValueError('Final application differs from inspected layout correction')
    return result


def main():
    root = Path(git('rev-parse', '--show-toplevel').decode().strip())
    trees = {name: read_tree(ref, tree) for name, (ref, tree) in SOURCES.items()}
    result = compose(trees['base'], trees['connected'], trees['pdf'])
    with lzma.open(root / 'tools/pdf_connected_reviewed.patch.xz', 'rb') as file:
        patch = file.read(131073)
    result = apply_reviewed(result, patch)
    for path, (_, data) in result.items():
        target = root / path
        if target.is_symlink() or any(p.is_symlink() for p in target.parents):
            raise ValueError('Unsafe target: ' + path)
        original = trees['connected'].get(path)
        allowed = {original[1] if original else None, data}
        if (target.read_bytes() if target.is_file() else None) not in allowed:
            raise ValueError('Refusing unrelated checkout changes: ' + path)
        if target.exists() and not target.is_file():
            raise ValueError('Non-file target: ' + path)
    for path, (mode, data) in result.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        target.chmod(0o755 if mode == '100755' else 0o644)
    print(f'Verified {len(result)} source files; application digest {FINAL}')


if __name__ == '__main__':
    main()
