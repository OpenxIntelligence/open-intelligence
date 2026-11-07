import {useEffect,useRef,useState} from 'react';
import type {Document,Finding} from './reviewed-documents';
import {decodeChosenPassage,decodeSavedPassage,manualHash} from './question-passages';
import type {RegistrySession} from './registry-client';

import {decodeQuestionEvidenceSearch,decodeQuestionEvidenceLinks,validEvidenceQuery} from './question-evidence-view';
import type {QuestionEvidenceSearch,QuestionEvidenceLinks,QuestionEvidenceRecord} from './question-evidence-view';

function PassageEvidenceSearch({patient,caseId,source,id,anchor,question,current,session}:{
 patient:string;caseId:string;source:string;id:string;anchor:string;question:string;current:boolean;session:RegistrySession;
}){
 const [query,setQuery]=useState('');
 const [result,setResult]=useState<QuestionEvidenceSearch|null>(null);
 const [status,setStatus]=useState('');
 const intent=session.documentQuestionIntent(patient,caseId,source,id);
 const [pending,setPending]=useState<string|null>(()=>intent.read());
 const [saving,setSaving]=useState(false);
 const [links,setLinks]=useState<QuestionEvidenceLinks|null>(null);
 const generation=useRef(0);
 useEffect(()=>()=>{generation.current++;},[patient,caseId,source,id,session]);
 async function search(){
  const request=++generation.current;
  setResult(null);setLinks(null);setStatus('Searching…');
  try{
   const reply=await session.documentRequest(caseId,'/'+source+'/questions/'+id+'/evidence-search',
    JSON.stringify({synthetic:true,query}));
   if(reply.status!==200)throw Error();
   const data=decodeQuestionEvidenceSearch(reply.body,patient,caseId,id,query);
   if(request===generation.current){setResult(data);setStatus('');}
  }catch{if(request===generation.current)setStatus('Evidence search unavailable. Recheck access and try again.');}
 }
 async function save(record?:QuestionEvidenceRecord){
  const request=++generation.current;
  setSaving(true);setLinks(null);setStatus('');
  let body=pending;
  try{
   if(!body){
    if(!record||!current)throw Error();
    const preflight=await manualHash([anchor,question]);
    if(request!==generation.current)return;
    body=intent.begin(JSON.stringify({synthetic:true,request_key:'PASSAGE-CITATION-'+crypto.randomUUID(),
      citation:record.citation,expected_metadata_sha256:record.metadata_sha256,
      source_snapshot_contract:'oi.reviewed-document-selection/1',
      expected_source_snapshot_sha256:anchor,expected_preflight_sha256:preflight}));
    setPending(body);
   }
   const reply=await session.documentRequest(caseId,'/'+source+'/questions/'+id+'/evidence-links',body);
   if([409,422].includes(reply.status)){intent.finish(body);if(request===generation.current)setPending(null);throw Error();}
   if(![200,201].includes(reply.status))throw Error();
   const expected=JSON.parse(body),receipt=reply.body as Record<string,unknown>;
   if(!receipt||!/^EVIDENCE-LINK-[A-F0-9]{32}$/.test(String(receipt.link_id))||
     receipt.citation!==expected.citation||receipt.metadata_sha256!==expected.expected_metadata_sha256||
     typeof receipt.duplicate!=='boolean')throw Error();
   intent.finish(body);
   if(request===generation.current){setPending(null);setStatus('Citation saved. Reopen saved citations to inspect it.');}
  }catch{if(request===generation.current)setStatus('Citation save unavailable or outcome unknown. Recheck access and retry the exact save.');}
  finally{if(request===generation.current)setSaving(false);}
 }
 async function reopen(){
  const request=++generation.current;setLinks(null);setStatus('');
  try{
   const reply=await session.documentRequest(caseId,'/'+source+'/questions/'+id+'/evidence-links');
   if(reply.status!==200)throw Error();
   const data=decodeQuestionEvidenceLinks(reply.body,patient,caseId,id);
   if(request===generation.current)setLinks(data);
  }catch{if(request===generation.current)setStatus('Saved citations unavailable. Recheck access.');}
 }
 return <form onSubmit={event=>{event.preventDefault();if(!saving&&validEvidenceQuery(query))void search();}}>
  <label>Search fictional evidence metadata<input value={query} disabled={saving} maxLength={200} data-testid="passage-evidence-query"
   onChange={event=>{generation.current++;setQuery(event.target.value);setStatus('');setResult(null);}}/></label>
  <button disabled={saving||!validEvidenceQuery(query)||status==='Searching…'}>Search evidence catalog</button>
  <div role="status">{status}{result&&<><p>{result.records.length} matching fictional catalog records.</p>
   {result.source_context_state==='source_reassessment_required'&&<p>The source passage needs reassessment.</p>}
   {result.records.map(record=><p key={record.citation}>{record.title} · {record.citation} · {record.licence} <button type="button" disabled={saving||!!pending||!current} onClick={()=>void save(record)}>Save citation {record.citation}</button></p>)}</>}</div>
  {pending&&<button type="button" disabled={saving} onClick={()=>void save()}>Retry exact citation save</button>}
  <button type="button" disabled={saving} onClick={()=>void reopen()}>Open saved passage citations</button>
  {links&&<div data-testid="passage-citations">{links.source_context_state==='source_reassessment_required'&&<p>The source passage needs reassessment.</p>}
   {links.links.length===0?<p>No saved citations.</p>:links.links.map(link=><p key={link.link_id}>{link.citation} · {link.status}{link.record&&' · '+link.record.title}</p>)}</div>}
 </form>;
}

