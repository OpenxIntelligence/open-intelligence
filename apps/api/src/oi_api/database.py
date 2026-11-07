"""Read-only dependency check. Application startup never migrates the database."""

from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool

from .config import Settings
from .contracts import DatabaseStatus, POSTGRES_MAJOR, SCHEMA_REVISION


def make_engine(settings: Settings, *, transport_timeout: float | None = None):
    if settings.database_url is None:
        raise ValueError("Database configuration is required")
    return create_engine(
        settings.database_url,
        poolclass=NullPool,
        connect_args={"timeout": settings.connect_timeout_seconds if transport_timeout is None else transport_timeout},
        hide_parameters=True,
        echo=False,
    )


class Database:
    def __init__(self, settings: Settings):
        self._engine = make_engine(settings) if settings.database_url else None
        self._timeout_ms = str(int(settings.connect_timeout_seconds * 1000))

    def check(self) -> DatabaseStatus:
        if self._engine is None:
            return DatabaseStatus(status="unconfigured")
        try:
            with self._engine.connect() as connection:
                connection.execute(text("SELECT set_config('statement_timeout', :timeout, true)"), {"timeout": self._timeout_ms})
                version = int(connection.execute(text("SELECT current_setting('server_version_num')")).scalar_one())
                if version // 10000 != POSTGRES_MAJOR:
                    return DatabaseStatus(status="unsupported_version")
                table = connection.execute(text("SELECT to_regclass('public.alembic_version')")).scalar_one()
                if table is None:
                    return DatabaseStatus(status="schema_mismatch")
                revisions = connection.execute(text("SELECT version_num FROM public.alembic_version")).scalars().all()
                if revisions != [SCHEMA_REVISION]:
                    return DatabaseStatus(status="schema_mismatch")
                return DatabaseStatus(status="ready")
        except (SQLAlchemyError, OSError, ValueError):
            # Database exceptions can contain SQL, addresses and credentials.
            # This public shell exposes only a bounded status, never exception text.
            return DatabaseStatus(status="unavailable")

    def close(self):
        if self._engine is not None:
            self._engine.dispose()

    @contextmanager
    def registry_connection(self):
        """An owned DB-API connection; validate this connection before any write.

        The canonical registry owns its transactions. Connection/session limits
        apply through its later commits, and closing rolls back failed reads.
        """
        if self._engine is None:
            raise RuntimeError("Database unavailable")
        pooled = self._engine.raw_connection()
        connection = pooled.driver_connection
        try:
            cursor = connection.cursor()
            try:
                cursor.execute("SELECT set_config('statement_timeout', %s, false)", (self._timeout_ms,))
                cursor.execute("SELECT set_config('lock_timeout', %s, false)", (self._timeout_ms,))
                cursor.execute("SELECT current_setting('server_version_num')")
                if int(cursor.fetchone()[0]) // 10000 != POSTGRES_MAJOR:
                    raise RuntimeError("Unsupported database")
                cursor.execute("SELECT version_num FROM public.alembic_version")
                if [row[0] for row in cursor.fetchall()] != [SCHEMA_REVISION]:
                    raise RuntimeError("Unsupported migration state")
            finally:
                cursor.close()
            connection.commit()
            yield connection
        finally:
            try:
                connection.rollback()
            finally:
                pooled.close()
