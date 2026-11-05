"""Create a synthetic episode draft from one explicit, current, source-reported primary.

The original source line is the natural creation key. Case and patient ownership
are derived through that immutable source rather than copied into a new registry.
"""
from datetime import datetime
from typing import Literal
from uuid import uuid4

from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import Field, StrictBool, StrictInt, StrictStr, field_validator

from open_intelligence.patient_registry import PatientRegistryConflict, PatientRegistryDenied
from open_intelligence.store import parse_report

from .contracts import Contract
from .sources import PostgresSourceVersions
from .source_integrity import SourceIntegrityError
from .source_world_model import project_source_world_model

MAX_DRAFTS = 64
DRAFT_PATH = "/{patient_id}/cases/{case_id}/episode-drafts"


class DraftCommand(Contract):
    synthetic: StrictBool
    source_id: StrictStr = Field(pattern=r"^SRC-[0-9A-F]{32}$")
    source_line: StrictInt = Field(ge=1, le=10_000)
    source_version: StrictInt = Field(ge=1)
    source_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    snapshot_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("synthetic")
    @classmethod
    def fictional_only(cls, value):
        if not value:
            raise ValueError("Synthetic command required")
        return value


class DraftReceipt(Contract):
    patient_id: str
    case_id: str
    episode_id: str
    duplicate: bool


class EpisodeDraft(Contract):
    episode_id: str
    created_by: str
    created_at: datetime
    source_id: str
    source_line: int
    source_version: int
    source_sha256: str
    document_id: str
    event_date: str
    issued_at: str
    source_label: str
    statement: str
    source_state: Literal["current", "superseded"]
    basis_sha256: str
    basis_state: Literal["current", "reassessment_required"]
    review_state: Literal["unreviewed_draft"] = "unreviewed_draft"


class EpisodeDrafts(Contract):
    patient_id: str
    case_id: str
    snapshot_sha256: str
    access_receipt_id: str
    drafts: list[EpisodeDraft]


def eligible_primary(role, episode_label, state):
    return role == "primary" and episode_label is not None and state == "reported"


def _save(registry, world, command, actor):
    source_id, line = command.source_id, command.source_line
    scope = dict(patient_id=world["patient_id"], case_id=world["case_id"])
    existing = registry._fetchone(
        "SELECT d.episode_id,d.basis_sha256,d.created_by,s.version,s.sha256 "
        "FROM clinical_source.episode_drafts d JOIN clinical_source.source_versions s USING(source_id) "
        "WHERE s.case_id=%s AND d.source_id=%s AND d.source_line=%s", (scope["case_id"], source_id, line))
    if existing:
        if tuple(existing[1:]) != (command.snapshot_sha256, actor, command.source_version, command.source_sha256):
            raise PatientRegistryConflict("Original line already has an episode draft")
        return DraftReceipt(**scope, episode_id=existing[0], duplicate=True)

    if command.snapshot_sha256 != world["snapshot_fingerprint"]:
        raise PatientRegistryConflict("Source snapshot has changed")
    finding = next((o for o in world["observations"] if (o["source_id"], o["source_line"]) == (source_id, line)), None)
    context = finding.get("oncology", {}) if finding else {}
    if (finding is None or (finding["document_version"], finding["source_sha256"]) !=
            (command.source_version, command.source_sha256) or
            not eligible_primary(context.get("role"), context.get("episode_id"), finding["reported_state"])):
        raise PatientRegistryConflict("A current source-reported primary with explicit attribution is required")
    # A replacement version cannot turn a previously saved document/finding into
    # a second identity. A future reassessment command must keep both versions.
    prior = registry._fetchone(
        "SELECT d.episode_id FROM clinical_source.episode_drafts d "
        "JOIN clinical_source.source_versions s USING(source_id) "
        "JOIN clinical_source.assertions a USING(source_id,source_line) "
        "WHERE s.case_id=%s AND s.document_id=%s AND a.finding_key=%s LIMIT 1",
        (scope["case_id"], finding["document_id"], finding["finding_key"]))
    if prior:
        raise PatientRegistryConflict("An earlier version already anchors an episode draft")
    count, = registry._fetchone(
        "SELECT count(*) FROM clinical_source.episode_drafts JOIN clinical_source.source_versions USING(source_id) "
        "WHERE case_id=%s", (scope["case_id"],))
    if count >= MAX_DRAFTS:
        raise PatientRegistryConflict("Episode draft capacity reached")
    episode_id = "EPISODE-" + uuid4().hex.upper()
    registry.append_event(scope["patient_id"], "episode.draft_created", case_id=scope["case_id"],
                          episode_id=episode_id, source_id=source_id, source_line=line,
                          basis_sha256=command.snapshot_sha256, actor=actor, purpose="operations")
    inserted = registry._execute(
        "INSERT INTO clinical_source.episode_drafts "
        "(episode_id,source_id,source_line,basis_sha256,created_by,creation_event_id) "
        "SELECT %s,%s,%s,%s,%s,id FROM identity.identity_domain_events "
        "WHERE patient_id=%s AND event_type='episode.draft_created' AND metadata_json->>'episode_id'=%s",
        (episode_id, source_id, line, command.snapshot_sha256, actor, scope["patient_id"], episode_id))
    if inserted != 1:
        raise SourceIntegrityError("Episode creation event unavailable")
    return DraftReceipt(**scope, episode_id=episode_id, duplicate=False)


