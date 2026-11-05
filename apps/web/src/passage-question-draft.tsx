import {useEffect,useRef,useState} from 'react';
import type {Document,Finding} from './reviewed-documents';
import {decodeChosenPassage,decodeSelection} from './question-passages';
import type {RegistrySession} from './registry-client';

export function PassageQuestionDraft({doc,session,patientId,caseId}:{
 doc:Document;session:RegistrySession;patientId:string;caseId:string;
}){
 const revision=doc.revisions.at(-1);
 const generation=useRef(0);
 const [finding,setFinding]=useState<Finding|null>(null);
 const [question,setQuestion]=useState('');
 const [digest,setDigest]=useState('');
 const [pending,setPending]=useState<string|null>(null);
 const [busy,setBusy]=useState(false);
 const [history,setHistory]=useState<{id:string;text:string;quote:string;line:number;revision:number;state:string}[]|null>(null);
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
  if(!finding||!revision||busy)return;
  const request=++generation.current;
  const body=pending??JSON.stringify({synthetic:true,request_key:'DQ-'+crypto.randomUUID(),question,
   revision_id:revision.revision_id,selection_key:finding.key,anchor_sha256:digest});
  setPending(body);setBusy(true);setHistory(null);
  try{
   const reply=await session.documentRequest(caseId,'/'+doc.source_id+'/questions',body);
   if(request!==generation.current)return;
   if([403,404,409,422].includes(reply.status)){setPending(null);setMessage('Save refused. Reopen the record to check the current passage.');return;}
   const result=reply.body as {question_id?:string;duplicate?:boolean}|null;
   if(![200,201].includes(reply.status)||!result||!/^QUESTION-[A-F0-9]{32}$/.test(result.question_id??'')||
      result.duplicate!==(reply.status===200))throw Error();
   setPending(null);setFinding(null);setQuestion('');setMessage('Question saved. Open saved passage questions to read it again.');
  }catch{if(request===generation.current)setMessage('Save outcome unknown. Retry this exact question.');}
  finally{if(request===generation.current)setBusy(false);}
 }
 async function reopen(){
  const request=++generation.current;setHistory(null);setBusy(true);setMessage('');
  try{
   const reply=await session.documentRequest(caseId,'/'+doc.source_id+'/questions');
   const data=reply.body as {patient_id:string;case_id:string;source_id:string;questions:Array<{question_id:string;question:string;selection:Parameters<typeof decodeSelection>[0]}>};
   if(reply.status!==200||data.patient_id!==patientId||data.case_id!==caseId||data.source_id!==doc.source_id||!Array.isArray(data.questions)||data.questions.length>250)throw Error();
   const rows=await Promise.all(data.questions.map(async row=>{
    const selection=row.selection as {anchor:{annotation_revision_id:string;selection_key:string}};
    const anchor=selection.anchor;
    const verified=await decodeSelection({...selection,access_receipt_id:reply.headers?.get('X-Access-Receipt-ID')},{patient_id:patientId,case_id:caseId},
     {source_id:doc.source_id,annotation_revision_id:anchor.annotation_revision_id,selection_key:anchor.selection_key});
    if(!/^QUESTION-[A-F0-9]{32}$/.test(row.question_id)||typeof row.question!=='string'||verified.anchor.original_sha256!==doc.sha256)throw Error();
    return {id:row.question_id,text:row.question,quote:verified.anchor.quote,line:verified.anchor.line,revision:verified.anchor.annotation_revision,state:verified.selection_state};
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
  </>:doc.state==='current'&&revision.findings.map(item=><button type="button" key={item.key}
   disabled={busy} onClick={()=>void start(item)}>Draft a question about “{item.quote}” (line {item.line})</button>)}
  {!finding&&<button type="button" disabled={busy} onClick={()=>void reopen()}>Open saved passage questions</button>}
  {history&&<div data-testid="saved-passage-questions">{history.length===0?'No saved passage questions.':history.map(row=><article key={row.id}><h5>{row.text}</h5><blockquote>{row.quote}</blockquote><p>Selection revision {row.revision} · line {row.line} · {row.state==='current_unreviewed_selection'?'Current selection':'Source or selection changed'}</p></article>)}</div>}
  {message&&<p role="status">{message}</p>}
 </section>;
}
