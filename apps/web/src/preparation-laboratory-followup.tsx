import type {SavedLabQuestion} from './laboratory-question';
import type {RegistrySession,ViewState} from './registry-client';
import type {FollowthroughTask} from './followthrough-view';
import {laboratoryQuestionFollowthrough,matchesFollowthroughFilter} from './followthrough-view';

function RecordedTasks({tasks,onOpenTask,disabled}:{tasks:readonly FollowthroughTask[];onOpenTask?:(taskId:string)=>void;disabled:boolean}){
 return <ul className="second-opinion-question-work-list">
  {tasks.map(task=><li key={task.task_id} data-testid="preparation-lab-task" data-task-id={task.task_id}>
   <strong>{task.title}</strong>
   {task.detail&&<p>{task.detail}</p>}
   <p>Recorded owner: {task.owner_label||'Unassigned'} · Status: {task.status}</p>
   {task.due_date&&<p>Revisit on <time dateTime={task.due_date}>{task.due_date}</time></p>}
   {task.review_trigger&&<p>Revisit trigger: {task.review_trigger}</p>}
   {task.needs_recheck&&<p data-testid="preparation-lab-task-recheck"><strong>Reassessment needed.</strong> Recheck the original result before completing this work.</p>}
   {onOpenTask&&<button type="button" data-testid="preparation-lab-open-task" disabled={disabled}
    onClick={()=>onOpenTask(task.task_id)}>Open task history and actions</button>}
  </li>)}
 </ul>;
}

export function PreparationLaboratoryFollowup({session,state,question,caseId,busy,onOpenTask}:{
 session:RegistrySession; state:ViewState; question:SavedLabQuestion; caseId:string; busy:boolean;onOpenTask?:(question:SavedLabQuestion,taskId:string)=>void;
}){
 const work=laboratoryQuestionFollowthrough(state,question);
 const open=work?.tasks.filter(task=>!matchesFollowthroughFilter(task,'history'))??[];
 const history=work?.tasks.filter(task=>matchesFollowthroughFilter(task,'history'))??[];
 const loading=state.followthroughPhase==='loading';
 const pending=state.followthroughWritePhase==='saving'||state.followthroughWritePhase==='unknown';
 return <section className="second-opinion-question-work" aria-labelledby="preparation-lab-followup-heading" data-testid="preparation-lab-followup">
  <h4 id="preparation-lab-followup-heading">Follow-up for this result</h4>
  <button type="button" data-testid="preparation-lab-followup-refresh" disabled={busy||loading||pending}
   onClick={()=>void session.loadFollowthrough(caseId)}>{work?'Refresh follow-up':'Check follow-up'}</button>
  {pending?<p role="status">A follow-up change is awaiting confirmation. Open Investigations to check its status.</p>:
   loading?<p role="status">Checking follow-up access…</p>:
   !work?<p role="status" data-testid="preparation-lab-followup-unavailable">{state.followthroughPhase==='error'?
    'Follow-up is unavailable. Recheck access to view recorded work.':
    state.followthroughPhase==='ready'?'Refresh laboratory questions and follow-up to verify their source references.':
    'Check follow-up to see recorded tasks for this result.'}</p>:<>
    <p className="small">Task dates evaluated on <time dateTime={work.evaluatedOn}>{work.evaluatedOn}</time>.</p>
    {open.length>0?<RecordedTasks tasks={open} disabled={busy} onOpenTask={onOpenTask?taskId=>onOpenTask(question,taskId):undefined}/>:<p data-testid="preparation-lab-no-open-work">This task check returned no open follow-up for this result.</p>}
    {history.length>0&&<details><summary>Completed or deferred work ({history.length})</summary><RecordedTasks tasks={history} disabled={busy} onOpenTask={onOpenTask?taskId=>onOpenTask(question,taskId):undefined}/></details>}
   </>}
 </section>;
}
