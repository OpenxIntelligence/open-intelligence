import {useState} from 'react';
import type {RegistrySession,ViewState} from './registry-client';

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
