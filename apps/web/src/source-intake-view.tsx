import {useEffect,useRef,useState} from 'react';
import {prepareSource} from './source-intake';
import type {PreparedSource} from './source-intake';
import type {RegistrySession} from './registry-client';
import {LaboratoryIntake} from './laboratory-fhir-view';
/** File selection never uploads; a context change discards the unsubmitted local preview. */
export function SourceIntake({session,caseId,patientId,sending}:{session:RegistrySession;caseId:string;patientId:string;sending:boolean}){
 const [prepared,setPrepared]=useState<PreparedSource|null>(null),[name,setName]=useState('');
 const [message,setMessage]=useState('No file selected. Nothing is uploaded automatically.'),[confirmed,setConfirmed]=useState(false);
 const file=useRef<HTMLInputElement>(null),generation=useRef(0);
 useEffect(()=>{return()=>{generation.current++}},[caseId,patientId]);
 function discard(){generation.current++;setPrepared(null);setName('');setConfirmed(false);setMessage('Local selection discarded; no import requested.');if(file.current)file.current.value='';}
 async function select(){
  const candidate=file.current?.files?.[0],request=++generation.current;
  setPrepared(null);setConfirmed(false);setName('');if(!candidate)return;
  try{
   if(candidate.size>65536)throw Error('The original exceeds 64 KiB. Nothing was read or sent.');
   const data=prepareSource(new Uint8Array(await candidate.arrayBuffer()),candidate.name);
   if(request!==generation.current)return;
   if(new TextEncoder().encode(JSON.stringify({synthetic:true,original_text:data.text})).length>72000)throw Error('The escaped API envelope exceeds 72,000 bytes. Nothing was sent.');
   setPrepared(data);setName(candidate.name);
   setMessage(data.declaredCase===caseId?'Inspect the exact original below before confirming import.':'Different declared case: it will be quarantined, not attached or relabeled.');
  }catch(e){if(request===generation.current)setMessage(e instanceof Error?e.message:'Unable to inspect this file.');}
 }
 return <><section className="intake-panel" aria-labelledby="source-intake-heading" data-testid="source-intake">
  <h3 id="source-intake-heading">Add an original fictional record</h3>
  <p>Patient <code>{patientId}</code> · case <code>{caseId}</code>. Only authored <code>OI-SYNTHETIC-REPORT/1</code> UTF-8 text with LF line endings is supported here. No PDF extraction or clinical inference.</p>
  <form onSubmit={e=>{e.preventDefault();if(prepared)void session.importSource(caseId,prepared.text,confirmed)}}>
   <label htmlFor="original-file">Original .txt file (up to 64 KiB)</label>
   <input ref={file} id="original-file" type="file" accept=".txt,text/plain" disabled={sending} onChange={()=>void select()} aria-describedby="file-status"/>
   <p id="file-status" role="status" aria-live="polite">{message}</p>
   {prepared&&<div data-testid="file-preview"><p><strong>{name}</strong> · {prepared.byteLength} bytes · declared case <code>{prepared.declaredCase}</code></p><pre className="original-text" data-testid="local-original" tabIndex={0} role="region" aria-label="Selected file text, not imported" onFocus={event=>event.currentTarget.scrollIntoView({block:'center'})}>{prepared.text}</pre></div>}
   <label className="check"><input id="original-confirm" type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)} disabled={!prepared||sending}/>This is independently authored fictional text; I have inspected the selected original and case.</label>
   <div className="actions"><button className="primary" data-testid="import-original" disabled={!prepared||!confirmed||sending}>{sending?'Import in progress…':'Import this original'}</button><button type="button" onClick={discard} disabled={sending}>Discard selection</button></div>
  </form>
  <p className="small muted">The server rechecks authority. A missing reply can leave the outcome unknown; no automatic retry or rollback is assumed.</p>
 </section><LaboratoryIntake session={session} patientId={patientId} caseId={caseId} disabled={sending}/></>;
}
