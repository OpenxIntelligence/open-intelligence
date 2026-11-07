"""Patient-scoped synthetic EHR operations over the existing clinical domain."""
from contextlib import contextmanager
import uuid
from typing import Annotated, Literal

from fastapi import Depends, HTTPException, Path, Query, Request
from fastapi.responses import JSONResponse
from pydantic import Field, StrictBool, field_validator

from open_intelligence.clinical_encounters import ClinicalAuthorizationError, ClinicalConflict, EncounterNotFound
from open_intelligence.patient_registry import PatientRegistryDenied
from open_intelligence.postgres_encounters import PostgresClinicalEncounters
from open_intelligence.store import InvalidInput

from .access import Principal
from .contracts import Contract
from .encounter_sources import PostgresEncounterSources
from .encounter_event_contract import EncounterEvents, VisitEvents, VisitState

Identifier = Annotated[int, Path(gt=0, le=2**63-1)]
NoteKey = Annotated[str, Path(pattern=r"^[A-Z][A-Z0-9-]{1,39}$")]
Cursor = Annotated[int, Query(ge=0, le=2**63-1)]
PageSize = Annotated[int, Query(ge=1, le=25)]
Kind = Literal["outpatient", "inpatient", "telehealth", "telephone", "procedure", "other"]
NoteKind = Literal["history_and_physical", "consultation", "progress", "procedure", "operative",
                   "discharge", "referral", "nursing", "other"]


class Command(Contract):
    synthetic: StrictBool
    request_key: str = Field(pattern=r"^[A-Za-z0-9_.:-]{8,100}$")

    @field_validator("synthetic")
    @classmethod
    def synthetic_only(cls, value):
        if not value:
            raise ValueError("Synthetic input required")
        return value


class Schedule(Command):
    external_key: str = Field(pattern=r"^[A-Z][A-Z0-9-]{1,39}$")
    kind: Kind
    service_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


class Transition(Command):
    target: Literal["in_progress", "completed", "cancelled"]
    expected_revision: int = Field(strict=True, ge=1, le=2**63-1)


class DraftNote(Command):
    expected_version: int = Field(strict=True, ge=0, le=2**31-2)
    body: str = Field(min_length=1, max_length=20000)
    note_kind: NoteKind | None = None
    facility_id: str | None = Field(default=None, max_length=100)
    department_id: str | None = Field(default=None, max_length=100)


class LinkSource(Command):
    source_id: str = Field(pattern=r"^SRC-[0-9A-F]{32}$")
    expected_version: int = Field(strict=True, ge=1, le=2**31-1)
    expected_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class EncounterSourceReceipt(Contract):
    id: int
    duplicate: bool


class EncounterSourceLink(Contract):
    id: int
    encounter_id: int
    patient_id: str
    case_id: str
    source_id: str
    version: int
    sha256: str
    source_state: Literal["current", "superseded"]


class EncounterSourcePage(Contract):
    encounter_id: int
    patient_id: str
    case_id: str
    links: list[EncounterSourceLink]
    next_after_id: int | None
    access_receipt_id: str


class EncounterReceipt(Contract):
    encounter_id: int
    status: VisitState
    revision: int


class NoteReceipt(Contract):
    note_id: int
    note_key: str
    version: int
    status: Literal["draft", "draft_correction"]
    sha256: str


class Encounter(Contract):
    id: int
    patient_id: str
    external_key: str
    kind: Kind
    service_date: str
    status: VisitState
    revision: int
    created_at: str
    updated_at: str


class EncounterPage(Contract):
    patient_id: str
    encounters: list[Encounter]
    next_after_id: int | None
    access_receipt_id: str


class NoteVersion(Contract):
    id: int
    version: int
    status: str
    body: str
    sha256: str
    authored_by: str
    created_at: str
    supersedes_id: int | None
    amendment_reason: str | None
    facility_id: str | None
    department_id: str | None
    note_kind: NoteKind | None


class NoteHistory(Contract):
    patient_id: str
    encounter_id: int
    note_key: str
    versions: list[NoteVersion]
    next_after_version: int | None
    access_receipt_id: str


class NoteHeader(Contract):
    id: int
    note_key: str
    latest_version: int


class NotesPage(Contract):
    patient_id: str
    encounter_id: int
    notes: list[NoteHeader]
    next_after_id: int | None
    access_receipt_id: str


@contextmanager
def encounter_errors():
    try:
        yield
    except (PatientRegistryDenied, ClinicalAuthorizationError, EncounterNotFound):
        raise HTTPException(404, "Encounter unavailable") from None
    except ClinicalConflict:
        raise HTTPException(409, "Encounter command, state or version conflict") from None
    except InvalidInput:
        raise HTTPException(422, "Invalid encounter command") from None


