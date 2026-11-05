import {useEffect,useRef,useState,useSyncExternalStore} from 'react';
import {prepareLaboratoryFile} from './laboratory-fhir';
import type {LaboratoryFile} from './laboratory-fhir';
import type {RegistrySession} from './registry-client';

/** Selection is local; only explicit confirmation sends an original to canonical custody. */
export function LaboratoryIntake({session,patientId,caseId,disabled=false}:{
  session:RegistrySession;patientId:string;caseId:string;disabled?:boolean;
}){
  const state=useSyncExternalStore(session.subscribe,session.snapshot);
  const [file,setFile]=useState<LaboratoryFile|null>(null),[name,setName]=useState('');
  const [confirmed,setConfirmed]=useState(false),[previous,setPrevious]=useState('');
  const [message,setMessage]=useState('Select a fictional JSON original. Selection does not upload it.');
  const generation=useRef(0),input=useRef<HTMLInputElement>(null);
  const scoped=state.laboratoryIntent?.patient_id===patientId&&state.laboratoryIntent?.case_id===caseId;
  const pending=scoped&&['sending','unknown'].includes(state.laboratoryPhase);
  const locked=disabled||pending;
  useEffect(()=>{generation.current++;setFile(null);setName('');setConfirmed(false);setPrevious('');
    return()=>{generation.current++;};},[patientId,caseId]);
  async function select(candidate?:File){
    if(locked)return;
    const request=++generation.current;setFile(null);setName('');setConfirmed(false);
    if(!candidate)return;
    try{
      if(candidate.size<1||candidate.size>65536)throw Error('Select a nonempty fictional JSON original up to 64 KiB.');
      const inspected=await prepareLaboratoryFile(new Uint8Array(await candidate.arrayBuffer()),candidate.name);
      if(request!==generation.current)return;
      setFile(inspected);setName(candidate.name);setMessage('Inspect the exact original and selected case. Nothing has been sent.');
    }catch(e){if(request===generation.current)setMessage(e instanceof Error?e.message:'The original could not be inspected.');}
  }
  function discard(){generation.current++;setFile(null);setName('');setConfirmed(false);setPrevious('');
    setMessage('Local selection discarded. No import was requested.');if(input.current)input.current.value='';}
  return <section className="intake-panel" data-testid="laboratory-intake" aria-labelledby="laboratory-heading">
    <h3 id="laboratory-heading">Add structured laboratory results</h3>
    <p>Import an independently authored fictional FHIR R4 laboratory JSON file into this patient’s existing record.
      The supported format contains one patient, one specimen, one final report and 1–16 final observations. Each observation can report a quantity, a fictional result code or a reason for an absent result.</p>
    <p className="small">Patient <code>{patientId}</code> · case <code>{caseId}</code>. Imported results stay unreviewed.</p>
    <form onSubmit={event=>{event.preventDefault();if(file&&!locked)void session.importLaboratory(caseId,file.text,confirmed,previous||null);}}>
      <label htmlFor="laboratory-file">Fictional laboratory JSON (up to 64 KiB)</label>
      <input ref={input} id="laboratory-file" data-testid="laboratory-file" type="file" accept=".json,application/json"
        disabled={locked} onChange={event=>void select(event.target.files?.[0])}/>
      <p role="status">{message}</p>
      {file&&<details open><summary>{name} · {file.byteCount} original bytes</summary>
        <p className="small">Original SHA-256 <code>{file.sha256}</code></p>
        <pre className="original-text" data-testid="laboratory-local-original" tabIndex={0} role="region"
          aria-label="Selected laboratory JSON, not imported" onFocus={event=>{
            const reader=event.currentTarget;
            // A resized patient header changes the scroll inset and reader height
            // after native focus. Align after that layout, without reclaiming focus.
            requestAnimationFrame(()=>requestAnimationFrame(()=>{
              if(reader.isConnected&&document.activeElement===reader)reader.scrollIntoView({block:'center'});
            }));
          }}>{file.text}</pre>
      </details>}
      <label htmlFor="laboratory-predecessor">Report version being replaced</label>
      <select id="laboratory-predecessor" data-testid="laboratory-predecessor" value={previous} disabled={locked}
        onChange={event=>{setPrevious(event.target.value);setConfirmed(false);}}>
        <option value="">New report — do not replace an existing version</option>
        {state.sourceIndex?.case_id===caseId&&state.sourceIndex.sources.filter(source=>source.kind==='laboratory'&&source.state==='current').map(source=>
          <option key={source.source_id} value={source.source_id}>{source.document_id} · version {source.version}</option>)}
      </select>
      <p className="small">Select a predecessor only for a correction of that same report. Different specimens and time points remain separate records.</p>
      <label className="check"><input data-testid="laboratory-confirm" type="checkbox" checked={confirmed} disabled={!file||locked}
        onChange={event=>setConfirmed(event.target.checked)}/>I confirm this is independently authored fictional data and I have inspected the original, case and report version.</label>
      <div className="actions"><button data-testid="laboratory-import" className="primary" disabled={!file||!confirmed||locked}>
        {state.laboratoryPhase==='sending'?'Importing laboratory original…':'Import laboratory original'}</button>
        <button type="button" onClick={discard} disabled={locked}>Discard local laboratory selection</button></div>
    </form>
    <p role="status" aria-live="polite" data-testid="laboratory-status">{state.laboratoryMessage}</p>
    {scoped&&state.laboratoryPhase==='unknown'&&<button data-testid="laboratory-retry" disabled={disabled}
      onClick={()=>void session.retryLaboratoryImport()}>Retry exact import to recover its receipt</button>}
    {scoped&&state.laboratoryReceipt&&<p data-testid="laboratory-receipt">Saved original <code>{state.laboratoryReceipt.source_id}</code>
      {' '}· version {state.laboratoryReceipt.version} · {state.laboratoryReceipt.observation_count} source-reported results.
      {' '}Inspect the original in Records or refresh the Patient World Model in Journey.</p>}
    <p className="small muted">No external laboratory connection, unit conversion, reference-range interpretation or clinical approval is performed.</p>
  </section>;
}
