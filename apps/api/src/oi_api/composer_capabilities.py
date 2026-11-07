"""The existing Composer owner's implemented workload, not the planned portfolio."""
from .execution_capabilities import CapabilityCatalog, CapabilityDescriptor

SOURCE_BRIEF_CAPABILITY = CapabilityDescriptor(
    kind="source-question-brief/1",
    owner="questions-review",
    input_contract="oi.pg-source-world-model/1",
    output_contract="oi.synthetic-source-brief/2",
    required_actions=("patient_read", "question_read", "source_read", "source_brief_export"),
)
COMPOSER_CAPABILITIES = CapabilityCatalog((SOURCE_BRIEF_CAPABILITY,))
