"""Reviewed-passage operations on the canonical investigation question table."""
import uuid
from fastapi.responses import JSONResponse
from pydantic import Field, StrictStr, field_validator
from open_intelligence.patient_registry import PatientRegistryConflict, PatientRegistryDenied, PatientRegistryError
from .document_contracts import FictionalDocument
from .reviewed_documents import fingerprint, selection_reference

CONTRACT = "oi.reviewed-document-selection/1"


class PassageQuestionWrite(FictionalDocument):
    request_key: StrictStr = Field(pattern=r"^[A-Za-z0-9-]{3,128}$")
    revision_id: StrictStr = Field(pattern=r"^ANN-[0-9A-F]{32}$")
    selection_key: StrictStr = Field(pattern=r"^[a-z][a-z0-9_-]{0,59}$")
    anchor_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    question: StrictStr = Field(min_length=8, max_length=500)

    @field_validator("question")
    @classmethod
    def one_line(cls, value):
        if value != value.strip() or not value.isprintable():
            raise ValueError("Enter one line of question text")
        return value


QUESTION_FROM = (" FROM investigation.source_questions LEFT JOIN investigation.reviewed_question_anchors USING(question_id) WHERE patient_id=%s AND case_id=%s"
         " AND origin_org=%s AND purpose=%s AND source_id=%s AND source_snapshot_contract='oi.reviewed-document-selection/1'")
QUESTION_SELECT = ("SELECT question_id,question,manual_revision,manual_key,source_snapshot_sha256,"
                  "source_version,source_sha256,actor,request_key,intent_sha256,preflight_sha256" + QUESTION_FROM)


def checked_question(row, doc, scope):
    patient, case = scope[:2]
    qid,text,rev,key,digest,version,sha,author,req,stored_intent,preflight = row
    selection = selection_reference(doc, patient, case, rev, key)
    if (digest,version,sha)!=(selection["anchor_sha256"],doc["version"],doc["sha256"]):
        raise PatientRegistryError("Inconsistent reviewed question provenance")
    reconstructed = PassageQuestionWrite(synthetic=True,request_key=req,revision_id=rev,
        selection_key=key,anchor_sha256=digest,question=text)
    if stored_intent != fingerprint([CONTRACT,*scope,author,reconstructed.model_dump()]) or preflight != fingerprint([digest,text]):
        raise PatientRegistryError("Stored question intent differs")
    return dict(question_id=qid,question=text,selection=selection)


def resolve_question_locked(owner, scope, question_id):
    patient, case, organization, purpose, source = scope
    binding = owner._binding(patient, case, organization, purpose)
    row = owner.registry._fetchone(QUESTION_SELECT + " AND question_id=%s", (*scope, question_id))
    if row is None:
        raise PatientRegistryDenied("Question evidence unavailable")
    doc = owner._load(case, source)
    return checked_question(row, doc, scope), binding


def passage_questions(owner, patient, case, source, payload, *, organization, actor, purpose, recheck_authority):
    if purpose != "operations":
        raise PatientRegistryDenied("Reviewed questions unavailable")
    reg = owner.registry
    with reg.transaction():
        binding = owner._binding(patient, case, organization, purpose)
        doc = owner._load(case, source)
        scope = (patient, case, organization, purpose, source)
        rows = reg._fetchall(QUESTION_SELECT + " ORDER BY created_at,question_id LIMIT 251", scope)
        if len(rows)>250:
            raise PatientRegistryError("Question history exceeds its bound")
        recheck_authority()
        if payload is None:
            questions = [checked_question(row, doc, scope) for row in rows]
            result = dict(patient_id=patient,case_id=case,source_id=source,questions=questions)
            status = 200
        else:
            selection = selection_reference(doc, patient, case, payload.revision_id, payload.selection_key)
            intent = fingerprint([CONTRACT,*scope,actor,payload.model_dump()])
            prior = reg._fetchone("SELECT question_id,intent_sha256 FROM investigation.source_questions WHERE patient_id=%s AND request_key=%s",(patient,payload.request_key))
            if prior:
                if prior[1]!=intent:
                    raise PatientRegistryConflict("Request key belongs to a different question")
                qid=prior[0]
                matching = next((row for row in rows if row[0] == qid), None)
                if matching is None or checked_question(matching, doc, scope)["selection"]["anchor_sha256"] != payload.anchor_sha256:
                    raise PatientRegistryError("Invalid reviewed question retry provenance")
            else:
                if len(rows)>=250 or selection["selection_state"]!="current_unreviewed_selection" or selection["anchor_sha256"]!=payload.anchor_sha256:
                    raise PatientRegistryConflict("Recheck this document selection before saving")
                qid="QUESTION-"+uuid.uuid4().hex.upper()
                inserted=reg._fetchone("""INSERT INTO investigation.source_questions
                    (question_id,patient_id,case_id,origin_org,purpose,source_id,actor,request_key,intent_sha256,
                     question,source_version,source_sha256,source_snapshot_contract,source_snapshot_sha256,preflight_sha256) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (patient_id,request_key) DO NOTHING RETURNING question_id""",
                    (qid,*scope,actor,payload.request_key,intent,payload.question,doc["version"],doc["sha256"],CONTRACT,
                     payload.anchor_sha256,fingerprint([payload.anchor_sha256,payload.question])))
                if inserted is None:
                    raise PatientRegistryConflict("Question request key belongs to a concurrent write")
                reg._execute("INSERT INTO investigation.reviewed_question_anchors(question_id,manual_revision,manual_key) VALUES (%s,%s,%s)",(qid,payload.revision_id,payload.selection_key))
                reg.append_event(patient,"investigation.question.created",case_id=case,source_id=source,question_id=qid,actor=actor,anchor_sha256=payload.anchor_sha256)
            result=dict(question_id=qid,duplicate=bool(prior))
            status=200 if prior else 201
        receipt="ACCESS-"+uuid.uuid4().hex.upper()
        if payload is None:
            result["access_receipt_id"]=receipt
        response=JSONResponse(result,status_code=status,headers={"Cache-Control":"no-store","X-Access-Receipt-ID":receipt})
        owner._read_receipt(patient,case,actor=actor,purpose=purpose,binding_revision=binding,
            event="source.document_question_access_authorized",receipt_id=receipt,recheck_authority=recheck_authority,source_id=source,sha256=doc["sha256"])
        recheck_authority()
        return response
