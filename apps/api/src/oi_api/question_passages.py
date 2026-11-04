"""Immutable reference-set children of canonical source questions.

Originals/annotations remain with ReviewedDocuments. This helper owns only the
question's explicitly selected reference set, under the existing case lock.
"""
import hmac
import uuid

from open_intelligence.patient_registry import PatientRegistryConflict, PatientRegistryDenied, PatientRegistryError
from .reviewed_documents import ReviewedDocuments, canonical, fingerprint
from .question_passage_contracts import ManualContext, ReplaceQuestionPassages, context_hash
from .sources import PostgresSourceVersions


def reference_audit(context):
    # The shared event port accepts primitive references only. Exact references
    # remain in immutable passage revisions; the audit pins their resolved set.
    references=context.get('manual_reads',[])
    return dict(reference_count=len(references),references_sha256=fingerprint(references))


class QuestionPassages:
    def __init__(self, registry):
        self.registry = registry

    def resolve_locked(self, c, references):
        if references:
            c['require_original']()
        result=[]
        owner=ReviewedDocuments(self.registry)
        for ref in references:
            value=owner.resolve_selection_locked(c['patient_id'],c['case_id'],ref['source_id'],
                ref['annotation_revision_id'],ref['selection_key'],organization=c['organization'],purpose=c['purpose'])
            if not hmac.compare_digest(value['anchor_sha256'],ref['anchor_sha256']):
                raise PatientRegistryConflict('Manual passage anchor changed')
            if ref not in c.setdefault('manual_reads',[]):
                c['manual_reads'].append(ref)
            result.append({k:value[k] for k in ('anchor','anchor_sha256','source_state','latest_annotation_revision_id','selection_state')})
        return result

    def rows_locked(self, c):
        if not self.registry._transaction_active:
            raise PatientRegistryError('Question passage preparation requires a transaction')
        rows=self.registry._fetchall(
            'SELECT revision_id,revision,references_json,actor,created_at,request_key,intent_sha256,command_json '
            'FROM investigation.question_passage_revisions WHERE patient_id=%s AND case_id=%s '
            'AND origin_org=%s AND question_id=%s ORDER BY revision LIMIT 65',
            (c['patient_id'],c['case_id'],c['organization'],c['question_id']))
        if len(rows)>64:
            raise PatientRegistryError('Question passage history exceeds its bounded limit')
        for ordinal,row in enumerate(rows,1):
            command=ReplaceQuestionPassages(**row[7]).model_dump(mode='json')
            if row[1]!=ordinal or command!=row[7] or command['references']!=row[2] or command['request_key']!=row[5] or self.intent(c,command,actor=row[3])!=row[6]:
                raise RuntimeError('Stored question passage command integrity failed')
        return rows

    @staticmethod
    def intent(c, command, *, actor=None):
        return fingerprint({k:c[k] for k in ('patient_id','case_id','organization','question_id','purpose')} |
                           {'actor':c['actor'] if actor is None else actor,'command':command})

    def metadata_locked(self,c,*,revision_id=None):
        """Read passage-set identity/freshness without disclosing original text."""
        if not self.registry._transaction_active:
            raise PatientRegistryError('Question passage preparation requires a transaction')
        if self.registry._fetchone(
                "SELECT to_regclass('investigation.question_passage_revisions')")[0] is None:
            # Direct migration fixtures seed published older authored schemas.
            # Current HTTP still requires the exact application schema revision.
            revisions=self.registry._fetchall(
                'SELECT version_num FROM public.alembic_version ORDER BY version_num')
            legacy={'0010_authored_evidence_origin','0011_evidence_convergence',
                    '0012_reviewed_documents','0013_document_image_convergence'}
            if revision_id is not None or len(revisions)!=1 or revisions[0][0] not in legacy:
                raise RuntimeError('Question passage owner unavailable at this schema revision')
            return dict(revision_id=None,revision=0,attached_by=None,attached_at=None,
                        references=[],state='current_unreviewed')
        rows=self.rows_locked(c)
        row=next((r for r in rows if r[0]==revision_id),None) if revision_id else (rows[-1] if rows else None)
        if revision_id and row is None:
            raise RuntimeError('Stored question passage revision unavailable')
        references=row[2] if row else []
        current=True
        for ref in references:
            source=self.registry._fetchone(
                'SELECT s.state FROM clinical_source.source_versions s '
                'JOIN clinical_source.document_intakes d ON d.source_id=s.source_id '
                'WHERE s.case_id=%s AND s.source_id=%s',
                (c['case_id'],ref['source_id']))
            selected=self.registry._fetchone(
                'SELECT revision FROM clinical_source.annotation_revisions '
                'WHERE source_id=%s AND revision_id=%s',
                (ref['source_id'],ref['annotation_revision_id']))
            latest=self.registry._fetchone(
                'SELECT revision_id FROM clinical_source.annotation_revisions '
                'WHERE source_id=%s ORDER BY revision DESC LIMIT 1',
                (ref['source_id'],))
            if source is None or selected is None or latest is None:
                raise RuntimeError('Stored question passage provenance unavailable')
            current=current and source[0]=='current' and latest[0]==ref['annotation_revision_id']
        return dict(revision_id=row[0] if row else None,revision=row[1] if row else 0,
                    attached_by=row[3] if row else None,
                    attached_at=row[4].isoformat() if row else None,
                    references=references,
                    state='current_unreviewed' if current else 'reassessment_required')

    def verify_frozen_metadata_locked(self,c,frozen):
        """Verify frozen report provenance/freshness without reading quotations."""
        historical=self.metadata_locked(c,revision_id=frozen['revision_id'])
        expected=sorted((dict(source_id=p['anchor']['source_id'],
                              annotation_revision_id=p['anchor']['annotation_revision_id'],
                              selection_key=p['anchor']['selection_key'],
                              anchor_sha256=p['anchor_sha256'])
                         for p in frozen['passages']),
                        key=lambda r:(r['source_id'],r['annotation_revision_id'],r['selection_key']))
        if (historical['revision']!=frozen['revision']
                or historical['attached_by']!=frozen['attached_by']
                or historical['attached_at']!=frozen['attached_at']
                or historical['references']!=expected):
            raise RuntimeError('Stored report manual provenance differs from its question revision')
        latest=self.metadata_locked(c)
        return (latest['revision_id']==frozen['revision_id']
                and historical['state']=='current_unreviewed')

    def context_locked(self,c,*,revision_id=None):
        rows=self.rows_locked(c)
        row=next((r for r in rows if r[0]==revision_id),None) if revision_id else (rows[-1] if rows else None)
        if revision_id and row is None:
            raise RuntimeError('Stored question passage revision unavailable')
        passages=self.resolve_locked(c,row[2] if row else [])
        result=dict(contract='oi.question-manual-passages/1',patient_id=c['patient_id'],case_id=c['case_id'],
                    question_id=c['question_id'],revision_id=row[0] if row else None,revision=row[1] if row else 0,
                    attached_by=row[3] if row else None,attached_at=row[4].isoformat() if row else None,
                    passages=passages,state='current_unreviewed' if all(p['selection_state']=='current_unreviewed_selection' for p in passages) else 'reassessment_required')
        result['context_sha256']=context_hash(result)
        return ManualContext(**result).model_dump(mode='json')

    def verify_frozen_locked(self,c,frozen):
        # Re-resolve historical references under current authority. Only mutable
        # freshness is ignored; immutable attribution and anchor bytes must match.
        actual=self.context_locked(c,revision_id=frozen['revision_id'])
        def identity(value):
            return {k:v for k,v in value.items() if k not in {'context_sha256','state','passages'}} | {
                'passages':[{'anchor':p['anchor'],'anchor_sha256':p['anchor_sha256']} for p in value['passages']]}
        if identity(actual)!=identity(frozen):
            raise RuntimeError('Stored report manual provenance differs from its source')

    def perform(self,patient_id,case_id,question_id,*,organization,actor,purpose,recheck_authority,prepare_response,payload=None):
        normalized=ReplaceQuestionPassages(**payload).model_dump(mode='json') if payload is not None else None
        c=dict(patient_id=patient_id,case_id=case_id,question_id=question_id,organization=organization,actor=actor,purpose=purpose)
        needs_original=False
        def require_original():
            nonlocal needs_original
            needs_original=True
            self.registry._allow(actor,patient_id,'source_original_read',purpose)
        c['require_original']=require_original
        def recheck():
            recheck_authority(needs_original)
        def prepare(index):
            if purpose!='operations' or self.registry._fetchone(
                'SELECT question_id FROM investigation.source_questions WHERE patient_id=%s AND case_id=%s AND origin_org=%s AND question_id=%s',
                (patient_id,case_id,organization,question_id)) is None:
                raise PatientRegistryDenied('Question context unavailable')
            current=self.context_locked(c)
            result=current|{'access_receipt_id':index['access_receipt_id']}
            if normalized is not None:
                require_original()
                intent=self.intent(c,normalized)
                previous=next((r for r in self.rows_locked(c) if r[5]==normalized['request_key']),None)
                if previous:
                    if previous[6]!=intent:
                        raise PatientRegistryConflict('Question passage request key reused with changed intent')
                    self.context_locked(c,revision_id=previous[0])
                    result=dict(revision_id=previous[0],question_id=question_id,duplicate=True)
                else:
                    if current['context_sha256']!=normalized['expected_context_sha256']:
                        raise PatientRegistryConflict('Question passage context changed; refresh before saving')
                    if current['revision']>=64:
                        raise PatientRegistryError('Question passage history exceeds its bounded limit')
                    passages=self.resolve_locked(c,normalized['references'])
                    if any(p['selection_state']!='current_unreviewed_selection' for p in passages):
                        raise PatientRegistryConflict('Selected manual passage requires reassessment')
                    revision_id='PASSAGES-'+uuid.uuid4().hex.upper()
                    self.registry._execute(
                        'INSERT INTO investigation.question_passage_revisions '
                        '(revision_id,revision,patient_id,case_id,origin_org,question_id,request_key,intent_sha256,references_json,command_json,actor,purpose) '
                        'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s)',
                        (revision_id,current['revision']+1,patient_id,case_id,organization,question_id,normalized['request_key'],intent,
                         canonical(normalized['references']),canonical(normalized),actor,purpose))
                    self.registry.append_event(patient_id,'investigation.question_passages_replaced',case_id=case_id,question_id=question_id,
                                               revision_id=revision_id,actor=actor,intent_sha256=intent)
                    result=dict(revision_id=revision_id,question_id=question_id,duplicate=False)
            response=prepare_response(result)
            recheck()
            self.registry.append_event(patient_id,'investigation.question_passages_access_prepared',case_id=case_id,question_id=question_id,
                actor=actor,receipt_id=index['access_receipt_id'],revision_id=result.get('revision_id'),context_sha256=current['context_sha256'],
                **reference_audit(c))
            return response
        with self.registry.transaction():
            response=PostgresSourceVersions(self.registry).list_locked(patient_id,case_id,organization=organization,actor=actor,purpose=purpose,
                recheck_authority=recheck,prepare_response=prepare)
            recheck()
            return response
