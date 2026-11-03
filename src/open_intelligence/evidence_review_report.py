"""Permission-scoped plain-text report over the existing quoted review packet.

No storage, HTTP endpoint, network, model invocation, clinical review or new
identity/evidence ledger. The caller's export policy must be separately scoped;
read permission and model-text permission do not establish export permission.
"""
from __future__ import annotations

import copy
import hashlib
import hmac
import json
import unicodedata
from typing import Callable

from .clinical_continuity import ClinicalContinuityError
from .evidence_review_packet import EvidenceReviewPacket, _snapshot_bytes
from .knowledge_context import KnowledgeContextError
from .patient_registry import PatientRegistryDenied

ExportAuthorizer = Callable[[str, str, str, str], bool]
MAX_BODY_BYTES = 1_000_000
GROUPS = (
    ("supports", "PROPOSED SUPPORT"),
    ("contradicts", "PROPOSED CONTRADICTION"),
    ("context", "PROPOSED CONTEXT"),
    ("unknown", "UNKNOWN RELATION"),
)


def _quoted(value: object) -> str:
    """One-line JSON representation, with directional controls made visible.

    Unicode letters are retained; JSON escape sequences preserve line breaks
    and controls without allowing untrusted text to add report status lines.
    This is plain text, never HTML; a future UI must use a text-only renderer.
    """
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)
    return "".join(json.dumps(c, ensure_ascii=True)[1:-1]
                   if unicodedata.category(c) in {"Cc", "Cf", "Zl", "Zp"} else c
                   for c in text)


