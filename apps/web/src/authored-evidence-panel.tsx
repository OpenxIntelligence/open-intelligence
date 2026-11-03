import {useEffect,useRef,useState} from 'react';
import type {RegistrySession,ViewState} from './registry-client';
import {declaredPermissions,downloadEvidenceOriginal,downloadEvidenceReport,visibleLine} from './authored-evidence';
import type {ContentItem,Permission,Relation,Applicability} from './authored-evidence';
import {activeComparisonDraft,evidenceSelectionMode} from './authored-evidence-session';
import './authored-evidence.css';

const relationLabel={supports:'Proposed support',contradicts:'Proposed contradiction',context:'Context only',unknown:'Relation unknown'};
const stateLabel={current_unreviewed:'Current proposal · unreviewed',reassessment_required:'Reassessment required',content_withheld:'Content withheld',historical_reassessment_required:'Historical preparation · reassessment required'};

/** Authored fictional evidence stays visibly separate from clinical conclusions. */
export function QuestionEvidencePanel({session,state,busy}:{session:RegistrySession;state:ViewState;busy:boolean}){
 const packet=state.evidencePacket,report=state.evidenceReport;
 const q=packet?.question??state.questions?.find(q=>q.question_id===report?.question_id);
 const [original,setOriginal]=useState(''),[fileName,setFileName]=useState(''),[fileMessage,setFileMessage]=useState('');
 const [fictional,setFictional]=useState(false),[item,setItem]=useState<ContentItem>('abstract');
 const [display,setDisplay]=useState<Permission>('allowed'),[redistribute,setRedistribute]=useState<Permission>('allowed');
 const [selected,setSelected]=useState('');
 const retainedDraft=state.evidenceComparisonDraft;
 const currentDraft=activeComparisonDraft(state);
 const comparison=currentDraft?.evidence_id===selected?currentDraft:null;
 const quote=comparison?.quote??'',rationale=comparison?.rationale??'';
 const relation=comparison?.relation??'unknown',applicability=comparison?.applicability??'unknown';
 const [reason,setReason]=useState(''),[chosen,setChosen]=useState<readonly string[]>([]);
 const fileRead=useRef(0),fileInput=useRef<HTMLInputElement>(null);
 const intent=state.evidenceWriteIntent,uncertain=state.evidenceWritePhase==='unknown';
 const locked=busy||state.evidenceWritePhase==='saving'||uncertain;
 const evidence=packet?.evidence.find(e=>e.evidence_id===selected);
 const current=packet?.question.source_context_state==='current_unreviewed_question'&&
   packet.source_snapshot_sha256===state.worldModel?.snapshot_fingerprint;
 useEffect(()=>{
  fileRead.current++;setOriginal('');setFileName('');setFileMessage('');setFictional(false);
  setSelected(currentDraft?.evidence_id??'');setReason('');setChosen([]);
  if(fileInput.current)fileInput.current.value='';
 },[packet?.packet_sha256,packet?.question.question_id]);
 useEffect(()=>()=>{fileRead.current++;},[]);
 async function inspectFile(file:File|undefined){
  const read=++fileRead.current;setOriginal('');setFileName('');setFileMessage('');
  if(!file)return;
  if(file.size<1||file.size>32768){setFileMessage('Choose one UTF-8 authored evidence file, at most 32 KiB.');return;}
  try{
   const bytes=new Uint8Array(await file.arrayBuffer());
   if(read!==fileRead.current)return;
   const text=new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(bytes);
   if(!text.startsWith('OI-SYNTHETIC-EVIDENCE/1\n')||/[\r\0]/.test(text)||new TextEncoder().encode(text).length!==bytes.length)throw Error('format');
   setOriginal(text);setFileName(file.name);setFileMessage('Original file read in memory. The server validates its fictional evidence grammar before storage.');
  }catch(_){if(read===fileRead.current)setFileMessage('Unsupported file. Use the exact OI-SYNTHETIC-EVIDENCE/1 UTF-8 format with LF line endings.');}
 }
 function selectEvidence(id:string){
  if(locked)return;
  const mode=evidenceSelectionMode(state,id);if(!mode)return;
  // Withdrawal remains separate from comparison creation: stale source context
  // or withheld quotation content must not prevent a deliberate family withdrawal.
  if(mode==='comparison'&&(!q||!session.selectEvidenceComparison(q.question_id,id)))return;
  setSelected(id);setReason('');
 }
 const canAssess=Boolean(comparison&&current&&evidence?.state==='current'&&evidence.statement&&quote&&Array.from(quote).length<=400&&
  evidence.statement.includes(quote)&&evidence.statement.indexOf(quote)===evidence.statement.lastIndexOf(quote)&&visibleLine(rationale)&&
  !(relation==='supports'&&applicability==='not_applicable'));
 return <section className="evidence-workspace" aria-label="Fictional evidence investigation">
  <p data-testid="evidence-status" role="status" aria-live="polite" className={'status '+(state.evidencePhase==='error'?'error':'')}>{state.evidenceMessage}</p>
  {(intent||state.evidenceWritePhase!=='idle')&&<section className="evidence-write-status" aria-label="Evidence save status">
   <p data-testid="evidence-write-status" role="status" aria-live="polite">{state.evidenceWriteMessage}</p>
   {uncertain&&intent&&<>
    <p>This exact {intent.kind} intent belongs to question <code>{intent.question_id}</code>. Its result is unknown; it cannot be edited into another write.</p>
    <button type="button" data-testid="evidence-write-retry" disabled={busy||state.patient?.patient_id!==intent.patient_id||!state.cases?.some(c=>c.case_id===intent.case_id&&c.status==='active')} onClick={()=>void session.retryEvidenceWrite()}>Retry exact intent and recover receipt</button>
   </>}
  </section>}
  {retainedDraft&&(retainedDraft.dirty||!currentDraft)&&state.connected&&retainedDraft.patient_id===state.patient?.patient_id&&
   <section className="evidence-write-status" data-testid="evidence-draft-status" aria-label="Unfinished evidence comparison">
    <p role="status" aria-live="polite">{state.evidenceDraftMessage}</p>
    <p>This comparison is kept only in the current browser session, not saved as an assessment. Its quotation and rationale appear only after a fresh matching access check.</p>
    {!currentDraft&&<button type="button" data-testid="evidence-draft-resume"
     disabled={locked||state.evidencePhase==='loading'||!state.questions?.some(row=>row.question_id===retainedDraft.question_id&&row.case_id===retainedDraft.case_id)}
     onClick={()=>void session.loadQuestionEvidence(retainedDraft.question_id)}>Recheck and resume unfinished comparison</button>}
    <button type="button" data-testid="evidence-draft-discard" disabled={locked}
     onClick={()=>{if(session.discardEvidenceComparison()){setSelected('');setReason('');}}}>Discard unfinished comparison</button>
   </section>}
  {(packet||report)&&q&&<section data-testid="evidence-panel" aria-labelledby="question-evidence-heading">
   <div className="evidence-heading">
    <div><span className="step">FICTIONAL EVIDENCE · HUMAN PROPOSALS</span><h3 id="question-evidence-heading">Evidence for this question</h3></div>
    <button type="button" data-testid="evidence-refresh" disabled={busy||state.evidencePhase==='loading'} onClick={()=>void session.loadQuestionEvidence(q.question_id)}>Refresh evidence and rights</button>
   </div>
   <p className="evidence-question"><strong>{q.question}</strong></p>
   <p>Case-owned authored records and human-proposed comparisons. Scientific appraisal, publisher clearance and clinical review have not been performed. No model was run.</p>
   {packet&&<>
    {!current&&<p className="evidence-notice" role="note">The source context changed. Earlier comparisons are retained as history. Prepare a new question from current source context before creating a new assessment or report.</p>}
    <section className="evidence-import" aria-labelledby="evidence-import-heading">
     <h4 id="evidence-import-heading">Add authored evidence or an amendment</h4>
     <p>Use an independently written fictional evidence file. An amendment names its earlier version in <code>Amends: KEY@VERSION</code>; originals and prior proposals remain preserved.</p>
     <div className="evidence-form-grid">
      <label htmlFor="evidence-file">Original evidence file<input ref={fileInput} id="evidence-file" data-testid="evidence-file" type="file" accept=".txt,text/plain" disabled={locked} onChange={e=>void inspectFile(e.target.files?.[0])}/></label>
      <label htmlFor="evidence-content-item">Declared content class<select id="evidence-content-item" data-testid="evidence-content-item" value={item} disabled={locked} onChange={e=>setItem(e.target.value as ContentItem)}><option value="abstract">Abstract</option><option value="full_text">Full text</option><option value="api_output">API output</option></select></label>
     </div>
     <p className="muted" role="status">{fileName&&<strong>{fileName}: </strong>}{fileMessage}</p>
     {original&&<details><summary>Inspect exact file before saving</summary><pre className="evidence-literal">{original}</pre></details>}
     <details className="evidence-permissions"><summary>Declared permissions for this fictional item</summary>
      <p>Storage is allowed for metadata and this selected content class. Other classes and every model-use permission remain unknown. This declaration is not independent rights verification.</p>
      <div className="evidence-form-grid">
       <label htmlFor="evidence-display">Display metadata and this content<select id="evidence-display" data-testid="evidence-display" value={display} disabled={locked} onChange={e=>setDisplay(e.target.value as Permission)}><option value="allowed">Allowed</option><option value="denied">Denied</option><option value="unknown">Unknown</option></select></label>
       <label htmlFor="evidence-redistribute">Redistribute metadata and this content<select id="evidence-redistribute" data-testid="evidence-redistribute" value={redistribute} disabled={locked} onChange={e=>setRedistribute(e.target.value as Permission)}><option value="allowed">Allowed</option><option value="denied">Denied</option><option value="unknown">Unknown</option></select></label>
      </div>
     </details>
     <label className="evidence-check"><input type="checkbox" data-testid="evidence-fictional" checked={fictional} disabled={locked} onChange={e=>setFictional(e.target.checked)}/><span>I confirm this file is independently authored and fictional, with no real patient information or patient-derived material.</span></label>
     <button type="button" className="primary" data-testid="evidence-import" disabled={locked||!original||!fictional} onClick={()=>void session.importQuestionEvidence(q.question_id,original,item,declaredPermissions(item,display,redistribute))}>Save original evidence</button>
    </section>
    <section aria-labelledby="evidence-history-heading"><h4 id="evidence-history-heading">Evidence versions ({packet.evidence.length})</h4>
     {packet.evidence.length===0?<p>No case evidence is visible under this grant.</p>:<ul className="evidence-cards">{packet.evidence.map(row=><li key={row.evidence_id} data-testid="evidence-version" data-evidence-id={row.evidence_id}>
      <div className="evidence-card-heading"><strong>{row.title??row.evidence_key}</strong><span className="evidence-state">{row.state}</span></div>
      <p>{row.content_item.replace('_',' ')} · version {row.version} · issued {row.issued_at}</p>
      {row.statement!==null?<blockquote>{row.statement}</blockquote>:<p className="evidence-notice">Content is withheld under current family permissions.</p>}
      <details><summary>Original and rights provenance</summary><p>Record <code>{row.evidence_key}</code> · <code>{row.evidence_id}</code>, statement line {row.statement_line}</p><p>Original SHA-256 <code>{row.sha256}</code></p><p>Rights SHA-256 <code>{row.rights_sha256}</code></p><p>Stored {row.created_at}. Rights are a fictional declaration, not publisher clearance.</p></details>
      <div className="actions"><button type="button" data-testid="evidence-select" disabled={locked||!evidenceSelectionMode(state,row.evidence_id)} onClick={()=>selectEvidence(row.evidence_id)}>{selected===row.evidence_id?'Selected evidence':'Select evidence'}</button>
       <button type="button" data-testid="evidence-original-download" disabled={locked||row.statement===null} onClick={()=>void downloadEvidenceOriginal(session,q.question_id,row.evidence_id)}>Recheck and download original</button></div>
     </li>)}</ul>}
    </section>
    {evidence&&<section className="evidence-assessment-editor" aria-labelledby="evidence-assessment-heading">
     <h4 id="evidence-assessment-heading">Propose a comparison</h4><p>Selected <strong>{evidence.title??evidence.evidence_key}</strong>, version {evidence.version}. The relation below is your proposal, not a conclusion authored by the evidence source.</p>
     {evidence.statement!==null&&comparison?<>
      <label htmlFor="evidence-quote">Exact unique passage<textarea id="evidence-quote" data-testid="evidence-quote" rows={3} value={quote} disabled={locked||!current} onChange={e=>session.editEvidenceComparison({quote:e.target.value})}/></label>
      <p className="muted">Choose 1–400 characters appearing once in the stored statement. The original statement line and Unicode character offset are retained.</p>
      <div className="evidence-form-grid">
       <label htmlFor="evidence-relation">Proposed relation<select id="evidence-relation" data-testid="evidence-relation" value={relation} disabled={locked||!current} onChange={e=>session.editEvidenceComparison({relation:e.target.value as Relation})}><option value="unknown">Unknown</option><option value="supports">Supports</option><option value="contradicts">Contradicts</option><option value="context">Context only</option></select></label>
       <label htmlFor="evidence-applicability">Proposed applicability<select id="evidence-applicability" data-testid="evidence-applicability" value={applicability} disabled={locked||!current} onChange={e=>session.editEvidenceComparison({applicability:e.target.value as Applicability})}><option value="unknown">Unknown</option><option value="limited">Limited</option><option value="applicable">Applicable</option><option value="not_applicable">Not applicable</option></select></label>
      </div>
      <label htmlFor="evidence-rationale">Your rationale and uncertainty<textarea id="evidence-rationale" data-testid="evidence-rationale" rows={3} value={rationale} disabled={locked||!current} onChange={e=>session.editEvidenceComparison({rationale:e.target.value})}/></label>
      <p className="muted">One visible line, 10–600 characters. Saving a proposal does not establish clinical relevance or approve a decision.</p>
      <button type="button" className="primary" data-testid="evidence-assess" disabled={locked||!canAssess} onClick={()=>void session.saveEvidenceComparison()}>Save human-authored comparison</button>
     </>:<p>{evidence.statement===null?'Comparison text is unavailable under current content permissions.':
      'A new comparison needs current source context and an explicitly selected draft. Withdrawal remains a separate action.'}</p>}
     <details className="evidence-withdrawal"><summary>Withdraw this evidence family</summary>
      <p>Withdrawal preserves original versions and earlier reports while withholding their evidence content. It cannot silently revive a withdrawn family.</p>
      <label htmlFor="evidence-withdraw-reason">Withdrawal reason<textarea id="evidence-withdraw-reason" data-testid="evidence-withdraw-reason" rows={2} value={reason} disabled={locked} onChange={e=>setReason(e.target.value)}/></label>
      <button type="button" data-testid="evidence-withdraw" disabled={locked||evidence.state!=='current'||!visibleLine(reason)} onClick={()=>void session.withdrawQuestionEvidence(q.question_id,evidence.evidence_id,reason)}>Withdraw current evidence family</button>
     </details>
    </section>}
    <section aria-labelledby="evidence-assessments-heading"><h4 id="evidence-assessments-heading">Human-authored comparisons ({packet.assessments.length})</h4>
     {packet.assessments.length===0?<p>No comparison has been proposed for this question.</p>:<ul className="evidence-cards">{packet.assessments.map(a=><li key={a.assessment_id} data-testid="evidence-assessment" data-assessment-id={a.assessment_id}>
      <div className="evidence-card-heading"><strong>{relationLabel[a.relation]}</strong><span className="evidence-state">{stateLabel[a.state]}</span></div>
      <p>Proposed applicability: {a.applicability.replace('_',' ')}. Clinical review: not performed.</p>
      {a.quote!==null?<><blockquote>{a.quote}</blockquote><p><strong>Authored rationale:</strong> {a.rationale}</p></>:<p>Quotation and rationale withheld under current rights.</p>}
      <details><summary>Comparison references</summary><p>Evidence <code>{a.evidence_id}</code> · character offset {a.quote_start??'withheld'}</p><p>Assessment <code>{a.assessment_id}</code></p><p>Recorded {a.created_at} by unverified fixture label <code>{a.actor_label}</code>.</p></details>
      <label className="evidence-check"><input type="checkbox" data-testid="evidence-report-select" checked={chosen.includes(a.assessment_id)} disabled={locked||!current||a.state!=='current_unreviewed'} onChange={e=>setChosen(ids=>e.target.checked?[...ids,a.assessment_id]:ids.filter(id=>id!==a.assessment_id))}/><span>Include this current proposal in a report</span></label>
     </li>)}</ul>}
     <button type="button" className="primary" data-testid="evidence-report-prepare" disabled={locked||!current||chosen.length<1||chosen.length>20} onClick={()=>void session.prepareEvidenceReport(q.question_id,chosen)}>Prepare selected comparison report ({chosen.length})</button>
     <p className="muted">Selection is explicit and limited to 20 current proposals. Excluded or missing counterevidence is not evidence of absence.</p>
    </section>
    <section aria-labelledby="evidence-reports-heading"><h4 id="evidence-reports-heading">Saved report preparations ({packet.reports.length})</h4>
     {packet.reports.length===0?<p>No comparison report has been prepared.</p>:<ul className="evidence-cards">{packet.reports.map(r=><li key={r.report_id} data-testid="evidence-report-row" data-report-id={r.report_id}>
      <p><strong>{stateLabel[r.state]}</strong> · {r.prepared_at}</p><p>Report <code>{r.report_id}</code></p>
      <button type="button" data-testid="evidence-report-open" disabled={locked||state.evidenceReportPhase==='loading'} onClick={()=>void session.readEvidenceReport(q.question_id,r.report_id)}>Recheck and open report</button>
     </li>)}</ul>}
    </section>
   </>}
  </section>}
  <p data-testid="evidence-report-status" role="status" aria-live="polite" className={'status '+(state.evidenceReportPhase==='error'?'error':'')}>{state.evidenceReportMessage}</p>
  {report&&<section data-testid="evidence-report-preview" className="evidence-report-preview" aria-labelledby="evidence-report-heading">
   <span className="step">IMMUTABLE PREPARATION · NO CLINICAL APPROVAL</span><h3 id="evidence-report-heading">Human-authored evidence comparison</h3>
   <p className="evidence-notice"><strong>{stateLabel[report.state]}</strong></p>
   {report.body!==null?<pre data-testid="evidence-report-body" className="evidence-literal">{report.body}</pre>:<p>Current content permissions withhold this report’s body and comparison snapshot. The original preparation references remain preserved.</p>}
   <details><summary>Report provenance</summary><p>Report <code>{report.report_id}</code></p><p>Prepared {report.prepared_at}</p><p>Body SHA-256 <code>{report.body_sha256}</code></p><p>Snapshot SHA-256 <code>{report.snapshot_sha256}</code></p><p>Current access receipt <code>{report.access_receipt_id}</code>. This records preparation authorization, not delivery, signoff or medical validity.</p></details>
   {report.body!==null&&<button type="button" data-testid="evidence-report-download" className="primary" disabled={locked||state.evidenceReportPhase==='loading'} onClick={()=>void downloadEvidenceReport(session,report.question_id,report.report_id)}>Recheck permission and download report</button>}
  </section>}
 </section>;
}
