"""Explicit migration CLI; neither importing nor serving the app applies DDL."""

import argparse
import os
from pathlib import Path
import sys

from alembic import command
from alembic.config import Config
from alembic.util.exc import CommandError
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from .config import ConfigurationError, Settings
from .contracts import POSTGRES_MAJOR
from .database import make_engine


def migrate(settings: Settings, operation: str, revision: str | None = None):
    if settings.database_url is None:
        raise ConfigurationError("Database configuration is required")
    if operation not in ("upgrade", "downgrade", "current"):
        raise ValueError("Unsupported migration operation")
    if operation != "current" and not revision:
        raise ValueError("A migration revision is required")
    if operation == "downgrade" and (
        os.environ.get("OI_API_RUN_DATABASE_TESTS") != "1"
        or not (make_url(settings.database_url).database or "").startswith("oi_api_test_")
    ):
        raise ConfigurationError("Downgrades require explicit test mode and an oi_api_test_ database")
    # pg8000 uses its socket timeout for reads as well as connection setup.
    # Give administrative DDL time to receive PostgreSQL's own bounded error.
    statement_seconds = 30
    engine = make_engine(settings, transport_timeout=statement_seconds + 5)
    try:
        with engine.begin() as connection:
            version = int(connection.execute(text("SELECT current_setting('server_version_num')")).scalar_one())
            if version // 10000 != POSTGRES_MAJOR:
                raise ConfigurationError("Migrations require PostgreSQL 16")
            # Bound waiting for locks/SQL in this baseline; extend deliberately for
            # future reviewed data migrations rather than waiting indefinitely.
            connection.execute(text("SELECT set_config('lock_timeout', '5000', true)"))
            connection.execute(text("SELECT set_config('statement_timeout', :budget, true)"),
                               {"budget": f"{statement_seconds}s"})
            config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
            config.attributes["connection"] = connection
            if operation == "current":
                command.current(config)
            elif operation == "upgrade":
                command.upgrade(config, revision)
            else:
                command.downgrade(config, revision)
    finally:
        engine.dispose()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Migrate the local synthetic H1 database explicitly")
    parser.add_argument("operation", choices=("upgrade", "downgrade", "current"))
    parser.add_argument("revision", nargs="?")
    args = parser.parse_args(argv)
    if args.operation != "current" and not args.revision:
        parser.error("upgrade/downgrade require an explicit revision")
    try:
        migrate(Settings.from_env(), args.operation, args.revision)
    except ConfigurationError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (SQLAlchemyError, CommandError, OSError):
        print("Database migration failed; inspect configuration and migration state without exposing credentials", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