def _history(registry, world):
    # list_locked has verified all originals, including historical bytes, in this transaction.
    # Read the attribution from those exact bytes; a later version cannot rename the draft.
    rows = registry._fetchall(
        "SELECT d.episode_id,d.source_line,d.basis_sha256,d.created_by,d.created_at,s.source_id,s.raw "
        "FROM clinical_source.episode_drafts d JOIN clinical_source.source_versions s USING(source_id) "
        "WHERE s.case_id=%s ORDER BY d.created_at,d.episode_id LIMIT %s", (world["case_id"], MAX_DRAFTS+1))
    if len(rows) > MAX_DRAFTS:
        raise SourceIntegrityError("Excess episode draft rows")
    sources = {s["source_id"]: s for s in [*world["current_sources"], *world["history"]]}
    drafts = []
    for episode_id, line, basis, actor, created_at, source_id, raw in rows:
        source = sources.get(source_id)
        finding = next((f for f in parse_report(bytes(raw), allow_oncology=True).findings if f.line == line), None)
        if (source is None or finding is None or finding.oncology is None or
                not eligible_primary(finding.oncology.role, finding.oncology.episode_id, finding.state)):
            raise SourceIntegrityError("Episode draft origin unavailable")
        drafts.append(EpisodeDraft(
            episode_id=episode_id, created_by=actor, created_at=created_at, source_id=source_id,
            source_line=line, source_version=source["version"], source_sha256=source["sha256"],
            document_id=source["document_id"], source_label=finding.oncology.episode_id, statement=finding.quote,
            event_date=source["event_date"], issued_at=source["issued_at"], source_state=source["state"],
            basis_sha256=basis, basis_state="current" if basis == world["snapshot_fingerprint"] else "reassessment_required"))
    return EpisodeDrafts(patient_id=world["patient_id"], case_id=world["case_id"],
                         snapshot_sha256=world["snapshot_fingerprint"], access_receipt_id=world["access_receipt_id"],
                         drafts=drafts)


def register_episode_routes(router, *, principal, registry, authorize, refresh, errors):
    def handle(request, patient_id, case_id, context, command=None):
        actions = ("source_read", "episode_draft_read") if command is None else (
            "source_read", "episode_draft_read", "episode_draft_create")
        if context.purpose != "operations":
            raise HTTPException(404, "Episode drafts unavailable")
        try:
            with registry(context) as patients:
                for action in actions:
                    authorize(patients, context, patient_id, action)

                def prepare(index):
                    world = project_source_world_model(index)
                    if command is None:
                        body, status = _history(patients, world), 200
                        patients.append_event(patient_id, "episode.drafts_read", case_id=case_id, actor=context.actor,
                                              purpose=context.purpose, source_receipt_id=index["access_receipt_id"],
                                              draft_count=len(body.drafts))
                    else:
                        body = _save(patients, world, command, context.actor)
                        status = 200 if body.duplicate else 201
                    return JSONResponse(body.model_dump(mode="json"), status_code=status,
                                        headers={"Cache-Control":"no-store", "X-Content-Type-Options":"nosniff"})

                return PostgresSourceVersions(patients).list(
                    patient_id, case_id, organization=context.organization, actor=context.actor,
                    purpose=context.purpose, prepare_response=prepare,
                    recheck_authority=lambda: refresh(request, context, patients, patient_id, actions))
        except PatientRegistryDenied:
            raise HTTPException(404, "Episode drafts unavailable") from None

    @router.get(DRAFT_PATH, response_model=EpisodeDrafts, responses=errors, operation_id="read_episode_drafts_v1")
    def read(request: Request, patient_id: str, case_id: str, context=Depends(principal)):
        return handle(request, patient_id, case_id, context)

    @router.post(DRAFT_PATH, response_model=DraftReceipt, status_code=201,
                 responses={200: {"model": DraftReceipt}, **errors}, operation_id="create_episode_draft_v1")
    def create(request: Request, patient_id: str, case_id: str, payload: DraftCommand,
               context=Depends(principal)):
        return handle(request, patient_id, case_id, context, payload)
