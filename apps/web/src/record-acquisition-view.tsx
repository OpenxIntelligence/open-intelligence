import {useState,useSyncExternalStore} from 'react';
import type {RegistrySession,ViewState} from './registry-client';
import {RECORD_KINDS,eligibleSources,receiptLabel} from './record-acquisition';
import type {RecordRequest} from './record-acquisition';
import './record-acquisition.css';

function RequestRow({row,session,state,busy}:{row:RecordRequest;session:RegistrySession;state:ViewState;busy:boolean}){
 const [sourceId,setSourceId]=useState(''),[reason,setReason]=useState(''),[confirmed,setConfirmed]=useState(false);
 const options=eligibleSources(row,state.patient!.patient_id,state.sourceIndex,state.cases);
 const selected=options.find(s=>s.source_id===sourceId);
 return <li className="acquisition-row" data-testid="record-request" data-request-id={row.request_id} data-state={row.status}>
  <div className="acquisition-row-heading"><div><strong>{row.record_label}</strong><p>{row.kind} · {row.source_organization}</p></div>
   <span className={'acquisition-state '+(row.receipt_status==='source_superseded_reconciliation_required'?'attention':'')} data-testid="request-state">{receiptLabel(row)}</span></div>
  <details><summary>Tracking and source details</summary><dl className="source-metadata">
   <div><dt>Tracking ID</dt><dd><code>{row.request_id}</code></dd></div>
   <div><dt>Updated</dt><dd>{row.updated_at}</dd></div>
   <div><dt>Provider contacted</dt><dd>No · internal tracking only</dd></div>
   <div><dt>Clinical review</dt><dd>Not established by receipt</dd></div>
   {row.source_reference?<><div><dt>Linked original</dt><dd><code>{row.source_reference.source_id}</code> · v{row.source_reference.version}</dd></div>
    <div><dt>Case</dt><dd><code>{row.source_reference.case_id}</code></dd></div>
    <div><dt>Original SHA-256</dt><dd><code>{row.source_reference.sha256}</code></dd></div></>:
    row.status==='received'?<div><dt>Source reference</dt><dd>Withheld or unavailable under current source permissions</dd></div>:null}
  </dl></details>
  {row.status==='requested'&&<details className="acquisition-actions"><summary>Link a received original or stop tracking</summary>
   <p>Only an already imported, current {row.kind} source in the selected authorized case can be linked. This does not verify the provider label or establish a complete record.</p>
   <form onSubmit={e=>{e.preventDefault();void session.acquisition.receive(row.request_id,sourceId,confirmed)}}>
    <label htmlFor={'receive-'+row.request_id}>Current original source</label>
    <select id={'receive-'+row.request_id} data-testid="request-source" value={selected?sourceId:''} onChange={e=>{setSourceId(e.target.value);setConfirmed(false)}} disabled={busy} required>
     <option value="">{options.length?'Choose the exact original':'Load matching current sources in Records below'}</option>
     {options.map(s=><option key={s.source_id} value={s.source_id}>{s.document_id} · v{s.version} · {s.specimen_id??'specimen not recorded'} · {s.event_date}</option>)}
    </select>
    <label className="check"><input type="checkbox" data-testid="request-receive-confirm" checked={confirmed} disabled={busy||!selected} onChange={e=>setConfirmed(e.target.checked)}/>I inspected this fictional original and intend to link it to this request.</label>
    <button data-testid="request-receive" className="primary" disabled={busy||!selected||!confirmed}>Record original received</button>
   </form>
   <form className="acquisition-cancel" onSubmit={e=>{e.preventDefault();void session.acquisition.cancel(row.request_id,reason,true)}}>
    <label htmlFor={'cancel-'+row.request_id}>Reason to stop tracking this request</label>
    <input id={'cancel-'+row.request_id} data-testid="request-cancel-reason" value={reason} onChange={e=>setReason(e.target.value)} maxLength={200} disabled={busy} required/>
    <button data-testid="request-cancel" disabled={busy||!reason.trim()}>Stop tracking request</button>
   </form>
  </details>}
 </li>;
}

