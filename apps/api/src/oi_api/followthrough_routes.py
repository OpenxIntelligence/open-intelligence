"""Task routes registered inside the canonical patient router and authority port."""
from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from open_intelligence.patient_registry import PatientRegistryDenied

from .access import Principal
from .followthrough_contracts import (
    FollowthroughCreate, FollowthroughTransition, FollowthroughReceipt, FollowthroughList,
    FollowthroughListV2,
)
from .question_followthrough import PostgresQuestionFollowthrough

MAX_RESPONSE_BYTES = 4 * 1024 * 1024
V2_MEDIA_TYPE = "application/vnd.open-intelligence.followthrough.v2+json"


def _accepts_v2(request: Request) -> bool:
    for header in request.headers.getlist("accept"):
        for item in header.split(","):
            media, *parameters = (part.strip().lower() for part in item.split(";"))
            if media == V2_MEDIA_TYPE:
                quality = next((p[2:] for p in parameters if p.startswith("q=")), "1")
                try:
                    if 0 < float(quality) <= 1:
                        return True
                except ValueError:
                    pass
    return False


def _prepare(model, result, *, command=False):
    validated = model(**result)
    response = JSONResponse(
        content=validated.model_dump(mode="json"),
        status_code=(200 if validated.duplicate else 201) if command else 200,
        media_type=V2_MEDIA_TYPE if model is FollowthroughListV2 else "application/json",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                 **({} if command else {"Vary": "Accept"})},
    )
    if len(response.body) > MAX_RESPONSE_BYTES:
        raise ValueError("Follow-through response exceeds bounded size")
    return response


def register_followthrough_routes(router, *, principal, registry,
                                  records_authorized, final_question_authority, errors):
    """Reuse the owning router's principal, connection and refreshed authority.

    Real response bytes are prepared within PostgresSourceVersions.list_locked,
    before the final authority check, access receipt and transaction commit.
    A validation/encoding/authority/audit failure cannot emit prepared task text
    or commit a newly created task/transition.
    """
    def actions_for(context, patients, patient_id, task_action):
        if context.purpose != "operations":
            raise PatientRegistryDenied("Follow-through unavailable")
        actions = ("question_read", "source_read", task_action)
        for action in actions:
            records_authorized(patients, context, patient_id, action)
        return actions

    @router.get("/{patient_id}/cases/{case_id}/followthrough",
                response_model=FollowthroughListV2, responses={**errors, 200: {
                    "model": FollowthroughList, "description": "Text tasks by default; opt in to include laboratory tasks.",
                    "content": {V2_MEDIA_TYPE: {"schema": {"$ref": "#/components/schemas/FollowthroughListV2"}}},
                }},
                operation_id="list_question_followthrough_v1")
    def listing(request: Request, patient_id: str, case_id: str,
                context: Principal = Depends(principal)):
        try:
            with registry(context) as patients:
                actions = actions_for(context, patients, patient_id, "followthrough_read")
                include_laboratory = _accepts_v2(request)
                return PostgresQuestionFollowthrough(patients).list(
                    patient_id, case_id, organization=context.organization,
                    actor=context.actor, purpose=context.purpose,
                    include_laboratory=include_laboratory,
                    prepare_response=lambda result: _prepare(
                        FollowthroughListV2 if include_laboratory else FollowthroughList, result),
                    recheck_authority=lambda: final_question_authority(
                        request, context, patients, patient_id, actions),
                )
        except PatientRegistryDenied:
            raise HTTPException(404, "Follow-through unavailable") from None

    @router.post("/{patient_id}/cases/{case_id}/questions/{question_id}/followthrough",
                 response_model=FollowthroughReceipt, status_code=201,
                 responses={200: {"model": FollowthroughReceipt}, **errors},
                 operation_id="create_question_followthrough_v1")
    def creating(request: Request, patient_id: str, case_id: str, question_id: str,
                 payload: FollowthroughCreate, context: Principal = Depends(principal)):
        try:
            with registry(context) as patients:
                actions = actions_for(context, patients, patient_id, "followthrough_create")
                return PostgresQuestionFollowthrough(patients).create(
                    patient_id, case_id, question_id, organization=context.organization,
                    actor=context.actor, purpose=context.purpose,
                    **payload.model_dump(exclude={"synthetic"}),
                    prepare_response=lambda result: _prepare(FollowthroughReceipt, result, command=True),
                    recheck_authority=lambda: final_question_authority(
                        request, context, patients, patient_id, actions),
                )
        except PatientRegistryDenied:
            raise HTTPException(404, "Follow-through unavailable") from None

    @router.post("/{patient_id}/cases/{case_id}/followthrough/{task_id}/transitions",
                 response_model=FollowthroughReceipt, status_code=201,
                 responses={200: {"model": FollowthroughReceipt}, **errors},
                 operation_id="transition_question_followthrough_v1")
    def transitioning(request: Request, patient_id: str, case_id: str, task_id: str,
                      payload: FollowthroughTransition,
                      context: Principal = Depends(principal)):
        try:
            with registry(context) as patients:
                actions = actions_for(context, patients, patient_id, "followthrough_update")
                return PostgresQuestionFollowthrough(patients).transition(
                    patient_id, case_id, task_id, organization=context.organization,
                    actor=context.actor, purpose=context.purpose,
                    **payload.model_dump(exclude={"synthetic"}),
                    prepare_response=lambda result: _prepare(FollowthroughReceipt, result, command=True),
                    recheck_authority=lambda: final_question_authority(
                        request, context, patients, patient_id, actions),
                )
        except PatientRegistryDenied:
            raise HTTPException(404, "Follow-through unavailable") from None
