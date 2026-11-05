import {useState} from 'react';
import type {RegistrySession,ViewState} from './registry-client';
import type {SourceQuestion} from './source-questions-view';
import {canCreateFollowthrough,FOLLOWTHROUGH_TRANSITIONS,validFollowthroughDraft,
  validFollowthroughText,projectFollowthroughAttention,FOLLOWTHROUGH_FILTERS,
  followthroughFilterForRead,matchesFollowthroughFilter,followthroughTransitionContext} from './followthrough-view';
import type {FollowthroughDraft,FollowthroughTask,FollowthroughStatus,FollowthroughFilterSelection,FollowthroughUnsentTransition} from './followthrough-view';

type Props={state:ViewState;session:RegistrySession;busy:boolean};
const blankDraft=():FollowthroughDraft=>({title:'',detail:'',owner_label:'',due_date:null,review_trigger:'',reason:''});
const labels:Record<FollowthroughStatus,string>={created:'Created',assigned:'Assigned',acknowledged:'Acknowledged',completed:'Completed',deferred:'Deferred'};

/** The exact saved question is the entry point. Unsent text stays in the tab session. */
export function FollowthroughCreate({state,session,busy,question}:Props&{question:SourceQuestion}){
 const retained=state.followthroughDrafts[question.question_id];
 const open=!!retained&&retained.patient_id===question.patient_id&&retained.case_id===question.case_id&&
  retained.source_snapshot_sha256===question.source_snapshot_sha256&&retained.preflight_sha256===question.preflight_sha256;
 const draft=open?retained.fields:blankDraft();
 const blocked=busy||state.followthroughWritePhase==='saving'||state.followthroughWritePhase==='unknown';
 const current=state.worldPhase==='ready'&&state.questionListPhase==='ready'&&canCreateFollowthrough(question,state.worldModel);
 const field=(key:keyof FollowthroughDraft,value:string|null)=>session.editFollowthroughDraft(question.question_id,{...draft,[key]:value});
 return <div className="followthrough-create">
  <button type="button" data-testid="followthrough-open-create" disabled={blocked||!current}
   onClick={()=>session.editFollowthroughDraft(question.question_id,draft)}>Record follow-up work for this question</button>
  {!current&&<p className="muted">New work needs a question prepared from the current source context. Earlier task history stays available below.</p>}
  {open&&<form data-testid="followthrough-create-form" className="followthrough-form"
    onSubmit={event=>{event.preventDefault();void session.createFollowthrough(question.question_id,draft);}}>
   <h4>Record the next piece of work</h4>
   <p>Record a coordination or verification task. The platform will not perform it, send a notification or issue a clinical order.</p>
   <p className="muted">Unsent details stay in this tab while you inspect the same case. They clear when the source context or access changes, or when you disconnect or reload.</p>
   <fieldset disabled={blocked||!current}>
    <legend className="visually-hidden">Follow-up details</legend>
    <label>Task title
     <input data-testid="followthrough-title" value={draft.title} required minLength={3} maxLength={160}
      autoComplete="off" onChange={event=>field('title',event.target.value)}/></label>
    <label>Details (optional)
     <textarea data-testid="followthrough-detail" value={draft.detail} rows={3} maxLength={2000}
      autoComplete="off" onChange={event=>field('detail',event.target.value)}/></label>
    <label>Recorded owner (optional until assignment)
     <input data-testid="followthrough-owner" value={draft.owner_label} maxLength={80} autoComplete="off"
      onChange={event=>field('owner_label',event.target.value)}/></label>
    <p className="muted">An owner label records responsibility. It does not grant access or verify professional identity.</p>
    <div className="followthrough-fields">
     <label>Revisit date
      <input type="date" data-testid="followthrough-due-date" value={draft.due_date??''}
       onChange={event=>field('due_date',event.target.value||null)}/></label>
     <label>Review trigger
      <input data-testid="followthrough-trigger" value={draft.review_trigger} maxLength={500} autoComplete="off"
       onChange={event=>field('review_trigger',event.target.value)}/></label>
    </div>
    <p className="muted">Provide a revisit date, a review trigger, or both. Date flags track recorded work, not clinical urgency.</p>
    <label>Reason for recording this work
     <textarea data-testid="followthrough-reason" value={draft.reason} required minLength={3} maxLength={600} rows={2}
      autoComplete="off" onChange={event=>field('reason',event.target.value)}/></label>
    <p className="muted">Title, details and timing are retained as recorded in this first version. Assignment changes through defer and reassign, preserving history.</p>
    <div className="actions">
     <button type="submit" className="primary" data-testid="followthrough-create" disabled={!validFollowthroughDraft(draft)}>Record follow-up task</button>
     <button type="button" data-testid="followthrough-cancel" onClick={()=>session.clearFollowthroughDraft(question.question_id)}>Clear draft</button>
    </div>
   </fieldset>
  </form>}
 </div>;
}

