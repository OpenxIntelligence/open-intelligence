import type {ReactNode} from 'react';
import {SourceOncologyLabel} from './source-oncology-label';
import type {FollowthroughTask} from './followthrough-view';
import type {WorldObservation} from './source-world-model';
import {LaboratoryResultBrowser,LaboratoryResultRow} from './laboratory-result-browser';
import {LaboratoryQuestionPanel,SavedLaboratoryQuestions} from './laboratory-question-panel';
import {questionSaveBlocksSourceChange} from './source-questions-view.js';
import type {RegistrySession,ViewState} from './registry-client';
import {SourceQuestionPanel} from './source-question-panel';
import {SourceHistoryView} from './source-history-view';

type Props={
  session:RegistrySession;
  state:ViewState;
  patientAccess:ReactNode;
  busy:boolean;
  showQuestions?:boolean;
  labsOnly?:boolean;
  onInvestigations?:()=>void;
  onReview?:()=>void;
  onRecords?:(caseId:string,taskOriginal?:FollowthroughTask)=>void;
};

/** First-party PG read-only Patient World Model view.
 * No generated diagnosis, triage, alerts, actions, clinician approval or
 * separate client-owned patient/source ledger. All clinical claims remain
 * attributed to the original fictional source and explicitly unreviewed.
 */
