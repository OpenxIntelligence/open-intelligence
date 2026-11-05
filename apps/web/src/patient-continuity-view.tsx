import type {ViewState} from './registry-client';
import {patientContinuity} from './patient-continuity';
import {FOLLOWTHROUGH_FILTERS,matchesFollowthroughFilter} from './followthrough-view';

export function PatientContinuity({state,onNavigate,onRefreshFollowthrough,busy}:{
 state:ViewState;onNavigate:(section:string)=>void;onRefreshFollowthrough:(caseId:string)=>void;busy:boolean;
}){
 const view=patientContinuity(state);
 if(!view)return null;
 const attention=view.followthrough;
 const openTasks=attention?.list.tasks.filter(task=>!matchesFollowthroughFilter(task,'history'))??[];
 const preview=openTasks.slice(0,3);
 const readPhase=attention?'ready':state.followthroughPhase==='loading'&&state.followthroughCaseId===view.caseId?'loading':
  state.followthroughPhase==='idle'?'idle':'error';
 const writePhase=state.followthroughWritePhase;
 const pendingWrite=writePhase==='saving'||writePhase==='unknown';
 const refreshDisabled=!view.caseId||busy||state.followthroughPhase==='loading'||pendingWrite;
 const readMessage=!view.caseId?'Open a case in Investigations to check its follow-up work.':
  readPhase==='ready'?'Recorded follow-up work from the last successful permission check.':
  readPhase==='loading'?'Checking current permission to read follow-up work…':
  writePhase==='unknown'?'A current follow-up list is unavailable while the submission outcome is unresolved.':
  writePhase==='saving'?'Waiting for the follow-up submission before checking recorded work.':
  readPhase==='error'?'Follow-up work is unavailable for the current case. Check again or open Investigations for details.':
  'Follow-up work has not been checked for the current case.';
 return <section className="panel continuity" aria-labelledby="continuity-heading" data-testid="patient-continuity">
  <span className="step">YOUR RECORDS · YOUR QUESTIONS · FOLLOW-UP</span>
  <h2 id="continuity-heading" data-workspace-anchor="Care preparation">Continue your care preparation</h2>
  <p>Return to your records and questions without starting again. These are preparation steps, not medical advice or completed clinical review.</p>
  <p className="small">Patient <code>{view.patientId}</code>{view.caseId?<> · Case <code>{view.caseId}</code></>:<> · No case context loaded</>}</p>
  <div className="continuity-grid">
   {view.draft&&<div className="continuity-item" data-testid="continuity-draft" data-state={view.draft}>
    <h3>{view.draft==='saved'?'Your question was saved':view.draft==='saving'?'Your question is being saved':view.draft==='needs_attention'?'Check your question save':'Continue your question'}</h3>
    <p>{view.draft==='saved'?'The server confirmed this question. Saving is not clinical review.':view.draft==='saving'?'Wait for confirmation before assuming the question is saved.':view.draft==='needs_attention'?'Return to the question to inspect the outcome and recovery instructions. Do not assume it was saved.':'Your unfinished question remains in this tab. Reloading or disconnecting clears this draft.'}</p>
    <button type="button" data-testid="continuity-resume" onClick={()=>onNavigate('Investigations')}>{view.draft==='saved'?'Return to your question':'Resume your question'}</button>
   </div>}
   <div className="continuity-item" data-testid="continuity-questions">
    <h3>Questions and changed records</h3>
    <p className="small">Text-anchored and laboratory questions have separate source and access checks. These are not clinical approvals.</p>
    {view.questions?<>
     <p><strong data-testid="continuity-reassessment">{view.questions.reassessment}</strong> {view.questions.reassessment===1?'question needs':'questions need'} source reassessment.</p>
     <p><strong data-testid="continuity-current">{view.questions.current}</strong> {view.questions.current===1?'question has':'questions have'} current source context, without clinical review.</p>
     {view.questions.reassessment>0&&<p>A supporting record changed. Inspect the question and its sources before using an earlier brief.</p>}
     {view.questions.current+view.questions.reassessment===0&&<p>No saved text-source questions were returned for this case and grant. Laboratory questions are checked separately; this does not mean there are no care needs.</p>}
    </>:<p>Question status has not been checked for the current case, or is unavailable. Open Questions to load the authorized history.</p>}
    <button type="button" data-testid="continuity-open-questions" onClick={()=>onNavigate('Investigations')}>Open text-source questions</button>
    {view.laboratoryAvailable&&<section className="continuity-laboratory-questions" data-testid="continuity-lab-questions" aria-label="Saved laboratory questions">
     <h4>Laboratory questions</h4>
     {view.laboratoryQuestions? <>
      <p><strong data-testid="continuity-lab-current">{view.laboratoryQuestions.current}</strong> with current source context, unreviewed.</p>
      <p><strong data-testid="continuity-lab-reassessment">{view.laboratoryQuestions.reassessment}</strong> needing reassessment after a source change.</p>
      {view.laboratoryQuestions.current+view.laboratoryQuestions.reassessment===0&&<p>No laboratory questions were returned in the last independently authorized read.</p>}
     </>:<p role="status">Laboratory question history has not been checked for this case or is unavailable. A missing check is not zero.</p>}
     <button type="button" disabled={busy} data-testid="continuity-open-lab-questions" onClick={()=>onNavigate('Journey')}>Reopen laboratory questions in Journey</button>
    </section>}
   </div>
   <div className="continuity-item">
    <h3>Your original records</h3>
    <p>Inspect original documents and their versions, or add another fictional record to an authorized case.</p>
    <button type="button" data-testid="continuity-open-records" onClick={()=>onNavigate('Records')}>Open records</button>
   </div>
  </div>
  {view.caseId&&<section className="continuity-item continuity-preparation" data-testid="continuity-preparation" aria-labelledby="continuity-preparation-heading">
   <h3 id="continuity-preparation-heading">What to look at next</h3>
   <p>Use the latest checked records, questions and follow-up work to prepare for discussion.</p>
   {view.preparation.length>0?<ol className="continuity-preparation-list" aria-label="Case preparation prompts">
    {view.preparation.map(item=><li key={item.key} data-testid="continuity-preparation-item" data-kind={item.key}>
     <h4>{item.title}</h4><p>{item.detail}</p>
     <button type="button" disabled={busy} onClick={()=>onNavigate(item.destination)}>{item.action}</button>
    </li>)}
   </ol>:<p data-testid="continuity-no-preparation-prompts">No supported prompts from the currently checked context. Other records or needs may still be unknown.</p>}
   {view.preparationTotal>view.preparation.length&&<p className="small" data-testid="continuity-preparation-coverage">
    Showing {view.preparation.length} of {view.preparationTotal} record-preparation prompts; inspect the source and investigation views for full context.
   </p>}
   <p className="muted small">Counts cover the structured records available here. Reviewed documents and records held by other providers may add context.</p>
  </section>}
  <section className="continuity-item continuity-followthrough" data-testid="continuity-followthrough" aria-labelledby="continuity-followthrough-heading">
   <h3 id="continuity-followthrough-heading" data-workspace-anchor="Follow-up work">Follow-up work</h3>
   <p>Recorded next steps across your saved questions. Owners and revisit dates describe coordination, not clinical urgency.</p>
   <p role="status" aria-live="polite" data-testid="continuity-followthrough-status" data-phase={readPhase}>{readMessage}</p>
   {pendingWrite&&<div className="continuity-followthrough-recovery" data-testid="continuity-followthrough-recovery" data-phase={writePhase}>
    <p><strong>{writePhase==='unknown'?'A follow-up submission has an unknown outcome.':'A follow-up submission is in progress.'}</strong> {writePhase==='unknown'?'Return to Follow-up work to retry the exact write or explicitly abandon recovery before recording different work.':'Return to Follow-up work to inspect its confirmation before assuming it was recorded.'}</p>
    <button type="button" data-testid="continuity-recover-followthrough" onClick={()=>onNavigate('Investigations')}>Review follow-up submission</button>
   </div>}
   {attention&&<>
    <dl className="continuity-followthrough-counts" aria-label="Recorded follow-up categories">
     {FOLLOWTHROUGH_FILTERS.map(({key,label})=><div key={key}><dt>{label}</dt><dd data-testid={'continuity-followthrough-count-'+key} data-count={attention.counts[key]}>{attention.counts[key]}</dd></div>)}
    </dl>
    <p className="small" data-testid="continuity-followthrough-evaluated-on">Evaluated on <time dateTime={attention.list.evaluated_on}>{attention.list.evaluated_on}</time> (UTC). Categories can overlap; they are not a total of separate care needs.</p>
    {attention.counts.all===0?<p>No recorded follow-up work was returned for this case and grant. This does not mean there are no care needs.</p>:<>
     <p className="small" data-testid="continuity-followthrough-coverage">Showing {preview.length} of {openTasks.length} open {openTasks.length===1?'task':'tasks'} in recorded order. Open Follow-up work to inspect all tasks and their source context.</p>
     {preview.length===0?<p>No open follow-up work was returned. Completed and deferred work remains available in Investigations.</p>:
      <ul className="continuity-followthrough-tasks" aria-label="Open follow-up preview">
       {preview.map(task=><li key={task.task_id} data-testid="continuity-followthrough-task" data-task-id={task.task_id} data-question-id={task.question_id} data-status={task.status}>
        <h4>{task.title}</h4>
        <p className="small">Recorded status: {task.status}</p>
        <dl>
         <div><dt>Recorded owner</dt><dd>{task.owner_label.trim()?task.owner_label:'Unassigned'}</dd></div>
         <div><dt>Revisit date</dt><dd>{task.due_date?<time dateTime={task.due_date}>{task.due_date}</time>:'Not recorded'}{task.is_overdue&&<span className="continuity-followthrough-date-note">Revisit date passed</span>}</dd></div>
         <div><dt>Review trigger</dt><dd>{task.review_trigger.trim()?task.review_trigger:'Not recorded'}</dd></div>
        </dl>
        {task.needs_recheck&&<p className="continuity-followthrough-flag">Source changed. Inspect the question and its source before continuing this work.</p>}
       </li>)}
      </ul>}
    </>}
   </>}
   <div className="actions">
    <button type="button" data-testid="continuity-followthrough-refresh" disabled={refreshDisabled} onClick={()=>{if(view.caseId&&!refreshDisabled)onRefreshFollowthrough(view.caseId)}}>{readPhase==='loading'?'Checking follow-up work…':attention?'Refresh follow-up work':'Check follow-up work'}</button>
    {!pendingWrite&&<button type="button" data-testid="continuity-open-followthrough" onClick={()=>onNavigate('Investigations')}>Open follow-up work</button>}
   </div>
  </section>
  <p className="muted small">Only the selected case and last successful reads in this session are represented. Other records, questions or follow-up work may be missing. Each server action checks permission again; nothing is sent to a care team from this panel.</p>
 </section>;
}
