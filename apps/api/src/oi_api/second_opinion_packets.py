"""Durable second-opinion packet drafts over canonical H1 sources/questions."""
from __future__ import annotations

from collections.abc import Callable
import hmac
import re
from typing import TypeVar
import uuid

from open_intelligence.patient_registry import (
    PatientRegistryConflict, PatientRegistryDenied, PatientRegistryError, _digest, _key,
)
from open_intelligence.postgres_registry import PostgresPatientRegistry

from .case_bindings import _case_id
from .source_questions import PostgresSourceQuestions
from .source_world_model import project_source_world_model
from .sources import PostgresSourceVersions

PreparedResponse=TypeVar("PreparedResponse")
CONTRACT="oi.pg-second-opinion-packets/1"
MAX_PACKETS=100
MAX_PACKET_SOURCES=32
MAX_PACKET_QUESTIONS=16


def _id(value:str,prefix:str)->str:
    if type(value) is not str or re.fullmatch(prefix+r"-[0-9A-F]{32}",value) is None:
        raise PatientRegistryError("Invalid second-opinion packet identifier")
    return value


def _title(value:str)->str:
    if (type(value) is not str or value!=value.strip() or not 8<=len(value)<=300
            or any(ord(c)<32 or ord(c)==127 for c in value)):
        raise PatientRegistryError("Invalid second-opinion packet title")
    return value


