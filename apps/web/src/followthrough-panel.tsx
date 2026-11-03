import {useEffect,useState} from 'react';
import type {RegistrySession,ViewState} from './registry-client';
import type {SourceQuestion} from './source-questions-view';
import {canCreateFollowthrough,FOLLOWTHROUGH_TRANSITIONS,validFollowthroughDraft,
  validFollowthroughText} from './followthrough-view';
import type {FollowthroughDraft,FollowthroughTask,FollowthroughStatus} from './followthrough-view';

type Props={state:ViewState;session:RegistrySession;busy:boolean};
const blankDraft=():FollowthroughDraft=>({title:'',detail:'',owner_label:'',due_date:null,review_trigger:'',reason:''});
const labels:Record<FollowthroughStatus,string>={created:'Created',assigned:'Assigned',acknowledged:'Acknowledged',completed:'Completed',deferred:'Deferred'};

/** The exact saved question is the entry point. Text remains in component memory only. */
export function FollowthroughCreate({state,session,busy,question}:Props&{question:SourceQuestion}){
 const [open,setOpen]=useState(false),[draft,setDraft]=useState<FollowthroughDraft>(blankDraft);
 const blocked=busy||state.followthroughWritePhase==='saving'||state.followthroughWritePhase==='unknown';
 const current=state.worldPhase==='ready'&&state.questionListPhase==='ready'&&canCreateFollowthrough(question,state.worldModel);
 const field=(key:keyof FollowthroughDraft,value:string|null)=>setDraft(previous=>({...previous,[key]:value}));
 useEffect(()=>{
  // Only creation has revision 1; another task's transition must preserve this draft.
  if(state.followthroughWritePhase==='saved'&&state.followthroughReceipt?.revision===1&&
     state.followthroughReceipt.question_id===question.question_id){
   setDraft(blankDraft());setOpen(false);
  }
 },[state.followthroughReceipt,state.followthroughWritePhase,question.question_id]);
 return <div className="followthrough-create">
  <button type="button" data-testid="followthrough-open-create" disabled={blocked||!current}
   onClick={()=>setOpen(true)}>Record follow-up work for this question</button>
  {!current&&<p className="muted">New work needs a question prepared from the current source context. Earlier task history stays available below.</p>}
  {open&&<form data-testid="followthrough-create-form" className="followthrough-form"
    onSubmit={event=>{event.preventDefault();void session.createFollowthrough(question.question_id,draft);}}>
   <h4>Record the next piece of work</h4>
   <p>Record a coordination or verification task. The platform will not perform it, send a notification or issue a clinical order.</p>
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
     <button type="button" data-testid="followthrough-cancel" onClick={()=>{setOpen(false);setDraft(blankDraft());}}>Clear draft</button>
    </div>
   </fieldset>
  </form>}
 </div>;
}

function TaskCard({task,session,disabled}:{task:FollowthroughTask;session:RegistrySession;disabled:boolean}){
 const [owner,setOwner]=useState(task.owner_label),[reason,setReason]=useState('');
 const choices=FOLLOWTHROUGH_TRANSITIONS[task.status];
 const actionLabels:Partial<Record<FollowthroughStatus,string>>={assigned:task.status==='deferred'?'Reassign task':'Assign task',
  acknowledged:'Record acknowledgment',completed:'Record completion',deferred:'Defer task'};
 const testIds:Partial<Record<FollowthroughStatus,string>>={assigned:'assign',acknowledged:'acknowledge',completed:'complete',deferred:'defer'};
 return <li className="followthrough-task" data-testid="followthrough-task" data-task-id={task.task_id}
   data-status={task.status} data-revision={task.revision}>
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
   <fieldset disabled={disabled}>
    <legend>Record a status change</legend>
    {choices.includes('assigned')&&<label>Owner for assignment
     <input data-testid="followthrough-transition-owner" value={owner} maxLength={80} autoComplete="off"
      onChange={event=>setOwner(event.target.value)}/></label>}
    <label>Reason for this status change
     <textarea data-testid="followthrough-transition-reason" value={reason} rows={2} maxLength={600}
      autoComplete="off" onChange={event=>setReason(event.target.value)}/></label>
    <div className="actions">{choices.map(status=><button key={status} type="button"
      data-testid={'followthrough-'+testIds[status]}
      disabled={!validFollowthroughText(reason,3,600)||(status==='assigned'&&!validFollowthroughText(owner,2,80))}
      onClick={()=>void session.transitionFollowthrough(task.task_id,{status,reason,owner_label:status==='assigned'?owner:''})}>
       {actionLabels[status]}</button>)}</div>
   </fieldset>
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
 const list=state.followthrough?.case_id===caseId?state.followthrough:null;
 const saving=state.followthroughWritePhase==='saving',unknown=state.followthroughWritePhase==='unknown';
 const active=state.connected&&state.phase==='ready'&&state.cases?.some(row=>row.case_id===caseId&&row.status==='active');
 const receipt=state.followthroughReceipt;
 return <section data-testid="followthrough-panel" className="followthrough-panel" aria-labelledby="followthrough-heading">
  <div className="question-history-heading"><div><h3 id="followthrough-heading">Follow-up work</h3>
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
  {list&&<>
   <p><strong>Case:</strong> <code>{list.case_id}</code> · Date flags evaluated {list.evaluated_on} (UTC).</p>
   <details><summary>Access receipt for this read</summary><code>{list.access_receipt_id}</code>
    <p>Access is checked separately for each read and write. Owner labels are not authorization.</p></details>
   {list.tasks.length===0?<p>No recorded work is visible. Start from a current saved question above.</p>:
    <ul className="followthrough-items">{list.tasks.map(task=><TaskCard key={task.task_id+':'+task.revision}
     task={task} session={session} disabled={busy||saving||unknown||state.followthroughPhase!=='ready'}/>)}</ul>}
  </>}
  <p className="muted">Fictional coordination records only. No external notification, clinical order or clinical approval is produced.</p>
 </section>;
}
