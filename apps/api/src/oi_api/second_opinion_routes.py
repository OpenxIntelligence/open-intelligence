"""Second-opinion packet draft routes inside the canonical patient authority."""
from fastapi import Depends,HTTPException,Request
from fastapi.responses import JSONResponse

from open_intelligence.patient_registry import PatientRegistryDenied

from .access import Principal
from .second_opinion_contracts import (
    CreateSecondOpinionPacket,SecondOpinionPacketReceipt,SecondOpinionPacketList,
)
from .second_opinion_packets import PostgresSecondOpinionPackets

MAX_RESPONSE_BYTES=4*1024*1024


def _prepare(model,result,*,command=False):
    validated=model(**result)
    response=JSONResponse(
        content=validated.model_dump(mode="json"),
        status_code=(200 if validated.duplicate else 201) if command else 200,
        headers={"Cache-Control":"no-store","X-Content-Type-Options":"nosniff"},
    )
    if len(response.body)>MAX_RESPONSE_BYTES:
        raise ValueError("Second-opinion response exceeds bounded size")
    return response


def register_second_opinion_routes(router,*,principal,registry,
                                   records_authorized,final_question_authority,errors):
    def actions_for(context,patients,patient_id,action):
        if context.purpose!="operations":
            raise PatientRegistryDenied("Second-opinion packet unavailable")
        actions=("question_read","source_read",action)
        for item in actions:
            records_authorized(patients,context,patient_id,item)
        return actions

    @router.get("/{patient_id}/cases/{case_id}/second-opinion-packets",
                response_model=SecondOpinionPacketList,responses=errors,
                operation_id="list_second_opinion_packets_v1")
    def listing(request:Request,patient_id:str,case_id:str,
                context:Principal=Depends(principal)):
        try:
            with registry(context) as patients:
                actions=actions_for(context,patients,patient_id,"second_opinion_packet_read")
                return PostgresSecondOpinionPackets(patients).list(
                    patient_id,case_id,organization=context.organization,actor=context.actor,
                    purpose=context.purpose,
                    prepare_response=lambda result:_prepare(SecondOpinionPacketList,result),
                    recheck_authority=lambda:final_question_authority(
                        request,context,patients,patient_id,actions),
                )
        except PatientRegistryDenied:
            raise HTTPException(404,"Second-opinion packet unavailable") from None

    @router.post("/{patient_id}/cases/{case_id}/second-opinion-packets",
                 response_model=SecondOpinionPacketReceipt,status_code=201,
                 responses={200:{"model":SecondOpinionPacketReceipt},**errors},
                 operation_id="create_second_opinion_packet_v1")
    def creating(request:Request,patient_id:str,case_id:str,payload:CreateSecondOpinionPacket,
                 context:Principal=Depends(principal)):
        try:
            with registry(context) as patients:
                actions=actions_for(context,patients,patient_id,"second_opinion_packet_create")
                return PostgresSecondOpinionPackets(patients).create(
                    patient_id,case_id,organization=context.organization,actor=context.actor,
                    purpose=context.purpose,**payload.model_dump(exclude={"synthetic"}),
                    prepare_response=lambda result:_prepare(
                        SecondOpinionPacketReceipt,result,command=True),
                    recheck_authority=lambda:final_question_authority(
                        request,context,patients,patient_id,actions),
                )
        except PatientRegistryDenied:
            raise HTTPException(404,"Second-opinion packet unavailable") from None