class PostgresSecondOpinionPackets:
    def __init__(self,registry:PostgresPatientRegistry):
        if not isinstance(registry,PostgresPatientRegistry):
            raise TypeError("Canonical PostgreSQL patient registry required")
        self.registry=registry

    def _scope(self,patient_id,case_id,organization,actor,purpose):
        scope=(_key(patient_id,"patient_id"),_case_id(case_id),
               _key(organization,"organization"),_key(actor,"actor"))
        if purpose!="operations":
            raise PatientRegistryDenied("Second-opinion packet unavailable")
        return scope

    def _authority(self,patient_id,actor,purpose,action,recheck_authority):
        if not callable(recheck_authority):
            raise PatientRegistryError("A trusted authority recheck is required")
        def allow():
            for grant in ("patient_read","source_read","question_read",action):
                self.registry._allow(actor,patient_id,grant,purpose)
        allow()
        def final():
            recheck_authority()
            allow()
        return final

    def _prior(self,patient_id,case_id,organization,request_key,intent):
        row=self.registry._fetchone(
            "SELECT packet_id,intent_sha256,case_id,origin_org "
            "FROM coordination.second_opinion_packets "
            "WHERE patient_id=%s AND request_key=%s FOR UPDATE",
            (patient_id,request_key),
        )
        if row is None:
            return None
        if row[2]!=case_id or row[3]!=organization:
            raise PatientRegistryDenied("Second-opinion packet unavailable")
        if not hmac.compare_digest(row[1],intent):
            raise PatientRegistryConflict("Second-opinion request key reused with changed intent")
        return {"packet_id":row[0],"duplicate":True}

    def _project_locked(self,patient_id,case_id,organization,index):
        world=project_source_world_model(index)
        current_snapshot=world["snapshot_fingerprint"]
        questions={q["question_id"]:q for q in PostgresSourceQuestions(self.registry).project_locked(
            patient_id,case_id,organization=organization,source_index=index)}
        source_by_id={s["source_id"]:s for s in index["sources"]}
        rows=self.registry._fetchall(
            "SELECT packet_id,patient_id,case_id,origin_org,title,source_snapshot_contract,source_snapshot_sha256,created_at "
            "FROM coordination.second_opinion_packets "
            "WHERE patient_id=%s AND case_id=%s AND origin_org=%s "
            "ORDER BY created_at,packet_id LIMIT 101",
            (patient_id,case_id,organization),
        )
        if len(rows)>MAX_PACKETS:
            raise PatientRegistryError("Second-opinion packet read exceeds bound")
        output=[]
        for row in rows:
            packet_id=row[0]
            source_rows=self.registry._fetchall(
                "SELECT ordinal,source_id,source_version,source_sha256 "
                "FROM coordination.second_opinion_packet_sources WHERE packet_id=%s "
                "ORDER BY ordinal LIMIT 33",(packet_id,))
            question_rows=self.registry._fetchall(
                "SELECT ordinal,question_id FROM coordination.second_opinion_packet_questions "
                "WHERE packet_id=%s ORDER BY ordinal LIMIT 17",(packet_id,))
            if (not source_rows or not question_rows or len(source_rows)>MAX_PACKET_SOURCES
                    or len(question_rows)>MAX_PACKET_QUESTIONS):
                raise PatientRegistryError("Second-opinion packet membership integrity mismatch")
            stale=not hmac.compare_digest(row[6],current_snapshot)
            sources=[]
            selected_ids=set()
            for ordinal,source_id,version,digest in source_rows:
                source=source_by_id.get(source_id)
                if source is None or source["version"]!=version or not hmac.compare_digest(source["sha256"],digest):
                    raise PatientRegistryError("Second-opinion source provenance integrity mismatch")
                selected_ids.add(source_id)
                stale=stale or source["state"]!="current"
                sources.append({
                    "source_id":source_id,"document_id":source["document_id"],
                    "version":version,"sha256":digest,"kind":source["kind"],"state":source["state"],
                })
            selected_questions=[]
            for ordinal,question_id in question_rows:
                question=questions.get(question_id)
                if question is None or question["source_id"] not in selected_ids:
                    raise PatientRegistryError("Second-opinion question provenance integrity mismatch")
                stale=stale or question["source_context_state"]!="current_unreviewed_question"
                stale=stale or question["source_snapshot_contract"]!=row[5]
                stale=stale or not hmac.compare_digest(question["source_snapshot_sha256"],row[6])
                selected_questions.append({
                    "question_id":question_id,"question":question["question"],
                    "source_id":question["source_id"],"source_line":question["source_line"],
                    "source_context_state":question["source_context_state"],
                })
            output.append({
                "packet_id":packet_id,"patient_id":row[1],"case_id":row[2],"title":row[4],
                "source_snapshot_contract":row[5],"source_snapshot_sha256":row[6],
                "created_at":row[7].isoformat(),
                "preparation_state":"source_reassessment_required" if stale else "current_preparation",
                "sources":sources,"questions":selected_questions,
                "record_completeness_verified":False,"recipient_verified":False,
                "external_request_sent":False,"clinical_approval":False,
            })
        return output,current_snapshot,source_by_id,questions

    def list(self,patient_id:str,case_id:str,*,organization:str,actor:str,purpose:str,
             recheck_authority:Callable[[],None],
             prepare_response:Callable[[dict],PreparedResponse]|None=None):
        patient_id,case_id,organization,actor=self._scope(
            patient_id,case_id,organization,actor,purpose)
        final=self._authority(patient_id,actor,purpose,"second_opinion_packet_read",recheck_authority)
        def prepare(index):
            packets,_,_,_=self._project_locked(patient_id,case_id,organization,index)
            result={"contract":CONTRACT,"patient_id":patient_id,"case_id":case_id,
                    "access_receipt_id":index["access_receipt_id"],"packets":packets,
                    "synthetic":True,"recipient_verification_supported":False,
                    "external_dispatch_supported":False,"clinical_approval":False}
            return prepare_response(result) if prepare_response is not None else result
        with self.registry.transaction():
            return PostgresSourceVersions(self.registry).list_locked(
                patient_id,case_id,organization=organization,actor=actor,purpose=purpose,
                recheck_authority=final,prepare_response=prepare)

    def create(self,patient_id:str,case_id:str,*,organization:str,actor:str,purpose:str,
               request_key:str,title:str,source_snapshot_contract:str,
               expected_source_snapshot_sha256:str,source_ids:list[str],question_ids:list[str],
               recheck_authority:Callable[[],None],
               prepare_response:Callable[[dict],PreparedResponse]|None=None):
        patient_id,case_id,organization,actor=self._scope(
            patient_id,case_id,organization,actor,purpose)
        request_key=_key(request_key,"request_key")
        title=_title(title)
        if source_snapshot_contract!="oi.pg-source-world-model/1":
            raise PatientRegistryConflict("Unsupported source snapshot contract")
        if (type(expected_source_snapshot_sha256) is not str
                or re.fullmatch(r"[0-9a-f]{64}",expected_source_snapshot_sha256) is None):
            raise PatientRegistryError("Invalid source snapshot fingerprint")
        if (type(source_ids) is not list or not 1<=len(source_ids)<=MAX_PACKET_SOURCES
                or len(source_ids)!=len(set(source_ids))):
            raise PatientRegistryError("Invalid second-opinion packet source selection")
        source_ids=[_id(value,"SRC") for value in source_ids]
        if (type(question_ids) is not list or not 1<=len(question_ids)<=MAX_PACKET_QUESTIONS
                or len(question_ids)!=len(set(question_ids))):
            raise PatientRegistryError("Invalid second-opinion packet question selection")
        question_ids=[_id(value,"QUESTION") for value in question_ids]
        final=self._authority(patient_id,actor,purpose,"second_opinion_packet_create",recheck_authority)
        intent=_digest({
            "operation":"second_opinion.packet.create","patient_id":patient_id,"case_id":case_id,
            "organization":organization,"actor":actor,"purpose":purpose,"request_key":request_key,
            "title":title,"source_snapshot_contract":source_snapshot_contract,
            "source_snapshot_sha256":expected_source_snapshot_sha256,
            "source_ids":source_ids,"question_ids":question_ids,
        })

        def prepare(index):
            prior=self._prior(patient_id,case_id,organization,request_key,intent)
            if prior is not None:
                return prepare_response(prior) if prepare_response is not None else prior
            packets,current_snapshot,source_by_id,questions=self._project_locked(
                patient_id,case_id,organization,index)
            if len(packets)>=MAX_PACKETS:
                raise PatientRegistryError("Second-opinion packet write exceeds bound")
            if not hmac.compare_digest(current_snapshot,expected_source_snapshot_sha256):
                raise PatientRegistryConflict("Source context changed; rebuild packet preparation")
            selected=[]
            for source_id in source_ids:
                source=source_by_id.get(source_id)
                if source is None or source["state"]!="current":
                    raise PatientRegistryConflict("Selected source is no longer current")
                selected.append(source)
            selected_id_set=set(source_ids)
            chosen_questions=[]
            for question_id in question_ids:
                question=questions.get(question_id)
                if question is None:
                    raise PatientRegistryDenied("Second-opinion question unavailable")
                if (question["source_id"] not in selected_id_set
                        or question["source_context_state"]!="current_unreviewed_question"
                        or question["source_snapshot_contract"]!=source_snapshot_contract
                        or not hmac.compare_digest(question["source_snapshot_sha256"],
                                                   expected_source_snapshot_sha256)):
                    raise PatientRegistryConflict("Selected question requires source reassessment")
                chosen_questions.append(question)
            packet_id="SECONDOP-"+uuid.uuid4().hex.upper()
            self.registry._execute(
                "INSERT INTO coordination.second_opinion_packets "
                "(packet_id,patient_id,case_id,origin_org,request_key,intent_sha256,actor,purpose,"
                "title,source_snapshot_contract,source_snapshot_sha256) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (packet_id,patient_id,case_id,organization,request_key,intent,actor,purpose,
                 title,source_snapshot_contract,expected_source_snapshot_sha256),
            )
            for ordinal,source in enumerate(selected,1):
                self.registry._execute(
                    "INSERT INTO coordination.second_opinion_packet_sources "
                    "(packet_id,ordinal,source_id,source_version,source_sha256) "
                    "VALUES (%s,%s,%s,%s,%s)",
                    (packet_id,ordinal,source["source_id"],source["version"],source["sha256"]),
                )
            for ordinal,question in enumerate(chosen_questions,1):
                self.registry._execute(
                    "INSERT INTO coordination.second_opinion_packet_questions "
                    "(packet_id,ordinal,question_id) VALUES (%s,%s,%s)",
                    (packet_id,ordinal,question["question_id"]),
                )
            self.registry.append_event(
                patient_id,"coordination.second_opinion_packet.created",
                packet_id=packet_id,case_id=case_id,source_count=len(selected),
                question_count=len(chosen_questions),actor=actor,
            )
            result={"packet_id":packet_id,"duplicate":False}
            return prepare_response(result) if prepare_response is not None else result

        with self.registry.transaction():
            return PostgresSourceVersions(self.registry).list_locked(
                patient_id,case_id,organization=organization,actor=actor,purpose=purpose,
                recheck_authority=final,prepare_response=prepare)
