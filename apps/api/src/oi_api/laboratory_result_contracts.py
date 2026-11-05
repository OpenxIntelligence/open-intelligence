"""Literal laboratory result fields shared by preview, projections and saved anchors."""
from typing import Annotated, Literal

from pydantic import Field, StrictStr, field_validator, model_validator
from pydantic.json_schema import SkipJsonSchema
from typing_extensions import NotRequired, TypedDict

from .contracts import Contract
from .laboratory_fhir_r4 import checked_result_coding


LaboratoryResultStatus = Literal["reported_value", "reported_absent", "reported_coded"]
CodingToken = Annotated[StrictStr, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")]


class CodedLaboratoryResult(TypedDict):
    system: Literal["urn:oi:synthetic:lab-results"]
    code: CodingToken
    version: NotRequired[CodingToken]
    display: NotRequired[Annotated[StrictStr, Field(pattern=r"^[!-~](?:[ -~]{0,118}[!-~])?$")]]


class ReportedLaboratoryResult(Contract):
    status: LaboratoryResultStatus
    value_text: StrictStr | None
    unit_code: StrictStr | None
    absent_reason: Literal["unknown", "not-performed", "error", "masked"] | None
    coded_result: CodedLaboratoryResult | SkipJsonSchema[None] = Field(
        default_factory=lambda: None, exclude_if=lambda v: v is None,
        description="Present only for reported_coded. Other result carriers are then null.",
    )

    @field_validator("coded_result", mode="before")
    @classmethod
    def literal_coding(cls, value):
        # The source profile rejects extra fields, explicit nulls and malformed
        # literal strings rather than coercing them into a different statement.
        return checked_result_coding(value)

    @model_validator(mode="after")
    def one_result_carrier(self):
        if self.status == "reported_value":
            valid = (self.value_text is not None and self.unit_code is not None
                     and self.absent_reason is None and self.coded_result is None)
        elif self.status == "reported_absent":
            valid = (self.value_text is None and self.unit_code is None
                     and self.absent_reason is not None and self.coded_result is None)
        else:
            valid = (self.value_text is None and self.unit_code is None
                     and self.absent_reason is None and self.coded_result is not None)
        if not valid:
            raise ValueError("Inconsistent reported laboratory result")
        return self
