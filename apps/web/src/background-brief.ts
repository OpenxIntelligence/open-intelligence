import type {EvidencePacket, EvidenceAssessment, EvidenceVersion} from './authored-evidence.js';
import type {QuestionEvidenceLinks, QuestionEvidenceLink} from './question-evidence-view.js';
import {canonicalEvidenceJson} from './authored-evidence.js';
import {documentByteHash} from './reviewed-documents.js';
import {decodeSourceBrief, type SourceBrief} from './source-brief.js';
import type {SourceQuestion} from './source-questions-view.js';
import type {SourceWorldModel} from './source-world-model.js';

const states = ['queued', 'running', 'completed', 'blocked', 'stale', 'cancelled', 'failed'] as const;
export type RunState = typeof states[number];
export type RunAction = 'enqueue' | 'refresh' | 'cancel' | 'result' | 'retry' | 'verify';
export type RunStatus = Readonly<{
  run_id: string; state: RunState; revision: number; attempt_count: number; result_sha256: string | null;
}>;
export type RunResult = Readonly<{brief: SourceBrief; accessReceipt: string}>;
export type BackgroundBrief = Readonly<{
  questionId: string; busy: boolean; status: RunStatus | null; result: RunResult | null; message: string;
}>;

const statusFields = ['contract', 'synthetic', 'run_id', 'patient_id', 'case_id', 'question_id',
  'kind', 'state', 'revision', 'attempt_count', 'max_attempts', 'source_snapshot_contract',
  'source_snapshot_sha256', 'preflight_sha256', 'created_at', 'updated_at', 'available_at',
  'lease_expires_at', 'result_sha256', 'model_executed', 'clinical_approval'];
const digest = /^[0-9a-f]{64}$/;

function exact(value: unknown, fields: string[]): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value) &&
    Object.keys(value).length === fields.length && fields.every(key => Object.hasOwn(value, key));
}

function timestamp(value: unknown): boolean {
  return typeof value === 'string' && value.length <= 64 &&
    /^\d{4}-\d\d-\d\dT.+(?:Z|[+-]\d\d:\d\d)$/.test(value) && Number.isFinite(Date.parse(value));
}

export function canRetryRun(state: RunState): boolean {
  return state === 'cancelled' || state === 'failed' || state === 'blocked';
}

export function readRunStatus(value: unknown, question: SourceQuestion, previous?: RunStatus): RunStatus {
  if (!exact(value, statusFields) || value.contract !== 'oi.synthetic-composer-run/1' ||
      value.synthetic !== true || value.model_executed !== false || value.clinical_approval !== false ||
      value.kind !== 'source-question-brief/1' || value.patient_id !== question.patient_id ||
      value.case_id !== question.case_id || value.question_id !== question.question_id ||
      value.source_snapshot_contract !== 'oi.pg-source-world-model/1' ||
      value.source_snapshot_contract !== question.source_snapshot_contract ||
      value.source_snapshot_sha256 !== question.source_snapshot_sha256 ||
      value.preflight_sha256 !== question.preflight_sha256 || typeof value.run_id !== 'string' ||
      !/^RUN-[0-9A-F]{32}$/.test(value.run_id) || !states.some(state => state === value.state) ||
      !Number.isSafeInteger(value.revision) || Number(value.revision) < 1 || value.max_attempts !== 3 ||
      !Number.isSafeInteger(value.attempt_count) || Number(value.attempt_count) < 0 || Number(value.attempt_count) > 3 ||
      ![value.created_at, value.updated_at, value.available_at].every(timestamp) ||
      (value.state === 'running' ? !timestamp(value.lease_expires_at) : value.lease_expires_at !== null) ||
      (value.state === 'completed' ? typeof value.result_sha256 !== 'string' || !digest.test(value.result_sha256)
                                  : value.result_sha256 !== null)) throw Error('Invalid run status');

  const status = Object.freeze({run_id: value.run_id, state: value.state as RunState, revision: Number(value.revision),
    attempt_count: Number(value.attempt_count), result_sha256: value.result_sha256 as string | null});
  if ((['running', 'completed', 'failed'].includes(status.state) && status.attempt_count === 0) ||
      (status.state === 'queued' && status.attempt_count === 3)) throw Error('Invalid attempt');
  if (previous && (status.run_id !== previous.run_id || status.revision < previous.revision ||
      status.attempt_count < previous.attempt_count ||
      ((previous.revision === status.revision || !['queued', 'running'].includes(previous.state)) &&
       canonicalEvidenceJson(status) !== canonicalEvidenceJson(previous)))) throw Error('Run identity or history changed');
  return status;
}

export function readRunReceipt(value: unknown, httpStatus: number, question: SourceQuestion): RunStatus {
  if (![200, 201].includes(httpStatus) || !exact(value, ['run', 'duplicate']) ||
      value.duplicate !== (httpStatus === 200)) throw Error('Invalid enqueue receipt');
  return readRunStatus(value.run, question);
}

