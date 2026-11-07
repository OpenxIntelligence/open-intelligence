import {useState} from 'react';
import type {RegistrySession,ViewState} from './registry-client';
import {amendmentAction,validAmendmentReason,validDisposition,type AmendmentVersion,type Disposition} from './laboratory-amendment';

const dispositions:Record<Disposition,string>={transcription_checked:'Transcription checked',needs_clarification:'Needs clarification'};

function SourceResult({version,original}:{version:AmendmentVersion;original:boolean}){
 const observation=version.observation;
 return <section data-testid={original?'amendment-comparison-original':'amendment-comparison-latest'}>
  <h4>{original?'Original report':'Latest amended report'} · {version.document_id} v{version.version}</h4>
  {observation?<dl>
   <dt>Source-reported result</dt><dd>{observation.status==='reported_value'?
    <><strong>{observation.value_text}</strong> {observation.unit_code}</>:
    <>Reported absent · {observation.absent_reason}</>}</dd>
   <dt>LOINC code</dt><dd>{observation.loinc_code}</dd>
   <dt>Specimen</dt><dd>{observation.specimen_reference}</dd>
   <dt>Effective</dt><dd><time dateTime={observation.effective_at}>{observation.effective_at}</time></dd>
   <dt>Issued</dt><dd><time dateTime={observation.issued_at}>{observation.issued_at}</time></dd>
  </dl>:<p><strong>Observation missing from the latest report.</strong> This version does not include the original Observation reference.</p>}
  <p>Source <code>{version.source_id}</code> · SHA-256 <code>{version.sha256}</code></p>
 </section>;
}

type Props={state:ViewState;session:RegistrySession;busy:boolean};
export function AmendmentPanel({state,session,busy,mode,caseId}:Props&{mode:'patient'|'review';caseId:string}){
 const a=state.amendment;
 const [reason,setReason]=useState(''),[disposition,setDisposition]=useState<Disposition|''>('');
 if(!a||a.mode!==mode||!a.scope||a.scope.case_id!==caseId||a.scope.patient_id!==state.patient?.patient_id||
    !state.cases?.some(c=>c.case_id===caseId&&c.patient_id===a.scope?.patient_id&&c.status==='active'))return null;
 if(!a.detail&&!a.command&&!a.message)return null;
 const {detail,command,target}=a;
 const action=detail&&target&&amendmentAction(detail,target.selection);
 return <section data-testid="amendment-review-panel" aria-label="Laboratory amendment verification" className="followthrough-form">
  <h3>Verify a laboratory amendment</h3>
  <p>Compare the source-reported transcription. A request or response records a human check or a need for clarification. Clinical interpretation and task completion are separate.</p>
  {a.message&&<p role="status" data-testid="amendment-status">{a.message}</p>}
  {command&&<div><p><strong>{command.body.action==='request'?'Request':'Response'} awaiting confirmation:</strong> {command.body.reason}</p>
   <p>Task <code>{command.target.task.task_id}</code> · amended source <code>{command.body.expected_latest_source_id}</code></p>
   {command.body.disposition&&<p>{dispositions[command.body.disposition]}</p>}
   {a.phase==='unknown'&&<div className="actions"><button type="button" disabled={busy} data-testid="amendment-retry" onClick={()=>void session.amendments.retry()}>Retry exact action</button>
    <button type="button" disabled={busy} onClick={()=>session.amendments.abandon()}>Abandon recovery and recheck history</button></div>}
  </div>}
  {detail&&target&&<>
   <p><strong>{detail.observation_reference}</strong> · Task <code>{detail.task_id}</code> · Question <code>{detail.question_id}</code></p>
   <SourceResult version={detail.original} original/><SourceResult version={detail.latest} original={false}/>
   <section data-testid="amendment-review-history" aria-label="Verification history"><h4>Verification history</h4>
    {!detail.entries.length?<p>No verification has been recorded.</p>:<ol>{detail.entries.map(entry=><li key={entry.entry_id} data-entry-id={entry.entry_id}>
     <strong>{entry.action==='request'?'Verification requested':dispositions[entry.disposition!]}</strong>
     <p>{entry.reason}</p><p>{entry.actor} · <time dateTime={entry.recorded_at}>{entry.recorded_at}</time></p>
     <p>Request <code>{entry.request_id}</code> · amended source <code>{entry.latest_source_id}</code></p>
    </li>)}</ol>}
   </section>
   {action?<form onSubmit={event=>{event.preventDefault();void session.amendments.submit(detail,reason,action==='respond'&&disposition?disposition:undefined);}}>
    {action==='respond'&&<label>Review outcome<select data-testid="amendment-response-disposition" value={disposition}
     onChange={e=>setDisposition(validDisposition(e.target.value)?e.target.value:'')}><option value="">Choose an outcome</option>
      <option value="transcription_checked">Transcription checked</option><option value="needs_clarification">Needs clarification</option></select></label>}
    <label>{action==='request'?'What should someone verify?':'What did you check, or what needs clarification?'}
     <textarea data-testid={'amendment-'+(action==='request'?'request':'response')+'-reason'} value={reason}
      onChange={e=>setReason(e.target.value)} maxLength={600} rows={2}/></label>
    <button type="submit" data-testid={'amendment-'+(action==='request'?'request':'response')+'-submit'}
     disabled={busy||a.phase!=='ready'||!validAmendmentReason(reason)||(action==='respond'&&!disposition)}>
      {action==='request'?'Request independent verification':'Record independent response'}</button>
   </form>:<p>{target.selection?.latest_source_id&&target.selection.latest_source_id!==detail.latest.source_id?
    'This request refers to an older amendment. A response cannot be recorded against this newer report.':
    mode==='review'?'The selected request already has a recorded response.':'Verification was already requested for this amended report.'}</p>}
  </>}
 </section>;
}

