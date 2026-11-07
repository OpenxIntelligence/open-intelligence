"""Permission management through shared authentication, registry and transactions."""
from fastapi import Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from open_intelligence.patient_registry import PatientRegistryDenied
from .access import Principal, authenticate_request
from .patient_permissions import PostgresPatientPermissions, GrantPermission, RevokePermission


def register_permission_routes(router, *, principal, registry, authentication, errors):
    def response(value):
        return JSONResponse(value, headers={"Cache-Control": "no-store"})

    def refresh(request, initial, permissions, patient, *, command=None):
        current = authenticate_request(request, authentication)
        if (current.actor, current.organization, current.purpose) != (initial.actor, initial.organization, initial.purpose):
            raise PatientRegistryDenied("Patient permissions unavailable")
        permissions.authorize(current, patient, write=command is not None, command=command)

    @router.get("/{patient_id}/permissions", operation_id="list_patient_permissions_v1", responses=errors)
    def list_permissions(patient_id: str, request: Request,
                         after: str = Query(default="", pattern=r"^(GRANT-[0-9A-F]{32})?$"),
                         context: Principal = Depends(principal)):
        try:
            with registry(context) as patients:
                permissions = PostgresPatientPermissions(patients)
                return permissions.list(patient_id, context, after=after, prepare=response,
                    recheck=lambda: refresh(request, context, permissions, patient_id))
        except PatientRegistryDenied:
            raise HTTPException(404, "Patient permissions unavailable") from None

    def change(patient, request, payload, context, grant_id=None):
        try:
            with registry(context) as patients:
                permissions = PostgresPatientPermissions(patients)
                return permissions.change(patient, context, payload, grant_id=grant_id, prepare=response,
                    recheck=lambda: refresh(request, context, permissions, patient, command=payload))
        except PatientRegistryDenied:
            raise HTTPException(404, "Patient permissions unavailable") from None

    @router.post("/{patient_id}/permissions", operation_id="grant_patient_permission_v1", responses=errors)
    def grant_permission(patient_id: str, request: Request, payload: GrantPermission,
                         context: Principal = Depends(principal)):
        return change(patient_id, request, payload, context)

    @router.post("/{patient_id}/permissions/{grant_id}/revocations", operation_id="revoke_patient_permission_v1", responses=errors)
    def revoke_permission(patient_id: str, grant_id: str, request: Request, payload: RevokePermission,
                          context: Principal = Depends(principal)):
        return change(patient_id, request, payload, context, grant_id)