export function WorldModelView({session,state,patientAccess,busy,showQuestions=false,labsOnly=false,onInvestigations,onReview,onRecords}:Props){
  const loading=state.worldPhase==='loading'||state.recordsPhase.startsWith('loading');
  const model=state.worldModel;
  const laboratoryByRef=new Map(model?.laboratory_observations.map(item=>[item.source_id+':'+item.observation_reference,item])??[]);
  const contextsByLine=new Map(model?.observations.map(item=>[item.source_id+':'+item.source_line,item.oncology])??[]);
  const episodes=new Map<string|null,WorldObservation[]>();
  const ordinary:WorldObservation[]=[];
  for(const item of model?.observations??[]){
    if(!item.oncology){ordinary.push(item);continue;}
    const id=item.oncology.episode_id;
    const group=episodes.get(id);
    if(group)group.push(item);
    else episodes.set(id,[item]);
  }
  const statementList=(items:readonly WorldObservation[])=>
    <ul className="world-observations">{items.map(item=><li key={item.source_id+':'+item.source_line} data-testid="world-observation">
      <p><strong>{item.finding_key}</strong> · <span data-testid="world-reported-state">{item.reported_state}</span> · {item.event_date}</p>
      <SourceOncologyLabel context={item.oncology} state={item.reported_state}/>
      <blockquote data-testid="world-statement">{item.source_statement}</blockquote>
      <small>Not clinically established · {item.document_id} v{item.document_version} · <code>{item.source_id}</code> · line {item.source_line}</small>
      <div className="source-context-action"><button type="button" data-testid="composer-preflight"
        disabled={loading||busy||state.composerPhase==='loading'||questionSaveBlocksSourceChange(state)}
        onClick={()=>{session.chooseQuestionDraft(item.source_id,item.source_line);void session.prepareDraftQuestion();onInvestigations?.();}}>
        Prepare source-only question context
      </button>{' '}
      <button type="button" data-testid="choose-question-draft"
        disabled={loading||busy||questionSaveBlocksSourceChange(state)}
        onClick={()=>{session.chooseQuestionDraft(item.source_id,item.source_line);onInvestigations?.();}}>
        Write a source-linked question
      </button></div>
    </li>)}</ul>;
  if(!state.patient)return <section aria-label="Source workspace" data-testid="world-workspace" data-view={showQuestions?'investigations':'journey'}><div data-testid="world-no-patient">{patientAccess}</div></section>;
  const caseChoices=<>
      <p className="record-scope" data-testid="world-patient"><strong>Patient:</strong> <code>{state.patient.patient_id}</code></p>
      <button className="primary" data-testid="world-load-cases" disabled={loading||busy} onClick={()=>void session.loadCases()}>Check authorized cases</button>
      {state.cases!==null&&<section aria-label="Authorized case choices">
        <h3>Source case</h3>
        {state.cases.length===0?<p>No fictional case is currently mapped to this identity.</p>:
         <ul className="world-cases">{state.cases.map(item=><li key={item.case_id}>
          <code>{item.case_id}</code> · {item.status}{' '}
          <button data-testid="world-load" disabled={item.status!=='active'||loading||busy} onClick={()=>void session.loadWorldModel(item.case_id)}>{labsOnly?'Open lab results':'Inspect World Model'}</button>
         </li>)}</ul>}
      </section>}
      <p role="status" aria-live="polite" className={'status '+(state.worldPhase==='error'||state.recordsPhase==='error'?'error':'')} data-testid="world-status">{state.recordsPhase==='loading-cases'||state.recordsPhase==='error'?state.recordMessage:state.worldMessage}</p>
  </>;
  const laboratoryContent=model&&<>
        {model.laboratory_observations.length>0&&<section aria-labelledby="laboratory-results-heading" data-testid="world-laboratory-results">
          <h3 id="laboratory-results-heading" data-workspace-anchor="Laboratory results">Laboratory results (<span data-testid="world-laboratory-count">{model.summary.current_laboratory_observations}</span>)</h3>
          <p>Values, units and dates are reported by the source. An absent result is not a negative result. Clinical interpretation and reference-range assessment have not been performed.</p>
          <LaboratoryResultBrowser key={'labs:'+model.access_receipt_id}>{model.laboratory_timeline.map(entry=>{
            const item=laboratoryByRef.get(entry.source_id+':'+entry.observation_reference)!;
            return <LaboratoryResultRow key={item.source_id+':'+item.observation_reference} result={item}>
              {onRecords&&<button type="button" data-testid="world-laboratory-records" disabled={loading||busy}
                onClick={()=>onRecords(model.case_id)}>Open report versions in Records</button>}
            </LaboratoryResultRow>;
          })}</LaboratoryResultBrowser>
          {state.worldPhase==='ready'&&<LaboratoryQuestionPanel key={model.access_receipt_id} session={session} model={model} state={state} busy={loading||busy} sourceSavePending={questionSaveBlocksSourceChange(state)}/>}
        </section>}
        {state.worldPhase==='ready'&&<SavedLaboratoryQuestions onFollowthrough={showQuestions?undefined:onInvestigations} session={session} model={model} state={state} busy={loading||busy} sourceSavePending={questionSaveBlocksSourceChange(state)}/>}
  </>;
  if(labsOnly)return <section className="panel source-world" data-testid="labs-workspace" aria-labelledby="labs-heading">
    <h2 id="labs-heading" data-workspace-anchor="Case selection">Lab results by case</h2>
    {caseChoices}
    {model&&<div data-testid="labs-results" key={model.access_receipt_id}>
      <p>Results for <strong>{model.case_id}</strong></p>
      {!model.laboratory_observations.length&&<p role="status">No current structured lab results were returned for this case. Other reports may be available in Records.</p>}
      {laboratoryContent}
      {onRecords&&<button type="button" disabled={busy||loading} onClick={()=>onRecords(model.case_id)}>Open case records and lab import</button>}
    </div>}
  </section>;
  return <section className="panel source-world" aria-labelledby="world-heading" data-testid="world-workspace" data-view={showQuestions?'investigations':'journey'}>
    <span className="step">SOURCE-LINKED PATIENT CONTEXT / SYNTHETIC ONLY</span>
    <h2 id="world-heading" data-workspace-anchor="Patient and case">{showQuestions?'Source-linked investigations':'Patient World Model — source-only view'}</h2>
    <p>This is a fresh read of the existing PostgreSQL original-source owner. It organizes reported observations, chronology, unresolved statements and source disagreements. It does not interpret cancer, authorize AI research, or replace clinician review.</p>

    {caseChoices}
      {showQuestions&&<SourceQuestionPanel session={session} state={state} busy={busy} onReview={onReview} onTaskOriginal={onRecords?task=>onRecords(task.case_id,task):undefined}/>}
      {model&&<div data-testid="world-projection">
        <p><strong>Case:</strong> <code>{model.case_id}</code> · Source statements unreviewed · Context checked at last read</p>
        <div className="world-summary" aria-label="Source context summary">
          <div><strong data-testid="world-current">{model.summary.current_sources}</strong><span>Current sources</span></div>
          <div><strong data-testid="world-history-count">{model.summary.historical_sources}</strong><span>Historical versions</span></div>
          <div><strong data-testid="world-observation-count">{model.summary.current_observations}</strong><span>Source statements</span></div>
          <div><strong data-testid="world-unresolved-count">{model.summary.unresolved_observations}</strong><span>Unresolved statements</span></div>
          <div><strong data-testid="world-conflict-count">{model.summary.source_disagreements}</strong><span>Source disagreements</span></div>
        </div>
        {!showQuestions&&<SourceHistoryView key={model.access_receipt_id} session={session} state={state} busy={busy||loading}/>}
        <h3>Source chronology</h3>
        {model.current_sources.length===0?<p>No current fictional original was imported.</p>:
        <ol className="world-timeline">{model.current_sources.map(item=><li key={item.source_id} data-testid="world-source">
          <strong>{item.event_date} · {item.document_id} v{item.version}</strong>
          <p>{item.kind} · specimen {item.specimen_id??'not recorded'} · issued {item.issued_at}</p>
          <details><summary>Exact source receipt</summary><p><code>{item.source_id}</code></p><p>SHA-256 <code>{item.sha256}</code></p></details>
        </li>)}</ol>}
        {laboratoryContent}
        {episodes.size>0&&<section aria-label="Source-reported cancer episodes">
          <h3>Source-reported cancer episodes</h3>
          <p>Reports are grouped by the episode identifier in the original finding. Each statement retains its reported status.</p>
          {Array.from(episodes,([episode,items])=><section key={episode??'?'}>
            <h4>{episode===null?'Episode unassigned':`Episode ${episode}`}</h4>
            {statementList(items)}
          </section>)}
        </section>}
        {(ordinary.length>0||episodes.size===0)&&<>
        <h3>Original source-reported statements</h3>
        <p>These are literal reported statements, not established clinical facts. A missing or pending item must never be interpreted as a negative finding.</p>
        {ordinary.length===0?<p>No additional source-reported statements are available.</p>:
        statementList(ordinary)}</>}
        {model.conflicts.length>0&&<section aria-labelledby="source-disagreements">
          <h3 id="source-disagreements" data-workspace-anchor="Source disagreements">Unresolved source disagreements</h3>
          <p>Conflicting source-reported states for the same documented specimen, date and finding; no clinical adjudication is performed.</p>
          <ul>{model.conflicts.map(item=><li key={item.source_refs[0].source_id+':'+item.source_refs[0].source_line} data-testid="world-conflict">
            <SourceOncologyLabel context={contextsByLine.get(item.source_refs[0].source_id+':'+item.source_refs[0].source_line)}/>
            <strong>{item.finding_key}</strong> · specimen {item.specimen_id} · {item.event_date} · reported states {item.reported_states.join(' / ')}
            <p>{item.source_refs.map(ref=><code key={ref.source_id+':'+ref.source_line}>{ref.source_id} line {ref.source_line}; </code>)}</p>
          </li>)}</ul>
        </section>}
        {model.history.length>0&&<details className="world-history"><summary>Superseded original history ({model.history.length})</summary>
          <ul>{model.history.map(item=><li key={item.source_id}><code>{item.source_id}</code> · {item.document_id} v{item.version} · SHA-256 <code>{item.sha256}</code></li>)}</ul>
        </details>}
        <details><summary>Context fingerprint and limitations</summary>
          <p>SHA-256 context fingerprint: <code data-testid="world-fingerprint">{model.snapshot_fingerprint}</code>. This is not an approval, signature or execution credential. It must be rechecked against the server before any future investigation.</p>
          <ul>{model.limitations.map(item=><li key={item}>{item}</li>)}</ul>
        </details>
        <p data-testid="world-no-approval" className="muted">Clinical interpretation: not generated. Composer execution: unavailable. Evidence rights and professional review: not integrated into this H1 view.</p>
      </div>}

  </section>;
}
