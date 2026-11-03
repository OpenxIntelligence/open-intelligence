"""Observe direct access using a real loopback HTTP server and invented bytes."""
from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import sys
from threading import Thread
import unittest
from unittest.mock import patch

from open_intelligence.store import InvalidInput
from tools.imaging import pacsnode_live_probe as pacs
try:
    from tools.imaging import pacsnode_security_evaluation as security
except ImportError:
    security = None


@contextmanager
def fictional_backend(status=200, *, altered=False, malformed=False):
    originals = {uid: b'\0' * 128 + b'DICM' + bytes([i]) * 24
                 for i, uid in enumerate(pacs.SOP_UIDS, 1)}
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            uid = self.path.rsplit('/', 1)[-1]
            requests.append((uid, self.headers.get('Authorization'),
                             self.headers.get('Cookie')))
            payload = originals[uid]
            if altered:
                payload += b'changed'
            media, body = pacs.multipart_body([payload])
            if malformed:
                body = b'PRIVATE_UNTRUSTED_RESPONSE'
            if status != 200:
                body = b'PRIVATE_UNTRUSTED_ERROR'
            self.send_response(status)
            self.send_header('Content-Type', media)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield (f'http://127.0.0.1:{server.server_port}',
               {uid: sha256(data).hexdigest() for uid, data in originals.items()},
               requests)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


class DirectPacsAccessTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(security, 'Security evaluation module is required')

    def test_direct_read_after_oi_amendment_is_an_observation_not_authority(self):
        with fictional_backend() as (origin, digests, requests):
            result = security.observe_direct_wado(origin, digests)
        self.assertEqual(result['kind'], 'oi.pacs-direct-access/1')
        self.assertEqual(result['phase'], 'after_oi_source_amendment')
        self.assertEqual(result['credential_mode'], 'none')
        self.assertTrue(result['anonymous_dicom_returned'])
        self.assertFalse(result['backend_authorization_verified'])
        self.assertEqual(set(result['objects']), set(pacs.SOP_UIDS))
        for uid, entry in result['objects'].items():
            self.assertEqual(entry['http_status'], 200)
            self.assertTrue(entry['original_bytes_match'])
            self.assertEqual(entry['returned_dicom_sha256'], digests[uid])
        self.assertEqual(requests, [(uid, None, None) for uid in pacs.SOP_UIDS])
        self.assertNotIn('DICM', json.dumps(result))

    def test_different_returned_object_still_demonstrates_anonymous_disclosure(self):
        with fictional_backend(altered=True) as (origin, digests, _):
            result = security.observe_direct_wado(origin, digests)
        self.assertTrue(result['anonymous_dicom_returned'])
        for entry in result['objects'].values():
            self.assertFalse(entry['original_bytes_match'])

    def test_denial_does_not_establish_patient_or_tenant_authority(self):
        for status in (401, 403, 404):
            with self.subTest(status=status), fictional_backend(status) as (origin, digests, _):
                result = security.observe_direct_wado(origin, digests)
            self.assertFalse(result['anonymous_dicom_returned'])
            self.assertFalse(result['backend_authorization_verified'])
            self.assertEqual({item['http_status'] for item in result['objects'].values()},
                             {status})
            self.assertNotIn('PRIVATE_UNTRUSTED', json.dumps(result))

    def test_malformed_dicom_and_wrong_scope_refused_without_false_receipt(self):
        with fictional_backend(malformed=True) as (origin, digests, _):
            with self.assertRaises(InvalidInput):
                security.observe_direct_wado(origin, digests)
        for origin, expected in [('https://example.org', {}),
                                 ('http://127.0.0.1:9', {'1.2.3': 'a' * 64})]:
            with self.subTest(origin=origin), self.assertRaises(InvalidInput):
                security.observe_direct_wado(origin, expected)

    def test_transport_error_excludes_backend_response_text(self):
        with fictional_backend(403) as (origin, _, _):
            with self.assertRaises(InvalidInput) as error:
                pacs._request(origin + '/wado/studies/' + pacs.SOP_UIDS[0])
        self.assertNotIn('PRIVATE_UNTRUSTED', str(error.exception))
        self.assertEqual(error.exception.status, 403)

    def test_late_confinement_failure_preserves_observed_disclosure_in_saved_receipts(self):
        from tools.imaging.network_confinement import NetworkEvidenceError
        root = Path(__file__).resolve().parents[1]
        base = json.loads((root / 'examples/synthetic/pacsnode_evidence_receipt_41555864030.json').read_text())
        base['first_party_wado_amendment_refused'] = True
        before = {'parent_namespace': 'net:[101]', 'probe_namespace': 'net:[202]',
                  'server_namespace': 'net:[202]', 'server_pid': 500,
                  'server_start_ticks': 12345, 'expected_ports': {'http': 18042, 'dicom': 11112}}
        with fictional_backend() as (origin, digests, requests), tempfile.TemporaryDirectory() as directory:
            base['sop_original_sha256'] = digests
            output, assessment = Path(directory) / 'receipt.json', Path(directory) / 'assessment.json'
            with patch.object(sys, 'argv', ['probe', '--base-url', origin, '--server-pid', '500',
                       '--parent-namespace', 'net:[101]', '--output', str(output),
                       '--assessment-output', str(assessment)]), \
                 patch.object(pacs, 'run_evaluation', return_value=base), \
                 patch('tools.imaging.network_confinement.capture_network_evidence',
                       side_effect=[before, NetworkEvidenceError('PRIVATE_KERNEL_ERROR')]), \
                 patch('tools.imaging.network_confinement.network_evidence_is_confined',
                       side_effect=lambda facts: isinstance(facts, dict)):
                status = security.main()
            result = json.loads(output.read_text())
            classified = json.loads(assessment.read_text())
        self.assertEqual(status, 1)
        self.assertEqual(len(requests), 2)
        self.assertEqual(result['sop_original_sha256'], digests)
        self.assertTrue(result['direct_access_after_amendment']['anonymous_dicom_returned'])
        self.assertTrue(classified['anonymous_direct_object_disclosure_observed'])
        self.assertFalse(classified['evaluation_network_namespace_confined'])
        self.assertIn('security_evaluation_incomplete', classified['open_gates'])
        self.assertNotIn('PRIVATE_KERNEL_ERROR', json.dumps(result))


if __name__ == '__main__':
    unittest.main()
