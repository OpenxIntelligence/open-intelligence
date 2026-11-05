"""Independently fictional, deterministic pure-owner fixtures; no database proof."""
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from open_intelligence.postgres_registry import PostgresPatientRegistry
from oi_api.composer_preflight import PostgresSourceComposerPreflight, prepare_laboratory_question
from oi_api.question_followthrough import _project_task
from oi_api.source_questions import PostgresSourceQuestions
from oi_api.source_world_model import project_source_world_model
from test_laboratory_question_preflight import context, PID, CASE, SID, QUESTION, OBS

WHEN = datetime(2026, 11, 5, 6, 0, tzinfo=timezone.utc)


def text_context():
    index, _ = context()
    index['sources'][0].update(document_id='FICTIONAL-TEXT-A', kind='pathology',
                               specimen_id='FICTIONAL-SPECIMEN-A', sha256='a' * 64)
    index['source_reported_assertions'] = [{
        'source_id': SID, 'source_line': 8, 'finding_key': 'fictional-marker',
        'reported_state': 'not-reported', 'source_statement': 'Fictional café <literal> source.',
        'clinical_review_state': 'not_established',
    }]
    return index


def text_preflight():
    index = text_context()
    registry = PostgresPatientRegistry(SimpleNamespace(autocommit=False))
    registry._transaction_active = True  # Pure calculation only; not authority evidence.
    return PostgresSourceComposerPreflight(registry).preview_locked(
        PID, CASE, organization='ORG-ALPHA', actor='ACTOR-ALPHA', purpose='operations',
        expected_source_snapshot_sha256=project_source_world_model(index)['snapshot_fingerprint'],
        source_id=SID, source_line=8, question=QUESTION, source_index=index)


def question_row():
    prepared = text_preflight()
    return ('QUESTION-' + 'D' * 32, PID, CASE, QUESTION, SID, 8, 'a' * 64, 1,
            prepared['source_snapshot_sha256'], prepared['preflight_sha256'], WHEN,
            prepared['source_snapshot_contract'])


def task_rows():
    question = PostgresSourceQuestions._question_state(
        question_row(), project_source_world_model(text_context()))
    fields = ('question_id', 'patient_id', 'case_id', 'source_id', 'source_line',
              'source_sha256', 'source_version', 'source_snapshot_contract',
              'source_snapshot_sha256', 'preflight_sha256')
    task = {name: question[name] for name in fields} | {
        'task_id': 'TASK-' + 'E' * 32, 'origin_org': 'ORG-ALPHA', 'actor': 'ACTOR-ALPHA',
        'purpose': 'operations', 'title': 'Prepare the fictional discussion',
        'detail': 'Gather source references.', 'initial_owner_label': '',
        'due_date': date(2026, 11, 6), 'review_trigger': '', 'created_at': WHEN,
    }
    history = [{
        'event_id': 'TASK-EVENT-' + 'F' * 32, 'task_id': task['task_id'],
        'patient_id': PID, 'case_id': CASE, 'origin_org': 'ORG-ALPHA',
        'purpose': 'operations', 'revision': 1, 'previous_status': None, 'status': 'created',
        'owner_label': '', 'actor_label': 'ACTOR-ALPHA',
        'reason': 'Recorded for a fictional discussion.', 'recorded_at': WHEN,
    }]
    return task, history, question


def compatibility_outputs():
    result = {'text_preflight': text_preflight()}
    for label, value, absent in (
        ('precision', Decimal('4.20'), None), ('zero', Decimal('0'), None),
        ('negative', Decimal('-2.50'), None), ('exponent', Decimal('1E-7'), None),
        *[(reason, Decimal('4.20'), reason)
          for reason in ('unknown', 'not-performed', 'error', 'masked')],
    ):
        index, labs = context(value, absent)
        result['lab_' + label] = prepare_laboratory_question(
            index, labs, patient_id=PID, case_id=CASE, source_id=SID,
            observation_reference=OBS, question=QUESTION,
            expected_source_snapshot_sha256=project_source_world_model(index)['snapshot_fingerprint'])
    world = project_source_world_model(text_context())
    result['question_current'] = PostgresSourceQuestions._question_state(question_row(), world)
    result['question_stale'] = PostgresSourceQuestions._question_state(
        question_row(), world | {'snapshot_fingerprint': '0' * 64})
    prepared = result['text_preflight']
    result['legacy_question_intent'] = PostgresSourceQuestions._intent(
        PID, CASE, 'ORG-ALPHA', 'ACTOR-ALPHA', 'operations', 'FICTIONAL-REQUEST-A', SID, 8,
        QUESTION, prepared['source_snapshot_sha256'], prepared['preflight_sha256'])
    task, history, question = task_rows()
    result['followthrough'] = _project_task(task, history, question, '2026-11-05')
    return result
