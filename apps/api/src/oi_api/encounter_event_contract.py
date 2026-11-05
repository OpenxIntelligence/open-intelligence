"""Reference-only contract shared by the H1 encounter feed and its receivers."""
from typing import Literal

from .contracts import Contract


class EncounterEvent(Contract):
    id: int
    event_type: Literal["clinical_encounter_scheduled", "clinical_encounter_state_changed",
                        "clinical_note_draft_saved"]
    occurred_at: str
    encounter_id: int
    encounter_revision: int | None
    note_key: str | None
    note_version: int | None


class EncounterEvents(Contract):
    patient_id: str
    events: list[EncounterEvent]
    resume_after_id: int
    has_more: bool
    access_receipt_id: str
