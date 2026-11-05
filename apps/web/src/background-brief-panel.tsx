import {canRetryRun, reviewChoices} from './background-brief';
import type {RunAction, RunState} from './background-brief';
import type {RegistrySession, ViewState} from './registry-client';
import {canPrepareSourceBrief} from './source-brief';
import type {SourceQuestion} from './source-questions-view';

const labels: Record<RunState, string> = {
  queued: 'Queued for the worker', running: 'Worker is preparing the brief', completed: 'Brief ready',
  blocked: 'Worker access unavailable', stale: 'Source changed', cancelled: 'Cancelled', failed: 'Run failed',
};

export function BackgroundBriefPanel({question, state, session, busy}: {
  question: SourceQuestion; state: ViewState; session: RegistrySession; busy: boolean;
}) {
  const view = state.backgroundBrief?.questionId === question.question_id ? state.backgroundBrief : null;
  const status = view?.status;
  const current = canPrepareSourceBrief(question, state.worldModel);
  const locked = busy || Boolean(view?.busy);
  const act = (action: RunAction) => void session.backgroundBriefAction(question.question_id, action);
  const choices = reviewChoices(question,
    state.evidenceFamily === 'text' && state.evidenceLinksPhase === 'ready' ? state.evidenceLinks : null,
    state.evidencePhase === 'ready' ? state.evidencePacket : null);
  if (!view && !current) return null;
  return <div className="background-brief">
    {!status && <button type="button" data-testid="run-open" disabled={locked || !current}
      onClick={() => act('enqueue')}>Queue or reopen background brief</button>}
    {status && <>
      <p role="status" data-testid="run-status" data-run-id={status.run_id} data-state={status.state}>
        <strong>{labels[status.state]}</strong>{status.attempt_count > 0 && ' · Attempt ' + status.attempt_count + ' of 3'}
      </p>
      <div className="actions">
        {(status.state === 'queued' || status.state === 'running') && <>
          <button type="button" data-testid="run-refresh" disabled={locked} onClick={() => act('refresh')}>Check status</button>
          <button type="button" data-testid="run-cancel" disabled={locked} onClick={() => act('cancel')}>Cancel run</button>
        </>}
        {status.state === 'completed' && <button type="button" data-testid="run-result" disabled={locked || !current}
          onClick={() => act('result')}>{view?.result ? 'Recheck and reopen result' : 'Open completed brief'}</button>}
        {canRetryRun(status.state) && <button type="button" data-testid="run-retry" disabled={locked || !current}
          onClick={() => act('retry')}>Queue or reopen a replacement</button>}
      </div>
    </>}
    {view?.message && <p role="status">{view.message}</p>}
    {view?.result && <section className="source-brief-preview" aria-label="Completed background brief">
      <pre data-testid="run-result-body">{view.result.brief.body}</pre>
      <details><summary>Run and access receipts</summary>
        <p>Run <code>{status?.run_id}</code></p>
        <p>Stored result SHA-256 <code>{status?.result_sha256}</code></p>
        <p>Current access receipt <code>{view.result.accessReceipt}</code></p>
      </details>
      <fieldset disabled={locked || !current}>
        <legend>Return this question for independent verification</legend>
        <p>Choose a passage to verify its original wording and version, or a citation to check its metadata.
          A reviewer still needs to decide whether it supports the question.</p>
        <div className="actions">
          <button type="button" disabled={state.evidencePhase === 'loading'}
            onClick={() => void session.loadQuestionEvidence(question.question_id)}>Check saved passages</button>
          <button type="button" disabled={state.evidenceLinksPhase === 'loading'}
            onClick={() => void session.loadQuestionEvidenceLinks(question.question_id)}>Check saved citations</button>
        </div>
        {choices.length ? <form onSubmit={event => {
          event.preventDefault();
          const id = new FormData(event.currentTarget).get('evidence');
          if (typeof id === 'string') void session.backgroundBriefAction(question.question_id, 'verify', id);
        }}>
          <label>Evidence for verification <select name="evidence" required defaultValue="">
            <option value="" disabled>Choose a passage or citation</option>
            {choices.map(choice => <option key={choice.id} value={choice.id}>{choice.label}</option>)}
          </select></label>
          <button type="submit" data-testid="run-verification-return">Return to review inbox</button>
        </form> : <p>{state.evidencePhase === 'ready' || state.evidenceLinksPhase === 'ready' ?
          'No current selection was found. Save a permitted passage assessment or link a citation to this question.' :
          'Check saved passages or citations to see the choices available for this question.'}</p>}
      </fieldset>
    </section>}
  </div>;
}
