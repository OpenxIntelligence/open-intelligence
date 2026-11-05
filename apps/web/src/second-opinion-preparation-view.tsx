import type {ViewState} from './registry-client';
import {secondOpinionPreparation} from './second-opinion-preparation';
import './second-opinion-agenda.css';

const summary={
 needs_check:'Check the case inputs before preparing a second-opinion discussion.',
 needs_records:'No current original source version is loaded for this case.',
 needs_question:'Original records are available, but no current source-grounded question is loaded.',
 needs_reassessment:'A source changed. Reassess affected questions before relying on earlier preparation.',
 inputs_prepared:'The currently loaded records and questions are organized for preparation.',
} as const;

export function SecondOpinionPreparation({state,onNavigate}:{state:ViewState;onNavigate:(section:string)=>void}){
 const view=secondOpinionPreparation(state);
 if(!view)return null;
 return <section className="panel second-opinion-preparation" data-testid="second-opinion-preparation" data-state={view.state} aria-labelledby="second-opinion-heading">
  <span className="step">SECOND OPINION · PREPARATION ONLY</span>
  <h2 id="second-opinion-heading">Prepare a focused second-opinion discussion</h2>
  <p>{summary[view.state]}</p>
  <p className="small">This view organizes the last successfully authorized information in this session. It does not verify record completeness, choose a specialist, create a referral, transmit records, establish eligibility, or confirm an appointment.</p>
  <dl className="second-opinion-checklist" aria-label="Second-opinion preparation status">
   <div data-testid="second-opinion-records">
    <dt>Original records</dt>
    <dd>{view.records?view.records.current===0?'Checked: no current source version returned.':<>{view.records.current} current source {view.records.current===1?'version':'versions'}{view.records.historical>0?' · '+view.records.historical+' historical':''}</>:'Not checked for the selected case.'}</dd>
   </div>
   <div data-testid="second-opinion-questions">
    <dt>Focused questions</dt>
    <dd>{view.questions?<>{view.questions.current} current · {view.questions.reassessment} needing source reassessment</>:'Not checked for the selected case.'}</dd>
   </div>
   <div data-testid="second-opinion-coordination">
    <dt>Recorded coordination</dt>
    <dd>{view.coordination?<>{view.coordination.open} open · {view.coordination.assigned} with a recorded owner{view.coordination.sourceChanged>0?' · '+view.coordination.sourceChanged+' source-changed':''}</>:'Follow-up work has not been checked or is unavailable.'}</dd>
   </div>
  </dl>
  <section className="second-opinion-agenda" aria-labelledby="second-opinion-agenda-heading" data-testid="second-opinion-agenda">
   <h3 id="second-opinion-agenda-heading">Saved questions for discussion</h3>
   <p>These are your exact saved questions, not generated recommendations or clinically reviewed conclusions. Source status is from the last authorized read.</p>
   {!view.agenda?<p role="status" data-testid="second-opinion-agenda-unavailable">Questions have not been checked for this case, or that history is no longer available. Return to Investigations for an authorized read.</p>:
    view.agenda.total===0?<p data-testid="second-opinion-agenda-empty">No saved questions were returned for this case and grant. This does not establish that there are no care questions.</p>:<>
     <p className="small" data-testid="second-opinion-agenda-coverage">Showing {view.agenda.preview.length} of {view.agenda.total} saved {view.agenda.total===1?'question':'questions'} in the recorded order. Open Investigations to see the full history.</p>
     <ol className="second-opinion-agenda-list" aria-label="Saved discussion questions">
      {view.agenda.preview.map(item=><li key={item.questionId} data-testid="second-opinion-agenda-item" data-question-id={item.questionId} data-source-context={item.sourceContextState}>
       <p className="second-opinion-agenda-question">{item.text}</p>
       <p className="small">Original source version {item.sourceVersion}, line {item.sourceLine}. <strong>{item.sourceContextState==='source_reassessment_required'?'Source changed: reassessment required before relying on earlier preparation.':'Current source context; not clinically reviewed.'}</strong></p>
       <section className="second-opinion-question-work" data-testid="second-opinion-question-work" data-work-state={item.work===null?'unavailable':'ready'} aria-label="Recorded follow-up for this question">
        <h4>Recorded follow-up</h4>
        {!item.work?<p className="small" data-testid="second-opinion-question-work-unavailable">Follow-up work has not been checked or is unavailable for this case. No task count is implied.</p>:
         item.work.recordedCount===0?<p className="small" data-testid="second-opinion-question-work-empty">No follow-up tasks were returned for this question by the current task read. This does not establish that no care work is needed.</p>:<>
          <p className="small" data-testid="second-opinion-question-work-summary" data-recorded-count={item.work.recordedCount} data-open-count={item.work.openCount} data-history-count={item.work.historicalCount}>
           {item.work.openCount} open · {item.work.historicalCount} completed/deferred · task read evaluated {item.work.evaluatedOn}
          </p>
          {item.work.preview.length>0?<ul className="second-opinion-question-work-list" aria-label="Open follow-up tasks for this question">
           {item.work.preview.map(task=><li key={task.taskId} data-testid="second-opinion-question-task" data-task-id={task.taskId} data-status={task.status}>
            <strong>{task.title}</strong>
            <p className="small">Recorded status: {task.status} · Owner: {task.ownerLabel.trim()||'Not recorded'}</p>
            <p className="small">{task.dueDate?'Revisit date: '+task.dueDate:'No revisit date recorded'}</p>
            {task.reviewTrigger.trim()&&<p className="small">Revisit trigger: {task.reviewTrigger}</p>}
            {task.needsRecheck&&<p className="small" data-testid="second-opinion-question-task-recheck">Source changed: recorded work requires reassessment.</p>}
            {task.revisitDatePassed&&<p className="small" data-testid="second-opinion-question-task-past-date">Revisit date passed as of {item.work?.evaluatedOn} (operational flag, not clinical urgency).</p>}
           </li>)}
          </ul>:<p className="small">No open tasks in this read. Historical work remains available in Investigations.</p>}
          {item.work.openCount>item.work.preview.length&&<p className="small" data-testid="second-opinion-question-work-more">{item.work.openCount-item.work.preview.length} additional open tasks are available in Investigations.</p>}
         </>}
       </section>
      </li>)}
     </ol>
     {view.agenda.total>view.agenda.preview.length&&<p data-testid="second-opinion-agenda-more">{view.agenda.total-view.agenda.preview.length} additional saved questions are available in Investigations; this preview is not the complete agenda.</p>}
    </>}
  </section>
  {view.state==='inputs_prepared'&&<p className="second-opinion-note" data-testid="second-opinion-prepared"><strong>Preparation inputs are organized.</strong> A real second-opinion request still requires a verified recipient, current authorization, deliberate record selection, and an external confirmation workflow that is not implemented here.</p>}
  {view.state==='needs_reassessment'&&<p className="second-opinion-note" data-testid="second-opinion-reassessment"><strong>Do not treat the earlier preparation as current.</strong> Inspect the changed source and affected question first.</p>}
  <div className="actions">
   <button type="button" data-testid="second-opinion-open-records" onClick={()=>onNavigate('Records')}>Inspect records</button>
   <button type="button" data-testid="second-opinion-open-questions" onClick={()=>onNavigate('Investigations')}>Prepare questions</button>
   <button type="button" data-testid="second-opinion-open-review" onClick={()=>onNavigate('Review')}>Inspect verification returns</button>
  </div>
 </section>;
}
