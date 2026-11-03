"""Observe the pinned fictional PACS boundary without inventing an access grant.

The original #207 evaluator remains the byte/pixel/source owner. This wrapper
runs it in a measured isolated network namespace, then observes direct WADO
access after its report amendment. No actor, tenant or consent system is added.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re

from open_intelligence.store import InvalidInput
from tools.imaging import pacsnode_live_probe as pacs

_SHA = re.compile(r'[a-f0-9]{64}\Z')


class IncompleteSecurityEvaluation(InvalidInput):
    """A failed step with the already completed digest-only observations."""

    def __init__(self, receipt: dict):
        self.receipt = receipt
        super().__init__('Security evaluation incomplete; completed observations retained')


def observe_direct_wado(base_url: str, originals: dict[str, str]) -> dict:
    """Read only the two just-generated fictional SOPs, without credentials.

Called after run_evaluation has amended its own fictional source and verified
the first-party refusal. A response can establish that this direct route
discloses bytes; a 401/403/404 cannot establish a complete authorization model.
No response body, patient identifier or caller-controlled URL is retained.
"""
    origin = pacs.loopback_origin(base_url)
    if (not isinstance(originals, dict) or set(originals) != set(pacs.SOP_UIDS)
            or any(not isinstance(value, str) or not _SHA.fullmatch(value)
                   for value in originals.values())):
        raise InvalidInput('Expected exact digests for the two fictional SOPs')
    observations = {}
    for uid in pacs.SOP_UIDS:
        path = (f'/wado/studies/{pacs.IMAGE_STUDY_UID}/series/'
                f'{pacs.IMAGE_SERIES_UID}/instances/{uid}')
        entry = {'http_status': None, 'returned_dicom_sha256': None,
                 'returned_dicom_bytes': 0, 'original_bytes_match': None}
        try:
            status, media, body = pacs._request(origin + path, accept=pacs.WADO_ACCEPT)
        except pacs.BackendHTTPError as error:
            entry['http_status'] = error.status
        else:
            entry['http_status'] = status
            if status != 200:
                raise InvalidInput('Unexpected direct WADO success status')
            parts = pacs.multipart_dicom_parts(media, body)
            if len(parts) != 1:
                raise InvalidInput('Expected one fictional direct WADO object')
            digest = sha256(parts[0]).hexdigest()
            entry.update(returned_dicom_sha256=digest,
                         returned_dicom_bytes=len(parts[0]),
                         original_bytes_match=digest == originals[uid])
        observations[uid] = entry
    return {
        'kind': 'oi.pacs-direct-access/1',
        'phase': 'after_oi_source_amendment',
        'credential_mode': 'none',
        'objects': observations,
        'anonymous_dicom_returned': any(
            entry['http_status'] == 200 for entry in observations.values()),
        'backend_authorization_verified': False,
        'limitation': ('Anonymous access observation for two fictional SOPs. '
                       'No actor, tenant, consent or clinical qualification.'),
    }


def run_confined_evaluation(base_url: str, server_pid: int,
                            parent_namespace: str) -> dict:
    from tools.imaging.network_confinement import (
        capture_network_evidence, network_evidence_is_confined,
    )

    result = {'technical_evaluation_passed': False, 'synthetic_only': True,
              'real_patient_data_used': False, 'clinical_or_full_dicomweb_approval': False,
              'security_evaluation_passed': False}
    phase = 'network_before'
    try:
        before = capture_network_evidence(server_pid, parent_namespace)
        result['evaluation_network_boundary'] = {'before': before}
        if not network_evidence_is_confined(before):
            raise InvalidInput('Isolated evaluation namespace was not established')
        phase = 'original_byte_source_evaluation'
        result.update(pacs.run_evaluation(base_url))
        phase = 'amendment_precondition'
        if (result.get('first_party_amendment_rejected') is not True
                or result.get('first_party_wado_amendment_refused') is not True):
            raise InvalidInput('OI amendment refusal must precede direct-access observation')
        phase = 'direct_access_after_amendment'
        result['direct_access_after_amendment'] = observe_direct_wado(
            base_url, result['sop_original_sha256'])
        phase = 'network_after'
        after = capture_network_evidence(server_pid, parent_namespace)
        result['evaluation_network_boundary']['after'] = after
        if (not network_evidence_is_confined(after)
                or any(before[key] != after[key] for key in
                       ('parent_namespace', 'probe_namespace', 'server_namespace',
                        'server_pid', 'server_start_ticks', 'expected_ports'))):
            raise InvalidInput('Evaluation namespace or server identity changed')
    except Exception as error:
        # Failure cannot erase a completed byte diagnostic or an observed bypass.
        # Keep only fields built by these bounded probes, never exception text.
        result.update(evaluation_status='HOLD_security_evaluation_incomplete',
                      security_evaluation_passed=False,
                      evaluation_network_namespace_confined=False,
                      failure_stage=phase, failure_type=type(error).__name__)
        raise IncompleteSecurityEvaluation(result) from None
    result['security_evaluation_passed'] = True
    result['evaluation_network_namespace_confined'] = True
    # Network namespace confinement is not a production service access policy.
    result['backend_listener_isolation_verified'] = False
    result['pacs_authentication_verified'] = False
    result['pacs_tenant_isolation_verified'] = False
    result['pacs_direct_object_access_revoked'] = False
    result['limitations'] = [
        item for item in result['limitations']
        if not item.startswith('Loopback client restriction')
    ] + [
        'Wildcard HTTP/DIMSE sockets are confined to the measured test network namespace',
        'Namespace confinement is not a process/filesystem sandbox or production authorization',
        'OI source amendment does not itself revoke objects from the external PACS',
        'Source-bound digest equality is not trusted ingestion or decoded DICOM identity',
    ]
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--server-pid', type=int, required=True)
    parser.add_argument('--parent-namespace', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--assessment-output', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run_confined_evaluation(args.base_url, args.server_pid,
                                        args.parent_namespace)
    except IncompleteSecurityEvaluation as error:
        result = error.receipt
    except Exception as error:
        result = {'evaluation_status': 'HOLD_security_evaluation_error',
                  'technical_evaluation_passed': False,
                  'security_evaluation_passed': False,
                  'failure_type': type(error).__name__,
                  'real_patient_data_used': False,
                  'clinical_or_full_dicomweb_approval': False}
    try:
        from tools.imaging.assess_pacsnode_receipt import assess_pacs_receipt
        assessment = assess_pacs_receipt(result)
    except Exception as error:
        result['assessment_failure_type'] = type(error).__name__
        assessment = {'classification': 'HOLD_NOT_APPROVED',
                      'approval_automatically_granted': False,
                      'open_gates': ['receipt_assessment_incomplete']}
    if result.get('security_evaluation_passed') is not True:
        assessment['evaluation_network_namespace_confined'] = False
        assessment['open_gates'].append('security_evaluation_incomplete')
    for path, value in ((args.output, result), (args.assessment_output, assessment)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    passed = (result.get('technical_evaluation_passed') is True
              and result.get('security_evaluation_passed') is True
              and assessment.get('first_party_source_bound_reads') is True
              and assessment.get('direct_access_boundary_characterized') is True
              and assessment.get('evaluation_network_namespace_confined') is True)
    print('Imaging evaluation evidence saved; deployment classification: HOLD_NOT_APPROVED')
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
