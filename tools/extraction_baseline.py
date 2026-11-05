"""Offline built-in fictional extraction baseline. No arbitrary document input.

Run from repository root: PYTHONPATH=src python -m tools.extraction_baseline
No patient store, external provider, model, or exporter is invoked.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import time

from open_intelligence.document_intake import preview_document
from open_intelligence.pdf_worker import canonical_json, extractor_descriptor, make_rendition
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
    # An isolated Tj has no authored final line advance.
    pdf_terminal_lf: bool = True


def _fixtures():
    spec = importlib.util.spec_from_file_location('oi_authored_pdf_fixtures', ROOT / 'tests/pdf_fixtures.py')
    fixtures = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixtures)
    return fixtures


def corpus() -> tuple[Case, ...]:
    fixtures = _fixtures()
    first = ('Fictional report ALPHA. Issued 2026-01-12.',
             'Marker Q: not detected; Marker R: pending.',
             'Specimen A: 2.5 mg/L; Specimen B: 25 mg/L.')
    second = ('Fictional report ALPHA amendment. Issued 2026-01-13.',
              'Specimen A corrected to 3.5 mg/L; Specimen B remains 25 mg/L.')
    unicode_lines = ('Fictional report BETA.', 'Mesure: 4.2 µg/L; état: indéterminé.')
    multilingual = ('\ufeffFictional multilingual note.', 'E\u0301chantillon A : 4,2 µg/L.',
                    'العينة ب: النتيجة قيد الانتظار')
    tabular = ('Specimen\tMarker\tStatus', 'A\tQ\tnot detected', '',
               'B\tQ\tpending', 'B\tR\tindeterminate')
    rotated = ('Specimen A: not detected.', 'Specimen B: pending.')
    streams = [f'BT /F1 10 Tf {matrix} 300 300 Tm ({line}) Tj ET'.encode()
               for matrix, line in zip(('0 1 -1 0', '0 -1 1 0'), rotated)]
    content = b'BT /F1 10 Tf 36 756 Td (Independent fictional cover.) Tj ET'
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
        Case('E10', '\r\n'.join(multilingual).encode(), 'multilingual.txt', (multilingual,)),
        Case('E11', '\n'.join(tabular).encode(), 'specimens.txt', (tabular,)),
        Case('E12', fixtures.streams_pdf(streams), 'rotated.pdf',
             tuple((line,) for line in rotated), pdf_terminal_lf=False),
        Case('E13', fixtures.streams_pdf([content, b'q 8 0 0 8 20 20 cm /Im0 Do Q'],
                                        image_pages=(1,)), 'partial-scan.pdf',
             rejection='Every nonblank page must have extractable text; image-only or unreadable pages are unsupported'),
        Case('E14', fixtures.streams_pdf([content], page_extra=b'/Annots [<< /Type /Annot /Subtype /Text /Rect [0 0 20 20] /Contents (Fictional correction.) >>]'),
             'annotation.pdf', rejection='PDF requires unsupported features or optional dependencies'),
        Case('E15', 'Specimen A: 2\u202e5 mg/L'.encode(), 'direction-control.txt',
             rejection='Document contains unsupported controls or binary content'),
        Case('E16', fixtures.streams_pdf([content], catalog_extra=b'/AcroForm << /Fields [] >>'),
             'form.pdf', rejection='PDF requires unsupported features or optional dependencies'),
    )


def _source_checks(raw: bytes, filename: str, value: dict) -> dict[str, bool]:
    pdf = filename.endswith('.pdf')
    return {
        'original_bytes': value.get('sha256') == hashlib.sha256(raw).hexdigest()
                          and type(value.get('byte_count')) is int and value['byte_count'] == len(raw),
        'source_attribution': value.get('filename') == filename
                              and value.get('media_type') == ('application/pdf' if pdf else 'text/plain; charset=utf-8')
                              and value.get('extraction_method') == ('pypdf-text-v1' if pdf else 'utf8-plain-text-v1')
                              and value.get('annotation_method') == ('manual-exact-extraction-line-selection'
                                                                     if pdf else 'manual-exact-line-selection'),
        'review_status': value.get('clinical_review') == 'not_performed',
    }


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
        **_source_checks(case.raw, case.filename, value),
        'literal_text': value.get('text') == expected_text,
        'exact_lines_and_anchors': canonical_json(value.get('lines')) == canonical_json(expected_lines),
    }
    if pdf:
        result['extractor_identity'] = (canonical_json(value.get('extractor')) ==
                                        canonical_json(extractor_descriptor()))
        expected_pages = [
            {'page': n, 'text': text, 'sha256': hashlib.sha256(text.encode()).hexdigest()}
            for n, page in enumerate(case.pages, 1)
            for text in [('\n'.join(page) + ('\n' if case.pdf_terminal_lf else '')) if page else '']
        ]
        result['physical_pages'] = (type(value.get('page_count')) is int
                                   and value['page_count'] == len(case.pages)
                                   and canonical_json(value.get('pages')) == canonical_json(expected_pages))
        payload = {key: value.get(key) for key in ('text', 'lines', 'pages', 'page_count', 'extractor')}
        result['rendition_fingerprint'] = value.get('extraction_sha256') == hashlib.sha256(canonical_json(payload)).hexdigest()
    return result


def layout_inputs():
    """Two independently authored fixture streams with identical cell positions."""
    fixtures = _fixtures()
    # The same four non-overlapping cells occupy the same positions in both files.
    cells = [(36, 720, 'Specimen A'), (240, 720, '2.5 mg/L'),
             (36, 650, 'Specimen B'), (240, 650, '25 mg/L')]
    for fixture_id, order in (('L01', (0, 1, 2, 3)), ('L02', (0, 2, 1, 3))):
        stream = '\n'.join(f'BT /F1 10 Tf 1 0 0 1 {x} {y} Tm ({s}) Tj ET'
                           for idx in order for x, y, s in [cells[idx]]).encode()
        yield fixture_id, fixtures.streams_pdf([stream])


def probe_layout(adapter=preview_document) -> dict:
    """Measure row order on two fixed PDFs; an inability to measure is not a fidelity finding."""
    # Independent visual oracle: ignore whitespace, not words, units, or order.
    expected = 'Specimen A 2.5 mg/L Specimen B 25 mg/L'.split()
    results = []
    # Pin the independently rendered pair. Missing or duplicated drawing-order
    # variants must not silently turn a two-case qualification into an easy pass.
    inputs = list(layout_inputs())
    pinned = {'L01': '57a2f07738b3fd4df453d28e6d0410b695a8a96d46171b07db0638c7d4e86d11',
              'L02': '6a366c4be4628ef2ba894d593c7195af7e2019164a67534f2f5083a79a9dc279'}
    for fixture_id, expected_hash in pinned.items():
        candidates = [raw for key, raw in inputs if key == fixture_id]
        raw = candidates[0] if len(candidates) == 1 else None
        digest = hashlib.sha256(raw).hexdigest() if isinstance(raw, bytes) else None
        if digest != expected_hash:
            results.append({'fixture_id': fixture_id, 'original_sha256': digest, 'outcome': 'error'})
            continue
        name = fixture_id + '.pdf'
        outcome = 'error'
        try:
            value = adapter(raw, name)
            if isinstance(value, dict) and all(_source_checks(raw, name, value).values()):
                # Verify internal page/line anchors, pinned descriptor and rendition hash
                # before treating any text difference as a measured layout limitation.
                raw_pages = value['pages']
                if isinstance(raw_pages, list) and len(raw_pages) == 1:
                    rebuilt = make_rendition([raw_pages[0]['text']])
                    if canonical_json({k: value[k] for k in rebuilt}) == canonical_json(rebuilt):
                        words = value['text'].split()
                        outcome = ('row_order_preserved' if words == expected else
                                   'order_changed' if Counter(words) == Counter(expected) else
                                   'cell_content_changed')
        except Exception:
            pass  # Do not persist source strings, worker exception text, or invalid output.
        results.append({'fixture_id': fixture_id, 'original_sha256': digest,
                        'outcome': outcome})
    measured = sum(r['outcome'] != 'error' for r in results)
    preserved = sum(r['outcome'] == 'row_order_preserved' for r in results)
    return {'case_count': len(results), 'measured_count': measured, 'preserved_count': preserved,
            'all_rows_preserved': preserved == len(results) if measured == len(results) else None,
            'results': results}


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
    layout = probe_layout(adapter)
    return {
        'schema': 'oi-extraction-baseline-v2', 'synthetic': True,
        'pass_scope': 'intake_contract_and_layout_measurement_completion_only',
        'clinical_validation': False, 'review_minutes': None,
        'comparison': 'current_parser_only', 'timing': 'single_attempt_diagnostic_not_benchmark',
        'case_count': len(results), 'passed_count': sum(r['passed'] for r in results),
        'accepted_count': sum(r['outcome'] == 'accepted' for r in results),
        'rejected_count': sum(r['outcome'] == 'expected_rejection' for r in results),
        'error_count': sum(r['outcome'] == 'error' for r in results),
        'passed': all(r['passed'] for r in results) and layout['measured_count'] == layout['case_count'],
        'results': results, 'metrics': metrics, 'layout_probe': layout,
        'code_sha256': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in (
            'tools/extraction_baseline.py', 'tests/pdf_fixtures.py',
            'src/open_intelligence/document_intake.py', 'src/open_intelligence/pdf_intake.py',
            'src/open_intelligence/pdf_worker.py', 'requirements-pdf.lock')},
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Create a new receipt; never replace an earlier one')
    parser.add_argument('--require-layout-order', action='store_true',
                        help='Also fail unless both fixed visual row orders survived extraction')
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
    return 0 if report['passed'] and (not args.require_layout_order or
                                      report['layout_probe']['all_rows_preserved'] is True) else 1


if __name__ == '__main__':
    raise SystemExit(main())