function TaskCard({task,session,disabled,hidden,draft}:{task:FollowthroughTask;session:RegistrySession;disabled:boolean;hidden:boolean;draft:FollowthroughUnsentTransition|undefined}){
 const retained=draft?.context===followthroughTransitionContext(task)?draft.fields:null;
 const owner=retained?.owner_label??task.owner_label,reason=retained?.reason??'';
 const choices=FOLLOWTHROUGH_TRANSITIONS[task.status];
 const actionLabels:Partial<Record<FollowthroughStatus,string>>={assigned:task.status==='deferred'?'Reassign task':'Assign task',
  acknowledged:'Record acknowledgment',completed:'Record completion',deferred:'Defer task'};
 const testIds:Partial<Record<FollowthroughStatus,string>>={assigned:'assign',acknowledged:'acknowledge',completed:'complete',deferred:'defer'};
 return <li className="followthrough-task" data-testid="followthrough-task" data-task-id={task.task_id}
   data-status={task.status} data-revision={task.revision} hidden={hidden}>
  <div className="question-status-title"><h4>{task.title}</h4><span className="question-status">{labels[task.status]}</span></div>
  {task.detail&&<p>{task.detail}</p>}
  <p><strong>Recorded owner:</strong> {task.owner_label||'Unassigned'} · <strong>Revisit date:</strong> {task.due_date??'Not set'}</p>
  {task.review_trigger&&<p><strong>Review trigger:</strong> {task.review_trigger}</p>}
  {task.needs_recheck&&<p className="followthrough-flag" data-testid="followthrough-recheck">Source context changed — recheck this open work against the original question. No replacement conclusion has been approved.</p>}
  {task.is_overdue&&<p className="followthrough-flag" data-testid="followthrough-overdue">Recorded revisit date has passed. This is a work-tracking flag, not a clinical urgency assessment.</p>}
  {task.is_due_soon&&<p className="followthrough-flag" data-testid="followthrough-due-soon">Recorded revisit date is within seven days of this check.</p>}
  {task.source_context_state==='source_reassessment_required'&&!task.needs_recheck&&<p className="muted">Original source context needs reassessment. This completed or deferred task remains historical.</p>}
  <details><summary>Original question and source provenance</summary>
   <p>Question <code>{task.question_id}</code> · Task <code>{task.task_id}</code> · revision {task.revision}</p>
   <p>Original <code>{task.source_id}</code> · v{task.source_version}, line {task.source_line}</p>
   <p>Original SHA-256 <code>{task.source_sha256}</code></p>
   <p>Source snapshot <code>{task.source_snapshot_contract}</code> · <code>{task.source_snapshot_sha256}</code></p>
   <p>Question preflight <code>{task.preflight_sha256}</code></p>
  </details>
  {choices.length>0&&<div className="followthrough-transition followthrough-form">
   <fieldset disabled={disabled||hidden}>
    <legend>Record a status change</legend>
    {choices.includes('assigned')&&<label>Owner for assignment
     <input data-testid="followthrough-transition-owner" value={owner} maxLength={80} autoComplete="off"
      onChange={event=>session.editFollowthroughTransitionDraft(task.task_id,{owner_label:event.target.value,reason})}/></label>}
    <label>Reason for this status change
     <textarea data-testid="followthrough-transition-reason" value={reason} rows={2} maxLength={600}
      autoComplete="off" onChange={event=>session.editFollowthroughTransitionDraft(task.task_id,{owner_label:owner,reason:event.target.value})}/></label>
    <div className="actions">{choices.map(status=><button key={status} type="button"
      data-testid={'followthrough-'+testIds[status]}
      disabled={!validFollowthroughText(reason,3,600)||(status==='assigned'&&!validFollowthroughText(owner,2,80))}
      onClick={()=>void session.transitionFollowthrough(task.task_id,{status,reason,owner_label:status==='assigned'?owner:''})}>
       {actionLabels[status]}</button>)}
     {retained&&<button type="button" data-testid="followthrough-clear-transition"
       onClick={()=>session.clearFollowthroughTransitionDraft(task.task_id)}>Clear unsent status change</button>}
    </div>
   </fieldset>
   <p className="muted">Unsent details stay in this tab while this task and its source context remain unchanged.</p>
   <p className="muted">A status change records an attributed assertion about work. Completion requires acknowledgment and does not approve the source or question.</p>
  </div>}
  <details className="followthrough-history"><summary>Attributed status history ({task.history.length})</summary>
   <ol data-testid="followthrough-history">{task.history.map(event=><li key={event.event_id}>
    <strong>{labels[event.status]}</strong> · <time dateTime={event.recorded_at}>{event.recorded_at}</time>
    <p>{event.reason}</p><p>Recorded owner: {event.owner_label||'Unassigned'} · Synthetic actor: <code>{event.actor_label}</code></p>
    <p className="muted">Revision {event.revision} · <code>{event.event_id}</code></p>
   </li>)}</ol>
  </details>
 </li>;
}

