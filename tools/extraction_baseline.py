"""Offline built-in fictional extraction baseline. No arbitrary document input.

Run from repository root: PYTHONPATH=src python -m tools.extraction_baseline
No patient store, external provider, model, or exporter is invoked.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import time

from open_intelligence.document_intake import preview_document
from open_intelligence.pdf_worker import canonical_json
from open_intelligence.store import InvalidInput

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Case:
    id: str
    raw: bytes
    filename: str
    # Literal source lines authored independently of the extractor output.
    pages: tuple[tuple[str, ...], ...] = ()
    rejection: str | None = None


def corpus() -> tuple[Case, ...]:
    spec = importlib.util.spec_from_file_location('oi_authored_pdf_fixtures', ROOT / 'tests/pdf_fixtures.py')
    fixtures = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixtures)
    first = ('Fictional report ALPHA. Issued 2026-01-12.',
             'Marker Q: not detected; Marker R: pending.',
             'Specimen A: 2.5 mg/L; Specimen B: 25 mg/L.')
    second = ('Fictional report ALPHA amendment. Issued 2026-01-13.',
              'Specimen A corrected to 3.5 mg/L; Specimen B remains 25 mg/L.')
    unicode_lines = ('Fictional report BETA.', 'Mesure: 4.2 µg/L; état: indéterminé.')
    return (
        Case('E01', ('\n'.join(first) + '\n').encode(), 'baseline.txt', (first,)),
        Case('E02', ('\r\n'.join(unicode_lines) + '\r\n').encode(), 'unicode.txt', (unicode_lines,)),
        Case('E03', fixtures.text_pdf([list(first), list(second)]), 'pages.pdf', (first, second)),
        Case('E04', fixtures.text_pdf([list(first), [], list(second)]), 'blank.pdf', (first, (), second)),
        Case('E05', fixtures.text_pdf([list(second)], compressed=True), 'amendment.pdf', (second,)),
        Case('E06', fixtures.encrypted_pdf(), 'encrypted.pdf', rejection='This intake does not support encrypted PDFs'),
        Case('E07', fixtures.streams_pdf([b'q 100 0 0 100 36 600 cm /Im0 Do Q'], image_pages=(0,)),
             'scan.pdf', rejection='Every nonblank page must have extractable text; image-only or unreadable pages are unsupported'),
        Case('E08', b'%PDF-1.4\nmalformed\n%%EOF\n', 'broken.pdf',
             rejection='PDF is malformed or could not be safely extracted'),
        Case('E09', b'x' * 65537, 'oversized.txt',
             rejection='Document must be nonempty UTF-8 text, at most 64 KiB'),
    )


def checks(case: Case, value: object) -> dict[str, bool]:
    """Compare independent expectations, never echo returned content or errors."""
    if not isinstance(value, dict):
        return {'output_shape': False}
    pdf = case.filename.endswith('.pdf')
    expected_lines = []
    for page_number, page in enumerate(case.pages, 1):
        for page_line, text in enumerate(page, 1):
            row = {'line': len(expected_lines) + 1, 'text': text}
            if pdf:
                row.update(page=page_number, page_line=page_line)
            expected_lines.append(row)
    expected_text = '\n'.join(line['text'] for line in expected_lines) if pdf else case.raw.decode('utf-8')
    result = {
        'original_bytes': value.get('sha256') == hashlib.sha256(case.raw).hexdigest()
                          and type(value.get('byte_count')) is int and value['byte_count'] == len(case.raw),
        'literal_text': value.get('text') == expected_text,
        'exact_lines_and_anchors': canonical_json(value.get('lines')) == canonical_json(expected_lines),
        'review_status': value.get('clinical_review') == 'not_performed',
    }
    if pdf:
        # These controlled fixture streams emit one LF per authored line.
        expected_pages = [
            {'page': n, 'text': text, 'sha256': hashlib.sha256(text.encode()).hexdigest()}
            for n, page in enumerate(case.pages, 1)
            for text in [('\n'.join(page) + '\n') if page else '']
        ]
        result['physical_pages'] = (type(value.get('page_count')) is int
                                   and value['page_count'] == len(case.pages)
                                   and canonical_json(value.get('pages')) == canonical_json(expected_pages))
        payload = {key: value.get(key) for key in ('text', 'lines', 'pages', 'page_count', 'extractor')}
        result['rendition_fingerprint'] = value.get('extraction_sha256') == hashlib.sha256(canonical_json(payload)).hexdigest()
    return result


def run_suite(*, adapter=preview_document, clock=time.perf_counter) -> dict:
    results, metrics = [], []
    for case in corpus():
        started = clock()
        verification = {}
        try:
            value = adapter(case.raw, case.filename)
            if case.rejection is not None:
                outcome, passed = 'unexpected_acceptance', False
            else:
                verification = checks(case, value)
                passed = all(verification.values())
                outcome = 'accepted' if passed else 'mismatch'
        except InvalidInput as exc:
            passed = case.rejection is not None and str(exc) == case.rejection
            outcome = 'expected_rejection' if passed else 'error'
        except Exception:
            # Deliberately do not serialize exception messages or returned data.
            outcome, passed = 'error', False
        duration = (clock() - started) * 1000
        if not math.isfinite(duration) or duration < 0:
            duration = None
            outcome, passed = 'error', False
        else:
            duration = round(duration, 3)
        results.append({
            'fixture_id': case.id, 'original_sha256': hashlib.sha256(case.raw).hexdigest(),
            'original_bytes': len(case.raw), 'expected': 'reject' if case.rejection else 'accept',
            'outcome': outcome, 'passed': passed, 'checks': verification,
        })
        metrics.append({'fixture_id': case.id, 'operation': 'document_preview',
                        'outcome': outcome, 'duration_ms': duration})
    return {
        'schema': 'oi-extraction-baseline-v1', 'synthetic': True,
        'clinical_validation': False, 'review_minutes': None,
        'comparison': 'current_parser_only', 'timing': 'single_attempt_diagnostic_not_benchmark',
        'case_count': len(results), 'passed_count': sum(r['passed'] for r in results),
        'accepted_count': sum(r['outcome'] == 'accepted' for r in results),
        'rejected_count': sum(r['outcome'] == 'expected_rejection' for r in results),
        'error_count': sum(r['outcome'] == 'error' for r in results),
        'passed': all(r['passed'] for r in results), 'results': results, 'metrics': metrics,
        'code_sha256': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in (
            'tools/extraction_baseline.py', 'tests/pdf_fixtures.py',
            'src/open_intelligence/document_intake.py', 'src/open_intelligence/pdf_intake.py',
            'src/open_intelligence/pdf_worker.py', 'requirements-pdf.lock')},
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Create a new receipt; never replace an earlier one')
    args = parser.parse_args(argv)
    report = run_suite()
    text = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + '\n'
    if args.output:
        try:
            with args.output.open('x', encoding='utf-8') as target:
                target.write(text)
        except OSError:
            print('{"error":"receipt_not_created"}')
            return 2
    else:
        print(text, end='')
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
