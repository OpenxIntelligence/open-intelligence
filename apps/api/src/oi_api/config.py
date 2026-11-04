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
    access_file: str | None = field(default=None, repr=False)

    def __post_init__(self):
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
        return cls(
            database_url=values.get("OI_API_DATABASE_URL"),
            environment=values.get("OI_API_ENVIRONMENT", "synthetic"),
            connect_timeout_seconds=timeout,
            access_file=values.get("OI_API_ACCESS_FILE"),
        )