def register_encounter_routes(router, *, principal, registry, authorize, refresh, errors):
    prefix = "/{patient_id}/encounters"

    @contextmanager
    def scoped_transaction(request, context, patient_id, required, *, reading):
        if context.purpose != "operations" or patient_id not in context.patient_ids or (
                "patient_read" not in context.actions or any(action not in context.actions for action in required)):
            raise HTTPException(404, "Encounter unavailable")
        with registry(context) as patients, encounter_errors(), patients.transaction():
            # Serialize patient retirement and scope changes with disclosure.
            locked = patients._fetchone("SELECT status FROM identity.identity_patients "
                "WHERE patient_id=%s AND origin_org=%s FOR " + ("SHARE" if reading else "UPDATE"),
                (patient_id, context.organization))
            if locked is None or locked[0] != "active":
                raise PatientRegistryDenied("Patient unavailable")
            for grant in required:
                authorize(patients, context, patient_id, grant)

            yield patients
            # Includes the actual serialized HTTP response and any audit append.
            refresh(request, context, patients, patient_id, required)

    def run(request, context, patient_id, action, model, operation, *, read_refs=None, extra_actions=()):
        required = (action, *extra_actions)
        with scoped_transaction(request, context, patient_id, required, reading=read_refs is not None) as patients:
            def allowed(actor, subject, requested, purpose):
                if (actor, subject, purpose) != (context.actor, patient_id, context.purpose) or requested not in required:
                    return False
                refresh(request, context, patients, patient_id, required)
                return True

            service = PostgresClinicalEncounters(patients, allowed, in_transaction=True)
            data = operation(service, {"actor": context.actor, "purpose": context.purpose})
            if read_refs is not None:
                receipt = "ACCESS-" + uuid.uuid4().hex.upper()
                data["access_receipt_id"] = receipt
                patients.append_event(patient_id, "clinical_encounter_read_authorized",
                                      receipt_id=receipt, action=action, actor=context.actor,
                                      purpose=context.purpose, **read_refs)
            return JSONResponse(model(**data).model_dump(mode="json"))

    source_links = prefix + "/{encounter_id}/cases/{case_id}/source-links"
    source_grants = ("encounter.read", "source_read")

    @router.post(source_links, response_model=EncounterSourceReceipt, status_code=201,
                 responses={200: {"model": EncounterSourceReceipt}, **errors},
                 operation_id="link_encounter_source_v1")
    def link_encounter_source(patient_id: str, encounter_id: Identifier, case_id: str,
                              payload: LinkSource, request: Request, context: Principal = Depends(principal)):
        with scoped_transaction(request, context, patient_id, (*source_grants, "encounter.source.link"),
                                reading=False) as patients:
            receipt = EncounterSourceReceipt(**PostgresEncounterSources(patients).link(
                patient_id, encounter_id, case_id, payload.source_id, payload.expected_version,
                payload.expected_sha256, payload.request_key, actor=context.actor,
                organization=context.organization, purpose=context.purpose))
            return JSONResponse(receipt.model_dump(mode="json"), status_code=200 if receipt.duplicate else 201)

    @router.get(source_links, response_model=EncounterSourcePage, responses=errors,
                operation_id="list_encounter_sources_v1")
    def list_encounter_sources(patient_id: str, encounter_id: Identifier, case_id: str, request: Request,
                               after_id: Cursor = 0, limit: PageSize = 25, context: Principal = Depends(principal)):
        with scoped_transaction(request, context, patient_id, source_grants, reading=True) as patients:
            rows = PostgresEncounterSources(patients).list(patient_id, encounter_id, case_id,
                after_id=after_id, limit=limit + 1, organization=context.organization)
            receipt = "ACCESS-" + uuid.uuid4().hex.upper()
            page = EncounterSourcePage(patient_id=patient_id, encounter_id=encounter_id, case_id=case_id,
                links=rows[:limit], next_after_id=rows[limit-1]["id"] if len(rows)>limit else None,
                access_receipt_id=receipt)
            response = JSONResponse(page.model_dump(mode="json"))
            patients.append_event(patient_id, "clinical_encounter_sources_read_authorized",
                                  receipt_id=receipt, actor=context.actor, purpose=context.purpose,
                                  encounter_id=encounter_id, case_id=case_id, after_id=after_id, page_size=limit)
            return response

    @router.post(prefix, response_model=EncounterReceipt, responses=errors)
    def schedule_encounter(patient_id: str, payload: Schedule, request: Request,
                           context: Principal = Depends(principal)):
        return run(request, context, patient_id, "encounter.schedule", EncounterReceipt,
                   lambda service, args: service.schedule(patient_id, payload.external_key, payload.kind,
                       payload.service_date, request_key=payload.request_key, **args))

    @router.get(prefix, response_model=EncounterPage, responses=errors)
    def read_encounters(patient_id: str, request: Request, after_id: Cursor = 0, limit: PageSize = 25,
                        context: Principal = Depends(principal)):
        def page(service, args):
            rows = service.list_encounters(patient_id, after_id=after_id, limit=limit+1, **args)
            return {"patient_id": patient_id, "encounters": rows[:limit],
                    "next_after_id": rows[limit-1]["id"] if len(rows)>limit else None}
        return run(request, context, patient_id, "encounter.read", EncounterPage, page,
                   read_refs={"after_id": after_id, "page_size": limit})

    @router.get(prefix+"/events", response_model=EncounterEvents | VisitEvents, responses=errors)
    def read_encounter_events(patient_id: str, request: Request, after_id: Cursor = 0, limit: PageSize = 25,
                              context: Principal = Depends(principal), include_visit_state: bool = False):
        def page(service, args):
            rows = service.changes(patient_id, after_id=after_id, limit=limit+1,
                                   include_visit_state=include_visit_state, **args)
            events = rows[:limit]
            return {"patient_id": patient_id, "events": events, "has_more": len(rows)>limit,
                    "resume_after_id": events[-1]["id"] if events else after_id}
        return run(request, context, patient_id, "encounter.events.read",
                   VisitEvents if include_visit_state else EncounterEvents, page,
                   read_refs={"after_id": after_id, "page_size": limit},
                   extra_actions=("encounter.read", "note.read"))

    @router.post(prefix+"/{encounter_id}/transitions", response_model=EncounterReceipt, responses=errors)
    def transition_encounter(patient_id: str, encounter_id: Identifier, payload: Transition, request: Request,
                             context: Principal = Depends(principal)):
        return run(request, context, patient_id, "encounter.transition", EncounterReceipt,
                   lambda service, args: service.transition(patient_id, encounter_id, payload.target,
                       expected_revision=payload.expected_revision, request_key=payload.request_key, **args))

    @router.get(prefix+"/{encounter_id}/notes", response_model=NotesPage, responses=errors)
    def read_encounter_notes(patient_id: str, encounter_id: Identifier, request: Request,
                             after_id: Cursor = 0, limit: PageSize = 25, context: Principal = Depends(principal)):
        def page(service, args):
            rows = service.list_note_headers(patient_id, encounter_id, after_id=after_id, limit=limit+1, **args)
            return {"patient_id": patient_id, "encounter_id": encounter_id, "notes": rows[:limit],
                    "next_after_id": rows[limit-1]["id"] if len(rows)>limit else None}
        return run(request, context, patient_id, "note.read", NotesPage, page,
                   read_refs={"encounter_id": encounter_id, "after_id": after_id, "page_size": limit})

    versions = prefix+"/{encounter_id}/notes/{note_key}/versions"

    @router.post(versions, response_model=NoteReceipt, responses=errors)
    def save_note_draft(patient_id: str, encounter_id: Identifier, note_key: NoteKey, payload: DraftNote,
                        request: Request, context: Principal = Depends(principal)):
        return run(request, context, patient_id, "note.write", NoteReceipt,
                   lambda service, args: service.write_note(patient_id, encounter_id, note_key, payload.body,
                       expected_version=payload.expected_version, note_kind=payload.note_kind,
                       facility_id=payload.facility_id, department_id=payload.department_id,
                       request_key=payload.request_key, **args))

    @router.get(versions, response_model=NoteHistory, responses=errors)
    def read_note_versions(patient_id: str, encounter_id: Identifier, note_key: NoteKey, request: Request,
                           after_version: Cursor = 0, limit: PageSize = 25,
                           context: Principal = Depends(principal)):
        def page(service, args):
            rows = service.note_history(patient_id, encounter_id, note_key, after_version=after_version,
                                        limit=limit+1, **args)
            return {"patient_id": patient_id, "encounter_id": encounter_id, "note_key": note_key,
                    "versions": rows[:limit], "next_after_version": rows[limit-1]["version"] if len(rows)>limit else None}
        return run(request, context, patient_id, "note.read", NoteHistory, page,
                   read_refs={"encounter_id": encounter_id, "note_key": note_key,
                              "after_version": after_version, "page_size": limit})
