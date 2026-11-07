"""Explicit configuration with credential-safe failures."""

import math
import os
from dataclasses import dataclass, field
from typing import Mapping

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class ConfigurationError(ValueError):
    """Invalid configuration; messages deliberately exclude supplied values."""


@dataclass(frozen=True)
class Settings:
    database_url: str | None = field(default=None, repr=False)
    environment: str = "synthetic"
    connect_timeout_seconds: float = 2.0
    require_persisted_grants: bool = False
    require_consent_decisions: bool = False
    access_file: str | None = field(default=None, repr=False)

    def __post_init__(self):
        if type(self.require_consent_decisions) is not bool:
            raise ConfigurationError("Consent policy must be boolean")
        if type(self.require_persisted_grants) is not bool:
            raise ConfigurationError("Persisted grant policy must be boolean")
        if self.environment != "synthetic":
            raise ConfigurationError("Only the synthetic environment is enabled")
        if not math.isfinite(self.connect_timeout_seconds) or not 0.1 <= self.connect_timeout_seconds <= 10:
            raise ConfigurationError("Database timeout must be between 0.1 and 10 seconds")
        if self.database_url is not None:
            try:
                url = make_url(self.database_url)
                valid = (
                    url.drivername == "postgresql+pg8000"
                    and bool(url.host) and bool(url.database) and bool(url.username)
                    and not url.query
                )
                if not valid:
                    raise ValueError()
            except (ArgumentError, ValueError, TypeError):
                raise ConfigurationError("A valid PostgreSQL/pg8000 database URL without query options is required") from None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None):
        values = os.environ if env is None else env
        try:
            timeout = float(values.get("OI_API_CONNECT_TIMEOUT_SECONDS", "2"))
        except (ValueError, TypeError):
            raise ConfigurationError("Database timeout must be numeric") from None
        if values.get("OI_API_REQUIRE_PERSISTED_GRANTS", "0") not in {"0", "1"}:
            raise ConfigurationError("Persisted grant policy must be 0 or 1")
        if values.get("OI_API_REQUIRE_CONSENT_DECISIONS", "0") not in {"0", "1"}:
            raise ConfigurationError("Consent policy must be 0 or 1")
        return cls(
            require_consent_decisions=values.get("OI_API_REQUIRE_CONSENT_DECISIONS", "0") == "1",
            require_persisted_grants=values.get("OI_API_REQUIRE_PERSISTED_GRANTS", "0") == "1",
            database_url=values.get("OI_API_DATABASE_URL"),
            environment=values.get("OI_API_ENVIRONMENT", "synthetic"),
            connect_timeout_seconds=timeout,
            access_file=values.get("OI_API_ACCESS_FILE"),
        )
