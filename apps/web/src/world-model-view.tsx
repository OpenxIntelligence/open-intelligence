import type {RegistrySession,ViewState} from './registry-client';
import {SourceQuestionPanel} from './source-question-panel';

type Props={
  session:RegistrySession;
  state:ViewState;
  onOverview:()=>void;
  busy:boolean;
  showQuestions?:boolean;
  onInvestigations?:()=>void;
  onReview?:()=>void;
};

/** First-party PG read-only Patient World Model view.
 * No generated diagnosis, triage, alerts, actions, clinician approval or
 * separate client-owned patient/source ledger. All clinical claims remain
 * attributed to the original fictional source and explicitly unreviewed.
 */
export function WorldModelView({session,state,onOverview,busy,showQuestions=false,onInvestigations,onReview}:Props){
  const loading=state.worldPhase==='loading'||state.recordsPhase.startsWith('loading');
  const model=state.worldModel;
  return <section className="panel source-world" aria-labelledby="world-heading" data-testid="world-workspace" data-view={showQuestions?'investigations':'journey'}>
    <span className="step">SOURCE-LINKED PATIENT CONTEXT / SYNTHETIC ONLY</span>
    <h2 id="world-heading">{showQuestions?'Source-linked investigations':'Patient World Model — source-only view'}</h2>
    <p>This is a fresh read of the existing PostgreSQL original-source owner. It organizes reported observations, chronology, unresolved statements and source disagreements. It does not interpret cancer, authorize AI research, or replace clinician review.</p>
    {!state.patient?<div data-testid="world-no-patient">
      <p>Open an authorized fictional patient before inspecting the source-derived view.</p>
      <button onClick={onOverview}>Go to patient overview</button>
    </div>:<>
      <p className="record-scope" data-testid="world-patient"><strong>Patient:</strong> <code>{state.patient.patient_id}</code></p>
      <button className="primary" data-testid="world-load-cases" disabled={loading||busy} onClick={()=>void session.loadCases()}>Check authorized cases</button>
      {state.cases!==null&&<section aria-label="Authorized case choices">
        <h3>Source case</h3>
        {state.cases.length===0?<p>No fictional case is currently mapped to this identity.</p>:
         <ul className="world-cases">{state.cases.map(item=><li key={item.case_id}>
          <code>{item.case_id}</code> · {item.status}{' '}
          <button data-testid="world-load" disabled={item.status!=='active'||loading||busy} onClick={()=>void session.loadWorldModel(item.case_id)}>Inspect World Model</button>
         </li>)}</ul>}
      </section>}
      <p role="status" aria-live="polite" className={'status '+(state.worldPhase==='error'?'error':'')} data-testid="world-status">{state.worldMessage}</p>
      {showQuestions&&<SourceQuestionPanel session={session} state={state} busy={busy} onReview={onReview}/>}
      {model&&<div data-testid="world-projection">
        <p><strong>Case:</strong> <code>{model.case_id}</code> · Source statements unreviewed · Context checked at last read</p>
        <div className="world-summary" aria-label="Source context summary">
          <div><strong data-testid="world-current">{model.summary.current_sources}</strong><span>Current sources</span></div>
          <div><strong data-testid="world-history-count">{model.summary.historical_sources}</strong><span>Historical versions</span></div>
          <div><strong data-testid="world-observation-count">{model.summary.current_observations}</strong><span>Source statements</span></div>
          <div><strong data-testid="world-unresolved-count">{model.summary.unresolved_observations}</strong><span>Unresolved statements</span></div>
          <div><strong data-testid="world-conflict-count">{model.summary.source_disagreements}</strong><span>Source disagreements</span></div>
        </div>
        <h3>Source chronology</h3>
        {model.current_sources.length===0?<p>No current fictional original was imported.</p>:
        <ol className="world-timeline">{model.current_sources.map(item=><li key={item.source_id} data-testid="world-source">
          <strong>{item.event_date} · {item.document_id} v{item.version}</strong>
          <p>{item.kind} · specimen {item.specimen_id??'not recorded'} · issued {item.issued_at}</p>
          <details><summary>Exact source receipt</summary><p><code>{item.source_id}</code></p><p>SHA-256 <code>{item.sha256}</code></p></details>
        </li>)}</ol>}
        <h3>Original source-reported observations</h3>
        <p>These are literal reported statements, not established clinical facts. A missing or pending item must never be interpreted as a negative finding.</p>
        {model.observations.length===0?<p>No source-reported observations are available.</p>:
        <ul className="world-observations">{model.observations.map(item=><li key={item.source_id+':'+item.source_line} data-testid="world-observation">
          <p><strong>{item.finding_key}</strong> · <span data-testid="world-reported-state">{item.reported_state}</span> · {item.event_date}</p>
          <blockquote data-testid="world-statement">{item.source_statement}</blockquote>
          <small>Not clinically established · <code>{item.source_id}</code> · line {item.source_line}</small>
          <div className="source-context-action"><button type="button" data-testid="composer-preflight"
            disabled={loading||busy||state.composerPhase==='loading'||state.questionSaveMessage.startsWith('Save outcome unknown.')}
            onClick={()=>{session.chooseQuestionDraft(item.source_id,item.source_line);void session.prepareDraftQuestion();onInvestigations?.();}}>
            Prepare source-only question context
          </button>{' '}
          <button type="button" data-testid="choose-question-draft"
            disabled={loading||busy||state.questionSavePhase==='saving'||state.questionSaveMessage.startsWith('Save outcome unknown.')}
            onClick={()=>{session.chooseQuestionDraft(item.source_id,item.source_line);onInvestigations?.();}}>
            Write a source-linked question
          </button></div>
        </li>)}</ul>}
        {model.conflicts.length>0&&<section aria-labelledby="source-disagreements">
          <h3 id="source-disagreements">Unresolved source disagreements</h3>
          <p>Conflicting source-reported states for the same documented specimen, date and finding; no clinical adjudication is performed.</p>
          <ul>{model.conflicts.map(item=><li key={item.specimen_id+':'+item.event_date+':'+item.finding_key} data-testid="world-conflict">
            <strong>{item.finding_key}</strong> · specimen {item.specimen_id} · {item.event_date} · reported states {item.reported_states.join(' / ')}
            <p>{item.source_refs.map(ref=><code key={ref.source_id+':'+ref.source_line}>{ref.source_id} line {ref.source_line}; </code>)}</p>
          </li>)}</ul>
        </section>}
        {model.history.length>0&&<details className="world-history"><summary>Superseded original history ({model.history.length})</summary>
          <ul>{model.history.map(item=><li key={item.source_id}><code>{item.source_id}</code> · {item.document_id} v{item.version} · SHA-256 <code>{item.sha256}</code></li>)}</ul>
        </details>}
        <details><summary>Context fingerprint and limitations</summary>
          <p>SHA-256 context fingerprint: <code data-testid="world-fingerprint">{model.snapshot_fingerprint}</code>. This is not an approval, signature or execution credential. It must be rechecked against the server before any future investigation.</p>
          <ul>{model.limitations.map(item=><li key={item}>{item}</li>)}</ul>
        </details>
        <p data-testid="world-no-approval" className="muted">Clinical interpretation: not generated. Composer execution: unavailable. Evidence rights and professional review: not integrated into this H1 view.</p>
      </div>}
    </>}
  </section>;
}
