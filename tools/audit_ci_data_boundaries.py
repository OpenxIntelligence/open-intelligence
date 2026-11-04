"""Offline policy gate: keep patient-case network workflows out of repository CI.

This is a source-code guard for our known workflow entrypoints, not a sandbox,
network firewall, PHI scanner, data-rights approval or complete security audit.
"""
from __future__ import annotations

from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
WORKFLOWS=ROOT/".github"/"workflows"
FORBIDDEN_SCRIPTS=frozenset({
    "public_case_intake",
    "rna_expression_probe",
    "single_cell_probe",
    "public_evidence_probe",
    "gdc_projection_probe",
    "clinical_semantics_probe",
    "trial_screening_probe",
})
# Prevent direct command execution and other obvious reintroductions of
# downloads. A Python function or imported module inside separate code still
# needs review; source matching is not a network egress enforcement boundary.
SCRIPT_CALL=re.compile(
    # Only a Python command invokes the script. A path-filter reference such as
    # 'tools/research/rna_expression_probe.py' is not executable work.
    r"\bpython(?:3(?:\.\d+)?)?\s+"
    r"(?:(?:-[uBIEsSOqb]+|-[WX]\s+[^\s;&|]+)\s+)*"
    r"(?:-m\s+tools\.research\.([a-z_]+)\b|(?:\./)?tools/research/([a-z_]+)\.py\b)"
)
BLOCKED_PUBLIC_CASE_URL=re.compile(
    r"https?://[^\s'\"<>]*(?:sid-sijbrandij-osteosarc-dataset|osteosarc\.com/data/catalog/datasets\.json)",
    re.I,
)
UNSAFE_SHELL=re.compile(
    r"\b(?:curl|wget|aws\s+s3\s+(?:cp|sync))\b",re.I
)

def scan_workflow_text(text: str, filename: str) -> list[str]:
    issues=[]
    for number,line in enumerate(text.splitlines(),1):
        stripped=line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        for found in SCRIPT_CALL.finditer(stripped):
            if (found.group(1) or found.group(2)) in FORBIDDEN_SCRIPTS:
                issues.append(f"{filename}:{number}: prohibited live research entrypoint")
        if BLOCKED_PUBLIC_CASE_URL.search(stripped):
            issues.append(f"{filename}:{number}: named-person data endpoint")
        if UNSAFE_SHELL.search(stripped):
            issues.append(f"{filename}:{number}: network/sync command needs explicit review")
    return issues


def build_receipt(*, checkout: str, audit_outcome: str, source_sha256: dict) -> dict:
    """Record the scan outcome without claiming to observe runtime data access."""
    return {
        'schema': 'oi-ci-data-boundary/1',
        'checkout': checkout,
        'declared_fixture_policy': 'independently_authored_synthetic_only',
        'known_entrypoint_scan': {
            'outcome': audit_outcome or 'unknown',
            'passed': audit_outcome == 'success',
            'scope': 'Known source patterns in repository workflow YAML',
        },
        'runtime_data_access_verified': False,
        'medical_validation': False,
        'sources_sha256': dict(source_sha256),
    }


def main() -> int:
    issues=[]
    for path in sorted(WORKFLOWS.glob("*.yml")):
        issues.extend(scan_workflow_text(path.read_text(encoding="utf-8"),path.name))
    for path in sorted(WORKFLOWS.glob("*.yaml")):
        issues.extend(scan_workflow_text(path.read_text(encoding="utf-8"),path.name))
    if issues:
        for message in issues:
            print(message)
        return 1
    print("PASS: no known patient-case download entrypoints in current workflows")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