export function FollowthroughPanel({state,session,busy}:Props){
 const intent=state.followthroughIntent;
 const caseId=state.worldModel?.case_id??intent?.case_id??state.followthroughCaseId??'';
 const attention=projectFollowthroughAttention(state);
 const list=attention?.list??null;
 const [selection,setSelection]=useState<FollowthroughFilterSelection|null>(null);
 const filter=followthroughFilterForRead(selection,attention);
 const saving=state.followthroughWritePhase==='saving',unknown=state.followthroughWritePhase==='unknown';
 const active=state.connected&&state.phase==='ready'&&state.cases?.some(row=>row.case_id===caseId&&row.status==='active');
 const receipt=state.followthroughReceipt;
 return <section data-testid="followthrough-panel" className="followthrough-panel" aria-labelledby="followthrough-heading">
  <div className="question-history-heading"><div><h3 id="followthrough-heading" data-workspace-anchor="Follow-up work">Follow-up work</h3>
   <p>Owners, revisit dates and attributed history for saved source questions.</p></div>
   <button type="button" data-testid="followthrough-refresh" disabled={!active||busy||saving||state.followthroughPhase==='loading'}
    onClick={()=>void session.loadFollowthrough(caseId)}>{state.followthroughPhase==='loading'?'Checking recorded work…':'Refresh recorded work'}</button>
  </div>
  <p role="status" aria-live="polite" data-testid="followthrough-status" data-phase={state.followthroughPhase}
   className={'status '+(state.followthroughPhase==='error'?'error':'')}>{state.followthroughMessage}</p>
  <p role="status" aria-live="polite" data-testid="followthrough-write-status" data-phase={state.followthroughWritePhase}
   className={'status '+(state.followthroughWritePhase==='error'?'error':'')}>{state.followthroughWriteMessage}</p>
  {receipt&&<p data-testid="followthrough-receipt" className="review-result" data-duplicate={receipt.duplicate}>
   {receipt.duplicate?'Original receipt recovered':'Work recorded'} · <code>{receipt.task_id}</code> · revision {receipt.revision} · <code>{receipt.event_id}</code>
  </p>}
  {intent&&(unknown||saving)&&<section className="review-recovery" data-testid="followthrough-recovery" aria-label="Exact pending follow-up write">
   <h4>{unknown?'Recover the uncertain write':'Recording this exact work'}</h4>
   <p><strong>Question:</strong> <code>{intent.question_id}</code></p>
   {intent.kind==='create'?<>
    <p><strong>Task:</strong> {intent.body.title}</p>{intent.body.detail&&<p>{intent.body.detail}</p>}
    <p><strong>Owner:</strong> {intent.body.owner_label||'Unassigned'} · <strong>Revisit date:</strong> {intent.body.due_date??'Not set'}</p>
    {intent.body.review_trigger&&<p><strong>Review trigger:</strong> {intent.body.review_trigger}</p>}
   </>:<p><strong>Task:</strong> <code>{intent.task_id}</code> · {labels[intent.body.status]} from revision {intent.body.expected_revision}
     {intent.body.owner_label&&<> · owner {intent.body.owner_label}</>}</p>}
   <p><strong>Recorded reason:</strong> {intent.body.reason}</p>
   <p>The earlier write may have committed. Retry sends the same task, source context or revision, reason and request key. It cannot retarget this work to a different question.</p>
   {unknown&&<div className="actions">
    <button type="button" data-testid="followthrough-retry" disabled={busy||!active} onClick={()=>void session.retryFollowthroughWrite()}>Retry exact write</button>
    <button type="button" data-testid="followthrough-abandon" disabled={busy} onClick={()=>session.abandonFollowthroughWrite()}>Abandon recovery and clear intent</button>
   </div>}
   {unknown&&<p className="muted">Abandoning recovery does not undo a committed write. Inspect current task history before recording new work.</p>}
  </section>}
  {list&&attention&&<>
   <div data-testid="followthrough-attention">
    <h4>Find recorded work that needs attention</h4>
    <div className="actions" role="group" aria-label="Filter recorded follow-up work">
     {FOLLOWTHROUGH_FILTERS.map(({key,label})=><button key={key} type="button"
      data-testid={'followthrough-filter-'+key} data-count={attention.counts[key]}
      aria-pressed={filter===key} aria-controls="followthrough-items" className={filter===key?'primary':''}
      onClick={()=>setSelection({access_receipt_id:list.access_receipt_id,
       patient_id:list.patient_id,case_id:list.case_id,filter:key})}>
       {label} ({attention.counts[key]})</button>)}
    </div>
    <p role="status" aria-live="polite" data-testid="followthrough-filter-status">
     Showing {attention.counts[filter]} of {attention.counts.all} recorded tasks.
    </p>
    <p className="muted">Filters can overlap. Counts describe the last successful read, not clinical urgency or an assessment of all care needs. Refreshing resets to All work.</p>
   </div>
   <p><strong>Case:</strong> <code>{list.case_id}</code> · Date flags evaluated {list.evaluated_on} (UTC).</p>
   <details><summary>Access receipt for this read</summary><code>{list.access_receipt_id}</code>
    <p>Access is checked separately for each read and write. Owner labels are not authorization.</p></details>
   {list.tasks.length===0?<p id="followthrough-items">No recorded work is visible. Start from a current saved question above.</p>:
    <>
     {attention.counts[filter]===0&&<p data-testid="followthrough-filter-empty">No recorded tasks match this filter in the last successful read.</p>}
     <ul id="followthrough-items" className="followthrough-items">{list.tasks.map(task=><TaskCard key={task.task_id+':'+task.revision}
      task={task} session={session} hidden={!matchesFollowthroughFilter(task,filter)}
      draft={state.followthroughTransitionDrafts[task.task_id]}
      disabled={busy||saving||unknown||state.followthroughPhase!=='ready'}/>)}</ul>
    </>}
  </>}
  <p className="muted">Fictional coordination records only. No external notification, clinical order or clinical approval is produced.</p>
 </section>;
}