export function PassageQuestionDraft({doc,session,patientId,caseId}:{
 doc:Document;session:RegistrySession;patientId:string;caseId:string;
}){
 const revision=doc.revisions.at(-1);
 const generation=useRef(0);
 const [finding,setFinding]=useState<Finding|null>(null);
 const [question,setQuestion]=useState('');
 const [digest,setDigest]=useState('');
 const intent=session.documentQuestionIntent(patientId,caseId,doc.source_id);
 const [pending,setPending]=useState<string|null>(()=>intent.read());
 const [busy,setBusy]=useState(false);
 const [history,setHistory]=useState<{id:string;text:string;quote:string;line:number;revision:number;state:string;anchor:string}[]|null>(null);
 const [message,setMessage]=useState('');
 useEffect(()=>()=>{generation.current++;},[doc,session,patientId,caseId]);
 async function start(chosen:Finding){
  if(!revision)return;
  const request=++generation.current;
  setFinding(null);setQuestion('');setMessage('Checking the saved passage…');
  try{
   const path='/'+doc.source_id+'/selections/'+revision.revision_id+'/'+chosen.key;
   const result=await session.documentRequest(caseId,path);
   if(result.status!==200)throw Error();
   const passage=await decodeChosenPassage(result.body,{patient_id:patientId,case_id:caseId},doc,chosen);
   if(request!==generation.current)return;
   setDigest(passage.anchor_sha256);setFinding(chosen);setMessage('');
  }catch{
   if(request===generation.current)setMessage('Reopen the record and check access to this passage.');
  }
 }
 async function save(){
  if((!pending&&!finding)||!revision||busy)return;
  const request=++generation.current;
  const recovering=Boolean(pending);
  const body=intent.begin(pending??JSON.stringify({synthetic:true,request_key:'DQ-'+crypto.randomUUID(),question,
   revision_id:revision.revision_id,selection_key:finding!.key,anchor_sha256:digest}));
  setPending(body);setBusy(true);setHistory(null);
  try{
   const reply=await session.documentRequest(caseId,'/'+doc.source_id+'/questions',body);
   if([401,403,404,409,422].includes(reply.status)){
    const terminal=reply.status===409||reply.status===422||!recovering;
    if(terminal)intent.finish(body);
    if(request===generation.current){
     if(terminal){setPending(null);setFinding(null);}
     setMessage('Save refused. Reopen the record to check the current passage.');
    }
    return;
   }
   const result=reply.body as {question_id?:string;duplicate?:boolean}|null;
   if(![200,201].includes(reply.status)||!result||!/^QUESTION-[A-F0-9]{32}$/.test(result.question_id??'')||
      result.duplicate!==(reply.status===200))throw Error();
   intent.finish(body);
   if(request!==generation.current)return;
   setPending(null);setFinding(null);setQuestion('');setMessage('Question saved. Open saved passage questions to read it again.');
  }catch{if(request===generation.current)setMessage('Save outcome unknown. Retry this exact question.');}
  finally{if(request===generation.current)setBusy(false);}
 }
 async function reopen(){
  const request=++generation.current;setHistory(null);setBusy(true);setMessage('');
  try{
   const reply=await session.documentRequest(caseId,'/'+doc.source_id+'/questions');
   const data=reply.body as {patient_id:string;case_id:string;source_id:string;access_receipt_id:string;questions:Array<{question_id:string;question:string;selection:unknown}>};
   const receipt=reply.headers?.get('X-Access-Receipt-ID')??'';
   if(!/^ACCESS-[A-F0-9]{32}$/.test(receipt)||data.access_receipt_id!==receipt||reply.status!==200||data.patient_id!==patientId||data.case_id!==caseId||data.source_id!==doc.source_id||!Array.isArray(data.questions)||data.questions.length>250)throw Error();
   const rows=await Promise.all(data.questions.map(async row=>{
    const selection=row.selection as {anchor:{annotation_revision_id:string;selection_key:string}};
    const anchor=selection.anchor;
    const revision=doc.revisions.find(item=>item.revision_id===anchor.annotation_revision_id);
    const finding=revision?.findings.find(item=>item.key===anchor.selection_key);
    if(!revision||!finding)throw Error();
    const verified=await decodeSavedPassage({...selection,access_receipt_id:receipt},{patient_id:patientId,case_id:caseId},doc,revision,finding);
    if(!/^QUESTION-[A-F0-9]{32}$/.test(row.question_id)||typeof row.question!=='string'||verified.anchor.original_sha256!==doc.sha256)throw Error();
    return {id:row.question_id,text:row.question,anchor:verified.anchor_sha256,quote:verified.anchor.quote,line:verified.anchor.line,revision:verified.anchor.annotation_revision,state:verified.selection_state};
   }));
   if(request===generation.current)setHistory(rows);
  }catch{if(request===generation.current)setMessage('Saved questions unavailable. Recheck record access.');}
  finally{if(request===generation.current)setBusy(false);}
 }
 if(!revision)return null;
 return <section aria-label="Draft a passage question">
  <h4>Ask about a saved passage</h4>
  {finding?<><p>{doc.document_id} · version {doc.version} · selection revision {revision.revision} · line {finding.line}{doc.preview.lines[finding.line-1]?.page ? " · PDF page "+doc.preview.lines[finding.line-1].page : ""}</p><blockquote>{finding.quote}</blockquote>
   <label>Your question<textarea data-testid="passage-question-draft" maxLength={500}
    disabled={busy||!!pending} value={question} onChange={event=>setQuestion(event.target.value)}/></label>
   <button data-testid="save-passage-question" type="button" disabled={busy||question.trim()!==question||question.length<8} onClick={()=>void save()}>{pending?'Retry exact save':'Save passage question'}</button>
   <button disabled={busy||!!pending} type="button" onClick={()=>{generation.current++;setFinding(null);setQuestion('');}}>Discard question draft</button>
  </>:pending?<button type="button" disabled={busy} onClick={()=>void save()}>Retry exact save</button>:doc.state==='current'&&revision.findings.map(item=><button type="button" key={item.key}
   disabled={busy} onClick={()=>void start(item)}>Draft a question about “{item.quote}” (line {item.line})</button>)}
  {!finding&&<button type="button" disabled={busy} onClick={()=>void reopen()}>Open saved passage questions</button>}
  {history&&<div data-testid="saved-passage-questions">{history.length===0?'No saved passage questions.':history.map(row=><article key={row.id}><h5>{row.text}</h5><blockquote>{row.quote}</blockquote><p>Selection revision {row.revision} · line {row.line} · {row.state==='current_unreviewed_selection'?'Current selection':'Source or selection changed'}</p><PassageEvidenceSearch patient={patientId} caseId={caseId} source={doc.source_id} id={row.id} anchor={row.anchor} question={row.text} current={row.state==='current_unreviewed_selection'} session={session}/></article>)}</div>}
  {message&&<p role="status">{message}</p>}
 </section>;
}
