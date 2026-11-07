"""Explicit, synthetic institution-identity review in the existing case workspace."""
from typing import Literal
from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import Field, StrictBool
from open_intelligence.patient_registry import PatientRegistryDenied
from .contracts import Contract
from .institution_identities import CaseInstitutionIdentities


class InstitutionProposal(Contract):
    synthetic: StrictBool
    request_key: str = Field(min_length=3,max_length=128)
    source_organization: str = Field(min_length=3,max_length=128)
    source_system: str = Field(min_length=3,max_length=128)
    source_subject_ref: str = Field(min_length=3,max_length=128)


class InstitutionDecision(Contract):
    synthetic: StrictBool
    decision: Literal['link','reject']
    review_ref: str = Field(min_length=3,max_length=128)


class InstitutionIdentity(Contract):
    identity_id: str = Field(pattern=r'^IDENTITY-[A-F0-9]{32}$')
    source_organization: str
    source_system: str
    source_subject_ref: str
    primary_identity: bool
    status: Literal['quarantined','active','rejected']
    review_ref: str | None


class InstitutionList(Contract):
    patient_id: str
    case_id: str
    identities: list[InstitutionIdentity]
    source_identity_verified: Literal[False] = False


class InstitutionReceipt(Contract):
    identity: InstitutionIdentity
    duplicate: bool
    source_identity_verified: Literal[False] = False


def register_institution_routes(router, *, principal, registry, records_authorized, final_authority, errors):
    path = '/{patient_id}/cases/{case_id}/institution-identities'

    def operate(request, patient_id, case_id, context, action, operation, payload=None, identity_id=None):
        if request.query_params or (payload is not None and payload.synthetic is not True):
            raise HTTPException(422, 'Invalid institution identity request')
        try:
            with registry(context) as patients:
                actions = tuple(dict.fromkeys(('case_binding_read', action)))
                for grant in actions:
                    records_authorized(patients, context, patient_id, grant)
                def encode(result):
                    body = InstitutionList(**result) if operation=='list' else InstitutionReceipt(**result)
                    response = JSONResponse(body.model_dump(mode='json'),
                        status_code=201 if operation=='propose' and not result['duplicate'] else 200,
                        headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
                    final_authority(request, context, patients, patient_id, actions)
                    return response
                args = dict(organization=context.organization, purpose=context.purpose, prepare_result=encode)
                if payload is not None:
                    args.update(payload.model_dump(exclude={'synthetic'}), actor=context.actor)
                owner = CaseInstitutionIdentities(patients)
                if operation == 'decide':
                    return owner.decide(patient_id, case_id, identity_id, **args)
                return getattr(owner, operation)(patient_id, case_id, **args)
        except PatientRegistryDenied:
            raise HTTPException(404,'Institution mapping unavailable') from None

    @router.get(path,response_model=InstitutionList,responses=errors)
    def identities(request: Request,patient_id: str,case_id: str,context=Depends(principal)):
        return operate(request,patient_id,case_id,context,'case_binding_read','list')

    @router.post(path,response_model=InstitutionReceipt,status_code=201,responses=errors)
    def propose(request: Request,patient_id: str,case_id: str,payload: InstitutionProposal,context=Depends(principal)):
        return operate(request,patient_id,case_id,context,'case_binding_create','propose',payload)

    @router.post(path+'/{identity_id}/decision',response_model=InstitutionReceipt,responses=errors)
    def decide(request: Request,patient_id: str,case_id: str,identity_id: str,
               payload: InstitutionDecision,context=Depends(principal)):
        return operate(request,patient_id,case_id,context,'case_binding_create','decide',payload,identity_id)

    @router.get('/{patient_id}/cases/{case_id}/sources/{source_id}/institution', responses=errors)
    def source_institution(request: Request, patient_id: str, case_id: str, source_id: str,
                           context=Depends(principal)):
        if request.query_params:
            raise HTTPException(422, 'Invalid request')
        from .sources import PostgresSourceVersions
        try:
            with registry(context) as patients:
                records_authorized(patients, context, patient_id, 'source_original_read')
                def encode(original):
                    row = patients._fetchone(
                        "SELECT f.source_organization,f.source_system,f.subject_reference,f.report_reference "
                        "FROM clinical_source.fhir_laboratory_sources f WHERE source_id=%s", (source_id,))
                    if row is None:
                        raise PatientRegistryDenied('Institution source unavailable')
                    return JSONResponse({
                        'patient_id': patient_id, 'case_id': case_id, 'source_id': source_id,
                        'document_id': original['document_id'], 'sha256': original['sha256'],
                        'source_organization': row[0], 'source_system': row[1],
                        'subject_reference': row[2], 'report_reference': row[3],
                        'source_identity_verified': False,
                    }, headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
                return PostgresSourceVersions(patients).original(
                    patient_id, case_id, source_id, organization=context.organization,
                    actor=context.actor, purpose=context.purpose, prepare_response=encode,
                    recheck_authority=lambda: final_authority(request, context, patients, patient_id,
                                                              ('source_original_read',)))
        except PatientRegistryDenied:
            raise HTTPException(404, 'Institution source unavailable') from None
