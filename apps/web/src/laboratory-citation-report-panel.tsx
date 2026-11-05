import {codedResultLabel,CodingProvenance} from './laboratory-coding-view';
import {useEffect,useRef,useState} from 'react';
import type {LaboratoryInspection} from './laboratory-citation-report.js';
import type {SavedLabQuestion} from './laboratory-question.js';
import type {RegistrySession,ViewState} from './registry-client.js';

type OpenReport={report:LaboratoryInspection;generation:number};
export function LaboratoryCitationReportPanel({question,state,session,busy}:{
  question:SavedLabQuestion;state:ViewState;session:RegistrySession;busy:boolean;
}){
  const [content,setContent]=useState<OpenReport|null>(null),[message,setMessage]=useState('');
  const request=useRef<AbortController|null>(null);
  useEffect(()=>()=>{request.current?.abort();request.current=null;},[question,session]);
  // A metadata search, save, refresh, scope change or denial invalidates every earlier title.
  // Gate the render synchronously; remove the old object from state after rendering.
  const report=content&&content.generation===state.evidenceGeneration&&
    content.report.citations.patient_id===state.patient?.patient_id&&content.report.citations.case_id===state.worldModel?.case_id&&
    content.report.citations.question_id===question.question_id?content.report:null;
  useEffect(()=>{if(content&&!report){setContent(null);setMessage('');}},[content,report]);
  const open=async()=>{
    if(busy||request.current||['saving','unknown'].includes(state.evidenceLinkPhase))return;
    setContent(null);setMessage('Checking the original result and current citation permissions…');
    const control=new AbortController();request.current=control;
    try{
      const next=await session.readLaboratoryCitationReport(question.question_id,control.signal);
      if(request.current===control){setContent(next);setMessage('');}
    }catch{if(request.current===control)setMessage('The report is unavailable. Recheck access, then reopen it.');}
    finally{if(request.current===control)request.current=null;}
  };
  const r=report?.result;
  return <section aria-label="Laboratory result and citations for review">
    <button type="button" data-testid="lab-citation-report-open" disabled={busy||Boolean(request.current)||['saving','unknown'].includes(state.evidenceLinkPhase)}
      onClick={()=>void open()}>{report?'Refresh result and citation report':'Inspect result and citations together'}</button>
    <p role="status" aria-live="polite">{message}</p>
    {report&&r&&<article data-testid="lab-citation-report">
      <h5>Result and citation report</h5><p>{report.question}</p>
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
        <p>Question <code>{question.question_id}</code> · read receipt <code>{report.citations.source_access_receipt_id}</code></p></details>
      <button type="button" onClick={()=>{setContent(null);setMessage('');}}>Close report</button>
    </article>}
  </section>;
}
