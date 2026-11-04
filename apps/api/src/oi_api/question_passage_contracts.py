"""Versioned manual context, distinct from source-authored observations."""
from datetime import datetime
import re
from typing import Annotated, Literal

from pydantic import Field, StrictBool, StrictInt, field_validator, model_validator
from .contracts import Contract
from .document_contracts import FictionalDocument
from .reviewed_documents import fingerprint
from open_intelligence.patient_registry import _key

Digest = Annotated[str, Field(pattern=r'^[a-f0-9]{64}$')]
RevisionID = Annotated[str, Field(pattern=r'^PASSAGES-[A-F0-9]{32}$')]


class PassageReference(Contract):
    source_id: str = Field(pattern=r'^SRC-[A-F0-9]{32}$')
    annotation_revision_id: str = Field(pattern=r'^ANN-[A-F0-9]{32}$')
    selection_key: str = Field(pattern=r'^[a-z][a-z0-9_-]{0,59}$')
    anchor_sha256: Digest


class ReplaceQuestionPassages(FictionalDocument):
    request_key: str = Field(min_length=3, max_length=128, pattern=r'^[A-Za-z0-9][A-Za-z0-9._:-]+$')
    expected_context_sha256: Digest
    references: list[PassageReference] = Field(max_length=20)

    @field_validator('references')
    @classmethod
    def distinct(cls, values):
        identities = [(v.source_id, v.annotation_revision_id, v.selection_key) for v in values]
        if len(set(identities)) != len(values):
            raise ValueError('Distinct exact passages required')
        return sorted(values, key=lambda v: (v.source_id, v.annotation_revision_id, v.selection_key))


class ManualAnchor(Contract):
    patient_id: str
    case_id: str
    source_id: str = Field(pattern=r'^SRC-[A-F0-9]{32}$')
    document_id: str = Field(pattern=r'^[A-Z][A-Z0-9-]{1,39}$')
    source_version: StrictInt = Field(ge=1, le=2147483647)
    original_sha256: Digest
    extraction_method: Literal['utf8-plain-text-v1','pypdf-text-v1']
    extraction_sha256: Digest | None
    annotation_revision_id: str = Field(pattern=r'^ANN-[A-F0-9]{32}$')
    annotation_revision: StrictInt = Field(ge=1, le=64)
    review_sha256: Digest
    selected_by: str
    selected_at: str
    selection_key: str = Field(pattern=r'^[a-z][a-z0-9_-]{0,59}$')
    selected_state: Literal['reported','negative','pending','indeterminate','not-reported','not-assessed','conflicting']
    quote: str = Field(min_length=1, max_length=1200)
    line: StrictInt = Field(ge=1, le=512)
    page: StrictInt | None = Field(default=..., ge=1, le=20)
    classification_origin: Literal['user_selected']
    clinical_review: Literal['not_performed']

    @field_validator('selected_at')
    @classmethod
    def timestamp(cls, value):
        if len(value)>64 or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}(?::[0-9]{2}(?:\.[0-9]+)?)?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])', value):
            raise ValueError('Exact timezone timestamp required')
        parsed = datetime.fromisoformat(value)
        if 'T' not in value or parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError('Explicit timestamp required')
        return value

    @field_validator('selected_by')
    @classmethod
    def actor(cls,value):
        return _key(value,'actor')

    @model_validator(mode='after')
    def extraction(self):
        pdf=self.extraction_method=='pypdf-text-v1'
        if pdf!=(self.extraction_sha256 is not None) or pdf!=(self.page is not None):
            raise ValueError('Physical page and extraction identity differ')
        return self


class ResolvedPassage(Contract):
    anchor: ManualAnchor
    anchor_sha256: Digest
    source_state: Literal['current','superseded']
    latest_annotation_revision_id: str = Field(pattern=r'^ANN-[A-F0-9]{32}$')
    selection_state: Literal['current_unreviewed_selection','selection_reassessment_required']

    @model_validator(mode='after')
    def provenance(self):
        if fingerprint(self.anchor.model_dump(mode='json')) != self.anchor_sha256:
            raise ValueError('Manual anchor hash differs')
        current = self.source_state == 'current' and self.latest_annotation_revision_id == self.anchor.annotation_revision_id
        if (self.selection_state == 'current_unreviewed_selection') != current:
            raise ValueError('Manual selection freshness differs')
        return self


def context_hash(value):
    return fingerprint({k:v for k,v in value.items() if k not in {'context_sha256','access_receipt_id'}})


class ManualContext(Contract):
    contract: Literal['oi.question-manual-passages/1']
    patient_id: str
    case_id: str
    question_id: str = Field(pattern=r'^QUESTION-[A-F0-9]{32}$')
    revision_id: RevisionID | None
    revision: StrictInt = Field(ge=0, le=64)
    attached_by: str | None
    attached_at: str | None
    passages: list[ResolvedPassage] = Field(max_length=20)
    state: Literal['current_unreviewed','reassessment_required']
    context_sha256: Digest

    @model_validator(mode='after')
    def provenance(self):
        if self.revision == 0:
            if self.revision_id is not None or self.attached_by is not None or self.attached_at is not None or self.passages:
                raise ValueError('Empty context provenance differs')
        elif self.revision_id is None or not self.attached_by or not self.attached_at:
            raise ValueError('Saved context requires attribution')
        elif ManualAnchor.timestamp(self.attached_at) != self.attached_at:
            raise ValueError('Context timestamp differs')
        if self.attached_by is not None:
            _key(self.attached_by,'actor')
        current = all(p.selection_state == 'current_unreviewed_selection' for p in self.passages)
        if (self.state == 'current_unreviewed') != current:
            raise ValueError('Context freshness differs')
        seen=set()
        for p in self.passages:
            a=p.anchor
            identity=(a.source_id,a.annotation_revision_id,a.selection_key)
            if (a.patient_id,a.case_id)!=(self.patient_id,self.case_id) or identity in seen:
                raise ValueError('Context scope or duplicate anchor differs')
            seen.add(identity)
        if context_hash(self.model_dump(mode='json')) != self.context_sha256:
            raise ValueError('Context digest differs')
        return self


class ManualContextPacket(ManualContext):
    access_receipt_id: str = Field(pattern=r'^ACCESS-[A-F0-9]{32}$')


class PassageReceipt(Contract):
    revision_id: RevisionID
    question_id: str = Field(pattern=r'^QUESTION-[A-F0-9]{32}$')
    duplicate: StrictBool