class EvidenceReviewReport:
    """Render a fresh review packet only with explicit export permission.

    The injected authorizer is an extension point for the existing authority
    service, not a credential or new permission store. Fixture authorizers do
    not establish actual clinician identity, patient consent or publisher rights.
    Sequential final reads narrow races, not distributed atomicity or freshness
    after return. This service cannot recall a previously exported copy.
    """

    def __init__(self, packets: EvidenceReviewPacket, *,
                 export_authorizer: ExportAuthorizer | None = None):
        if not isinstance(packets, EvidenceReviewPacket):
            raise TypeError("Use the existing authority-checked quoted packet owner")
        self.packets = packets
        self.export_authorizer = export_authorizer

    def _allow_export(self, patient_id: str, *, actor: str, purpose: str) -> None:
        try:
            allowed = (self.export_authorizer is not None and
                       self.export_authorizer(actor, patient_id,
                                              "evidence_report.export", purpose) is True)
        except Exception:
            allowed = False
        if not allowed:
            raise PatientRegistryDenied("evidence report export is not permitted")

    @staticmethod
    def _check_content_export(packet: dict) -> None:
        for row in packet["quoted_comparisons"]:
            if row["external_reference"].get("report_export_allowed") is not True:
                raise KnowledgeContextError(
                    "selected source lacks explicit metadata and text redistribution rights")

    def render(self, patient_id: str, case_id: str, question_id: int, *,
               actor: str, purpose: str, selected_quotes: list[dict]) -> dict:
        """Return a text/plain report to the caller, with no file or DB write."""
        # Deny before provider access. Ordinary context read is not export.
        self._allow_export(patient_id, actor=actor, purpose=purpose)
        selected = copy.deepcopy(selected_quotes)
        before = self.packets.preview(patient_id, case_id, question_id,
                                      actor=actor, purpose=purpose,
                                      selected_quotes=selected)
        self._check_content_export(before)
        # The renderer receives a detached copy: it must not mutate the sealed
        # comparison used for the final freshness check.
        body = self._render_text(copy.deepcopy(before))
        encoded = body.encode("utf-8")
        if len(encoded) > MAX_BODY_BYTES:
            raise KnowledgeContextError("review report exceeds bounded output size")
        after = self.packets.preview(patient_id, case_id, question_id,
                                     actor=actor, purpose=purpose,
                                     selected_quotes=selected)
        if not hmac.compare_digest(_snapshot_bytes(before), _snapshot_bytes(after)):
            raise ClinicalContinuityError(
                "review context changed during report assembly; refresh before export")
        self._check_content_export(after)
        self._allow_export(patient_id, actor=actor, purpose=purpose)
        return {
            "contract": "oi.synthetic-evidence-review-report/1",
            "media_type": "text/plain; charset=utf-8",
            "body": body,
            "body_sha256": hashlib.sha256(encoded).hexdigest(),
            "packet_sha256": hashlib.sha256(_snapshot_bytes(before)).hexdigest(),
            "human_review_state": "pending",
            "model_executed": False,
            "clinical_conclusion_established": False,
            "clinical_action_authorized": False,
            "authorization_basis": "injected_fixture_policy_not_verified_identity_or_consent",
            "rights_basis": "fixture_declarations_not_verified_publisher_authorization",
            "snapshot_consistency": "sequential_preflight_not_cross_system_atomic",
        }

    @staticmethod
    def _render_text(packet: dict) -> str:
        rows = packet["quoted_comparisons"]
        lines = [
            "OPEN INTELLIGENCE — EVIDENCE REVIEW REPORT",
            "SYNTHETIC ENGINEERING OUTPUT — NOT A CLINICAL REPORT",
            "Human review: pending",
            "Model executed: no. Clinical conclusion: not established.",
            "Clinical applicability: proposed, not assessed by this renderer",
            "Literal quotation is not scientific entailment or a treatment recommendation.",
            "Copied values below use JSON-quoted text; escapes preserve the original characters.",
            "",
            f"Patient reference: {_quoted(packet['patient_id'])}",
            f"Case reference: {_quoted(packet['case_id'])}",
            f"Question ID: {packet['question_id']}",
            f"Question: {_quoted(packet['question'])}",
            f"Context fingerprint: {packet['review_context_sha256']}",
            f"Composer fingerprint: {packet['composer_context_fingerprint']}",
            f"Selected comparisons: {len(rows)}",
            f"Unselected comparisons: {packet['available_comparison_count'] - len(rows)}",
            f"Withheld or unavailable sources: {len(packet['missing_or_withheld_evidence'])}",
            "Coverage: selected passages only; absence here is not absence of counterevidence.",
            "",
        ]
        if not rows:
            lines.append("No selected quotations; no conclusion is established.")
        for relation, heading in GROUPS:
            group = [r for r in rows if r["candidate_relation"] == relation]
            lines.extend([heading, f"Selected items: {len(group)}"])
            # Stable order does not constitute clinical importance ranking.
            group.sort(key=lambda r: (r["patient_reference"]["assertion_id"],
                                      r["external_reference"]["knowledge_id"]))
            for index, row in enumerate(group, 1):
                p, e = row["patient_reference"], row["external_reference"]
                lines.extend([
                    f"  Item {index} — unreviewed proposal",
                    f"  Proposed applicability: {_quoted(row['candidate_applicability'])}",
                    f"  Patient assertion: {p['assertion_id']}",
                    f"  Source document: {_quoted(p['document_id'])}; version: {p['version']}",
                    f"  Source version ID: {p['source_version_id']}; line: {p['source_line']}",
                    f"  Source SHA-256: {p['sha256']}",
                    f"  Reported event date: {_quoted(p['event_date'])}",
                    f"  Report issued: {_quoted(p['issued_at'])}",
                    f"  Workspace received: {_quoted(p['received_at'] or 'not recorded')}",
                    (f"  User-selected status: {_quoted(p['reported_state'])}"
                     if p.get("classification_origin") == "user_selected"
                     else f"  Source-reported state: {_quoted(p['reported_state'])}"),
                    *([
                        f"  Classification origin: {_quoted(p['classification_origin'])}",
                        f"  Annotation method: {_quoted(p['annotation_method'])}",
                        f"  Clinical review: {_quoted(p['clinical_review'])}",
                        f"  Transcription review SHA-256: {p['transcription_review_sha256']}",
                    ] if "classification_origin" in p else []),
                    *([
                        f"  Text origin: {_quoted(p['text_origin'])}",
                        f"  Extraction SHA-256: {p['extraction_sha256']}",
                        f"  Physical PDF page: {p['source_page']}; page line: {p['page_line']}; extraction line: {p['source_line']}",
                        f"  Page text SHA-256: {p['page_text_sha256']}",
                    ] if p.get("text_origin") == "pdf_extraction" else []),
                    f"  Original statement: {_quoted(p['original_statement'])}",
                    f"  Evidence ID: {_quoted(e['knowledge_id'])}",
                    f"  Evidence content item: {_quoted(e['content_item'])}",
                    f"  Content item basis: {_quoted(e['content_item_basis'])}",
                    f"  Public reference: {_quoted(e['public_identifier'])}",
                    f"  Evidence version: {_quoted(e['version'])}; date: {_quoted(e['source_date'])}",
                    f"  Evidence text SHA-256: {e['evidence_text_sha256']}",
                    f"  Exact selected passage: {_quoted(e['exact_quote'])}",
                    f"  Proposal author label (unverified): {_quoted(row['proposed_by'])}",
                    f"  Proposal note: {_quoted(row['reviewer_note'])}",
                    "  Rights: export declaration present; publisher authorization not independently verified.",
                    "",
                ])
        lines.extend([
            "LIMITS AND REVIEW REQUIRED",
            "Study quality, population fit, clinical relevance and benefit/harm have not been assessed.",
            "No reviewer signature, accepted medical conclusion, order or treatment change is created.",
            "Identity, consent and publisher rights are fictional test declarations, not production proof.",
            "Sequential checks are not an atomic cross-system snapshot. Revalidate at later use.",
            "Previously exported files cannot be recalled by this renderer.",
            "No claim is made that all relevant evidence has been found or selected.",
        ])
        return "\n".join(lines) + "\n"
