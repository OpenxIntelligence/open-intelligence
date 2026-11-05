"""Exact human-only H1 evidence wire contracts, distinct from source-only briefs."""
from __future__ import annotations

from datetime import date, datetime
import hashlib
import re
from typing import Annotated, Literal

from pydantic import Field, StrictBool, StrictInt, field_validator, model_validator

from open_intelligence.patient_registry import _key
from open_intelligence.rights import normalize_permissions, permitted
from .contracts import Contract
from .source_question_contracts import QuestionSourceState, SelectedComposerSource
from .evidence_report import canonical_hash, packet_hash, quote_offset, visible_line
from .question_passage_contracts import ManualContext

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
EID = Annotated[str, Field(pattern=r"^EVIDENCE-[0-9A-F]{32}$")]
AID = Annotated[str, Field(pattern=r"^ASSESSMENT-[0-9A-F]{32}$")]
RID = Annotated[str, Field(pattern=r"^REPORT-[0-9A-F]{32}$")]
QID = Annotated[str, Field(pattern=r"^QUESTION-[0-9A-F]{32}$")]
AccessID = Annotated[str, Field(pattern=r"^ACCESS-[0-9A-F]{32}$")]
ContentItem = Literal["full_text", "abstract", "api_output"]
Relation = Literal["supports", "contradicts", "context", "unknown"]
Applicability = Literal["applicable", "limited", "not_applicable", "unknown"]
ReportState = Literal["current_unreviewed", "historical_reassessment_required", "content_withheld"]

_WIRE_TIMESTAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}"
    r"(?::[0-9]{2}(?:\.[0-9]+)?)?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])"
)


def aware(value: str) -> str:
    # fromisoformat alone accepts arbitrary single-character separators,
    # including line breaks, and rolls over offset minutes above 59.
    # Preserve valid wire bytes; never normalize them.
    if len(value) > 64 or not _WIRE_TIMESTAMP.fullmatch(value):
        raise ValueError("Timestamp requires an ISO date, T separator and explicit timezone")
    when = datetime.fromisoformat(value)
    if when.tzinfo is None or when.utcoffset() is None:
        raise ValueError("Timestamp requires an explicit timezone")
    return value


def calendar_date(value: str) -> str:
    if date.fromisoformat(value).isoformat() != value:
        raise ValueError("Issue date requires an exact YYYY-MM-DD calendar date")
    return value


class WriteEvidence(Contract):
    synthetic: StrictBool
    request_key: str = Field(min_length=3, max_length=128)

    @field_validator("synthetic")
    @classmethod
    def fictional(cls, value):
        if value is not True:
            raise ValueError("Only independently authored fictional evidence is enabled")
        return value

    @field_validator("request_key")
    @classmethod
    def opaque(cls, value):
        return _key(value, "request_key")


class ImportEvidence(WriteEvidence):
    original_text: str = Field(min_length=1, max_length=32768)
    content_item: ContentItem
    permissions: dict[str, dict[str, str]]

    @field_validator("permissions")
    @classmethod
    def normalized(cls, value):
        return normalize_permissions(value)


class WithdrawEvidence(WriteEvidence):
    reason: str

    @field_validator("reason")
    @classmethod
    def visible(cls, value):
        return visible_line(value, "Withdrawal reason")


class AssessEvidence(WriteEvidence):
    evidence_id: EID
    evidence_sha256: Digest
    rights_sha256: Digest
    expected_source_snapshot_sha256: Digest
    expected_preflight_sha256: Digest
    quote: str = Field(min_length=1, max_length=400)
    relation: Relation
    applicability: Applicability
    rationale: str

    @field_validator("rationale")
    @classmethod
    def visible(cls, value):
        return visible_line(value)

    @model_validator(mode="after")
    def applicable_support(self):
        if self.relation == "supports" and self.applicability == "not_applicable":
            raise ValueError("Not applicable evidence cannot be proposed support")
        return self


class PrepareEvidenceReport(WriteEvidence):
    expected_packet_sha256: Digest
    expected_manual_context_sha256: Digest | None = None
    assessment_ids: list[AID] = Field(min_length=1, max_length=20)

    @field_validator("assessment_ids")
    @classmethod
    def distinct(cls, values):
        if len(values) != len(set(values)):
            raise ValueError("Distinct assessment selections required")
        return sorted(values)


class EvidenceImportReceipt(Contract):
    evidence_id: EID
    version: StrictInt = Field(ge=1)
    duplicate: StrictBool


class EvidenceWithdrawReceipt(Contract):
    withdrawal_id: str = Field(pattern=r"^WITHDRAWAL-[0-9A-F]{32}$")
    evidence_id: EID
    duplicate: StrictBool


