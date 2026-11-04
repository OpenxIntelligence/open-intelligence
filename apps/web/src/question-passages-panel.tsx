import {useEffect,useMemo,useRef,useState,useSyncExternalStore} from 'react';
import type {RegistrySession} from './registry-client';
import {DocumentClient} from './reviewed-documents';
import {QuestionPassageClient,decodeSelection,passageReference} from './question-passages';
import type {ManualContext,PassageScope,ResolvedPassage} from './question-passages';

/** Additional record context never changes the primary structured observation. */
export function QuestionPassagesPanel({session,scope,busy,onContext,onSaved}:{session:RegistrySession;scope:PassageScope;busy:boolean;
 onContext:(context:ManualContext|null)=>void;onSaved:()=>void}){
 const client=useMemo(()=>new QuestionPassageClient(scope,body=>session.questionPassageRequest(scope.case_id,scope.question_id,body)),[session,scope.patient_id,scope.case_id,scope.question_id]);
 const documents=useMemo(()=>new DocumentClient((path,body)=>session.documentRequest(scope.case_id,path,body)),[session,scope.patient_id,scope.case_id,scope.question_id]);
 const state=useSyncExternalStore(client.subscribe,client.snapshot,client.snapshot),docs=useSyncExternalStore(documents.subscribe,documents.snapshot,documents.snapshot);
 const [chosen,setChosen]=useState<readonly ResolvedPassage[]>([]),[message,setMessage]=useState(''),[selecting,setSelecting]=useState(false);
 const generation=useRef(0);
 const locked=busy||selecting||['loading','saving','uncertain'].includes(state.phase)||['loading','saving','uncertain'].includes(docs.phase);
 useEffect(()=>{generation.current++;void client.load();return()=>{generation.current++;client.dispose();documents.dispose();};},[client,documents]);
 useEffect(()=>{onContext(state.phase==='idle'?state.packet:null);},[state.packet,state.phase,onContext]);
 useEffect(()=>{setChosen(state.packet?.passages??[]);setMessage('');},[state.packet]);
 const latest=docs.document?.revisions.at(-1);
 async function select(key:string){
  if(locked||!docs.document||!latest||!state.packet||chosen.length>=20)return;
  const stamp=++generation.current,reference={source_id:docs.document.source_id,annotation_revision_id:latest.revision_id,selection_key:key};
  setSelecting(true);setMessage('Rechecking the exact saved passage…');
  try{const reply=await session.documentRequest(scope.case_id,'/'+reference.source_id+'/selections/'+reference.annotation_revision_id+'/'+key);
   if(stamp!==generation.current)return;if(reply.status!==200)throw Error('Saved passage unavailable. Refresh document and permissions.');
   const passage=await decodeSelection(reply.body,scope,reference);if(stamp!==generation.current)return;
   if(passage.selection_state!=='current_unreviewed_selection')throw Error('This selection changed. Refresh the document before attaching it.');
   setChosen(values=>values.some(p=>p.anchor_sha256===passage.anchor_sha256)?values:[...values,passage]);
   setMessage('Passage selected locally. Save the set to attach it to this question.');
  }catch(e){if(stamp===generation.current)setMessage(e instanceof Error?e.message:'Passage unavailable.');}
  finally{if(stamp===generation.current)setSelecting(false);}
 }
 async function save(retry=false){
  const stamp=generation.current;
  if(retry)await client.retry();else await client.replace(chosen.map(passageReference));
  if(stamp===generation.current&&client.snapshot().packet&&client.snapshot().phase==='idle')onSaved();
 }
 return <section data-testid="question-manual-passages" aria-labelledby="manual-context-heading" className="evidence-import">
  <h4 id="manual-context-heading">Additional passages from the patient’s records</h4>
  <p>Attach exact saved text or PDF selections to this question. Their classifications are user-selected and unreviewed; comparisons still concern the primary structured observation.</p>
  <p role="status" data-testid="manual-context-status">{state.message} {message}</p>
  <button type="button" disabled={locked} onClick={()=>void client.load()}>Refresh attached passages</button>
  {state.phase==='uncertain'&&<button type="button" disabled={busy} data-testid="manual-context-retry" onClick={()=>void save(true)}>Retry exact passage set</button>}
  {state.packet&&<>
   <p>Saved context revision {state.packet.revision} · {state.packet.state==='current_unreviewed'?'unreviewed':'reassessment required'}</p>
   <ul data-testid="manual-context-selected">{chosen.map(p=><li key={p.anchor_sha256}>
    <blockquote>{p.anchor.quote}</blockquote>
    <p>{p.anchor.document_id} v{p.anchor.source_version}, line {p.anchor.line}{p.anchor.page!==null?`, physical page ${p.anchor.page}`:''} · user-selected {p.anchor.selected_state} · {p.selection_state==='current_unreviewed_selection'?'unreviewed':'reassessment required'}</p>
    <details><summary>Exact manual provenance</summary><p>{p.anchor.annotation_revision_id} · selected by unverified label {p.anchor.selected_by} at {p.anchor.selected_at}</p><p>Anchor SHA-256 <code>{p.anchor_sha256}</code></p></details>
    <button type="button" disabled={locked} onClick={()=>setChosen(values=>values.filter(row=>row.anchor_sha256!==p.anchor_sha256))}>Remove passage {p.anchor.selection_key}</button>
   </li>)}</ul>
   <button type="button" disabled={locked} data-testid="manual-context-documents" onClick={()=>void documents.load()}>Choose from saved text and PDF records</button>
   <p role="status">{docs.message}</p>
   {docs.documents.length>0&&<ul>{docs.documents.filter(d=>d.state==='current').map(d=><li key={d.source_id}>
    <button type="button" disabled={locked} data-testid="manual-context-document" onClick={()=>void documents.open(d.source_id)}>{d.document_id} v{d.version} · {d.filename}</button>
   </li>)}</ul>}
   {docs.document?.state==='current'&&latest&&<fieldset disabled={locked||chosen.length>=20}><legend>Saved selections from {docs.document.document_id}, revision {latest.revision}</legend>
    {latest.findings.length===0?<p>No saved passages in this revision. Select and save a passage in Records first.</p>:
     latest.findings.map(f=><p key={f.key}><q>{f.quote}</q> · line {f.line} <button type="button" data-testid="manual-context-add" onClick={()=>void select(f.key)}>Choose passage {f.key}</button></p>)}
   </fieldset>}
   <button type="button" className="primary" data-testid="manual-context-save" disabled={locked||chosen.some(p=>p.selection_state!=='current_unreviewed_selection')} onClick={()=>void save()}>Save passage set ({chosen.length}/20)</button>
   <p className="muted">Saving an empty set removes attachments from current context while preserving earlier revisions and reports. Nothing here establishes clinical approval.</p>
  </>}
 </section>;
}
