import {StrictMode, useEffect, useRef, useState, useSyncExternalStore} from 'react';
import {createRoot} from 'react-dom/client';
import {RegistrySession} from './registry-client';
import {RecordsPanel} from './records-panel';
import {WorldModelPanel} from './world-model-panel';
import './styles.css';
const session=new RegistrySession();
const unavailable=[['Journey','Longitudinal events and treatment history'],['Review','Reports and accountable review history']];
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
   <nav aria-label="Patient workspace">{['Overview','Records','Investigations',...unavailable.map(s=>s[0])].map(name=><button type="button" key={name} data-testid={name==='Records'?'records-nav':name==='Investigations'?'world-nav':undefined} aria-current={name===section?'page':undefined} onClick={()=>setSection(name)}><span>{name}</span>{name!=='Overview'&&<span className="nav-hint">{name==='Records'?'Authorized reads':name==='Investigations'?'Source-only view':'Not connected'}</span>}</button>)}</nav>
   <div className="rail-note">One patient context.<br/>Original sources.<br/>Human clinical authority.</div>
  </aside>
  <div className="body"><header className="topbar"><span>Patient workspace <span className="muted">/ {section}</span></span><span className={'connection '+readiness} data-testid="readiness">{readiness==='checking'?'Checking API':readiness==='ready'?'PostgreSQL API ready':'API unavailable'}</span></header>
   <main id="main" tabIndex={-1}>
    <div className="heading"><div><p className="eyebrow">OPEN INTELLIGENCE · H1</p><h1>{section==='Overview'?'Start with the right patient.':section}</h1><p className="lede">{section==='Overview'?'A connected foundation for the patient’s story, evidence and care.':section==='Records'?'Original record receipts, source versions, and explicit permissions — anchored to one selected patient.':section==='Investigations'?'Current source-reported observations, provenance and unresolved disagreements — not a clinical assessment.':'This capability remains part of the platform, but is not connected to this H1 API yet.'}</p></div></div>
    <div className="boundary" role="note"><strong>Development workspace, not a clinical service.</strong> Use operator-issued synthetic credentials and fictional identities only. These are not patient accounts, verified consent or professional sign-off.</div>
    {section==='Records'?<RecordsPanel state={state} session={session}/>:section==='Investigations'?<WorldModelPanel key={state.patient?.patient_id||'none'} state={state} session={session}/>:section!=='Overview'?<section className="panel"><h2>{section} is not connected</h2><p>The existing reference application retains this workflow. No placeholder patient data, generated conclusions or clinical actions are shown here.</p><p>The source, evidence and review owners must be integrated with the same scoped patient API before this becomes available.</p><button onClick={()=>setSection('Overview')}>Return to overview</button></section>:<>
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
