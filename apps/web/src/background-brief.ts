import {canonicalEvidenceJson} from './authored-evidence.js';
import {documentByteHash} from './reviewed-documents.js';
import {decodeSourceBrief, type SourceBrief} from './source-brief.js';
import type {SourceQuestion} from './source-questions-view.js';
import type {SourceWorldModel} from './source-world-model.js';

const states = ['queued', 'running', 'completed', 'blocked', 'stale', 'cancelled', 'failed'] as const;
export type RunState = typeof states[number];
export type RunAction = 'latest' | 'enqueue' | 'refresh' | 'cancel' | 'result' | 'retry';
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