export function AmendmentInbox({state,session,busy,currentCase}:Props&{currentCase:string}){
 const [chosen,setChosen]=useState('');
 const cases=state.cases?.filter(c=>c.status==='active'&&c.patient_id===state.patient?.patient_id)??[];
 const caseId=cases.find(c=>c.case_id===chosen)?.case_id??cases.find(c=>c.case_id===currentCase)?.case_id??'';
 const a=state.amendment;
 const inbox=a?.mode==='review'&&a.scope?.case_id===caseId&&a.scope?.patient_id===state.patient?.patient_id?a.inbox:null;
 const locked=!!a?.command,loading=a?.phase==='loading';
 return <section aria-label="Laboratory amendment requests">
  <h3>Laboratory amendment requests</h3>
  {!state.cases?<button type="button" data-testid="amendment-cases-load" disabled={busy||state.recordsPhase.startsWith('loading')}
   onClick={()=>void session.loadCases()}>Check available cases</button>:<label>Case for amendment verification
    <select data-testid="amendment-case-select" value={caseId} disabled={busy||locked} onChange={e=>{session.amendments.dismiss();setChosen(e.target.value);}}>
     <option value="">Select a case</option>{cases.map(c=><option key={c.case_id} value={c.case_id}>{c.case_id}</option>)}</select></label>}
  <button type="button" data-testid="amendment-inbox-load" disabled={busy||locked||loading||!caseId}
   onClick={()=>void session.amendments.loadInbox(caseId)}>Check pending amendment requests</button>
  {locked&&a.mode==='patient'&&<p>Recover the pending request in Investigations before opening another request.</p>}
  {inbox&&(inbox.length===0?<p data-testid="amendment-inbox-empty">No pending requests in this case.</p>:<ul>{inbox.map(item=><li key={item.request_id}>
   <p>Request <code>{item.request_id}</code> · Task <code>{item.task_id}</code></p>
   <button type="button" data-testid="amendment-inbox-open" data-request-id={item.request_id} disabled={busy||locked||loading}
    onClick={()=>void session.amendments.openRequest(item)}>Inspect amendment request</button>
  </li>)}</ul>)}
  <AmendmentPanel key={a?.target?.selection?.request_id+':'+a?.detail?.latest.source_id}
   mode="review" caseId={caseId} state={state} session={session} busy={busy}/>
 </section>;
}
