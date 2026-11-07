import {useState} from 'react';
import type {RegistrySession,ViewState} from './registry-client';
import type {LabQuestionList,SavedLabQuestion} from './laboratory-question';
import {PreparationLaboratoryFollowup} from './preparation-laboratory-followup';
import {LaboratoryCitationReportPanel} from './laboratory-citation-report-panel';
import {questionSaveBlocksSourceChange} from './source-questions-view';
import {secondOpinionPreparation} from './second-opinion-preparation';
import './second-opinion-agenda.css';

const summary={
 needs_check:'Check the case inputs before preparing a second-opinion discussion.',
 needs_records:'No current original source version is loaded for this case.',
 needs_question:'Original records are available, but no current text-anchored question is loaded in this agenda. Laboratory questions are checked separately.',
 needs_laboratory_review:'Choose a saved laboratory question to inspect its original result and permitted citations.',
 needs_reassessment:'A source changed. Reassess affected questions before relying on earlier preparation.',
 inputs_prepared:'The currently loaded records and questions are organized for preparation.',
} as const;

type OpenLaboratoryTask=(question:SavedLabQuestion,taskId:string)=>void;

function PreparationLaboratoryQuestions({history,session,state,busy,onOpenTask}:{
 history:LabQuestionList; session:RegistrySession; state:ViewState; busy:boolean;onOpenTask?:OpenLaboratoryTask;
}){
 const [questionId,setQuestionId]=useState('');
 const selected=history.questions.find(row=>row.question_id===questionId);
 const sources=[...(state.worldModel?.current_sources??[]),...(state.worldModel?.history??[])];
 const reportNames=new Map(sources.map(source=>[source.source_id,source.document_id]));
 return <section className="second-opinion-agenda preparation-lab" aria-labelledby="preparation-lab-heading">
  <h3 id="preparation-lab-heading">Laboratory questions for discussion</h3>
  <label>Choose a saved laboratory question
   <select data-testid="preparation-lab-select" value={questionId}
    onChange={event=>setQuestionId(event.currentTarget.value)}>
    <option value="">Choose a question</option>
    {history.questions.map(row=><option key={row.question_id} value={row.question_id}>
     {row.question} · {reportNames.get(row.source_id)} v{row.source_version} · {row.observation_reference}
    </option>)}
   </select>
  </label>
  {selected&&<div data-testid="preparation-lab-question" data-question-id={selected.question_id}>
   <p className="second-opinion-agenda-question"><strong>{selected.question}</strong></p>
   <p>{reportNames.get(selected.source_id)} · version {selected.source_version} · {selected.observation_reference}.{' '}
    {selected.source_context_state==='source_reassessment_required'?
     'Needs reassessment. Review the original result.':'Source context current at last check. Unreviewed.'}</p>
   <LaboratoryCitationReportPanel key={selected.question_id} session={session} state={state} question={selected}
    busy={busy}/>
   <PreparationLaboratoryFollowup session={session} state={state} question={selected} caseId={history.case_id} busy={busy} onOpenTask={onOpenTask}/>
  </div>}
 </section>;
}

