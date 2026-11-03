import {StrictMode, useEffect, useLayoutEffect, useRef, useState, useSyncExternalStore} from 'react';
import {createRoot} from 'react-dom/client';
import {RegistrySession} from './registry-client';
import {SourceIntake} from './source-intake-view';
import {WorldModelView} from './world-model-view';
import {ReviewPanel} from './review-panel';
import {SourceReading, emptySourceFilters} from './source-reading';
import type {ReadingView} from './source-reading';
import './styles.css';
import './source-intake.css';
const session=new RegistrySession();
const navigation=['Overview','Journey','Records','Investigations','Review'];
function WorkspaceContext({section,patientId,readiness,view,onViewChange}:{section:string;patientId:string|null;readiness:'checking'|'ready'|'unavailable';view:ReadingView;onViewChange:(view:ReadingView)=>void}){
 const header=useRef<HTMLElement>(null);
 useLayoutEffect(()=>{
  const element=header.current;if(!element)return;
  const measure=()=>{const height=Math.ceil(element.getBoundingClientRect().height);const sticky=height<=window.innerHeight/2;
   element.dataset.sticky=String(sticky);document.documentElement.style.setProperty('--workspace-offset',`${sticky?height+24:24}px`);};
  measure();const observer=new ResizeObserver(measure);observer.observe(element);window.addEventListener('resize',measure);
  return()=>{observer.disconnect();window.removeEventListener('resize',measure);document.documentElement.style.removeProperty('--workspace-offset');};
 },[]);
 return <header ref={header} className="topbar" aria-label="Current workspace context">
  <div className="workspace-context"><span className="workspace-location">Patient workspace <span className="muted">/ {section}</span></span>
   <span className="workspace-identity" data-testid="workspace-identity">{patientId?<><span className="workspace-context-label">Authorized fictional patient</span> <code>{patientId}</code></>:<span className="muted">No authorized patient open</span>}</span>
  </div>
  <div className="reading-controls"><div><label htmlFor="reading-view">Reading layout</label><select id="reading-view" value={view} onChange={e=>onViewChange(e.target.value as ReadingView)} aria-describedby="reading-view-help"><option value="patient">Patient reading</option><option value="clinical">Clinical reading</option></select><span id="reading-view-help">Presentation only · permissions unchanged</span></div>
  <span role="status" aria-live="polite" className={'connection '+readiness} data-testid="readiness">{readiness==='checking'?'Checking API':readiness==='ready'?'PostgreSQL API ready':'API unavailable'}</span></div>
 </header>;
}
function App(){
 const state=useSyncExternalStore(session.subscribe,session.snapshot);
 const [token,setToken]=useState(''),[patientId,setPatientId]=useState(''),[confirmed,setConfirmed]=useState(false);
 const [requestKey,setRequestKey]=useState(()=>crypto.randomUUID());
 const [readiness,setReadiness]=useState<'checking'|'ready'|'unavailable'>('checking');
 const [section,setSection]=useState('Overview');
 const [view,setView]=useState<ReadingView>('patient');
 const [sourceFilters,setSourceFilters]=useState({scope:state.sourceIndex,...emptySourceFilters});
 const filters=sourceFilters.scope===state.sourceIndex?sourceFilters:emptySourceFilters;
 useEffect(()=>{setSourceFilters({scope:state.sourceIndex,...emptySourceFilters})},[state.sourceIndex]);
 const heading=useRef<HTMLHeadingElement>(null),moveFocus=useRef(false);
 useEffect(()=>{if(moveFocus.current){heading.current?.focus();moveFocus.current=false}},[section]);
 function navigate(next:string){if(next===section){heading.current?.focus();return}moveFocus.current=true;setSection(next)}
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
  const busy=state.phase==='creating'||state.phase==='reading'||state.importOutcome==='sending'||state.questionSavePhase==='saving'||state.reviewReturnPhase==='saving';
 function disconnect(){session.disconnect();setToken('');setPatientId('');setConfirmed(false);setSection('Overview');}
 return <div className="app">
  <a className="skip" href="#main">Skip to workspace</a>
  <aside className="rail" aria-label="Workspace navigation">
   <div className="brand"><span className="mark" aria-hidden="true">oi</span><span>Open<br/>Intelligence</span></div>
   <div className="environment">Development · fictional identities only</div>
   <nav aria-label="Patient workspace">{navigation.map(name=><button type="button" key={name} aria-current={name===section?'page':undefined} onClick={()=>{session.dismissSourceQuotePacket();session.dismissSourceBrief();navigate(name)}}><span>{name}</span>{name==='Records'?<span className="nav-hint">Original records</span>:name==='Journey'?<span className="nav-hint">Source view</span>:name==='Investigations'?<span className="nav-hint">Source questions</span>:name==='Review'?<span className="nav-hint">Verification returns</span>:null}</button>)}</nav>
   <div className="rail-note">One patient context.<br/>Original sources.<br/>Human clinical authority.</div>
  </aside>
  <div className="body"><WorkspaceContext section={section} patientId={state.patient?.patient_id??null} readiness={readiness} view={view} onViewChange={setView}/>
   <main id="main" tabIndex={-1}>
    <div className="heading"><div><p className="eyebrow">OPEN INTELLIGENCE · H1</p><h1 ref={heading} tabIndex={-1}>{section==='Overview'?'Start with the right patient.':section}</h1><p className="lede">{section==='Overview'?'A connected foundation for the patient’s story, evidence and care.':section==='Records'?'Inspect authorized fictional case mappings, original source history and unreviewed source statements.':section==='Journey'?'View source-linked chronology, uncertainty and disagreements without implying clinical assessment.':section==='Investigations'?'Prepare exact source context, save a question and inspect its current or reassessment status. No AI execution or clinical approval.':'Inspect saved questions, record a source verification return and preserve its history as sources change. Clinical approval remains unavailable.'}</p></div></div>
    <div className="boundary" role="note"><strong>Development workspace, not a clinical service.</strong> Use operator-issued synthetic credentials and fictional identities only. These are not patient accounts, verified consent or professional sign-off.</div>
    {section==='Journey'||section==='Investigations'?<WorldModelView session={session} state={state} busy={busy} showQuestions={section==='Investigations'} onOverview={()=>navigate('Overview')} onInvestigations={()=>navigate('Investigations')} onReview={()=>navigate('Review')}/>:section==='Review'?<ReviewPanel key={state.patient?.patient_id??'no-patient'} session={session} state={state} busy={busy} onOverview={()=>navigate('Overview')} onInvestigations={()=>navigate('Investigations')}/>:section==='Records'?<section className="panel records-workspace" data-testid="records-workspace" aria-labelledby="records-heading">
     <span className="step">CANONICAL SOURCE OWNER / ORIGINALS</span>
     <h2 id="records-heading">{view==='patient'?'Records available to you':'Original source records'}</h2>
     <p>Shows source-reported information from the existing scoped PostgreSQL API. Original-text inspection and deliberate import require separate server permissions. AI interpretation, clinical decisions, verified identity and consent are not supplied by this screen. Information is current only at its last successful check.</p>
     {!state.patient?<div data-testid="records-no-patient"><p>Open an authorized fictional patient in Overview before loading records.</p><button onClick={()=>navigate('Overview')}>Go to patient overview</button></div>:
     <div>
      <p className="record-scope" data-testid="records-patient"><strong>Selected patient:</strong> <code>{state.patient.patient_id}</code></p>
      <button className="primary" data-testid="load-cases" disabled={state.recordsPhase.startsWith('loading')||busy} onClick={()=>void session.loadCases()}>Check authorized cases</button>
      <p role="status" aria-live="polite" data-testid="records-status" className={'status '+(state.recordsPhase==='error'?'error':'')}>{state.recordMessage}</p>
      {state.importOutcome!=='idle'&&<p role="status" aria-live="polite" className="status" data-testid="import-receipt" data-outcome={state.importOutcome} data-result={state.importReceipt?.result??''}>{state.importMessage}</p>}
      {state.original&&<section className="original-panel" aria-labelledby="opened-original" data-testid="opened-original">
       <h3 id="opened-original">Exact original: {state.original.document_id} · v{state.original.version}</h3>
       <p>{state.original.state} · SHA-256 <code>{state.original.sha256}</code></p>
       <p>Verified against the selected version metadata. Clinical review: not established. Access was checked for this read.</p>
       <button onClick={()=>session.dismissOriginal()}>Close original</button>
       <pre className="original-text" data-testid="server-original">{state.original.original_text}</pre>
      </section>}
      {state.cases!==null&&<section aria-labelledby="case-list-heading" data-testid="records-cases">
       <h3 id="case-list-heading">Case mappings</h3>
       {state.cases.length===0?<p>No current authorized case mappings were returned.</p>:
        <ul className="case-list">{state.cases.map(item=><li key={item.case_id} className="case-row" data-testid="case-row">
         <div><strong><code>{item.case_id}</code></strong><span className="record-state"> {item.status}</span></div>
         <p>Origin: {item.source_organization} · System: {item.source_system} · Version {item.revision}</p>
         <p>Fictional identity verification: not established. Clinical sources automatically linked: no.</p>
         <button data-testid="load-sources" disabled={item.status!=='active'||state.recordsPhase.startsWith('loading')||busy} onClick={()=>void session.loadSources(item.case_id)}>Inspect source versions</button>
        </li>)}</ul>}
      </section>}
      {state.sourceIndex&&<section className="records-detail" data-testid="source-index" aria-labelledby="sources-heading">
       <h3 id="sources-heading">Source history for <code>{state.sourceIndex.case_id}</code></h3>
       <p>Immutable original source identifiers, hashes and historical versions. These records are independently fictional.</p>
       <SourceIntake key={state.patient.patient_id+':'+state.sourceIndex.case_id} session={session} patientId={state.patient.patient_id} caseId={state.sourceIndex.case_id} sending={state.importOutcome==='sending'}/>
       <p>Source-reported statements are unreviewed quotations, not independently established clinical facts.</p>
       <SourceReading index={state.sourceIndex} view={view} filters={filters}
         onFiltersChange={next=>setSourceFilters({scope:state.sourceIndex,...next})}
         busy={busy||state.recordsPhase.startsWith('loading')}
         investigateBusy={state.worldPhase==='loading'}
         onOpenOriginal={id=>void session.loadOriginal(id)}
         onInvestigate={(id,line)=>{
           const caseId=state.sourceIndex!.case_id;
           session.dismissSourceQuotePacket();session.dismissSourceBrief();
           navigate('Investigations');
           void session.beginQuestionFromSourceReading(caseId,id,line);
         }}/>
       <p className="muted">Amendments are preserved as separate versions. Use Investigations for source-linked questions and follow-up work, or Review for verification returns. Clinical approval is not supplied by this screen.</p>
      </section>}
     </div>}
    </section>:section!=='Overview'?<section className="panel"><h2>{section} is not connected</h2><p>The existing reference application retains this workflow. No placeholder patient data, generated conclusions or clinical actions are shown here.</p><p>The source, evidence and review owners must be integrated with the same scoped patient API before this becomes available.</p><button onClick={()=>navigate('Overview')}>Return to overview</button></section>:<>
    <div className="grid">
     <section className="panel" aria-labelledby="access-heading"><span className="step">01 / ACCESS</span><h2 id="access-heading">Connect your session</h2><p>Permission is checked by the API on every request. Your credential stays in this tab’s memory and is cleared on disconnect or reload.</p>
      {!state.connected?<form onSubmit={e=>{e.preventDefault();session.connect(token);setToken('')}}><label htmlFor="credential">Synthetic access credential</label><input id="credential" name="credential" type="password" autoComplete="off" autoCapitalize="none" spellCheck={false} value={token} onChange={e=>setToken(e.target.value)} required minLength={32} maxLength={256}/><button type="submit" className="primary">Connect credential</button></form>:<div><p className="session-status">Credential present · grants checked by server</p><button onClick={disconnect}>Disconnect and clear</button></div>}
     </section>
     <section className="panel" aria-labelledby="patient-heading"><span className="step">02 / PATIENT</span><h2 id="patient-heading">Open an authorized identity</h2><p>Enter the exact opaque patient ID. Creating an identity does not automatically grant permission to read it.</p><form onSubmit={e=>{e.preventDefault();void session.read(patientId)}}><label htmlFor="patient-id">Patient ID</label><input id="patient-id" value={patientId} onChange={e=>setPatientId(e.target.value)} autoComplete="off" spellCheck={false} disabled={!state.connected||state.phase==='creating'} required maxLength={128}/><button className="primary" disabled={!state.connected||busy}>Open patient</button></form></section>
    </div>
    <p className={'status '+(state.phase==='error'?'error':'')} role="status" aria-live="polite" data-testid="status">{state.message}</p>
    {state.patient&&<section className="panel patient" data-testid="patient-card"><span className="step">LATEST SUCCESSFUL REGISTRY RESPONSE</span><h2>Patient identity</h2><dl><div><dt>Patient ID</dt><dd>{state.patient.patient_id}</dd></div><div><dt>Organization</dt><dd>{state.patient.origin_org}</dd></div><div><dt>Registry status</dt><dd>{state.patient.status}</dd></div><div><dt>Revision</dt><dd>{state.patient.revision}</dd></div><div><dt>Created</dt><dd>{state.patient.created_at}</dd></div></dl><p className="muted">Identity metadata only, authorized at the last successful request. Recheck access for current permissions. {state.sourceIndex||state.worldModel?'Source information is loaded separately; it does not establish a reviewed clinical conclusion.':'No clinical record or conclusion has been loaded.'}</p><button disabled={busy} onClick={()=>void session.read(state.patient!.patient_id)}>Recheck current access</button></section>}
    <details className="panel create-panel"><summary>Create a fictional patient identity</summary><p>This uses the existing canonical registry. No names or clinical details are accepted. Your credential needs a separate create action.</p><form onSubmit={e=>{e.preventDefault();keyForReceipt.current=requestKey;void session.create(requestKey,confirmed)}}><label htmlFor="request-key">Creation request key</label><input id="request-key" value={requestKey} readOnly/><p className="muted small">Keep the same key when retrying an uncertain response. The server prevents duplicate identities.</p><label className="check"><input id="synthetic-confirm" type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)} disabled={!state.connected||busy}/>This is an independently fictional identity, not a real person.</label><div className="actions"><button disabled={!state.connected||!confirmed||busy} className="primary">Create fictional identity</button><button type="button" disabled={busy||!state.created||keyForReceipt.current!==requestKey} onClick={()=>{setRequestKey(crypto.randomUUID());setConfirmed(false)}}>Start a different creation</button></div></form>{state.created&&<p data-testid="created-id">{state.created.duplicate?'Existing identity recovered: ':'Identity created: '}<code>{state.created.patient_id}</code><br/>The operator must separately grant access to this ID before it can be read.</p>}</details>
    </>}
    <footer>FastAPI · PostgreSQL 16 · React · TypeScript <span>No live model or external biomedical data is used by this screen.</span></footer>
   </main>
  </div>
 </div>;
}
createRoot(document.getElementById('root')!).render(<StrictMode><App/></StrictMode>);
