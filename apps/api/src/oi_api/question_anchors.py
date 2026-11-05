"""Immutable source identities shared by existing question/preparation owners.

These are identity contracts, NOT source reads, authorization tokens, freshness
proofs, clinical interpretations or database writes. Only an existing owner may
resolve them against original custody and current patient/case permissions.
No new persistence or wire response is introduced by the legacy adapters.
"""
from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import Field, StrictInt, StrictStr, TypeAdapter, ValidationError, field_validator

from open_intelligence.patient_registry import PatientRegistryError, _key
from .case_bindings import _case_id
from .contracts import Contract
from .laboratory_fhir_r4 import LaboratoryBundleRejected, _reference

ANCHOR_CONTRACT = 'oi.question-source-anchor/1'
TEXT_PREFLIGHT_CONTRACT = 'oi.synthetic-source-composer-preflight/2'
LAB_PREFLIGHT_CONTRACT = 'oi.synthetic-laboratory-question-preflight/1'


class _ScopedQuestionAnchor(Contract):
    contract: Literal['oi.question-source-anchor/1']
    patient_id: StrictStr
    case_id: StrictStr
    source_id: StrictStr
    source_version: StrictInt = Field(ge=1)
    source_sha256: StrictStr

    @field_validator('patient_id')
    @classmethod
    def patient_scope(cls, value: str) -> str:
        return _key(value, 'patient_id')

    @field_validator('case_id')
    @classmethod
    def case_scope(cls, value: str) -> str:
        return _case_id(value)

    @field_validator('source_id')
    @classmethod
    def source_identity(cls, value: str) -> str:
        if re.fullmatch(r'SRC-[0-9A-F]{32}', value) is None:
            raise ValueError('Invalid source identity')
        return value

    @field_validator('source_sha256')
    @classmethod
    def source_digest(cls, value: str) -> str:
        if re.fullmatch(r'[0-9a-f]{64}', value) is None:
            raise ValueError('Invalid source fingerprint')
        return value


class TextLineQuestionAnchor(_ScopedQuestionAnchor):
    anchor_kind: Literal['text_line']
    source_line: StrictInt = Field(ge=1, le=10_000)


class FHIRObservationQuestionAnchor(_ScopedQuestionAnchor):
    anchor_kind: Literal['fhir_observation']
    resource_reference: StrictStr
    specimen_reference: StrictStr
    report_reference: StrictStr

    @field_validator('resource_reference', 'specimen_reference', 'report_reference')
    @classmethod
    def local_resource(cls, value: str, info) -> str:
        kind = {'resource_reference': 'Observation', 'specimen_reference': 'Specimen',
                'report_reference': 'DiagnosticReport'}[info.field_name]
        try:
            return _reference({'reference': value}, kind)
        except LaboratoryBundleRejected:
            raise ValueError('Invalid local source resource reference') from None


QuestionSourceAnchor = Annotated[
    TextLineQuestionAnchor | FHIRObservationQuestionAnchor,
    Field(discriminator='anchor_kind'),
]
_ANCHOR_ADAPTER = TypeAdapter(QuestionSourceAnchor)


def parse_question_anchor(value: dict) -> QuestionSourceAnchor:
    """Validate one explicit identity; never coerce a line or infer a variant.

    Accept plain mappings only. Already-created models, including models built
    without validation, must not bypass this entry point's field validation.
    """
    if type(value) is not dict:
        raise PatientRegistryError('Invalid typed question source anchor')
    try:
        return _ANCHOR_ADAPTER.validate_python(value, strict=True)
    except (ValidationError, PatientRegistryError):
        # Do not include source values or submitted fields in caller-visible errors.
        raise PatientRegistryError('Invalid typed question source anchor') from None


def anchor_from_preflight(prepared: dict) -> QuestionSourceAnchor:
    """Extract identity from a known internal preflight, without altering it.

    This is not validation of the entire preflight or its source relationships.
    The canonical source owner and response contracts retain those obligations.
    In particular, matching references here do not prove patient/specimen linkage.
    """
    if type(prepared) is not dict or type(prepared.get('selected_source')) is not dict:
        raise PatientRegistryError('Invalid question preflight anchor')
    selected = prepared['selected_source']
    try:
        fields = {
            'contract': ANCHOR_CONTRACT, 'patient_id': prepared['patient_id'],
            'case_id': prepared['case_id'], 'source_id': selected['source_id'],
            'source_version': selected['version'], 'source_sha256': selected['sha256'],
        }
        if prepared.get('contract') == TEXT_PREFLIGHT_CONTRACT:
            if any(name in selected for name in (
                    'anchor_kind', 'source_line', 'resource_reference',
                    'specimen_reference', 'report_reference')):
                raise PatientRegistryError('Mixed question preflight anchor')
            fields.update(anchor_kind='text_line', source_line=selected['line'])
        elif prepared.get('contract') == LAB_PREFLIGHT_CONTRACT:
            if (selected.get('anchor_kind') != 'fhir_observation'
                    or selected.get('kind') != 'laboratory'
                    or any(name in selected for name in ('line', 'source_line'))):
                raise PatientRegistryError('Mixed question preflight anchor')
            fields.update(anchor_kind='fhir_observation',
                          resource_reference=selected['resource_reference'],
                          specimen_reference=selected['specimen_reference'],
                          report_reference=selected['report_reference'])
        else:
            raise PatientRegistryError('Unsupported question preflight anchor')
    except KeyError:
        raise PatientRegistryError('Incomplete question preflight anchor') from None
    return parse_question_anchor(fields)


def legacy_text_question_anchor(row: dict) -> TextLineQuestionAnchor:
    """Adapt a legacy question/task row; never relabel a resource as text.

    Other existing row metadata is retained by its owner. This adapter returns
    only validated identity and does not rewrite request hashes, history or rows.
    A future typed-row reader must be explicit rather than reuse this adapter.
    """
    if type(row) is not dict or any(name in row for name in (
            'anchor_kind', 'line', 'resource_reference', 'specimen_reference', 'report_reference')):
        raise PatientRegistryError('Invalid legacy text question anchor')
    try:
        fields = {name: row[name] for name in (
            'patient_id', 'case_id', 'source_id', 'source_version', 'source_sha256', 'source_line')}
    except KeyError:
        raise PatientRegistryError('Incomplete legacy text question anchor') from None
    parsed = parse_question_anchor(fields | {'contract': ANCHOR_CONTRACT, 'anchor_kind': 'text_line'})
    # The explicit discriminator above guarantees this; keep the return contract
    # concrete so downstream legacy callers cannot accidentally accept resources.
    if not isinstance(parsed, TextLineQuestionAnchor):
        raise PatientRegistryError('Invalid legacy text question anchor')
    return parsed
