"""Allow a versioned manual-context renderer without rewriting earlier reports."""
from alembic import op
from alembic.util.exc import CommandError
from sqlalchemy import text

revision='0015_manual_report_context'
down_revision='0014_question_passages'
branch_labels=None
depends_on=None


def change_renderer(*,reverse=False):
    conn=op.get_bind()
    conn.exec_driver_sql('LOCK TABLE investigation.evidence_command_origins IN SHARE ROW EXCLUSIVE MODE')
    rows=conn.execute(text("SELECT conname,pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid='investigation.evidence_command_origins'::regclass AND contype='c' AND pg_get_constraintdef(oid) LIKE '%report_renderer%'")).all()
    guard=conn.execute(text("SELECT pg_get_functiondef('investigation.guard_evidence_command_origin_insert()'::regprocedure)")).scalar_one()
    old_check="(report_renderer = 'oi.h1-evidence-text/2'::text)"
    new_check="(report_renderer = ANY (ARRAY['oi.h1-evidence-text/2'::text, 'oi.h1-evidence-text/3'::text]))"
    old_guard="NEW.report_renderer!='oi.h1-evidence-text/2'"
    new_guard="NEW.report_renderer NOT IN ('oi.h1-evidence-text/2','oi.h1-evidence-text/3')"
    if reverse:
        old_check,new_check=new_check,old_check
        old_guard,new_guard=new_guard,old_guard
    if len(rows)!=1 or rows[0][1].count(old_check)!=1 or guard.count(old_guard)!=1:
        raise CommandError('Evidence renderer guard differs; explicit owner reconciliation required')
    name=conn.dialect.identifier_preparer.quote(rows[0][0])
    conn.exec_driver_sql('ALTER TABLE investigation.evidence_command_origins DROP CONSTRAINT '+name)
    conn.exec_driver_sql('ALTER TABLE investigation.evidence_command_origins ADD CONSTRAINT '+name+' '+rows[0][1].replace(old_check,new_check))
    conn.exec_driver_sql(guard.replace(old_guard,new_guard))


def upgrade():
    change_renderer()


def downgrade():
    if op.get_bind().execute(text("SELECT EXISTS(SELECT 1 FROM investigation.evidence_command_origins WHERE report_renderer='oi.h1-evidence-text/3')")).scalar_one():
        raise CommandError('Manual-context reports require explicit reconciliation before downgrade')
    change_renderer(reverse=True)
