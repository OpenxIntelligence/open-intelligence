"""Fictional animal identities and cases. Veterinary grants are independently scoped."""
from contextlib import closing, contextmanager
from datetime import datetime
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import Field, StrictBool, field_validator

from .access import AnimalId, Authentication, Principal, authenticate_request
from .contracts import Contract
from .database import Database

Key = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$")]
CaseId = Annotated[str, Field(pattern=r"^VCASE-[0-9A-F]{32}$")]
Species = Literal["dog", "cat"]


class VeterinaryCommand(Contract):
    synthetic: StrictBool
    request_key: Key

    @field_validator("synthetic")
    @classmethod
    def fictional_only(cls, value):
        if value is not True:
            raise ValueError("An independently fictional subject is required")
        return value


class RegisterAnimal(VeterinaryCommand):
    species: Species
    source_system: Key
    source_subject_ref: Key


class AnimalReceipt(Contract):
    animal_id: AnimalId
    duplicate: bool


class CaseReceipt(AnimalReceipt):
    case_id: CaseId


class AnimalRecord(Contract):
    animal_id: AnimalId
    species: Species
    origin_org: Key
    created_at: datetime


class CaseRecord(AnimalRecord):
    case_id: CaseId


def unavailable():
    return HTTPException(404, "Veterinary record unavailable")


def require_scope(context: Principal, action: str, animal_id: str | None):
    if action == "animal_register":
        if action not in context.actions:
            raise HTTPException(403, "Animal registration unavailable")
    elif (action not in context.actions or "animal_read" not in context.actions
          or animal_id not in context.animal_ids):
        raise unavailable()


def receipt(model):
    return JSONResponse(model.model_dump(mode="json"), status_code=200 if model.duplicate else 201)


def veterinary_router(database: Database, authentication: Authentication) -> APIRouter:
    router = APIRouter(prefix="/v1/veterinary/animals", tags=["Synthetic veterinary registry"])
    bearer = HTTPBearer(auto_error=False, scheme_name="SyntheticFixture")

    def principal(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        return authenticate_request(request, authentication)

    @contextmanager
    def transaction(request, context, action, animal_id=None):
        require_scope(context, action, animal_id)
        try:
            with database.registry_connection() as connection, closing(connection.cursor()) as cursor:
                yield cursor
                # The caller has validated and encoded the entire response. Re-read the
                # same bearer before either committing a command or disclosing its result.
                current = authenticate_request(request, authentication)
                if (current.actor, current.organization, current.purpose) != (
                        context.actor, context.organization, context.purpose):
                    raise unavailable()
                require_scope(current, action, animal_id)
                connection.commit()
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, "Veterinary registry unavailable") from None

    @router.post("", response_model=AnimalReceipt, status_code=201, responses={200: {"model": AnimalReceipt}})
    def register_animal(request: Request, payload: RegisterAnimal, context: Principal = Depends(principal)):
        with transaction(request, context, "animal_register") as cursor:
            animal_id = "ANM-" + uuid4().hex.upper()
            origin = (context.organization, payload.request_key)
            intent = (payload.species, payload.source_system, payload.source_subject_ref, context.actor, context.purpose)
            cursor.execute("""
                INSERT INTO identity.veterinary_animals
                    (animal_id, origin_org, request_key, species, source_system, source_subject_ref, created_by, purpose)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING animal_id
            """, (animal_id, *origin, *intent))
            if cursor.fetchone():
                return receipt(AnimalReceipt(animal_id=animal_id, duplicate=False))
            cursor.execute("""
                SELECT animal_id, species, source_system, source_subject_ref, created_by, purpose
                FROM identity.veterinary_animals WHERE origin_org=%s AND request_key=%s
            """, origin)
            prior = cursor.fetchone()
            if prior is None or tuple(prior[1:]) != intent:
                raise HTTPException(409, "Veterinary registration conflict")
            return receipt(AnimalReceipt(animal_id=prior[0], duplicate=True))

    @router.get("/{animal_id}", response_model=AnimalRecord)
    def read_animal(request: Request, animal_id: AnimalId, context: Principal = Depends(principal)):
        with transaction(request, context, "animal_read", animal_id) as cursor:
            cursor.execute("""
                SELECT species, created_at FROM identity.veterinary_animals WHERE origin_org=%s AND animal_id=%s
            """, (context.organization, animal_id))
            row = cursor.fetchone()
            if row is None:
                raise unavailable()
            record = AnimalRecord(animal_id=animal_id, species=row[0], created_at=row[1], origin_org=context.organization)
            return JSONResponse(record.model_dump(mode="json"))

    @router.post("/{animal_id}/cases", response_model=CaseReceipt, status_code=201, responses={200: {"model": CaseReceipt}})
    def open_veterinary_case(request: Request, animal_id: AnimalId, payload: VeterinaryCommand,
                             context: Principal = Depends(principal)):
        with transaction(request, context, "veterinary_case_open", animal_id) as cursor:
            cursor.execute("SELECT 1 FROM identity.veterinary_animals WHERE origin_org=%s AND animal_id=%s",
                           (context.organization, animal_id))
            if cursor.fetchone() is None:
                raise unavailable()
            case_id = "VCASE-" + uuid4().hex.upper()
            origin = (context.organization, payload.request_key)
            intent = (animal_id, context.actor, context.purpose)
            cursor.execute("""
                INSERT INTO coordination.veterinary_cases (case_id, origin_org, request_key, animal_id, created_by, purpose)
                VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (origin_org, request_key) DO NOTHING RETURNING case_id
            """, (case_id, *origin, *intent))
            if cursor.fetchone():
                return receipt(CaseReceipt(animal_id=animal_id, case_id=case_id, duplicate=False))
            cursor.execute("""
                SELECT case_id, animal_id, created_by, purpose FROM coordination.veterinary_cases
                WHERE origin_org=%s AND request_key=%s
            """, origin)
            prior = cursor.fetchone()
            if prior is None or tuple(prior[1:]) != intent:
                raise HTTPException(409, "Veterinary registration conflict")
            return receipt(CaseReceipt(animal_id=animal_id, case_id=prior[0], duplicate=True))

    @router.get("/{animal_id}/cases/{case_id}", response_model=CaseRecord)
    def read_veterinary_case(request: Request, animal_id: AnimalId, case_id: CaseId,
                             context: Principal = Depends(principal)):
        with transaction(request, context, "veterinary_case_read", animal_id) as cursor:
            cursor.execute("""
                SELECT a.species, c.created_at FROM coordination.veterinary_cases c
                JOIN identity.veterinary_animals a USING (origin_org, animal_id)
                WHERE c.origin_org=%s AND c.animal_id=%s AND c.case_id=%s
            """, (context.organization, animal_id, case_id))
            row = cursor.fetchone()
            if row is None:
                raise unavailable()
            record = CaseRecord(animal_id=animal_id, case_id=case_id, species=row[0],
                                created_at=row[1], origin_org=context.organization)
            return JSONResponse(record.model_dump(mode="json"))

    return router
