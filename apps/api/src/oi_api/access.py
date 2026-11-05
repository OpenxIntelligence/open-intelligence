"""Trusted request-context port and a deliberately synthetic fixture adapter.

This is not identity proofing, account management, caregiver delegation or
consent. Missing, expired, ambiguous or unreadable configuration fails closed.
"""

from datetime import datetime, timezone
import hashlib
import hmac
import json
import re
from pathlib import Path
from typing import Literal, Protocol

from fastapi import HTTPException, Request
from pydantic import Field, ValidationError, field_validator, model_validator

from open_intelligence.patient_registry import _key

from .contracts import Contract


class AccessUnavailable(Exception):
    """The trusted context provider is unavailable; details are not public."""


class Principal(Contract):
    actor: str
    organization: str
    purpose: Literal["operations", "research"]
    actions: frozenset[Literal["patient_create", "patient_read", "record_request_create", "record_request_read", "record_request_cancel", "record_request_receive", "case_binding_create", "case_binding_read", "case_binding_revoke", "source_import", "source_read", "source_original_read", "composer_context_read", "question_create", "question_read", "image_import", "image_read", "image_original_read", "review_queue_read", "review_return", "source_brief_export", "review_packet_read", "followthrough_read", "followthrough_create", "followthrough_update", "evidence_read", "evidence_link", "authored_evidence_read", "authored_evidence_import", "authored_evidence_assess", "authored_evidence_withdraw", "authored_evidence_original_read", "evidence_report_export", "encounter.schedule", "encounter.read", "encounter.events.read", "encounter.transition", "note.write", "note.read"]] = frozenset()
    patient_ids: frozenset[str] = Field(default_factory=frozenset, max_length=256)
    expires_at: datetime

    @field_validator("actor", "organization")
    @classmethod
    def bounded_identity(cls, value):
        return _key(value, "identity")

    @field_validator("patient_ids")
    @classmethod
    def bounded_patients(cls, values):
        for value in values:
            _key(value, "patient_id")
        return values

    @field_validator("expires_at")
    @classmethod
    def aware_expiry(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("An explicit expiry timezone is required")
        return value


class Credential(Principal):
    token_sha256: str = Field(pattern=r"^[0-9a-f]{64}$", repr=False)


class AccessDocument(Contract):
    version: Literal["oi.synthetic-access/1"]
    credentials: list[Credential] = Field(max_length=64)

    @model_validator(mode="after")
    def unambiguous_tokens(self):
        if len({item.token_sha256 for item in self.credentials}) != len(self.credentials):
            raise ValueError("Duplicate credential digest")
        return self


class Authentication(Protocol):
    def authenticate(self, token: str) -> Principal | None: ...


class DenyAuthentication:
    def authenticate(self, token: str) -> Principal | None:
        return None


def authenticate_request(request: Request, authentication: Authentication) -> Principal:
    """Recheck the same bearer under the current grant without storing its token."""
    values = request.headers.getlist("authorization")
    if len(values) != 1:
        raise HTTPException(401, "Authentication required",
                            headers={"WWW-Authenticate": "Bearer"})
    scheme, _, token = values[0].partition(" ")
    if scheme.lower() != "bearer":
        raise HTTPException(401, "Authentication required",
                            headers={"WWW-Authenticate": "Bearer"})
    return authenticate_token(token, authentication)


def authenticate_token(token: str, authentication: Authentication) -> Principal:
    """Recheck a supplied bearer using the current trusted authentication provider."""
    if re.fullmatch(r"[A-Za-z0-9._~-]{32,256}", token) is None:
        raise HTTPException(401, "Authentication required",
                            headers={"WWW-Authenticate": "Bearer"})
    try:
        context = authentication.authenticate(token)
    except Exception:
        raise HTTPException(503, "Access service unavailable") from None
    if context is None:
        raise HTTPException(401, "Authentication required",
                            headers={"WWW-Authenticate": "Bearer"})
    if not isinstance(context, Principal):
        raise HTTPException(503, "Access service unavailable")
    if context.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(401, "Authentication required",
                            headers={"WWW-Authenticate": "Bearer"})
    return context


class SyntheticFileAuthentication:
    """Operator-controlled local fixture; reread every time, never cache grants.

    Every authentication call rereads the fixture. Operations with a final
    authority check can refuse changes during preparation; other operations
    still use their entry check. This is not distributed revocation atomicity.
    No raw bearer token is stored in this file or returned in its parsed context.
    """

    def __init__(self, path: str):
        self._path = Path(path)

    def authenticate(self, token: str) -> Principal | None:
        try:
            with self._path.open("rb") as stream:
                data = stream.read(65_537)
            if len(data) > 65_536:
                raise ValueError("Access fixture exceeds its bound")
            # Validate the wire representation before model validation can
            # discard duplicate keys (including escaped spellings). A policy
            # with two scopes must not silently acquire last-member semantics.
            parsed = json.loads(data.decode("utf-8"),
                                object_pairs_hook=_unique_policy_object,
                                parse_constant=_reject_nonfinite_policy_number)
            document = AccessDocument.model_validate(parsed)
        except (OSError, ValueError, ValidationError, RecursionError):
            raise AccessUnavailable() from None
        digest = hashlib.sha256(token.encode("ascii")).hexdigest()
        now = datetime.now(timezone.utc)
        for candidate in document.credentials:
            if hmac.compare_digest(candidate.token_sha256, digest) and candidate.expires_at > now:
                return Principal.model_validate(candidate.model_dump(exclude={"token_sha256"}))
        return None


def _unique_policy_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Ambiguous access policy")
        result[key] = value
    return result


def _reject_nonfinite_policy_number(_value):
    raise ValueError("Invalid access policy number")
