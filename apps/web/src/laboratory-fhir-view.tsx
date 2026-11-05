import {useEffect,useRef,useState,useSyncExternalStore} from 'react';
import {prepareLaboratoryFile} from './laboratory-fhir';
import {LABORATORY_PREVIEW_REJECTED,LaboratoryPreviewRejected} from './laboratory-preview';
import type {LaboratoryPreview} from './laboratory-preview';
import type {LaboratoryFile} from './laboratory-fhir';
import type {RegistrySession} from './registry-client';

function LaboratoryResults({preview}:{preview:LaboratoryPreview}) {
  return <section className="record-scope" data-testid="laboratory-preview-results" aria-labelledby="laboratory-results-heading">
    <h4 id="laboratory-results-heading">Source-reported results</h4>
    <p>{preview.specimen_type_text} · <code>{preview.specimen_reference}</code><br/>
      Collected <time>{preview.specimen_collected_at}</time><br/>
      {preview.report_reference ? <>Report <code>{preview.report_reference}</code></> :
        'This file has no diagnostic report. Import requires a report.'}</p>
    <ul className="world-observations">{preview.observations.map(row=>
      <li key={row.reference}><strong>LOINC {row.loinc_code}</strong>
        <div>{row.status==='reported_value' ? <>{row.value_text} {row.unit_code} (UCUM)</> :
          <>Result absent · source reason: {row.absent_reason}</>}</div>
        <div className="small"><code>{row.reference}</code><br/>
          Effective <time>{row.effective_at}</time> · Issued <time>{row.issued_at}</time></div>
      </li>)}</ul>
  </section>;
}

/** Selection is local; only explicit confirmation sends an original to canonical custody. */
export function LaboratoryIntake({session,patientId,caseId,disabled=false}:{
  session:RegistrySession;patientId:string;caseId:string;disabled?:boolean;
}){
  const state=useSyncExternalStore(session.subscribe,session.snapshot);
  const [file,setFile]=useState<LaboratoryFile|null>(null),[name,setName]=useState('');
  const [confirmed,setConfirmed]=useState(false),[previous,setPrevious]=useState('');
  const [message,setMessage]=useState('Select a fictional JSON original. Selection does not upload it.');
  const [previewState,setPreviewState]=useState<LaboratoryPreview|'loading'|'rejected'|null>(null);
  const preview=typeof previewState==='object' ? previewState : null;
  const previewing=previewState==='loading';
  const generation=useRef(0),input=useRef<HTMLInputElement>(null);
  const scoped=state.laboratoryIntent?.patient_id===patientId&&state.laboratoryIntent?.case_id===caseId;
  const pending=scoped&&['sending','unknown'].includes(state.laboratoryPhase);
  const locked=disabled||pending;
  const canConfirm=!!file && !locked && !previewing && previewState!=='rejected' && preview?.report_reference!==null;
  const canImport=canConfirm && confirmed;
  useEffect(()=>{generation.current++;setFile(null);setName('');setConfirmed(false);setPrevious('');setPreviewState(null);
    return()=>{generation.current++;};},[patientId,caseId]);
  async function select(candidate?:File){
    if(locked)return;
    const request=++generation.current;setFile(null);setName('');setConfirmed(false);
    setPreviewState(null);setMessage('Select a fictional JSON original.');
    if(!candidate)return;
    try{
      if(candidate.size<1||candidate.size>65536)throw Error('Select a nonempty fictional JSON original up to 64 KiB.');
      const inspected=await prepareLaboratoryFile(new Uint8Array(await candidate.arrayBuffer()),candidate.name);
      if(request!==generation.current)return;
      setFile(inspected);setName(candidate.name);setMessage('File selected locally. Inspect the original or request a structured preview.');
    }catch(e){if(request===generation.current)setMessage(e instanceof Error?e.message:'The original could not be inspected.');}
  }
  async function requestPreview() {
    if(!file || locked || previewing) return;
    const request=++generation.current;
    setPreviewState('loading');setConfirmed(false);setMessage('Checking the file against this case…');
    try {
      const result=await session.previewLaboratory(caseId,file);
      if(request!==generation.current) return;
      setPreviewState(result);setMessage('Preview ready. Results are source-reported and clinically unreviewed.');
    } catch(error) {
      if(request!==generation.current) return;
      if(error instanceof LaboratoryPreviewRejected) {
        setPreviewState('rejected');
        setMessage(error.message===LABORATORY_PREVIEW_REJECTED ? error.message :
          'The preview could not be verified against this file and case. Recheck the selection.');
      } else {
        setPreviewState(null);
        setMessage('Preview unavailable. Retry the preview or inspect the original before confirming import.');
      }
    }
  }
  function discard(){generation.current++;setFile(null);setName('');setConfirmed(false);setPrevious('');
    setPreviewState(null);setMessage('Local selection discarded. No import was requested.');if(input.current)input.current.value='';}
  return <section className="intake-panel" data-testid="laboratory-intake" aria-labelledby="laboratory-heading">
    <h3 id="laboratory-heading">Add structured laboratory results</h3>
    <p>Import an independently authored fictional FHIR R4 laboratory JSON file into this patient’s existing record.
      The supported format contains one patient, one specimen, one final report and 1–16 final observations.</p>
    <p className="small">Patient <code>{patientId}</code> · case <code>{caseId}</code>. Imported results stay unreviewed.</p>
    <form onSubmit={event=>{event.preventDefault();if(file&&canImport)void session.importLaboratory(caseId,file.text,confirmed,previous||null);}}>
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
      {file&&<div>
        <button type="button" data-testid="laboratory-preview" disabled={locked||previewing} onClick={()=>void requestPreview()}>
          Preview results without importing</button>
        <p className="small">Preview sends this fictional file to the case service to check its patient mapping and read the specimen and values.</p>
        {preview&&!pending&&<LaboratoryResults preview={preview}/>}
      </div>}
      <label className="check"><input data-testid="laboratory-confirm" type="checkbox" checked={confirmed} disabled={!canConfirm}
        onChange={event=>setConfirmed(event.target.checked)}/>I confirm this is independently authored fictional data and I have inspected the original, case and report version.</label>
      <div className="actions"><button data-testid="laboratory-import" className="primary" disabled={!canImport}>
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
