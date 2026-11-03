import {useState} from 'react';
import type {RegistrySession,ViewState} from './registry-client.js';
import type {SourceQuestion} from './source-questions-view.js';
import type {QuestionEvidenceRecord} from './question-evidence-view.js';
import {safeFictionalEvidenceLink,safeDoiEvidenceLink,validEvidenceQuery,normalizePublicDoi} from './question-evidence-view.js';
import {canPrepareSourceBrief} from './source-brief.js';

function CitationMetadata({record}:{record:QuestionEvidenceRecord}){
 const bibliography=record.source_kind==='crossref'?record.bibliography:null;
 return <div className="evidence-metadata">
  <dl>
   <div><dt>Exact citation</dt><dd><code>{record.citation}</code></dd></div>
   <div><dt>Catalog ID</dt><dd><code>{record.id}</code></dd></div>
   <div><dt>{bibliography?'Catalog snapshot':'Version'}</dt><dd><code>{record.version}</code></dd></div>
   <div><dt>{bibliography?'Metadata rights basis':'License'}</dt><dd>{record.licence}</dd></div>
   <div><dt>Available content</dt><dd>{bibliography?'Bibliographic metadata only · Crossref':'Metadata only · fictional fixture'}</dd></div>
   <div><dt>Metadata rights</dt><dd>{bibliography?'Current metadata storage and display check passed':'Granted for this fixture'}</dd></div>
  </dl>
  {bibliography?<div data-testid="evidence-bibliography">
   <p><strong>{bibliography.acquisition_mode==='protocol_fixture'?'Offline protocol fixture — no live provider request.':
     'Public metadata obtained through a Crossref provider lookup.'}</strong></p>
   <dl>
    <div><dt>Publication year</dt><dd>{bibliography.year??'Not supplied'}</dd></div>
    <div><dt>Journal</dt><dd>{bibliography.journal??'Not supplied'}</dd></div>
    <div><dt>Publication type</dt><dd>{bibliography.publication_type??'Not supplied'}</dd></div>
    <div><dt>Authors</dt><dd>{bibliography.authors.length?bibliography.authors.join('; '):'Not supplied'}</dd></div>
   </dl>
   <p data-testid="evidence-retrieved-at"><strong>First retrieved for this snapshot:</strong>{' '}
    <time dateTime={bibliography.retrieved_at}>{bibliography.retrieved_at}</time>.</p>
   <p className="muted">The catalog snapshot identifies selected metadata. It is not a publisher article edition, an article-content license or a clinical assessment.</p>
   {safeDoiEvidenceLink(record.link,record.id)?<p><a href={record.link} target="_blank" rel="noopener noreferrer"
     data-testid="evidence-doi-link">Open DOI reference: {bibliography.doi}</a></p>:<p>DOI link unavailable.</p>}
   <details><summary>Bibliography provenance</summary>
    <p>Adapter <code>{bibliography.adapter_version}</code> · metadata projection SHA-256 <code>{bibliography.projection_sha256}</code>.</p>
    <p>Provider record: <code>{bibliography.record_url}</code></p>
    <p><a href="https://www.crossref.org/documentation/retrieve-metadata/" target="_blank" rel="noopener noreferrer">Crossref metadata policy</a>{' · '}
     <a href="https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/" target="_blank" rel="noopener noreferrer">Crossref access policy</a></p>
   </details>
  </div>:safeFictionalEvidenceLink(record.link)?<p><a href={record.link} target="_blank" rel="noopener noreferrer"
    data-testid="evidence-fixture-link">{record.link}</a><br/>
    <span className="muted">Fictional fixture address on example.invalid; this is not a publisher or clinical source.</span></p>:
   <p>Fixture link unavailable.</p>}
  <p><strong>Metadata SHA-256:</strong> <code>{record.metadata_sha256}</code></p>
 </div>;
}

/** Scoped write progress survives temporary loss of the question projection.
 * The opaque recovery intent remains in the existing session, never local storage.
 */
