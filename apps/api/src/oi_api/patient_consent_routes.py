"""Consent composition through the shared authentication and identity owners."""
from fastapi import Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from open_intelligence.patient_registry import PatientRegistryDenied
from .access import Principal, authenticate_request
from .patient_consent import ConsentDecision, PostgresPatientConsent


def register_consent_routes(router, *, principal, registry, authentication, errors):
    def prepare(value):
        return JSONResponse(value, headers={'Cache-Control':'no-store'})

    def refresh(request, initial, service, patient, command=None):
        current = authenticate_request(request, authentication)
        if (current.actor,current.organization,current.purpose) != (initial.actor,initial.organization,initial.purpose):
            raise PatientRegistryDenied('Consent decisions unavailable')
        service.authorize(current,patient,command=command)

    @router.get('/{patient_id}/consent-decisions', operation_id='list_patient_consent_v1', responses=errors)
    def history(patient_id: str, request: Request, before: int=Query(default=0,ge=0,le=9_007_199_254_740_991),
                context: Principal=Depends(principal)):
        try:
            with registry(context) as patients:
                service=PostgresPatientConsent(patients)
                return service.list(patient_id,context,before=before,prepare=prepare,
                    recheck=lambda:refresh(request,context,service,patient_id))
        except PatientRegistryDenied:
            raise HTTPException(404,'Consent decisions unavailable') from None

    @router.post('/{patient_id}/consent-decisions', operation_id='record_patient_consent_v1', responses=errors)
    def decide(patient_id: str, request: Request, payload: ConsentDecision, context: Principal=Depends(principal)):
        try:
            with registry(context) as patients:
                service=PostgresPatientConsent(patients)
                return service.change(patient_id,context,payload,prepare=prepare,
                    recheck=lambda:refresh(request,context,service,patient_id,payload))
        except PatientRegistryDenied:
            raise HTTPException(404,'Consent decisions unavailable') from None
