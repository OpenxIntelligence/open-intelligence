import {useEffect,useRef,useState} from 'react';
import type {Document,Finding} from './reviewed-documents';
import {decodeChosenPassage} from './question-passages';
import type {RegistrySession} from './registry-client';

export function PassageQuestionDraft({doc,session,patientId,caseId}:{
 doc:Document;session:RegistrySession;patientId:string;caseId:string;
}){
 const revision=doc.revisions.at(-1);
 const generation=useRef(0);
 const [finding,setFinding]=useState<Finding|null>(null);
 const [question,setQuestion]=useState('');
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
   await decodeChosenPassage(result.body,{patient_id:patientId,case_id:caseId},doc,chosen);
   if(request!==generation.current)return;
   setFinding(chosen);setMessage('');
  }catch{
   if(request===generation.current)setMessage('Reopen the record and check access to this passage.');
  }
 }
 if(!revision?.findings.length)return null;
 return <section aria-label="Draft a passage question">
  <h4>Ask about a saved passage</h4>
  {finding?<><p>{doc.document_id} · version {doc.version} · selection revision {revision.revision} · line {finding.line}{doc.preview.lines[finding.line-1]?.page ? " · PDF page "+doc.preview.lines[finding.line-1].page : ""}</p><blockquote>{finding.quote}</blockquote>
   <label>Your question<textarea data-testid="passage-question-draft" maxLength={500}
    value={question} onChange={event=>setQuestion(event.target.value)}/></label>
   <p>This is a local draft. Refreshing the record or leaving the editor discards it.</p>
   <button type="button" onClick={()=>{generation.current++;setFinding(null);setQuestion('');}}>Discard question draft</button>
  </>:revision.findings.map(item=><button type="button" key={item.key}
   onClick={()=>void start(item)}>Draft a question about “{item.quote}” (line {item.line})</button>)}
  {message&&<p role="status">{message}</p>}
 </section>;
}