class EvidenceAssessmentReceipt(Contract):
    assessment_id: AID
    question_id: QID
    duplicate: StrictBool


class EvidenceReportReceipt(Contract):
    report_id: RID
    question_id: QID
    duplicate: StrictBool


class EvidenceQuestion(QuestionSourceState):
    # Keep the already-normalized wire string unchanged for canonical hashes.
    created_at: str
    _aware = field_validator("created_at")(aware)


class EvidenceVersion(Contract):
    evidence_id: EID
    evidence_key: str = Field(pattern=r"^[A-Z][A-Z0-9-]{1,39}$")
    version: StrictInt = Field(ge=1)
    sha256: Digest
    statement_line: StrictInt = Field(ge=1, le=10000)
    content_item: ContentItem
    rights_sha256: Digest
    permissions: dict[str, dict[str, str]]
    state: Literal["current", "superseded", "withdrawn"]
    title: str | None = Field(default=..., min_length=4, max_length=180)
    issued_at: str
    statement: str | None = Field(default=..., min_length=10, max_length=1200)
    created_at: str
    _aware = field_validator("created_at")(aware)
    _date = field_validator("issued_at")(calendar_date)

    @model_validator(mode="after")
    def integrity(self):
        if normalize_permissions(self.permissions) != self.permissions or canonical_hash(self.permissions) != self.rights_sha256:
            raise ValueError("Exact normalized rights declaration required")
        if (self.title is None) != (self.statement is None):
            raise ValueError("Withheld content must not contain a partial disclosure")
        if self.title is not None and (self.state == "withdrawn" or not all(
                permitted(self.permissions, item, use)
                for item in ("metadata", self.content_item) for use in ("store", "display"))):
            raise ValueError("Evidence display declaration unavailable")
        return self


class EvidenceAssessment(Contract):
    assessment_id: AID
    question_id: QID
    evidence_id: EID
    evidence_sha256: Digest
    rights_sha256: Digest
    source_snapshot_sha256: Digest
    preflight_sha256: Digest
    relation: Relation
    applicability: Applicability
    quote: str | None = Field(default=..., min_length=1, max_length=400)
    quote_start: StrictInt | None = Field(default=..., ge=0, le=1200)
    rationale: str | None
    actor_label: str
    created_at: str
    state: Literal["current_unreviewed", "reassessment_required", "content_withheld"]
    _aware = field_validator("created_at")(aware)

    @model_validator(mode="after")
    def integrity(self):
        if self.relation == "supports" and self.applicability == "not_applicable":
            raise ValueError("Not applicable support is invalid")
        absent = (self.quote is None, self.quote_start is None, self.rationale is None)
        if any(absent) != all(absent) or all(absent) != (self.state == "content_withheld"):
            raise ValueError("Exact withholding state required")
        if self.rationale is not None:
            visible_line(self.rationale)
        _key(self.actor_label, "actor")
        return self


class ReportSummary(Contract):
    report_id: RID
    question_id: QID
    prepared_at: str
    body_sha256: Digest
    snapshot_sha256: Digest
    state: ReportState
    _aware = field_validator("prepared_at")(aware)


class EvidencePacket(Contract):
    contract: Literal["oi.h1-question-evidence/1"]
    patient_id: str
    case_id: str
    question: EvidenceQuestion
    source_snapshot_sha256: Digest
    access_receipt_id: AccessID
    evidence: list[EvidenceVersion] = Field(max_length=100)
    assessments: list[EvidenceAssessment] = Field(max_length=200)
    reports: list[ReportSummary] = Field(max_length=100)
    packet_sha256: Digest
    synthetic: Literal[True]
    human_review_state: Literal["not_performed"]
    clinical_approval: Literal[False]
    model_executed: Literal[False]

    @model_validator(mode="after")
    def integrity(self):
        if (self.patient_id, self.case_id) != (self.question.patient_id, self.question.case_id):
            raise ValueError("Question scope differs")
        ev = {e.evidence_id: e for e in self.evidence}
        if len(ev) != len(self.evidence) or len({a.assessment_id for a in self.assessments}) != len(self.assessments) or len({r.report_id for r in self.reports}) != len(self.reports):
            raise ValueError("Duplicate identities")
        for a in self.assessments:
            e = ev.get(a.evidence_id)
            if (a.question_id != self.question.question_id or e is None
                    or (a.evidence_sha256, a.rights_sha256) != (e.sha256, e.rights_sha256)
                    or (a.source_snapshot_sha256, a.preflight_sha256) !=
                    (self.question.source_snapshot_sha256, self.question.preflight_sha256)):
                raise ValueError("Assessment provenance differs")
            if a.quote is not None and (e.statement is None or quote_offset(e.statement, a.quote) != a.quote_start):
                raise ValueError("Quotation differs")
            if a.state == "current_unreviewed" and (e.state != "current" or self.question.source_context_state != "current_unreviewed_question"):
                raise ValueError("Stale context cannot be current")
        if any(r.question_id != self.question.question_id for r in self.reports):
            raise ValueError("Report scope differs")
        if packet_hash(self.model_dump(mode="json")) != self.packet_sha256:
            raise ValueError("Evidence packet digest differs")
        return self