export function RecordAcquisitionPanel({session,state,busy}:{session:RegistrySession;state:ViewState;busy:boolean}){
 const acquisition=useSyncExternalStore(session.acquisition.subscribe,session.acquisition.snapshot);
 const [confirmed,setConfirmed]=useState(false);
 if(!state.patient)return null;
 const locked=busy||acquisition.writePhase==='sending'||acquisition.writePhase==='unknown';
 const counts=acquisition.requests?{requested:acquisition.requests.filter(r=>r.status==='requested').length,received:acquisition.requests.filter(r=>r.status==='received').length,cancelled:acquisition.requests.filter(r=>r.status==='cancelled').length}:null;
 return <section className="record-acquisition" data-testid="record-acquisition" aria-labelledby="record-acquisition-heading">
  <div className="acquisition-heading"><div><p className="eyebrow">RECORD ACQUISITION</p><h3 id="record-acquisition-heading">Track what is still needed</h3></div>
   <button data-testid="load-record-requests" disabled={busy||acquisition.phase==='loading'} onClick={()=>void session.acquisition.load()}>Check request history</button></div>
  <p>Track a missing record and link its exact original when it arrives. Saving here does not contact a hospital or laboratory.</p>
  <p role="status" aria-live="polite" data-testid="acquisition-status">{acquisition.message}</p>
  {counts&&<p className="acquisition-counts" data-testid="acquisition-counts"><strong>{counts.requested}</strong> awaiting records · <strong>{counts.received}</strong> original receipts · <strong>{counts.cancelled}</strong> cancelled<br/><small>Counts cover tracked requests only, not every record the patient may need.</small></p>}
  {acquisition.writePhase!=='idle'&&<div role="status" aria-live="polite" className={'status '+(acquisition.writePhase==='unknown'||acquisition.writePhase==='rejected'?'error':'')} data-testid="acquisition-write" data-state={acquisition.writePhase}>
   <p>{acquisition.writeMessage}</p>{acquisition.receipt&&<p>Tracking ID: <code>{acquisition.receipt.request_id}</code>{acquisition.receipt.duplicate?' · existing receipt recovered':''}</p>}
   {acquisition.writePhase==='unknown'&&<><p>The saved {acquisition.intent?.operation} action is retained for this patient in this tab. Other actions stay held until it is resolved. Reloading or disconnecting clears this local intent; inspect server history before creating another request.</p>
    <button data-testid="acquisition-retry" disabled={busy} onClick={()=>void session.acquisition.retry()}>Retry exact saved action</button></>}
  </div>}
  <details className="acquisition-create"><summary>Track a needed record</summary>
   <form data-testid="request-create-form" onSubmit={e=>{e.preventDefault();void session.acquisition.create(confirmed)}}>
    <div className="acquisition-fields"><div><label htmlFor="record-kind">Record category</label><select id="record-kind" data-testid="request-kind" value={acquisition.draft.kind} disabled={locked} onChange={e=>session.acquisition.setDraft({...acquisition.draft,kind:e.target.value})}>{RECORD_KINDS.map(kind=><option key={kind} value={kind}>{kind[0].toUpperCase()+kind.slice(1)}</option>)}</select></div>
    <div><label htmlFor="record-label">What record is needed?</label><input id="record-label" data-testid="request-label" maxLength={140} required disabled={locked} value={acquisition.draft.record_label} onChange={e=>session.acquisition.setDraft({...acquisition.draft,record_label:e.target.value})} placeholder="For example, a fictional pathology report"/></div>
    <div><label htmlFor="record-provider">Source organization label</label><input id="record-provider" data-testid="request-provider" maxLength={100} required disabled={locked} value={acquisition.draft.source_organization} onChange={e=>session.acquisition.setDraft({...acquisition.draft,source_organization:e.target.value})} placeholder="Fictional laboratory"/></div></div>
    <label className="check"><input type="checkbox" data-testid="request-create-confirm" disabled={locked} checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>This is independently fictional information. I am recording a need, not sending a request.</label>
    <button className="primary" data-testid="request-create" disabled={locked||!confirmed||!acquisition.draft.record_label.trim()||!acquisition.draft.source_organization.trim()}>Save tracked record need</button>
   </form>
  </details>
  {acquisition.requests&&<ul className="acquisition-list" data-testid="record-request-list">{acquisition.requests.map(row=><RequestRow key={row.request_id+':'+state.sourceIndex?.access_receipt_id} row={row} session={session} state={state} busy={locked||state.recordsPhase.startsWith('loading')}/>)}</ul>}
 </section>;
}