export function QuestionEvidenceRecovery({state,session,busy,showReadError=true}:{state:ViewState;session:RegistrySession;busy:boolean;showReadError?:boolean}){
 const intent=state.evidenceLinkIntent;
 const questionId=intent?.question_id??state.evidenceQuestionId;
 const uncertain=state.evidenceLinkPhase==='unknown';
 if(!state.patient||!questionId||state.evidenceLinkPhase==='idle'||
  (intent&&intent.patient_id!==state.patient.patient_id)||(uncertain&&!intent))return null;
 return <section className="evidence-recovery" data-testid={uncertain?'evidence-recovery':'evidence-operation'}
  aria-label={uncertain?'Uncertain citation save recovery':'Citation save status'}>
  <h4>{uncertain?'Recover the earlier citation save':'Citation save status'}</h4>
  <p>{uncertain?<>The outcome is uncertain for <code>{intent!.body.citation}</code> on question </>:'Saved-question reference: '}
   <code>{questionId}</code>.</p>
  <p role="status" aria-live="polite" data-testid="evidence-link-status"
   className={'status '+(state.evidenceLinkPhase==='error'?'error':'')}>{state.evidenceLinkMessage}</p>
  {uncertain&&<><div className="actions">
   <button type="button" data-testid="evidence-retry" disabled={busy}
    onClick={()=>void session.retryQuestionEvidenceLink()}>Retry exact citation save</button>
   <button type="button" data-testid="evidence-abandon" disabled={busy}
    onClick={()=>session.abandonQuestionEvidenceLink()}>Abandon recovery for this uncertain save</button>
  </div>
  <p role="note">Abandoning recovery does not cancel or undo a save that may already have committed. Refresh saved citations before starting another link.</p></>}
  {state.evidenceLinkReceipt&&<p className="question-receipt" data-testid="evidence-link-receipt">
   <strong>{state.evidenceLinkReceipt.duplicate?'Original link receipt recovered':'Citation link recorded'}:</strong>{' '}
   <code>{state.evidenceLinkReceipt.citation}</code> · <code>{state.evidenceLinkReceipt.link_id}</code>.
  </p>}
  {showReadError&&state.evidenceLinksPhase==='error'&&<p role="status" data-testid="evidence-links-status"
   className="status error">{state.evidenceLinksMessage}</p>}
 </section>;
}

