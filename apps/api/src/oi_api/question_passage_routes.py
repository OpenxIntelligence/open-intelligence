"""Question-owned manual context through the existing principal boundary."""
from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from open_intelligence.patient_registry import PatientRegistryDenied
from .access import Principal
from .question_passage_contracts import ReplaceQuestionPassages, ManualContextPacket, PassageReceipt
from .question_passages import QuestionPassages


def register_question_passage_routes(router,*,principal,registry,records_authorized,final_authority):
    path='/{patient_id}/cases/{case_id}/questions/{question_id}/manual-passages'
    def perform(request,context,patient_id,case_id,question_id,payload=None):
        actions=('source_read','question_read')+(('question_create','source_original_read') if payload is not None else ())
        try:
            with registry(context) as patients:
                for action in actions:
                    records_authorized(patients,context,patient_id,action)
                def recheck(original):
                    final_authority(request,context,patients,patient_id,tuple(dict.fromkeys(actions+(('source_original_read',) if original else ()))))
                def prepare(result):
                    model=PassageReceipt if payload is not None else ManualContextPacket
                    return JSONResponse(model(**result).model_dump(mode='json'),status_code=(200 if result['duplicate'] else 201) if payload is not None else 200)
                return QuestionPassages(patients).perform(patient_id,case_id,question_id,organization=context.organization,
                    actor=context.actor,purpose=context.purpose,recheck_authority=recheck,prepare_response=prepare,
                    payload=payload.model_dump(mode='json') if payload is not None else None)
        except PatientRegistryDenied:
            raise HTTPException(404,'Question context unavailable') from None

    @router.get(path,response_model=ManualContextPacket)
    def read(request:Request,patient_id:str,case_id:str,question_id:str,context:Principal=Depends(principal)):
        return perform(request,context,patient_id,case_id,question_id)

    @router.post(path,response_model=PassageReceipt,status_code=201)
    def replace(request:Request,patient_id:str,case_id:str,question_id:str,payload:ReplaceQuestionPassages,context:Principal=Depends(principal)):
        return perform(request,context,patient_id,case_id,question_id,payload)
