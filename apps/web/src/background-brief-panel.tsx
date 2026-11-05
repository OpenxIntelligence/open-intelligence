import {useState} from 'react';
import {openedReviewArtifacts, validReturnReason} from './review-queue-view';
import {canRetryRun} from './background-brief';
import type {RunAction, RunState} from './background-brief';
import type {RegistrySession, ViewState} from './registry-client';
import {canPrepareSourceBrief} from './source-brief';
import type {SourceQuestion} from './source-questions-view';

const labels: Record<RunState, string> = {
  queued: 'Queued for the worker', running: 'Worker is preparing the brief', completed: 'Brief ready',
  blocked: 'Worker access unavailable', stale: 'Source changed — reassessment required', cancelled: 'Cancelled', failed: 'Run failed',
};

function EvidenceReturn({question,state,session,busy}:{
  question:SourceQuestion;state:ViewState;session:RegistrySession;busy:boolean;
}) {
  const [reason,setReason]=useState('');
  const run=state.backgroundBrief;
  const report=state.evidenceReport;
  if(!run?.result||run.questionId!==question.question_id||!report||report.question_id!==question.question_id||
     report.case_id!==question.case_id||report.patient_id!==question.patient_id||report.state!=='current_unreviewed')return null;
  const item=state.reviewQueue?.items.find(row=>row.question_id===question.question_id);
  const artifacts=item&&openedReviewArtifacts(item,run,report);
  const locked=busy||state.reviewReturnPhase==='saving'||state.reviewReturnPhase==='unknown';
  return <div>
    {artifacts&&item?.queue_fingerprint?<>
      <label htmlFor={'brief-return-'+question.question_id}>What should be independently verified?</label>
      <textarea data-testid="brief-return-reason" id={'brief-return-'+question.question_id} value={reason} maxLength={600}
        disabled={locked} onChange={e=>setReason(e.target.value)}/>
      <button type="button" data-testid="return-brief-and-report" disabled={locked||!validReturnReason(reason)}
        onClick={()=>void session.returnReviewQuestion(question.question_id,item.queue_fingerprint!,reason,true)}>
        Return brief and comparison report for verification
      </button>
    </>:<button type="button" data-testid="check-brief-report-inbox" disabled={locked||state.reviewPhase==='loading'}
      onClick={()=>void session.loadReviewQueue(question.case_id)}>Check verification inbox for this brief and report</button>}
    {state.reviewReturnIntent?.question_id===question.question_id&&state.reviewReturnIntent.artifacts&&
      <p role="status">{state.reviewReturnMessage}</p>}
    {state.reviewPhase==='error'&&<p role="status">{state.reviewMessage}</p>}
  </div>;
}

export function BackgroundBriefPanel({question, state, session, busy}: {
  question: SourceQuestion; state: ViewState; session: RegistrySession; busy: boolean;
}) {
  const view = state.backgroundBrief?.questionId === question.question_id ? state.backgroundBrief : null;
  const status = view?.status;
  const current = canPrepareSourceBrief(question, state.worldModel);
  const locked = busy || Boolean(view?.busy);
  const act = (action: RunAction) => void session.backgroundBriefAction(question.question_id, action);
  const historical = question.source_context_state === 'source_reassessment_required' &&
    question.source_snapshot_contract === 'oi.pg-source-world-model/1';
  if (!view && !current && !historical) return null;
  return <div className="background-brief">
    {!status && (historical || current) && <button type="button" data-testid="run-latest" disabled={locked}
      onClick={() => act('latest')}>Check latest background run</button>}
    {!status && current && <button type="button" data-testid="run-open" disabled={locked}
      onClick={() => act('enqueue')}>Queue background brief</button>}
    {status && <>
      <p role="status" data-testid="run-status" data-run-id={status.run_id} data-state={status.state}>
        <strong>{historical && status.state === 'completed' ? 'Completed before source reassessment' : labels[status.state]}</strong>{status.attempt_count > 0 && ' · Attempt ' + status.attempt_count + ' of 3'}
      </p>
      <div className="actions">
        {(status.state === 'queued' || status.state === 'running') && <>
          <button type="button" data-testid="run-refresh" disabled={locked} onClick={() => act('refresh')}>Check status</button>
          {current && <button type="button" data-testid="run-cancel" disabled={locked} onClick={() => act('cancel')}>Cancel run</button>}
        </>}
        {current && status.state === 'completed' && <button type="button" data-testid="run-result" disabled={locked}
          onClick={() => act('result')}>{view?.result ? 'Recheck and reopen result' : 'Open completed brief'}</button>}
        {current && canRetryRun(status.state) && <button type="button" data-testid="run-retry" disabled={locked}
          onClick={() => act('retry')}>Queue or reopen a replacement</button>}
      </div>
    </>}
    {view?.message && <p role="status">{view.message}</p>}
    {current && view?.result && <section className="source-brief-preview" aria-label="Completed background brief">
      <pre data-testid="run-result-body">{view.result.brief.body}</pre>
      <details><summary>Run and access receipts</summary>
        <p>Run <code>{status?.run_id}</code></p>
        <p>Stored result SHA-256 <code>{status?.result_sha256}</code></p>
        <p>Current access receipt <code>{view.result.accessReceipt}</code></p>
      </details>
      {state.evidenceReport&&<EvidenceReturn key={question.patient_id+question.question_id+state.evidenceReport.report_id}
        question={question} state={state} session={session} busy={busy}/>}
    </section>}
  </div>;
}
