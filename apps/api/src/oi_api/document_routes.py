"""Authenticated adapters for canonical source-owned reviewed documents."""
from fastapi import Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from open_intelligence.patient_registry import PatientRegistryDenied, PatientRegistryError
from open_intelligence.store import InvalidInput
from .access import Principal
from .document_contracts import DocumentUpload, DocumentImport, AnnotationCorrection
from .reviewed_documents import ReviewedDocuments


def register_document_routes(router, *, principal, registry, records_authorized, final_authority):
    prefix = "/{patient_id}/cases/{case_id}/documents"

    def execute(request, context, patient_id, case_id, actions, action):
        try:
            with registry(context) as patients:
                for permission in actions:
                    records_authorized(patients,context,patient_id,permission)
                def recheck():
                    final_authority(request,context,patients,patient_id,actions)
                try:
                    return action(ReviewedDocuments(patients),dict(organization=context.organization,
                        actor=context.actor,purpose=context.purpose,recheck_authority=recheck))
                except PatientRegistryError:
                    raise
                except (InvalidInput, ValueError):
                    raise PatientRegistryError("Invalid reviewed document input") from None
        except PatientRegistryDenied:
            raise HTTPException(404,"Document unavailable") from None

    def saved(result):
        return JSONResponse(result,status_code=200 if result["duplicate"] else 201)

    @router.post(prefix+"/preview")
    def preview(request:Request,patient_id:str,case_id:str,payload:DocumentUpload,context:Principal=Depends(principal)):
        def action(owner,kwargs):
            kwargs.pop("actor")
            return owner.preview(patient_id,case_id,payload,**kwargs,prepare_response=JSONResponse)
        return execute(request,context,patient_id,case_id,("source_import",),action)

    @router.post(prefix)
    def import_document(request:Request,patient_id:str,case_id:str,payload:DocumentImport,context:Principal=Depends(principal)):
        return execute(request,context,patient_id,case_id,("source_import",),
            lambda owner,kwargs:owner.import_document(patient_id,case_id,payload,**kwargs,prepare_response=saved))

    @router.get(prefix)
    def list_documents(request:Request,patient_id:str,case_id:str,context:Principal=Depends(principal)):
        return execute(request,context,patient_id,case_id,("source_read",),
            lambda owner,kwargs:owner.read(patient_id,case_id,**kwargs,prepare_response=lambda result,raw:JSONResponse(result)))

    @router.get(prefix+"/{source_id}")
    def document(request:Request,patient_id:str,case_id:str,source_id:str,context:Principal=Depends(principal)):
        return execute(request,context,patient_id,case_id,("source_read","source_original_read"),
            lambda owner,kwargs:owner.read(patient_id,case_id,source_id,**kwargs,prepare_response=lambda result,raw:JSONResponse(result)))

    @router.get(prefix+"/{source_id}/original")
    def original(request:Request,patient_id:str,case_id:str,source_id:str,context:Principal=Depends(principal)):
        def prepare(result,raw):
            return Response(raw,media_type=result["preview"]["media_type"],headers={
                "Content-Disposition":'attachment; filename="'+result["filename"]+'"',
                "X-Content-SHA256":result["sha256"],"X-Access-Receipt-ID":result["access_receipt_id"],
                "Cache-Control":"no-store","X-Content-Type-Options":"nosniff"})
        return execute(request,context,patient_id,case_id,("source_original_read",),
            lambda owner,kwargs:owner.read(patient_id,case_id,source_id,**kwargs,original=True,prepare_response=prepare))

    @router.post(prefix+"/{source_id}/annotations")
    def correct(request:Request,patient_id:str,case_id:str,source_id:str,payload:AnnotationCorrection,context:Principal=Depends(principal)):
        return execute(request,context,patient_id,case_id,("source_import","source_original_read"),
            lambda owner,kwargs:owner.correct(patient_id,case_id,source_id,payload,**kwargs,prepare_response=saved))