/** Progressive inspection within the existing saved-question workspace. */
export function QuestionEvidencePanel({question,state,session,busy}:{question:SourceQuestion;state:ViewState;session:RegistrySession;busy:boolean}){
 const [query,setQuery]=useState('');
 const [doi,setDoi]=useState(''),[publicDoiAcknowledged,setPublicDoiAcknowledged]=useState(false);
 const selected=state.evidenceQuestionId===question.question_id;
 const links=selected&&state.evidenceLinks?.question_id===question.question_id?state.evidenceLinks:null;
 const search=selected&&!links&&state.evidenceSearch?.question_id===question.question_id?state.evidenceSearch:null;
 const unresolved=state.evidenceLinkPhase==='unknown';
 const writing=state.evidenceLinkPhase==='saving';
 const reading=selected&&(state.evidenceSearchPhase==='loading'||state.evidenceLinksPhase==='loading');
 const blocked=busy||writing||unresolved;
 const stale=question.source_context_state==='source_reassessment_required'||
  search?.source_context_state==='source_reassessment_required'||links?.source_context_state==='source_reassessment_required';
 const canSave=!blocked&&!stale&&state.worldPhase==='ready'&&canPrepareSourceBrief(question,state.worldModel);
 const panelId='evidence-'+question.question_id,queryId=panelId+'-query',hintId=panelId+'-hint',doiId=panelId+'-doi';
 const ownRecovery=state.evidenceLinkIntent?.question_id===question.question_id;
 return <section className="question-evidence" data-testid="question-evidence-panel" aria-label="Question evidence citations">
  <button type="button" data-testid="metadata-evidence-open" aria-expanded={selected} aria-controls={panelId}
   disabled={busy||writing||reading} onClick={()=>void session.loadQuestionEvidenceLinks(question.question_id)}>
   {selected?'Refresh saved evidence citations':'Find evidence citations for this question'}
  </button>
  {selected&&<div id={panelId} className="evidence-workspace" data-testid="evidence-workspace">
   <h4>Evidence citations for this question</h4>
   <p id={hintId}>Search the permitted catalog or explicitly look up a public DOI. Content is not appraised. No model runs or clinical approval is created.</p>
   {stale&&<p className="evidence-reassessment" role="note" data-testid="evidence-stale">
    Source reassessment required. You can inspect citation history and search the catalog. Prepare a question from current source context before saving another link.
   </p>}
   <form className="evidence-search" aria-label="Public DOI lookup" onSubmit={event=>{event.preventDefault();void session.lookupQuestionDoi(question.question_id,doi,publicDoiAcknowledged);}}>
    <label htmlFor={doiId}>Public publication DOI</label>
    <input id={doiId} data-testid="evidence-doi-input" type="text" value={doi} maxLength={200}
     autoComplete="off" spellCheck={false} disabled={blocked} aria-describedby={doiId+'-hint'}
     placeholder="Enter a public DOI identifier" onChange={event=>{setDoi(event.target.value);setPublicDoiAcknowledged(false);}}/>
    <p id={doiId+'-hint'} className="muted">Only the DOI is sent to Crossref. Patient records and question text are never added automatically. Public lookup is disabled by default and requires a separate permission.</p>
    <label className="evidence-check"><input type="checkbox" data-testid="evidence-doi-acknowledge" checked={publicDoiAcknowledged}
     disabled={blocked} onChange={event=>setPublicDoiAcknowledged(event.target.checked)}/>
     <span>I confirm this is a public DOI identifier and contains no patient information.</span></label>
    <button type="submit" data-testid="evidence-doi-lookup" disabled={blocked||reading||!publicDoiAcknowledged||!normalizePublicDoi(doi)}>Look up public DOI metadata</button>
   </form>
   <form className="evidence-search" onSubmit={event=>{event.preventDefault();void session.searchQuestionEvidence(question.question_id,query);}}>
    <label htmlFor={queryId}>Your catalog search terms</label>
    <input id={queryId} data-testid="evidence-query" type="search" value={query} maxLength={200}
     autoComplete="off" spellCheck={false} disabled={blocked} aria-describedby={hintId}
     placeholder="Search metadata already in the catalog" onChange={event=>setQuery(event.target.value)}/>
    <p className="muted">Enter 1–200 visible characters. The query is yours; patient records and question text are not added automatically.</p>
    <button type="submit" data-testid="evidence-search" disabled={blocked||reading||!validEvidenceQuery(query)}>
     {state.evidenceSearchPhase==='loading'?'Reading metadata…':'Search permitted catalog'}
    </button>
   </form>
   {unresolved&&!ownRecovery&&<p role="note">Another citation save needs recovery. Resolve its exact intent before starting a new search or save.</p>}
   {state.evidenceSearchPhase!=='idle'&&<p role="status" aria-live="polite" data-testid="evidence-search-status"
    className={'status '+(state.evidenceSearchPhase==='error'?'error':'')}>{state.evidenceSearchMessage}</p>}
   {search&&<div className="evidence-results" data-testid="evidence-results">
    {search.records.map(record=><details key={record.citation} className="evidence-result" data-testid="evidence-result" data-citation={record.citation}>
     <summary><strong>{record.title}</strong><span className="muted">Inspect citation metadata</span></summary>
     <CitationMetadata record={record}/>
     <p className="muted">Saving records a citation link only. It does not assert that this item supports the question or any clinical claim.</p>
     <button type="button" data-testid="evidence-save" disabled={!canSave}
      onClick={()=>void session.saveQuestionEvidence(question.question_id,record.citation)}>Save this citation link</button>
    </details>)}
   </div>}
   <p role="status" aria-live="polite" data-testid="evidence-links-status"
    className={'status '+(state.evidenceLinksPhase==='error'?'error':'')}>{state.evidenceLinksMessage}</p>
   {links&&<div data-testid="evidence-saved-links">
    <h4>Saved citation links</h4>
    {links.links.length===0?<p>No citations are linked to this question yet.</p>:
     <ul className="evidence-links">{links.links.map(item=><li key={item.link_id} data-testid="evidence-saved-link" data-link-id={item.link_id}>
      <p><strong>Exact citation:</strong> <code>{item.citation}</code></p>
      {item.record?<details><summary>{item.record.title} — inspect metadata</summary><CitationMetadata record={item.record}/></details>:
       <p className="evidence-unavailable" data-testid="evidence-restricted">
        {item.status==='rights_restricted'?'Rights restricted':item.status==='superseded'?'Superseded version':'Unavailable'}
        {' '}— title, license and URL are withheld. The earlier search metadata is not reused.</p>}
      <details><summary>Saved link receipt</summary>
       <p>Link <code>{item.link_id}</code></p><p>Recorded {item.created_at} by <code>{item.actor_label}</code></p>
       <p>Metadata SHA-256 <code>{item.metadata_sha256}</code></p>
      </details>
     </li>)}</ul>}
   </div>}
   {(search||links)&&<details className="evidence-access"><summary>Metadata access check</summary>
    <p>Source access receipt <code>{(search??links)?.source_access_receipt_id}</code></p>
    <p>This read does not confer a separate link permission or clinical authority.</p>
   </details>}
  </div>}
  {(ownRecovery||(selected&&!unresolved))&&<QuestionEvidenceRecovery state={state} session={session} busy={busy} showReadError={false}/>}
 </section>;
}
