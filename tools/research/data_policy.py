"""Non-overridable boundary for retired individual-case research entrypoints.

Generic parsers and calculations remain available for independently authored
synthetic fixtures. Public narratives inform requirements, never patient inputs.
"""
import sys


MESSAGE = (
    'Personal medical data acquisition and case-specific analysis are disabled. '
    'Use independently authored synthetic fixtures. No manual or opt-in override exists.'
)


def deny_personal_data_use() -> None:
    raise PermissionError(MESSAGE)


def disabled_cli() -> None:
    print(MESSAGE, file=sys.stderr)
    raise SystemExit(2)