export async function readRunResult(value: unknown, previous: RunStatus, world: SourceWorldModel,
                                    question: SourceQuestion): Promise<RunResult> {
  if (!exact(value, ['contract', 'run', 'access_receipt_id', 'result_sha256', 'brief']) ||
      value.contract !== 'oi.synthetic-composer-run-result/1' || typeof value.access_receipt_id !== 'string' ||
      !/^ACCESS-[0-9A-F]{32}$/.test(value.access_receipt_id)) throw Error('Invalid result receipt');
  const status = readRunStatus(value.run, question, previous);
  if (status.state !== 'completed' || value.result_sha256 !== status.result_sha256) throw Error('Invalid result identity');
  const brief = await decodeSourceBrief(value.brief, world, question);
  const hash = await documentByteHash(new TextEncoder().encode(canonicalEvidenceJson(value.brief)));
  if (hash !== status.result_sha256) throw Error('Invalid stored result digest');
  return Object.freeze({brief, accessReceipt: value.access_receipt_id});
}

export type ReviewChoice = {id: string; label: string} & (
  {kind: 'exact_version_metadata_only'; link: QuestionEvidenceLink} |
  {kind: 'exact_authored_quote'; assessment: EvidenceAssessment; evidence: EvidenceVersion}
);

export function reviewChoices(q: SourceQuestion, links: QuestionEvidenceLinks | null,
                              packet: EvidencePacket | null): ReviewChoice[] {
  const choices: ReviewChoice[] = [];
  if (packet?.patient_id === q.patient_id && packet.case_id === q.case_id && packet.question.question_id === q.question_id &&
      packet.source_snapshot_sha256 === q.source_snapshot_sha256 && packet.question.preflight_sha256 === q.preflight_sha256) {
    for (const a of packet.assessments) {
      const e = packet.evidence.find(row => row.evidence_id === a.evidence_id);
      if (a.state === 'current_unreviewed' && a.quote && a.quote_start !== null && a.question_id === q.question_id &&
          a.source_snapshot_sha256 === q.source_snapshot_sha256 && a.preflight_sha256 === q.preflight_sha256 &&
          e?.state === 'current' && e.sha256 === a.evidence_sha256 && e.rights_sha256 === a.rights_sha256)
        choices.push({kind: 'exact_authored_quote', id: a.assessment_id, assessment: a, evidence: e,
          label: 'Passage · ' + (e.title ?? e.evidence_id) + ' v' + e.version + ' · “' + a.quote + '”'});
    }
  }
  if (links?.patient_id === q.patient_id && links.case_id === q.case_id && links.question_id === q.question_id &&
      links.source_context_state === 'current_unreviewed_question')
    for (const link of links.links) if (link.status === 'available' && link.record)
      choices.push({kind: 'exact_version_metadata_only', id: link.link_id, link,
        label: 'Citation only · ' + link.citation + ' · ' + link.record.title});
  return choices;
}

export async function verificationIntent(choice: ReviewChoice, run: RunStatus) {
  const common = {synthetic: true, verification: choice.kind, expected_result_sha256: run.result_sha256};
  if (choice.kind === 'exact_authored_quote') {
    const quote = choice.assessment.quote;
    if (!quote) throw Error('Quote unavailable');
    return {...common, assessment_id: choice.assessment.assessment_id, expected_evidence_sha256: choice.evidence.sha256,
      expected_quote_sha256: await documentByteHash(new TextEncoder().encode(quote))};
  }
  return {...common, link_id: choice.link.link_id, citation: choice.link.citation, expected_metadata_sha256: choice.link.metadata_sha256};
}

export function readVerificationReturn(value: unknown, httpStatus: number, run: RunStatus,
                                       question: SourceQuestion, choice: ReviewChoice, quoteHash?: string): string {
  const fields = choice.kind === 'exact_authored_quote' ? ['assessment_id', 'evidence_id', 'evidence_version', 'evidence_sha256',
    'rights_sha256', 'statement_line', 'quote_start', 'quote_length', 'quote_sha256'] : ['link_id', 'citation', 'metadata_sha256'];
  if (!exact(value, ['contract', 'receipt_id', 'question_id', 'run_id', 'result_sha256', 'duplicate',
      'verification', 'review_state', 'clinical_approval', 'model_executed', ...fields]) ||
      value.contract !== 'oi.synthetic-run-evidence-review-return/1' || value.verification !== choice.kind ||
      ![200, 201].includes(httpStatus) || value.duplicate !== (httpStatus === 200) ||
      value.question_id !== question.question_id || run.state !== 'completed' || value.run_id !== run.run_id ||
      !run.result_sha256 || value.result_sha256 !== run.result_sha256 ||
      value.review_state !== 'returned_for_independent_verification' ||
      value.clinical_approval !== false || value.model_executed !== false ||
      typeof value.receipt_id !== 'string' || !/^REVIEW-[0-9A-F]{32}$/.test(value.receipt_id))
    throw Error('Invalid verification return receipt');
  if (choice.kind === 'exact_authored_quote') {
    const a = choice.assessment, e = choice.evidence;
    if (!a.quote || !quoteHash || value.assessment_id !== a.assessment_id || value.evidence_id !== e.evidence_id ||
        value.evidence_version !== e.version || value.evidence_sha256 !== e.sha256 || value.rights_sha256 !== e.rights_sha256 ||
        value.statement_line !== e.statement_line || value.quote_start !== a.quote_start ||
        value.quote_length !== Array.from(a.quote).length || value.quote_sha256 !== quoteHash) throw Error('Invalid quote receipt');
  } else if (value.link_id !== choice.link.link_id || value.citation !== choice.link.citation ||
             value.metadata_sha256 !== choice.link.metadata_sha256) throw Error('Invalid metadata receipt');
  return value.receipt_id;
}