export function SecondOpinionPreparation({state,session,busy,onNavigate,onResumeQuestion,onCheckEvidence,onOpenLaboratoryTask}:{
 state:ViewState;session:RegistrySession;busy:boolean;onNavigate:(section:string)=>void;onResumeQuestion:(questionId:string)=>void;
 onCheckEvidence:(questionId:string)=>void;onOpenLaboratoryTask?:OpenLaboratoryTask;
}){
 const view=secondOpinionPreparation(state);
 if(!view)return null;
 const model=state.worldModel;
 const laboratoryBusy=busy||questionSaveBlocksSourceChange(state)||
  ['saving','unknown'].includes(state.labQuestionWritePhase)||
  ['saving','unknown'].includes(state.evidenceLinkPhase)||state.evidenceWritePhase==='unknown';
 return <section className="panel second-opinion-preparation" data-testid="second-opinion-preparation" data-state={view.state} aria-labelledby="second-opinion-heading">
  <span className="step">SECOND OPINION · PREPARATION ONLY</span>
  <h2 id="second-opinion-heading" data-workspace-anchor="Second-opinion preparation">Prepare a focused second-opinion discussion</h2>
  <p>{summary[view.state]}</p>
  <p className="small">This view organizes the last successfully authorized information in this session. It does not verify record completeness, choose a specialist, create a referral, transmit records, establish eligibility, or confirm an appointment.</p>
  <dl className="second-opinion-checklist" aria-label="Second-opinion preparation status">
   <div data-testid="second-opinion-records">
    <dt>Original records</dt>
    <dd>{view.records?view.records.current===0?'Checked: no current source version returned.':<>{view.records.current} current source {view.records.current===1?'version':'versions'}{view.records.historical>0?' · '+view.records.historical+' historical':''}</>:'Not checked for the selected case.'}</dd>
   </div>
   <div data-testid="second-opinion-questions">
    <dt>Text-anchored focused questions</dt>
    <dd>{view.questions?<>{view.questions.current} current · {view.questions.reassessment} needing source reassessment</>:'Not checked for the selected case.'}</dd>
   </div>
   {view.laboratoryAvailable&&<div data-testid="second-opinion-lab-questions">
    <dt>Saved laboratory questions</dt>
    <dd>{view.laboratoryQuestions?<>{view.laboratoryQuestions.current} current · {view.laboratoryQuestions.reassessment} needing source reassessment. These unreviewed questions refer to individual laboratory observations.</>:state.labQuestionListPhase==='loading'?'Checking saved laboratory questions…':'Saved laboratory questions have not been checked for this case.'}
     {model&&<button type="button" data-testid="preparation-lab-refresh"
      disabled={laboratoryBusy||state.labQuestionListPhase==='loading'} onClick={()=>void session.loadLabQuestions(model)}>
      {view.laboratoryQuestions?'Refresh laboratory questions':'Check laboratory questions'}
     </button>}
    </dd>
   </div>}
   <div data-testid="second-opinion-coordination">
    <dt>Recorded coordination</dt>
    <dd>{view.coordination?<>{view.coordination.open} open · {view.coordination.assigned} with a recorded owner{view.coordination.sourceChanged>0?' · '+view.coordination.sourceChanged+' source-changed':''}</>:'Follow-up work has not been checked or is unavailable.'}</dd>
   </div>
  </dl>
  {view.laboratoryQuestions&&state.labQuestionHistory&&state.labQuestionHistory.questions.length>0&&
   <PreparationLaboratoryQuestions key={state.labQuestionHistory.access_receipt_id} history={state.labQuestionHistory}
    session={session} state={state} busy={laboratoryBusy} onOpenTask={onOpenLaboratoryTask}/>}
  <section className="second-opinion-agenda" aria-labelledby="second-opinion-agenda-heading" data-testid="second-opinion-agenda">
   <h3 id="second-opinion-agenda-heading" data-workspace-anchor="Discussion questions">Text-source questions for discussion</h3>
   <p>Each saved question below refers to a line in a record. Source status reflects the last authorized read.</p>
   <p data-testid="second-opinion-context-scope">Attached passages and preserved reports need a separate freshness check in Investigations.</p>
   {view.agenda&&state.manualPassageDraftQuestionIds.length>0&&<p data-testid="second-opinion-passage-drafts">
    {state.manualPassageDraftQuestionIds.length} {state.manualPassageDraftQuestionIds.length===1?'question has':'questions have'} unsaved record-passage changes in this session, not yet attached.
    {' '}Open the matching question to recheck and resume. Questions outside this preview are available in Investigations.
   </p>}
   {!view.agenda?<p role="status" data-testid="second-opinion-agenda-unavailable">Questions have not been checked for this case, or that history is no longer available. Return to Investigations for an authorized read.</p>:
    view.agenda.total===0?<p data-testid="second-opinion-agenda-empty">No text-anchored questions were returned for this case and grant. Laboratory questions are tracked separately; this does not establish that there are no care questions.</p>:<>
     <p className="small" data-testid="second-opinion-agenda-coverage">Showing {view.agenda.preview.length} of {view.agenda.total} saved {view.agenda.total===1?'question':'questions'} in the recorded order. Open Investigations to see the full history.</p>
     <ol className="second-opinion-agenda-list" aria-label="Saved discussion questions">
      {view.agenda.preview.map(item=><li key={item.questionId} data-testid="second-opinion-agenda-item" data-question-id={item.questionId} data-source-context={item.sourceContextState}>
       <p className="second-opinion-agenda-question">{item.text}</p>
       {state.manualPassageDraftQuestionIds.includes(item.questionId)?
        <button type="button" data-testid="second-opinion-resume-passages" onClick={()=>onResumeQuestion(item.questionId)}>Resume unsaved record passages</button>:
        <button type="button" data-testid="second-opinion-open-question" aria-label={'Inspect records and reports for: '+item.text} onClick={()=>onResumeQuestion(item.questionId)}>Inspect records and reports</button>}
       <p className="small">Primary source version {item.sourceVersion}, line {item.sourceLine}. <strong>{item.sourceContextState==='source_reassessment_required'?'Source changed: reassessment required before relying on earlier preparation.':'Primary source context is current; not clinically reviewed.'}</strong></p>
       <section className="second-opinion-question-evidence" data-testid="second-opinion-question-evidence"
        data-original-state={item.evidenceReadiness.original}
        data-citation-state={item.evidenceReadiness.citations===null?'unchecked':'checked'}
        aria-label="Evidence-readiness for this saved question">
        <h4>What evidence should be checked?</h4>
        {item.evidenceReadiness.original==='matched'?
         <p data-testid="second-opinion-original-matched">The exact source version and hash matched the last authorized structured-record read, not an independent clinical review.</p>:
         item.evidenceReadiness.original==='changed'?
         <p data-testid="second-opinion-original-changed">The question needs source reassessment before relying on earlier preparation.</p>:
         item.evidenceReadiness.original==='not_matched'?
         <p data-testid="second-opinion-original-unmatched">The question's original version was not current in the last checked structured-record list. Review the original; separately reviewed documents are outside this count.</p>:
         <p data-testid="second-opinion-original-unchecked">The exact original has not been checked in the current Records view.</p>}
        {!item.evidenceReadiness.citations?
         <p data-testid="second-opinion-citations-unchecked">Citation history has not been successfully checked under its separate permission for this question. Open Investigations to request a fresh read.</p>:
         item.evidenceReadiness.citations.total===0?
         <p data-testid="second-opinion-citations-empty">The authorized citation read returned zero links. This does not establish that no scientific evidence exists.</p>:
         <p data-testid="second-opinion-citations-counts" data-count={item.evidenceReadiness.citations.total}>
          {item.evidenceReadiness.citations.metadataOnly} available metadata link(s) · {item.evidenceReadiness.citations.restricted} rights restricted · {item.evidenceReadiness.citations.superseded} superseded · {item.evidenceReadiness.citations.unavailable} unavailable.
         </p>}
        <p className="small">Citation metadata has not been appraised for scientific support. Trial eligibility, treatment benefit and clinical decisions have not been assessed by this view.</p>
       </section>
       <section className="second-opinion-proposal-readiness" data-testid="second-opinion-proposal-readiness"
        data-checked={item.comparisonReadiness!==null} aria-label="Human-authored evidence comparison status">
        <h4>Proposed evidence relationships</h4>
        <button type="button" data-testid="second-opinion-check-proposals"
         disabled={state.evidencePhase==='loading'||state.evidenceWritePhase==='saving'||state.evidenceWritePhase==='unknown'}
         onClick={()=>onCheckEvidence(item.questionId)}>
         {state.evidencePhase==='loading'?'Checking evidence permission…':'Check authored comparisons'}
        </button>
        {item.comparisonReadiness===null?
         <p data-testid="second-opinion-proposals-unchecked">Human-authored comparisons have not been freshly checked for this question and source snapshot. Use the button above to request an authorized read here, or inspect the question in Investigations.</p>:
         <div data-testid="second-opinion-proposals-checked">
          <p data-testid="second-opinion-proposals-counts">
           {item.comparisonReadiness.proposed.support} proposed support · {item.comparisonReadiness.proposed.contradiction} proposed contradiction · {item.comparisonReadiness.proposed.context} context · {item.comparisonReadiness.proposed.unknown} relationship unknown.
          </p>
          <p data-testid="second-opinion-proposals-history">
           {item.comparisonReadiness.reassessment} comparison(s) need reassessment · {item.comparisonReadiness.withheld} content withheld.
           {' '}{item.comparisonReadiness.reports.currentUnreviewed} current unreviewed report(s) · {item.comparisonReadiness.reports.historical} historical report(s) · {item.comparisonReadiness.reports.withheld} report(s) withheld.
          </p>
          {Object.values(item.comparisonReadiness.proposed).every(count=>count===0)&&
           item.comparisonReadiness.reassessment===0&&item.comparisonReadiness.withheld===0&&
           Object.values(item.comparisonReadiness.reports).every(count=>count===0)&&
           <p data-testid="second-opinion-proposals-empty">This authorized evidence read returned no authored comparisons or reports. It does not establish that no relevant research exists.</p>}
         </div>}
        <p className="small">All relationship labels are human-authored, unreviewed proposals—not a scientific evidence grade, AI conclusion, medical recommendation or clinician approval. Contents require a fresh rights check in Investigations.</p>
       </section>
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
   {view.state==='needs_laboratory_review'&&<button type="button" onClick={()=>onNavigate('Labs')}>Open lab questions</button>}
   <button type="button" data-testid="second-opinion-open-questions" onClick={()=>onNavigate('Investigations')}>Prepare questions</button>
   <button type="button" data-testid="second-opinion-open-review" onClick={()=>onNavigate('Review')}>Inspect verification returns</button>
  </div>
 </section>;
}