class EvidenceOriginal(Contract):
    contract: Literal["oi.h1-evidence-original/1"]
    patient_id: str
    case_id: str
    evidence_id: EID
    sha256: Digest
    original_text: str = Field(min_length=1, max_length=32768)
    access_receipt_id: AccessID
    synthetic: Literal[True]

    @model_validator(mode="after")
    def integrity(self):
        if hashlib.sha256(self.original_text.encode("utf-8")).hexdigest() != self.sha256:
            raise ValueError("Original bytes differ")
        return self


class Comparison(Contract):
    assessment: EvidenceAssessment
    evidence: EvidenceVersion


class ReportSnapshot(Contract):
    question: EvidenceQuestion
    selected_source: SelectedComposerSource
    comparisons: list[Comparison] = Field(min_length=1, max_length=20)
    prepared_at: str
    actor_label: str
    _aware = field_validator("prepared_at")(aware)

    @model_validator(mode="after")
    def provenance(self):
        q, s = self.question, self.selected_source
        if (q.source_context_state != "current_unreviewed_question"
                or q.source_snapshot_contract != "oi.pg-source-world-model/1"
                or (q.source_id, q.source_line, q.source_sha256, q.source_version) !=
                (s.source_id, s.line, s.sha256, s.version)):
            raise ValueError("Canonical current source anchor required")
        ids, families = set(), set()
        for row in self.comparisons:
            a, e = row.assessment, row.evidence
            if (a.assessment_id in ids or e.evidence_key in families
                    or a.question_id != q.question_id or a.evidence_id != e.evidence_id
                    or (a.evidence_sha256, a.rights_sha256) != (e.sha256, e.rights_sha256)
                    or (a.source_snapshot_sha256, a.preflight_sha256) !=
                    (q.source_snapshot_sha256, q.preflight_sha256)
                    or a.state != "current_unreviewed" or e.state != "current"
                    or e.statement is None or a.quote is None
                    or quote_offset(e.statement, a.quote) != a.quote_start):
                raise ValueError("Exact current comparison provenance required")
            ids.add(a.assessment_id)
            families.add(e.evidence_key)
        _key(self.actor_label, "actor")
        return self


class ManualReportSnapshot(ReportSnapshot):
    manual_passages: ManualContext

    @model_validator(mode='after')
    def manual_provenance(self):
        c,q=self.manual_passages,self.question
        if (c.patient_id,c.case_id,c.question_id)!=(q.patient_id,q.case_id,q.question_id) or c.state!='current_unreviewed' or c.revision_id is None:
            raise ValueError('Exact current question manual context required')
        return self


def checked_report_snapshot(value):
    return (ManualReportSnapshot if 'manual_passages' in value else ReportSnapshot)(**value).model_dump(mode='json')


class EvidenceReport(Contract):
    contract: Literal["oi.h1-evidence-report/1"]
    patient_id: str
    case_id: str
    question_id: QID
    report_id: RID
    prepared_at: str
    state: ReportState
    body: str | None
    body_sha256: Digest
    snapshot: ManualReportSnapshot | ReportSnapshot | None
    snapshot_sha256: Digest
    access_receipt_id: AccessID
    synthetic: Literal[True]
    human_review_state: Literal["not_performed"]
    clinical_approval: Literal[False]
    model_executed: Literal[False]
    _aware = field_validator("prepared_at")(aware)

    @model_validator(mode="after")
    def provenance(self):
        if (self.body is None) != (self.snapshot is None) or (self.body is None) != (self.state == "content_withheld"):
            raise ValueError("Exact report withholding state required")
        if self.snapshot is not None:
            q = self.snapshot.question
            if ((q.patient_id, q.case_id, q.question_id) != (self.patient_id, self.case_id, self.question_id)
                    or self.snapshot.prepared_at != self.prepared_at
                    or canonical_hash(self.snapshot.model_dump(mode="json")) != self.snapshot_sha256
                    or hashlib.sha256(self.body.encode("utf-8")).hexdigest() != self.body_sha256):
                raise ValueError("Report provenance or digest differs")
        return self
