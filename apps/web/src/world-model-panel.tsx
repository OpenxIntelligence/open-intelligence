import {useState} from 'react';
import type {RegistrySession,ViewState} from './registry-client';
import {DEFAULT_SOURCE_QUESTION} from './composer-preflight-view';

/** Source-provenanced inspection; no model inference, question write or approval. */
export function WorldModelPanel({state,session}:{state:ViewState;session:RegistrySession}){
 const [caseId,setCaseId]=useState(()=>
   state.records?.find(r=>r.source_reference)?.source_reference?.case_id||'');
 const model=state.worldModel;
 return <section className="panel world-panel" aria-labelledby="world-heading">
  <span className="step">PATIENT WORLD MODEL / SOURCE-REPORTED OBSERVATIONS</span>
  <h2 id="world-heading">Inspect current original-source findings</h2>
  <p>This is the existing first-party World Model's read-only source projection
    over the canonical PostgreSQL source ledger. Findings are reported statements,
    <strong> not clinical facts, diagnoses, or treatment recommendations.</strong></p>
  {!state.patient?<p role="status">Open an explicitly authorized patient on Overview first.</p>:<>
   <form className="world-case-form" onSubmit={event=>{
     event.preventDefault();void session.loadWorldModel(caseId);
   }}>
    <label htmlFor="world-case-id">Source case identifier</label>
    <div className="world-case-controls">
     <input id="world-case-id" data-testid="world-case-id" value={caseId}
       onChange={e=>setCaseId(e.target.value)} autoComplete="off"
       spellCheck={false} maxLength={40} pattern="CASE-[A-Z0-9-]{1,35}"
       placeholder="CASE-ALPHA" required/>
     <button type="submit" className="primary" data-testid="world-refresh"
       disabled={state.worldPhase==='loading'}>
       {state.worldPhase==='loading'?'Verifying sources…':'Inspect authorized sources'}
     </button>
    </div>
   </form>
   <p className={'status '+(state.worldPhase==='error'?'error':'')}
      data-testid="world-status" role="status" aria-live="polite">{state.worldMessage}</p>
   <p className={'status '+(state.composerPhase==='error'?'error':'')}
      data-testid="composer-status" role="status" aria-live="polite">{state.composerMessage}</p>
   {state.composerPreview&&<section className="composer-preview" data-testid="composer-context"
       aria-labelledby="composer-context-heading">
     <span className="step">SOURCE-PINNED COMPOSER PREFLIGHT · NO EXECUTION</span>
     <h3 id="composer-context-heading">Prepared source context</h3>
     <p><strong>Standard source question (not submitted):</strong>
       {state.composerPreview.question}</p>
     <blockquote>{state.composerPreview.selected_source.statement}</blockquote>
     <p><strong>Exact original:</strong>
       <code>{state.composerPreview.selected_source.source_id}</code>,
       line {state.composerPreview.selected_source.line},
       version {state.composerPreview.selected_source.version}.</p>
     <p><strong>Snapshot fingerprint:</strong>
       <code>{state.composerPreview.source_snapshot_sha256}</code></p>
     <p><strong>Preflight receipt hash (not a credential):</strong>
       <code>{state.composerPreview.preflight_sha256}</code></p>
     <p role="note"><strong>Not a clinical review.</strong> This preview alone does not
       save a question, execute a model, establish biomedical source rights or
       authorize a clinician. Saving below creates only a source-linked
       question-intake record with independent source revalidation.</p>
     <button type="button" className="primary" data-testid="save-source-question"
       disabled={state.questionSavePhase==='saving'}
       onClick={()=>void session.savePreparedQuestion()}>
       {state.questionSavePhase==='saving'?'Saving authorized question…':
        'Save source-linked question (no clinical approval)'}
     </button>
     <p className={'status '+(state.questionSavePhase==='error'?'error':'')}
       data-testid="question-save-status" role="status" aria-live="polite">
       {state.questionSaveMessage}</p>
     {state.savedQuestion&&<p className="question-receipt" data-testid="saved-source-question">
       <strong>{state.savedQuestion.duplicate?'Existing question recovered':'Question saved'}:</strong>
       <code>{state.savedQuestion.question_id}</code>. This does not submit
       or approve a clinician review.</p>}
   </section>}
   <section className="question-history" aria-labelledby="question-history-heading">
    <div className="question-history-heading">
      <div><h3 id="question-history-heading">Saved source-linked questions</h3>
       <p>Durable question intake only. No clinical reviewer has received or approved these items.</p></div>
      <button type="button" data-testid="load-source-questions" disabled={state.questionListPhase==='loading'}
        onClick={()=>void session.loadSavedQuestions(caseId)}>
        {state.questionListPhase==='loading'?'Checking question history…':'Refresh question history'}
      </button>
    </div>
    <p data-testid="questions-status" role="status" aria-live="polite"
      className={'status '+(state.questionListPhase==='error'?'error':'')}>
      {state.questionListMessage}</p>
    {state.questions&&<div data-testid="source-question-history">
      {state.questions.length===0?<p>No saved source-linked questions are visible.</p>:
       <ul className="question-items">
        {state.questions.map(item=><li key={item.question_id}>
          <div className="question-status-title">
           <strong>{item.question}</strong>
           <span className={'question-status '+(item.source_context_state==='source_reassessment_required'?'reassessment':'')}>
           {item.source_context_state==='source_reassessment_required'?
             'Source changed — reassessment required':'Current source context — unreviewed'}
           </span>
          </div>
          <p><strong>Original anchor:</strong> <code>{item.source_id}</code> · v{item.source_version}, line {item.source_line}.</p>
          <p><strong>Saved question:</strong> <code>{item.question_id}</code></p>
          <p className="muted">Human review not submitted. Clinical approval: none.</p>
         </li>)}</ul>}
    </div>}
   </section>
   {model&&<div data-testid="world-model-result">
    <div className="world-summary" aria-label="Source-only summary">
     <div><strong>{model.summary.current_sources}</strong><span>Current source versions</span></div>
     <div><strong>{model.summary.current_observations}</strong><span>Source statements</span></div>
     <div><strong>{model.summary.unresolved_observations}</strong><span>Unresolved statements</span></div>
     <div><strong>{model.summary.source_disagreements}</strong><span>Source disagreements</span></div>
    </div>
    <p className="world-fingerprint"><strong>Exact source snapshot:</strong>
     <code>{model.source_snapshot_sha256}</code></p>
    <p className="muted">Snapshot describes the source set at the last authorized read.
    Refresh before using any statement after an amendment. Clinical review is not connected.</p>
    <h3>Current source-reported observations</h3>
    {model.observations.length===0?<p>No current source-reported findings are available.</p>:
     <ul className="world-observations">{model.observations.map(o=>
      <li key={o.assertion_id} className="world-observation">
       <p className="step">{o.source_kind.toUpperCase()} · {o.reported_state.toUpperCase()} · ORIGINAL LINE {o.source_line}</p>
       <blockquote>{o.source_statement}</blockquote>
       <dl>
        <div><dt>Finding key</dt><dd>{o.finding_key}</dd></div>
        <div><dt>Source and version</dt><dd><code>{o.source_version_id}</code> · {o.document_id}@{o.document_version}</dd></div>
        <div><dt>Specimen / event</dt><dd>{o.specimen_id||'Not specified'} · {o.event_date}</dd></div>
        <div><dt>Original SHA-256</dt><dd><code>{o.source_sha256}</code></dd></div>
       </dl>
       <p className="muted">Review not established. No clinical meaning inferred.</p>
       <button type="button" data-testid="composer-preflight" disabled={state.composerPhase==='loading'}
         onClick={()=>void session.prepareSourceContext(
           o.source_version_id,o.source_line,DEFAULT_SOURCE_QUESTION)}>
         Prepare source-only Composer context
       </button>
      </li>)}</ul>}
    {model.conflicts.length>0&&<section aria-labelledby="world-conflicts">
     <h3 id="world-conflicts">Unresolved source disagreements</h3>
     <p>These are contradictory source-reported labels for the same explicit
      specimen, date, and finding key; not an adjudicated medical conclusion.</p>
     <ul>{model.conflicts.map(c=><li key={c.specimen_id+':'+c.event_date+':'+c.finding_key}>
      <strong>{c.finding_key}</strong> · {c.specimen_id} · {c.event_date}.
      Source labels: {c.reported_states.join(' / ')}. References: {c.observation_refs.map(r=>
       r.source_version_id+' line '+r.source_line).join('; ')}.
     </li>)}</ul>
    </section>}
    {model.history.length>0&&<section aria-labelledby="world-history">
     <h3 id="world-history">Superseded source versions</h3>
     <ul>{model.history.map(s=><li key={s.source_version_id}>
      {s.document_id}@{s.version} · <code>{s.source_version_id}</code>.
      Historical original retained; no longer used as a current observation.
     </li>)}</ul>
    </section>}
    <p className="world-boundary" role="note"><strong>Workflow boundary:</strong>
      No investigation question, biomedical evidence appraisal, AI answer or clinician review
      has been generated or approved by this view.</p>
   </div>}
  </>}
 </section>;
}
