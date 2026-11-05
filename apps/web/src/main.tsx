import {StrictMode, useEffect, useLayoutEffect, useMemo, useRef, useState, useSyncExternalStore} from 'react';
import {createRoot} from 'react-dom/client';
import {RegistrySession} from './registry-client';
import {createEncounterScope, EncounterChart} from './encounter-chart';
import {EncounterSourceLinks} from './encounter-source-links-view';
import {SourceIntake} from './source-intake-view';
import {RecordImportDisclosure} from './record-import-disclosure';
import {ReviewedDocumentDisclosure} from './reviewed-documents-view';
import {WorldModelView} from './world-model-view';
import {PatientContinuity} from './patient-continuity-view';
import {SecondOpinionPreparation} from './second-opinion-preparation-view';
import {ReviewPanel,useReviewReasonDrafts} from './review-panel';
import {SourceReading, emptySourceFilters} from './source-reading';
import type {ReadingView,SourceFilters} from './source-reading';
import './styles.css';
import './source-intake.css';
import {PatientAccess} from './patient-access';
import {PageContents} from './page-contents';
import {LeaveVisitForm} from './visit-navigation';
const session=new RegistrySession();
const navigation=['Overview','Journey','Records','Visits','Investigations','Review'];
const diagnostics=['Labs','Imaging','Pathology','Molecular'];
const reportKinds:Readonly<Record<string,string>>={Imaging:'imaging',Pathology:'pathology',Molecular:'molecular'};
const sectionDescriptions:Readonly<Record<string,string>>={
 Journey:'Follow events over time and see where records are incomplete or disagree.',
 Records:'Find original records, check their versions and see what each source reported.',
 Visits:'Read visit notes, schedule a visit or check the records linked to it.',
 Investigations:'Save a question with its source and see when a record change calls for another look.',
 Review:'Check the sources behind saved questions and record what needs independent verification.',
 Labs:'Read structured lab values with their units, specimen and original report.',
 Imaging:'Read imaging reports and inspect the original images linked to a report.',
 Pathology:'Read pathology reports and trace each reported finding to its source.',
 Molecular:'Read molecular reports, inspect their versions and ask about a reported finding.',
};
function WorkspaceContext({section,patientId,readiness,view,onViewChange}:{section:string;patientId:string|null;readiness:'checking'|'ready'|'unavailable';view:ReadingView;onViewChange:(view:ReadingView)=>void}){
 const header=useRef<HTMLElement>(null);
 useLayoutEffect(()=>{
  const element=header.current;if(!element)return;
  const measure = () => {
   const height = Math.ceil(element.getBoundingClientRect().height);
   const sticky = height <= window.innerHeight / 2;
   element.dataset.sticky = String(sticky);
   document.documentElement.style.setProperty('--workspace-offset', `${sticky ? height + 24 : 24}px`);

   // Resizing a focused reader does not trigger its focus handler again.
   const reader = document.activeElement;
   if (reader instanceof HTMLElement && reader.matches(':is(.intake-panel,.original-panel) .original-text')) {
    const bounds = reader.getBoundingClientRect();
    const visibleTop = sticky ? element.getBoundingClientRect().bottom : 0;
    if (bounds.top < visibleTop || bounds.bottom > window.innerHeight) {
     reader.scrollIntoView({block: 'start', inline: 'nearest'});
    }
   }
  };
  measure();const observer=new ResizeObserver(measure);observer.observe(element);window.addEventListener('resize',measure);
  return()=>{observer.disconnect();window.removeEventListener('resize',measure);document.documentElement.style.removeProperty('--workspace-offset');};
 },[]);
 return <header ref={header} className="topbar" aria-label="Current workspace context">
  <div className="workspace-context"><div className="workspace-location-row"><span className="workspace-location">Patient workspace <span className="muted">/ {section}</span></span><a className="workspace-navigation-link" href="#workspace-navigation">Change section</a></div>
   <span className="workspace-identity" data-testid="workspace-identity">{patientId?<><span className="workspace-context-label">Authorized fictional patient</span> <code>{patientId}</code></>:<span className="muted">No authorized patient open</span>}</span>
  </div>
  <div className="reading-controls">{patientId&&<div><label htmlFor="reading-view">Reading layout</label><select id="reading-view" value={view} onChange={e=>onViewChange(e.target.value as ReadingView)} aria-describedby="reading-view-help"><option value="patient">Patient reading</option><option value="clinical">Clinical reading</option></select><span id="reading-view-help">Presentation only · permissions unchanged</span></div>}
  <span role="status" aria-live="polite" className={'connection '+readiness} data-testid="readiness">{readiness==='checking'?'Checking API':readiness==='ready'?'PostgreSQL API ready':'API unavailable'}</span></div>
 </header>;
}
function App(){
 const state=useSyncExternalStore(session.subscribe,session.snapshot);
 const encounterScope=useMemo(()=>state.connected&&state.phase==='ready'&&state.patient?.status==='active'
  ?createEncounterScope(session,state.patient.patient_id):null,[state.connected,state.phase,state.patient]);
 const reviewReasonDrafts=useReviewReasonDrafts(state);
 const [patientId,setPatientId]=useState(''),[confirmed,setConfirmed]=useState(false);
 const [requestKey,setRequestKey]=useState(()=>crypto.randomUUID());
 const [readiness,setReadiness]=useState<'checking'|'ready'|'unavailable'>('checking');
 const visitDirty=useRef(false);
 const [leaveFor,setLeaveFor]=useState<{section:string;scopeKey:string}|null>(null);
 const [recordsVisit,setRecordsVisit]=useState<{id:number;patient:typeof state.patient}|null>(null);
 const [section,setSection]=useState('Overview');
 const [view,setView]=useState<ReadingView>('patient');
 const reportKind=reportKinds[section];
 const recordsSection=section==='Records'||Boolean(reportKind);
 const [sourceFilters,setSourceFilters]=useState({scope:state.sourceIndex,bySection:{} as Record<string,SourceFilters>});
 const filters=sourceFilters.scope===state.sourceIndex?sourceFilters.bySection[section]??emptySourceFilters:emptySourceFilters;
 useEffect(()=>{setSourceFilters({scope:state.sourceIndex,bySection:{}})},[state.sourceIndex]);
 const heading=useRef<HTMLHeadingElement>(null),moveFocus=useRef(false);
 useEffect(()=>{if(moveFocus.current){heading.current?.focus();moveFocus.current=false}},[section]);
 // Hand keyboard focus to the section only for the read that removed its entry form.
 const entryFocus=useRef<HTMLFormElement|null>(null);
 useLayoutEffect(()=>{
  const form=entryFocus.current;
  if(!form || state.phase==='reading')return;
  entryFocus.current=null;
  if(state.patient && !form.isConnected && document.activeElement===document.body)heading.current?.focus();
 },[state.phase,state.patient]);
 const passageResume=useRef<{patientId:string;questionId:string}|null>(null);
 useEffect(()=>{
  const target=passageResume.current;if(!target)return;
  if(section!=='Investigations'||state.patient?.patient_id!==target.patientId||state.phase!=='ready'||state.evidencePhase==='error'){
   passageResume.current=null;return;
  }
  if(state.evidencePhase==='ready'&&state.evidencePacket?.question.question_id===target.questionId){
   document.getElementById('manual-context-heading')?.focus();passageResume.current=null;
  }
 },[section,state.patient?.patient_id,state.phase,state.evidencePhase,state.evidencePacket]);
 const originalHeading=useRef<HTMLHeadingElement>(null),sourcesHeading=useRef<HTMLHeadingElement>(null);
 const sourceEntry=useRef<{patientId:string;caseId:string;trigger:HTMLButtonElement}|null>(null);
 const originalReturn=useRef<{sourceId:string;trigger:HTMLButtonElement;pending:boolean}|null>(null);
 useEffect(()=>{
  const requested=sourceEntry.current;if(!requested)return;
  if(!recordsSection||requested.patientId!==state.patient?.patient_id||
     (state.recordsPhase!=='loading-sources'&&state.recordsPhase!=='ready')){sourceEntry.current=null;return;}
  if(state.recordsPhase!=='ready')return;
  sourceEntry.current=null;
  if(state.sourceIndex?.case_id===requested.caseId&&
     (document.activeElement===requested.trigger||document.activeElement===document.body)){
   sourcesHeading.current?.focus({preventScroll:true});
   sourcesHeading.current?.scrollIntoView({block:'start'});
  }
 },[state.sourceIndex,state.recordsPhase,state.patient?.patient_id,section]);
 function inspectSources(caseId:string,trigger:HTMLButtonElement){
  originalReturn.current=null;
  sourceEntry.current=state.patient?{patientId:state.patient.patient_id,caseId,trigger}:null;
  void session.loadSources(caseId);
 }
 useEffect(()=>{originalReturn.current=null},[state.sourceIndex,state.patient?.patient_id]);
 useEffect(()=>{
  const requested=originalReturn.current;
  if(state.recordsPhase==='error'){originalReturn.current=null;return;}
  if(recordsSection&&requested?.pending&&state.original?.source_id===requested.sourceId){
   requested.pending=false;originalHeading.current?.focus();
  }
 },[state.original,state.recordsPhase,section]);
 function closeOriginal(){
  const trigger=originalReturn.current?.trigger;originalReturn.current=null;
  session.dismissOriginal();
  if(trigger?.isConnected&&!trigger.disabled)trigger.focus();
  else (sourcesHeading.current??heading.current)?.focus();
 }
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
  const busy=state.phase==='creating'||state.phase==='reading'||state.importOutcome==='sending'||state.questionSavePhase==='saving'||state.reviewReturnPhase==='saving'||state.evidenceWritePhase==='saving';
 function navigate(nextSection:string,discardVisit=false){
  if(section==='Visits'&&nextSection!==section&&visitDirty.current&&encounterScope&&!discardVisit){setLeaveFor({section:nextSection,scopeKey:encounterScope.key});return;}
  entryFocus.current=null;
  if(nextSection!==section){
   setRecordsVisit(null);
   if((reportKind||reportKinds[nextSection])&&(state.original||state.recordsPhase==='loading-original'))session.dismissOriginal();
  }
  passageResume.current=null;sourceEntry.current=null;originalReturn.current=null;session.dismissSourceQuotePacket();session.dismissSourceBrief();session.dismissEvidenceMetadata();session.dismissQuestionEvidence();session.dismissSourceImages();if(nextSection===section){heading.current?.focus();return}moveFocus.current=true;setSection(nextSection);}
 function disconnect(){passageResume.current=null;sourceEntry.current=null;entryFocus.current=null;session.disconnect();setPatientId('');setConfirmed(false);}
 const patientAccess=<PatientAccess key={section} session={session} state={state} busy={busy}
  patientId={patientId} onPatientIdChange={setPatientId} onDisconnect={disconnect}
  onRead={form=>{
   entryFocus.current=section!=='Overview'&&form.contains(document.activeElement)?form:null;
   void session.read(patientId);
  }}/>;
 function sectionButton(name:string){
  return <button type="button" key={name} aria-current={name===section?'page':undefined} onClick={()=>navigate(name)}>{name}</button>;
 }
 return <div className="app" onFocusCapture={()=>{
  if(entryFocus.current&&!entryFocus.current.contains(document.activeElement))entryFocus.current=null;
  if(sourceEntry.current&&document.activeElement!==sourceEntry.current.trigger)sourceEntry.current=null;
 }}>
  <a className="skip" href="#main">Skip to workspace</a>
  <aside className="rail" aria-label="Workspace navigation">
   <div className="brand"><span className="mark" aria-hidden="true">oi</span><span>Open<br/>Intelligence</span></div>
   <nav id="workspace-navigation" tabIndex={-1} aria-label="Patient workspace">
    {navigation.map(sectionButton)}
    <div className="diagnostic-nav" role="group" aria-labelledby="diagnostic-nav-heading">
     <span id="diagnostic-nav-heading">Diagnostics</span>
     {diagnostics.map(sectionButton)}
    </div>
   </nav>
  </aside>
  <div className="body"><WorkspaceContext section={section} patientId={state.patient?.patient_id??null} readiness={readiness} view={view} onViewChange={setView}/>
   {leaveFor&&leaveFor.scopeKey===encounterScope?.key&&<LeaveVisitForm destination={leaveFor.section} onStay={()=>setLeaveFor(null)} onLeave={()=>{
     setLeaveFor(null);navigate(leaveFor.section,true);
   }}/>}
   <main id="main" tabIndex={-1}>
    <div className="heading"><div><h1 ref={heading} tabIndex={-1}>{section==='Overview'?(state.patient?'Patient overview':'Open a patient'):section}</h1><p className="lede">{section==='Overview'?(state.patient?'Revisit your records, questions and follow-up work.':'Connect your session, then open a fictional patient using their ID.'):sectionDescriptions[section]}</p></div></div>
    <div className="boundary" role="note"><strong>Synthetic workspace.</strong> Use fictional records and operator-issued credentials only. Clinical sign-off is unavailable.</div>
    {state.patient&&<PageContents key={section}/>}
    {section==='Visits'?(encounterScope?<EncounterChart key={encounterScope.key} scope={encounterScope} dirtyRef={visitDirty}
      onRecords={id=>{navigate('Records');setRecordsVisit({id,patient:state.patient});}}/>:<div data-testid="visits-no-patient">{state.patient?.status==='suspended'&&<p role="status">This identity is suspended. Open an active patient to see visits.</p>}{patientAccess}</div>):section==='Journey'||section==='Investigations'||section==='Labs'?<WorldModelView labsOnly={section==='Labs'} session={session} state={state} busy={busy} showQuestions={section==='Investigations'} onRecords={caseId=>{navigate('Records');void session.loadSources(caseId);}} patientAccess={patientAccess} onInvestigations={()=>navigate('Investigations')} onReview={()=>navigate('Review')}/>:section==='Review'?<ReviewPanel key={state.patient?.patient_id??'no-patient'} session={session} state={state} busy={busy} drafts={reviewReasonDrafts} patientAccess={patientAccess} onInvestigations={()=>navigate('Investigations')}/>:recordsSection&&!state.patient?<section data-testid="records-workspace" aria-label={section}><div data-testid="records-no-patient">{patientAccess}</div></section>:recordsSection&&state.patient?<section className="panel records-workspace" data-testid="records-workspace" aria-labelledby="records-heading">
     <h2 id="records-heading" data-workspace-anchor={reportKind?'Case selection':'Records'}>{reportKind?section+' reports':view==='patient'?'Records available to you':'Original source records'}</h2>
     <p>{reportKind?'Choose a case to read its structured reports. Text and PDF uploads have their own reader in Records.':'Select a case to inspect reported findings, original files and version history.'}</p>
     <div>
      <p className="record-scope" data-testid="records-patient"><strong>Selected patient:</strong> <code>{state.patient.patient_id}</code></p>
      <button className="primary" data-testid="load-cases" disabled={state.recordsPhase.startsWith('loading')||busy} onClick={()=>void session.loadCases()}>Check authorized cases</button>
      <p role="status" aria-live="polite" data-testid="records-status" className={'status '+(state.recordsPhase==='error'?'error':'')}>{state.recordMessage}</p>
      {!reportKind&&encounterScope&&<div className="visit-record-entry">
        {recordsVisit&&recordsVisit.patient===state.patient&&<p>Open an authorized case’s source versions, then choose <strong>Check records for selected visit</strong>.</p>}
        <button type="button" data-testid="records-open-visits" onClick={()=>navigate('Visits')}>Open visits and draft notes</button>
      </div>}
      {!reportKind&&state.importOutcome!=='idle'&&<p role="status" aria-live="polite" className="status" data-testid="import-receipt" data-outcome={state.importOutcome} data-result={state.importReceipt?.result??''}>{state.importMessage}</p>}
      {state.original&&(!reportKind||state.sourceIndex?.sources.some(source=>source.source_id===state.original!.source_id&&source.kind===reportKind))&&<section className="original-panel" aria-labelledby="opened-original" data-testid="opened-original">
       <h3 id="opened-original" data-workspace-anchor="Opened original" ref={originalHeading} tabIndex={-1}>Exact original: {state.original.document_id} · v{state.original.version}</h3>
       <p>{state.original.state} · SHA-256 <code>{state.original.sha256}</code></p>
       <p>Verified against the selected version metadata. Clinical review: not established. Access was checked for this read.</p>
       <button data-testid="close-original" onClick={closeOriginal}>Close original</button>
       <pre className="original-text" data-testid="server-original" tabIndex={0} role="region" aria-label="Original document text" onFocus={event=>event.currentTarget.scrollIntoView({block:'center'})}>{state.original.original_text}</pre>
      </section>}
      {state.cases!==null&&<section aria-labelledby="case-list-heading" data-testid="records-cases">
       <h3 id="case-list-heading" data-workspace-anchor="Case mappings">Case mappings</h3>
       {state.cases.length===0?<p>No current authorized case mappings were returned.</p>:
        <ul className="case-list">{state.cases.map(item=><li key={item.case_id} className="case-row" data-testid="case-row">
         <div><strong><code>{item.case_id}</code></strong><span className="record-state"> {item.status}</span></div>
         <p>Origin: {item.source_organization} · System: {item.source_system} · Version {item.revision}</p>
         <p>Fictional identity verification: not established. Clinical sources automatically linked: no.</p>
         <button data-testid="load-sources" disabled={item.status!=='active'||state.recordsPhase.startsWith('loading')||busy} onClick={event=>inspectSources(item.case_id,event.currentTarget)}>{reportKind?'Open '+section.toLowerCase()+' reports':'Inspect source versions'}</button>
        </li>)}</ul>}
      </section>}
      {state.sourceIndex&&<section className="records-detail" data-testid="source-index" aria-labelledby="sources-heading">
       <h3 id="sources-heading" data-workspace-anchor="Source versions" ref={sourcesHeading} tabIndex={-1}>Source history for <code>{state.sourceIndex.case_id}</code></h3>
       {reportKind?<button type="button" onClick={()=>navigate('Records')}>Open all records and uploads for this case</button>:<>
       <p>Immutable original source identifiers, hashes and historical versions. These records are independently fictional.</p>
       <ReviewedDocumentDisclosure key={"documents:"+state.patient.patient_id+":"+state.sourceIndex.case_id} session={session} patientId={state.patient.patient_id} caseId={state.sourceIndex.case_id}/>
       <RecordImportDisclosure key={state.patient.patient_id+':'+state.sourceIndex.case_id} initiallyOpen={state.sourceIndex.sources.length===0}>
        <SourceIntake session={session} patientId={state.patient.patient_id} caseId={state.sourceIndex.case_id} sending={state.importOutcome==='sending'}/>
       </RecordImportDisclosure>
       </>}
       <SourceReading key={section} kind={reportKind} index={state.sourceIndex} view={view} filters={filters}
        onFiltersChange={next=>setSourceFilters(previous=>({scope:state.sourceIndex,bySection:{...(previous.scope===state.sourceIndex?previous.bySection:{}),[section]:next}}))}
        busy={busy||state.recordsPhase.startsWith('loading')}
        questionBusy={state.worldPhase==='loading'}
        sourceImages={state.sourceImages} sourceImagesSourceId={state.sourceImagesSourceId}
        sourceImagesPhase={state.sourceImagesPhase} sourceImagesMessage={state.sourceImagesMessage}
        sourceImageDownload={state.sourceImageDownload} sourceImageDownloadPhase={state.sourceImageDownloadPhase}
        sourceImageDownloadMessage={state.sourceImageDownloadMessage}
        sourceImagePreview={state.sourceImagePreview} sourceImagePreviewPhase={state.sourceImagePreviewPhase}
        sourceImagePreviewMessage={state.sourceImagePreviewMessage}
        onInspectImages={sourceId=>void session.loadSourceImages(sourceId)}
        onPreviewImage={(sourceId,imageId)=>void session.previewSourceImage(sourceId,imageId)}
        onDismissImagePreview={session.dismissSourceImagePreview}
        onDownloadImage={(sourceId,imageId)=>void session.downloadSourceImage(sourceId,imageId)}
        onDismissImages={session.dismissSourceImages}
        onOpenOriginal={(sourceId,trigger)=>{originalReturn.current={sourceId,trigger,pending:true};void session.loadOriginal(sourceId)}}
        onAskQuestion={(sourceId,line)=>{const caseId=state.sourceIndex!.case_id;
          navigate('Investigations');
          void session.beginQuestionFromSourceReading(caseId,sourceId,line);}}/>
       {!reportKind&&<EncounterSourceLinks key={state.sourceIndex.access_receipt_id} session={session} patientId={state.patient.patient_id} index={state.sourceIndex}
        requestedVisit={recordsVisit?.patient===state.patient?recordsVisit?.id:undefined}
        onOpenOriginal={(sourceId,trigger)=>{originalReturn.current={sourceId,trigger,pending:true};void session.loadOriginal(sourceId)}}/>}
       <p className="muted">Amendments are preserved as separate versions. Connected questions and reports retain their source context and reassessment states. Clinical approval is not supplied by this screen.</p>
      </section>}
     </div>
    </section>:section!=='Overview'?<section className="panel"><h2>{section} is not connected</h2><p>The existing reference application retains this workflow. No placeholder patient data, generated conclusions or clinical actions are shown here.</p><p>The source, evidence and review owners must be integrated with the same scoped patient API before this becomes available.</p><button onClick={()=>navigate('Overview')}>Return to overview</button></section>:<>
    <PatientContinuity state={state} onNavigate={navigate} busy={busy} onRefreshFollowthrough={caseId=>void session.loadFollowthrough(caseId)}/>
    <SecondOpinionPreparation state={state} onNavigate={navigate} onResumeQuestion={questionId=>{navigate('Investigations');if(state.patient)passageResume.current={patientId:state.patient.patient_id,questionId};void session.loadQuestionEvidence(questionId);}} onCheckEvidence={questionId=>void session.loadQuestionEvidence(questionId)}/>
    {patientAccess}
    {state.patient&&<section className="panel patient" data-testid="patient-card"><span className="step">LATEST SUCCESSFUL REGISTRY RESPONSE</span><h2>Patient identity</h2><dl><div><dt>Patient ID</dt><dd>{state.patient.patient_id}</dd></div><div><dt>Organization</dt><dd>{state.patient.origin_org}</dd></div><div><dt>Registry status</dt><dd>{state.patient.status}</dd></div><div><dt>Revision</dt><dd>{state.patient.revision}</dd></div><div><dt>Created</dt><dd>{state.patient.created_at}</dd></div></dl><p className="muted">Identity metadata only, authorized at the last successful request. Recheck access for current permissions. {state.sourceIndex||state.worldModel?'Source information is loaded separately; it does not establish a reviewed clinical conclusion.':'No clinical record or conclusion has been loaded.'}</p><button disabled={busy} onClick={()=>void session.read(state.patient!.patient_id)}>Recheck current access</button></section>}
    <details className="panel create-panel"><summary>Create a fictional patient identity</summary><p>This uses the existing canonical registry. No names or clinical details are accepted. Your credential needs a separate create action.</p><form onSubmit={e=>{e.preventDefault();keyForReceipt.current=requestKey;void session.create(requestKey,confirmed)}}><label htmlFor="request-key">Creation request key</label><input id="request-key" value={requestKey} readOnly/><p className="muted small">Keep the same key when retrying an uncertain response. The server prevents duplicate identities.</p><label className="check"><input id="synthetic-confirm" type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)} disabled={!state.connected||busy}/>This is an independently fictional identity, not a real person.</label><div className="actions"><button disabled={!state.connected||!confirmed||busy} className="primary">Create fictional identity</button><button type="button" disabled={busy||!state.created||keyForReceipt.current!==requestKey} onClick={()=>{setRequestKey(crypto.randomUUID());setConfirmed(false)}}>Start a different creation</button></div></form>{state.created&&<p data-testid="created-id">{state.created.duplicate?'Existing identity recovered: ':'Identity created: '}<code>{state.created.patient_id}</code><br/>The operator must separately grant access to this ID before it can be read.</p>}</details>
    </>}

    <footer><a href="#workspace-navigation">Back to workspace navigation</a></footer>
   </main>
  </div>
 </div>;
}
createRoot(document.getElementById('root')!).render(<StrictMode><App/></StrictMode>);
