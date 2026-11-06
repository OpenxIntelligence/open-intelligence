import {codedResultLabel,CodingProvenance} from './laboratory-coding-view';
import {useEffect,useRef,useState} from 'react';
import type {LaboratoryInspection} from './laboratory-citation-report.js';
import type {SavedLabQuestion} from './laboratory-question.js';
import type {RegistrySession,ViewState} from './registry-client.js';

import type {InspectionSnapshot} from './laboratory-inspection-snapshots.js';

type OpenReport={report:LaboratoryInspection;generation:number;snapshot?:InspectionSnapshot};
export function LaboratoryCitationReportPanel({question,state,session,busy}:{
  question:SavedLabQuestion;state:ViewState;session:RegistrySession;busy:boolean;
}){
  const [content,setContent]=useState<OpenReport|null>(null),[message,setMessage]=useState('');
  const [history,setHistory]=useState<{snapshots:readonly InspectionSnapshot[];generation:number}|null>(null);
  const [save,setSave]=useState<{id:string;duplicate:boolean;generation:number}|null>(null);
  const [working,setWorking]=useState(false),request=useRef<AbortController|null>(null);
  useEffect(()=>{
    setWorking(false);setMessage('');setContent(null);setHistory(null);setSave(null);
    return ()=>{request.current?.abort();request.current=null;};
  },[question,session]);
  const generation=state.evidenceGeneration;
  const report=content&&content.generation===generation&&content.report.citations.patient_id===state.patient?.patient_id&&
    content.report.citations.case_id===state.worldModel?.case_id&&content.report.citations.question_id===question.question_id?content.report:null;
  const rows=history&&history.generation===generation?history.snapshots:null;
  const receipt=save&&save.generation===generation?save:null;
  useEffect(()=>{if(content&&!report)setContent(null);if(history&&!rows)setHistory(null);if(save&&!receipt)setSave(null);},
    [content,report,history,rows,save,receipt]);
  const phase=session.laboratorySnapshotWritePhase(question.question_id);
  const disabled=busy||working||['saving','unknown'].includes(state.evidenceLinkPhase)||phase==='saving';
  const run=async(action:'live'|'list'|'reopen'|'capture'|'retry',row?:InspectionSnapshot)=>{
    if(disabled||request.current)return;
    const control=new AbortController();request.current=control;setWorking(true);
    setContent(null);setHistory(null);setSave(null);setMessage(action==='capture'||action==='retry'?'Saving this inspection…':'Checking current access…');
    try{
      const id=question.question_id;
      if(action==='live'||action==='reopen'){
        const result=action==='live'?await session.readLaboratoryCitationReport(id,control.signal):
          await session.reopenLaboratorySnapshot(id,row!,control.signal);
        if(request.current===control)setContent(result);
      }else if(action==='list'){
        const result=await session.listLaboratorySnapshots(id,control.signal);
        if(request.current===control)setHistory(result);
      }else{
        const {receipt:saved,generation}=await session.captureLaboratorySnapshot(id,action==='retry'?null:report,control.signal);
        if(request.current===control)setSave({id:saved.snapshot_id,duplicate:saved.duplicate,generation});
      }
      if(request.current===control)setMessage('');
    }catch{
      if(request.current===control)setMessage(action==='capture'||action==='retry'?
        'A save receipt is unavailable. Check saved inspections or reopen the current report.':
        'The inspection is unavailable. Recheck access and try again.');
    }finally{if(request.current===control){request.current=null;setWorking(false);}}
  };
  const r=report?.result;
  return <section aria-label="Laboratory result and citations for review">
    <button type="button" data-testid="lab-citation-report-open" disabled={disabled}
      onClick={()=>void run('live')}>{report?'Refresh result and citation report':'Inspect result and citations together'}</button>
    <button type="button" data-testid="lab-snapshot-list" disabled={disabled}
      onClick={()=>void run('list')}>View saved inspections</button>
    {phase==='unknown'&&<button type="button" data-testid="lab-snapshot-retry" disabled={disabled}
      onClick={()=>void run('retry')}>Retry the unconfirmed save</button>}
    <p role="status" aria-live="polite" data-testid="lab-snapshot-status">{receipt?
      <>{receipt.duplicate?'Original save confirmed':'Inspection saved'} · <code>{receipt.id}</code></>:
      phase==='unknown'?'The save is unconfirmed. Retry to recover the original receipt.':message}</p>
    {rows&&(rows.length?<ul aria-label="Saved inspections">{rows.map(row=><li key={row.snapshot_id} data-testid="lab-snapshot-row" data-snapshot-id={row.snapshot_id}>
      <time dateTime={row.captured_at}>{row.captured_at}</time> · {row.citation_count} {row.citation_count===1?'citation':'citations'} ·
      {' '}{row.captured_source_context_state==='source_reassessment_required'?'Required reassessment when saved':'Source current when saved'}{' '}
      <button type="button" data-testid="lab-snapshot-reopen" disabled={disabled} onClick={()=>void run('reopen',row)}>Reopen saved inspection</button>
    </li>)}</ul>:<p>No inspections saved for this question.</p>)}
    {report&&r&&<article data-testid="lab-citation-report" data-snapshot-id={content?.snapshot?.snapshot_id}>
      <h5>{content?.snapshot?'Saved result and citation report':'Result and citation report'}</h5><p>{report.question}</p>
      {content?.snapshot&&<p>Saved <time dateTime={content.snapshot.captured_at}>{content.snapshot.captured_at}</time>. Citation details reflect your current access.</p>}
      {!content?.snapshot&&<button type="button" data-testid="lab-snapshot-capture" disabled={disabled||phase==='unknown'} onClick={()=>void run('capture')}>Save this inspection</button>}
      <p><strong>{report.citations.source_context_state==='source_reassessment_required'?'Needs reassessment.':'Unreviewed.'}</strong>{' '}
        {report.citations.source_context_state==='source_reassessment_required'?'The source context changed. This is the result from the original question.':'This is the result from the report used to save this question.'}</p>
      <p><strong>Reported result: </strong>{r.status==='reported_value'?<>{r.value_text} {r.unit_code}</>:r.status==='reported_coded'?<span className="lab-coded-label">{codedResultLabel(r.coded_result)}</span>:<>No value reported. The source gives the reason: {r.absent_reason}.</>}</p>
      <p>Source: {r.report_reference}, version {r.version}. Collected specimen: {r.specimen_type_text} ({r.specimen_reference}).</p>
      <p><strong>Saved citations</strong></p>
      {report.citations.links.length?<ul>{report.citations.links.map(l=><li key={l.link_id}><code>{l.citation}</code> ·{' '}
        {l.record?<>{l.record.title} (fictional catalog metadata only)</>:l.status==='rights_restricted'?'Permission to display this metadata was withdrawn or is unavailable.':
          l.status==='superseded'?'This citation version has been superseded.':'Metadata unavailable.'}</li>)}</ul>:<p>No citations are saved on this question.</p>}
      <p>The citations identify catalog entries. Their contents have not been assessed, and no clinician approval is recorded here.</p>
      <details><summary>Inspect the original references</summary><p>Observation <code>{r.resource_reference}</code> · LOINC {r.loinc_code}</p>
        {r.status==='reported_coded'&&<CodingProvenance coding={r.coded_result}/>}
        <p>Specimen collected {r.specimen_collected_at}. Result effective {r.effective_at}; issued {r.issued_at}.</p>
        <p>Original <code>{r.source_id}</code> · SHA-256 <code>{r.sha256}</code></p>
        {content?.snapshot&&<p>Report SHA-256 at capture: <code data-testid="lab-snapshot-captured-digest">{content.snapshot.captured_report_sha256}</code></p>}
        <p>Current report SHA-256: <code data-testid="lab-snapshot-current-digest">{report.report_sha256}</code></p>
        {content?.snapshot&&content.snapshot.captured_report_sha256!==report.report_sha256&&
          <p>The report now differs from the saved inspection. A change in source status or citation access can change this fingerprint.</p>}
        <p>Question <code>{question.question_id}</code> · read receipt <code>{report.citations.source_access_receipt_id}</code></p></details>
      <button type="button" onClick={()=>{setContent(null);setMessage('');}}>Close report</button>
    </article>}
  </section>;
}
