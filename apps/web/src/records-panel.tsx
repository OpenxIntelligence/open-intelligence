import type {RegistrySession,ViewState} from './registry-client';

const receiptLabel={
  not_received:'Awaiting a linked original',
  source_current_unreviewed:'Received original · not clinically reviewed',
  source_superseded_reconciliation_required:'Historical source · reconciliation required',
  binding_revoked_not_usable:'Patient/case binding withdrawn · source unusable',
} as const;

/** Read-only H1 clinical-source custody view; no clinical review or send action. */
export function RecordsPanel({state,session}:{state:ViewState;session:RegistrySession}){
 const patient=state.patient;
 return <section className="panel records-panel" aria-labelledby="records-heading">
  <span className="step">RECORD ACQUISITION / ORIGINAL SOURCE CUSTODY</span>
  <h2 id="records-heading">Authorized record requests</h2>
  <p>The request list, source receipt and exact original remain separate permissions.
  These are fictional operational records, not a confirmed hospital response or clinical approval.</p>
  {!patient?<div role="status"><strong>No authorized patient selected.</strong>
    <p>Open an explicitly granted patient on Overview. A created identity does not grant record access.</p></div>:<>
   <div className="record-toolbar"><div><strong>Selected patient</strong>
      <p><code>{patient.patient_id}</code></p></div>
      <button type="button" className="primary" data-testid="load-records"
        disabled={state.recordsPhase==='loading'}
        onClick={()=>void session.loadRecords()}>
        {state.recordsPhase==='loading'?'Checking grant…':'Refresh authorized requests'}
      </button></div>
   <p className={'status '+(state.recordsPhase==='error'?'error':'')} role="status"
     aria-live="polite" data-testid="records-status">{state.recordsMessage}</p>
   {state.records&&<div data-testid="record-requests">
    {state.records.length===0?<p>No record requests are available to this session.</p>:
     <ul className="record-list">{state.records.map(item=><li className="record-item" key={item.request_id}>
      <div className="record-title"><div><span className="step">{item.kind.toUpperCase()}</span>
       <h3>{item.record_label}</h3></div><span className="record-state">{item.status}</span></div>
      <p><strong>Receipt:</strong> {receiptLabel[item.receipt_status]}</p>
      <p><strong>Institution label (unverified):</strong> {item.source_organization}</p>
      <p><strong>Last operational activity:</strong> <time dateTime={item.updated_at}>{item.updated_at}</time></p>
      {item.source_reference?<div className="record-reference">
        <p><strong>Case:</strong> <code>{item.source_reference.case_id}</code></p>
        <p><strong>Exact original:</strong> <code>{item.source_reference.source_id}</code> · version {item.source_reference.version}</p>
        <p><strong>SHA-256:</strong> <code>{item.source_reference.sha256}</code></p>
        <button type="button" data-testid="view-original"
         disabled={state.originalPhase==='loading'}
         onClick={()=>void session.openOriginal(item.source_reference!.case_id,item.source_reference!.source_id)}>
         Read exact original (separate permission)
        </button>
      </div>:<p className="muted">No source identifier is disclosed under the current grant/binding.</p>}
     </li>)}</ul>}
    </div>}
   <p className={'status '+(state.originalPhase==='error'?'error':'')} role="status"
     aria-live="polite" data-testid="original-status">{state.originalMessage}</p>
   {state.original&&<section className="original-custody" aria-labelledby="original-heading" data-testid="original-report">
    <span className="step">EXACT ORIGINAL · FICTIONAL ONLY</span>
    <h3 id="original-heading">{state.original.document_id} · Version {state.original.version}</h3>
    <p><strong>Source status:</strong> {state.original.state==='superseded'?
      'Historical / superseded — not safe as current':'Current in this fictional source store — not clinically verified'}</p>
    <p><strong>Review:</strong> Not established. This source is not a diagnosis, clinical conclusion or approved report.</p>
    <pre>{state.original.original_text}</pre>
   </section>}
  </>}
 </section>;
}
