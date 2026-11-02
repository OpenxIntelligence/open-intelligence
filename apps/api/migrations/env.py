"""Use only the explicit, prevalidated migration connection."""

from alembic import context

connection = context.config.attributes.get("connection")
if connection is None:
    raise RuntimeError("Use python -m oi_api.migrate with explicit database configuration")

context.configure(
    connection=connection,
    target_metadata=None,
    version_table_schema="public",
)
with context.begin_transaction():
    context.run_migrations()
