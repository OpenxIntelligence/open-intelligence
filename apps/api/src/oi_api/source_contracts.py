"""Shared source attribution contracts, independent of HTTP composition."""

from typing import Literal

from pydantic import Field, field_validator

from .contracts import Contract


class ReportedOncologyContext(Contract):
    role: Literal["primary", "metastasis"]
    episode_id: str | None = Field(pattern=r"^EP-[A-Z0-9][A-Z0-9-]{0,35}$")


class SourceOncologyFields(Contract):
    oncology: ReportedOncologyContext | None = Field(default=None, exclude_if=lambda value: value is None)

    @field_validator("oncology", mode="before")
    @classmethod
    def require_context_if_present(cls, value):
        if value is None:
            raise ValueError("Omit oncology when the original has no attribution")
        return value
