import {StrictMode, useEffect, useRef, useState, useSyncExternalStore} from 'react';
import {createRoot} from 'react-dom/client';
import {RegistrySession} from './registry-client';
import './styles.css';
const session=new RegistrySession();
const navigation=['Overview','Journey','Records','Investigations','Review'];
function App(){
 const state=useSyncExternalStore(session.subscribe,session.snapshot);
 const [token,setToken]=useState(''),[patientId,setPatientId]=useState(''),[confirmed,setConfirmed]=useState(false);
 const [requestKey,setRequestKey]=useState(()=>crypto.randomUUID());
 const [readiness,setReadiness]=useState<'checking'|'ready'|'unavailable'>('checking');
 const [section,setSection]=useState('Overview');
 const keyForReceipt=useRef(requestKey);
 useEffect(()=>{let active=true;const c=new AbortController();const timer=setTimeout(()=>c.abort(),5000);
  fetch('/health/ready',{signal:c.signal,credentials:'omit',redirect:'error',cache:'no-store'})
   .then(async r=>{const v=await r.json();if(active)setReadiness(r.ok&&v.status==='ready'?'ready':'unavailable')})
   .catch(()=>{if(active)setReadiness('unavailable')});
  return()=>{active=false;c.abort();clearTimeout(timer)};
 },[]);
 useEffect(()=>{if(state.created) setPatientId(state.created.patient_id)},[state.created]);
 useEffect(()=>{if(!state.connected){setPatientId('');setConfirmed(false)}},[state.connected]);
 useEffect(()=>{const clear=()=>session.disconnect();window.addEventListener('pagehide',clear);return()=>window.removeEventListener('pagehide',clear)},[]);
 const busy=state.phase==='creating'||state.phase==='reading';
 function disconnect(){session.disconnect();setToken('');setPatientId('');setConfirmed(false);setSection('Overview');}
 return <div className="app">
  <a className="skip" href="#main">Skip to workspace</a>
  <aside className="rail" aria-label="Workspace navigation">
   <div className="brand"><span className="mark" aria-hidden="true">oi</span><span>Open<br/>Intelligence</span></div>
   <div className="environment">Development · fictional identities only</div>
   <nav aria-label="Patient workspace">{navigation.map(name=><button type="button" key={name} aria-current={name===section?'page':undefined} onClick={()=>setSection(name)}><span>{name}</span>{name==='Records'?<span className="nav-hint">Read-only H1</span>:name!=='Overview'?<span className="nav-hint">Not connected</span>:null}</button>)}</nav>
   <div className="rail-note">One patient context.<br/>Original sources.<br/>Human clinical authority.</div>
  </aside>
  <div className="body"><header className="topbar"><span>Patient workspace <span className="muted">/ {section}</span></span><span className={'connection '+readiness} data-testid="readiness">{readiness==='checking'?'Checking API':readiness==='ready'?'PostgreSQL API ready':'API unavailable'}</span></header>
   <main id="main" tabIndex={-1}>
    <div className="heading"><div><p className="eyebrow">OPEN INTELLIGENCE · H1</p><h1>{section==='Overview'?'Start with the right patient.':section}</h1><p className="lede">{section==='Overview'?'A connected foundation for the patient’s story, evidence and care.':section==='Records'?'Inspect authorized fictional case mappings, original source history and unreviewed source statements.':'This capability remains part of the platform, but is not connected to this H1 API yet.'}</p></div></div>
    <div className="boundary" role="note"><strong>Development workspace, not a clinical service.</strong> Use operator-issued synthetic credentials and fictional identities only. These are not patient accounts, verified consent or professional sign-off.</div>
    {section==='Records'?<section className="panel records-workspace" data-testid="records-workspace" aria-labelledby="records-heading">
     <span className="step">READ ONLY / CANONICAL SOURCE OWNER</span>
     <h2 id="records-heading">Original source records</h2>
     <p>Shows source-reported information from the existing scoped PostgreSQL API. No original document bytes, AI interpretation, clinical decision, identity verification or consent is available from this screen. Information is current only at its last successful check.</p>
     {!state.patient?<div data-testid="records-no-patient"><p>Open an authorized fictional patient in Overview before loading records.</p><button onClick={()=>setSection('Overview')}>Go to patient overview</button></div>:
     <div>
      <p className="record-scope" data-testid="records-patient"><strong>Selected patient:</strong> <code>{state.patient.patient_id}</code></p>
      <button className="primary" data-testid="load-cases" disabled={state.recordsPhase.startsWith('loading')||busy} onClick={()=>void session.loadCases()}>Check authorized cases</button>
      <p role="status" aria-live="polite" data-testid="records-status" className={'status '+(state.recordsPhase==='error'?'error':'')}>{state.recordMessage}</p>
      <section className="request-work" data-testid="record-requests-workspace" aria-labelledby="requests-heading">
       <h3 id="requests-heading">Records to obtain</h3>
       <p>Operational tracking only: these fictional requests do not contact an institution, order a test, verify a document or establish medical need. Access requires a separate request-read grant.</p>
       <button data-testid="load-record-requests" disabled={state.requestPhase==='loading'||busy} onClick={()=>void session.loadRecordRequests()}>Check request and receipt status</button>
       <p role="status" aria-live="polite" data-testid="request-status" className={'status '+(state.requestPhase==='error'?'error':'')}>{state.requestMessage}</p>
       {state.recordRequests&&<div data-testid="record-request-list">
        {state.recordRequests.requests.length===0?<p>No fictional records are currently tracked as requested.</p>:
         <ul className="case-list">{state.recordRequests.requests.map(item=><li key={item.request_id} className="case-row" data-testid="record-request-item">
          <strong>{item.record_label}</strong> <span className="record-state">{item.receipt_status.replaceAll('_',' ')}</span>
          <p>Category: {item.kind} · Listed institution: {item.source_organization}</p>
          <p>Local tracking state: {item.status} · Last recorded: {item.updated_at}</p>
          {item.receipt_status==='source_superseded_reconciliation_required'&&<p data-testid="request-reconcile">Original source superseded; explicit reconciliation required. Earlier receipt remains historical.</p>}
          {item.receipt_status==='binding_revoked_not_usable'&&<p>Patient/case binding revoked; the source receipt is not usable.</p>}
          {item.source_reference?<dl className="source-metadata" data-testid="request-source-reference">
           <div><dt>Bound case</dt><dd><code>{item.source_reference.case_id}</code></dd></div>
           <div><dt>Original ID</dt><dd><code>{item.source_reference.source_id}</code></dd></div>
           <div><dt>Source version</dt><dd>{item.source_reference.version}</dd></div>
           <div><dt>Original SHA-256</dt><dd><code>{item.source_reference.sha256}</code></dd></div>
          </dl>:<p data-testid="request-source-withheld">No original-source identifier disclosed by this request-read result. Source access requires a separate grant.</p>}
         </li>)}</ul>}
       </div>}
      </section>
      {state.cases!==null&&<section aria-labelledby="case-list-heading" data-testid="records-cases">
       <h3 id="case-list-heading">Case mappings</h3>
       {state.cases.length===0?<p>No current authorized case mappings were returned.</p>:
        <ul className="case-list">{state.cases.map(item=><li key={item.case_id} className="case-row" data-testid="case-row">
         <div><strong><code>{item.case_id}</code></strong><span className="record-state"> {item.status}</span></div>
         <p>Origin: {item.source_organization} · System: {item.source_system} · Version {item.revision}</p>
         <p>Fictional identity verification: not established. Clinical sources automatically linked: no.</p>
         <button data-testid="load-sources" disabled={item.status!=='active'||state.recordsPhase.startsWith('loading')} onClick={()=>void session.loadSources(item.case_id)}>Inspect source versions</button>
        </li>)}</ul>}
      </section>}
      {state.sourceIndex&&<section className="records-detail" data-testid="source-index" aria-labelledby="sources-heading">
       <h3 id="sources-heading">Source history for <code>{state.sourceIndex.case_id}</code></h3>
       <p>Immutable original source identifiers, hashes and historical versions. These records are independently fictional.</p>
       {state.sourceIndex.sources.length===0?<p>No imported original sources for this case.</p>:
        <ol className="source-list">{state.sourceIndex.sources.map(item=><li key={item.source_id} data-testid="source-version">
         <div className="source-heading"><strong>{item.document_id} · v{item.version}</strong><span className="record-state">{item.state}</span></div>
         <dl className="source-metadata">
          <div><dt>Type</dt><dd>{item.kind}</dd></div><div><dt>Event date</dt><dd>{item.event_date}</dd></div>
          <div><dt>Issued</dt><dd>{item.issued_at}</dd></div><div><dt>Specimen</dt><dd>{item.specimen_id??'Not recorded'}</dd></div>
          <div><dt>Original source ID</dt><dd><code>{item.source_id}</code></dd></div>
          <div><dt>Original SHA-256</dt><dd><code>{item.sha256}</code></dd></div>
          {item.supersedes_id&&<div><dt>Supersedes</dt><dd><code>{item.supersedes_id}</code></dd></div>}
         </dl></li>)}</ol>}
       <h3>Source-reported findings from current versions</h3>
       <p>Statements below are unreviewed quotations reported by fictional input files, not independently established clinical facts.</p>
       {state.sourceIndex.source_reported_assertions.length===0?<p>No source-reported assertions were returned.</p>:
        <ul className="finding-list">{state.sourceIndex.source_reported_assertions.map((finding,i)=><li key={finding.source_id+':'+finding.source_line+':'+i} data-testid="source-finding">
         <p><strong>{finding.finding_key}</strong> · reported state: {finding.reported_state} · line {finding.source_line}</p>
         <blockquote data-testid="source-statement">{finding.source_statement}</blockquote>
         <small>Review state: not established · <code>{finding.source_id}</code></small>
        </li>)}</ul>}
       <p className="muted">Amendments are preserved as separate versions. Research/review invalidation is not yet integrated with this PostgreSQL screen.</p>
      </section>}
     </div>}
    </section>:section!=='Overview'?<section className="panel"><h2>{section} is not connected</h2><p>The existing reference application retains this workflow. No placeholder patient data, generated conclusions or clinical actions are shown here.</p><p>The source, evidence and review owners must be integrated with the same scoped patient API before this becomes available.</p><button onClick={()=>setSection('Overview')}>Return to overview</button></section>:<>
    <div className="grid">
     <section className="panel" aria-labelledby="access-heading"><span className="step">01 / ACCESS</span><h2 id="access-heading">Connect your session</h2><p>Permission is checked by the API on every request. Your credential stays in this tab’s memory and is cleared on disconnect or reload.</p>
      {!state.connected?<form onSubmit={e=>{e.preventDefault();session.connect(token);setToken('')}}><label htmlFor="credential">Synthetic access credential</label><input id="credential" name="credential" type="password" autoComplete="off" autoCapitalize="none" spellCheck={false} value={token} onChange={e=>setToken(e.target.value)} required minLength={32} maxLength={256}/><button type="submit" className="primary">Connect credential</button></form>:<div><p className="session-status">Credential present · grants checked by server</p><button onClick={disconnect}>Disconnect and clear</button></div>}
     </section>
     <section className="panel" aria-labelledby="patient-heading"><span className="step">02 / PATIENT</span><h2 id="patient-heading">Open an authorized identity</h2><p>Enter the exact opaque patient ID. Creating an identity does not automatically grant permission to read it.</p><form onSubmit={e=>{e.preventDefault();void session.read(patientId)}}><label htmlFor="patient-id">Patient ID</label><input id="patient-id" value={patientId} onChange={e=>setPatientId(e.target.value)} autoComplete="off" spellCheck={false} disabled={!state.connected||state.phase==='creating'} required maxLength={128}/><button className="primary" disabled={!state.connected||busy}>Open patient</button></form></section>
    </div>
    <p className={'status '+(state.phase==='error'?'error':'')} role="status" aria-live="polite" data-testid="status">{state.message}</p>
    {state.patient&&<section className="panel patient" data-testid="patient-card"><span className="step">LATEST SUCCESSFUL REGISTRY RESPONSE</span><h2>Patient identity</h2><dl><div><dt>Patient ID</dt><dd>{state.patient.patient_id}</dd></div><div><dt>Organization</dt><dd>{state.patient.origin_org}</dd></div><div><dt>Registry status</dt><dd>{state.patient.status}</dd></div><div><dt>Revision</dt><dd>{state.patient.revision}</dd></div><div><dt>Created</dt><dd>{state.patient.created_at}</dd></div></dl><p className="muted">Identity metadata only, authorized at the last successful request. Recheck access for current permissions. No clinical record or conclusion has been loaded.</p><button disabled={busy} onClick={()=>void session.read(state.patient!.patient_id)}>Recheck current access</button></section>}
    <details className="panel create-panel"><summary>Create a fictional patient identity</summary><p>This uses the existing canonical registry. No names or clinical details are accepted. Your credential needs a separate create action.</p><form onSubmit={e=>{e.preventDefault();keyForReceipt.current=requestKey;void session.create(requestKey,confirmed)}}><label htmlFor="request-key">Creation request key</label><input id="request-key" value={requestKey} readOnly/><p className="muted small">Keep the same key when retrying an uncertain response. The server prevents duplicate identities.</p><label className="check"><input id="synthetic-confirm" type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)} disabled={!state.connected||busy}/>This is an independently fictional identity, not a real person.</label><div className="actions"><button disabled={!state.connected||!confirmed||busy} className="primary">Create fictional identity</button><button type="button" disabled={busy||!state.created||keyForReceipt.current!==requestKey} onClick={()=>{setRequestKey(crypto.randomUUID());setConfirmed(false)}}>Start a different creation</button></div></form>{state.created&&<p data-testid="created-id">{state.created.duplicate?'Existing identity recovered: ':'Identity created: '}<code>{state.created.patient_id}</code><br/>The operator must separately grant access to this ID before it can be read.</p>}</details>
    </>}
    <footer>FastAPI · PostgreSQL 16 · React · TypeScript <span>No live model or external biomedical data is used by this screen.</span></footer>
   </main>
  </div>
 </div>;
}
createRoot(document.getElementById('root')!).render(<StrictMode><App/></StrictMode>);
