import {useEffect,useRef,useState} from 'react';
import {LaboratoryCitationReportPanel} from './laboratory-citation-report-panel.js';
import {QuestionEvidencePanel} from './question-evidence-panel';
import type {RegistrySession,ViewState} from './registry-client';
import type {SourceWorldModel} from './source-world-model';
import {validLabQuestion} from './laboratory-question';
import type {LabPreparation,LabQuestionView} from './laboratory-question';

export function LaboratoryQuestionPanel({session,model,busy,sourceSavePending,state}:{session:RegistrySession;model:SourceWorldModel;busy:boolean;sourceSavePending:boolean;state:LabQuestionView}){
  const [selection,select]=useState(''),[question,edit]=useState(''),[pending,setPending]=useState(false);
  const [receipt,setReceipt]=useState<LabPreparation|null>(null),active=useRef<AbortController|null>(null);
  const locked=state.labQuestionWritePhase==='saving'||state.labQuestionWritePhase==='unknown';
  const stop=()=>{active.current?.abort();active.current=null;setPending(false);setReceipt(null);};
  useEffect(()=>()=>{active.current?.abort();active.current=null;},[]);
  useEffect(()=>{if(state.labQuestionListPhase==='error'||state.labQuestionWritePhase==='error'){active.current?.abort();active.current=null;setReceipt(null);setPending(false);}},[state.labQuestionListPhase,state.labQuestionWritePhase]);
  const keyOf=(o:SourceWorldModel['laboratory_observations'][number])=>o.source_id+'|'+o.observation_reference;
  const item=model.laboratory_observations.find(o=>keyOf(o)===selection);
  const prepare=async()=>{
    if(!item||busy||sourceSavePending||locked||active.current||!validLabQuestion(question))return;
    const control=new AbortController();active.current=control;setPending(true);setReceipt(null);
    try{
      const result=await session.prepareLabQuestion(model,item.source_id,item.observation_reference,question,control.signal);
      if(active.current===control)setReceipt(result);
    }finally{if(active.current===control){active.current=null;setPending(false);}}
  };
  const save=()=>{if(!receipt||!item||locked||sourceSavePending||busy)return;const verified=receipt;setReceipt(null);void session.saveLabQuestion(model,verified);};
  return <form className="lab-question-form" aria-label="Question about a laboratory result" onSubmit={e=>{e.preventDefault();void prepare();}}>
    <h4>Prepare a question about a result</h4>
    <p>Choose a result and write what you want to ask your care team. Check the wording against the current report. You can then save the question for your next discussion.</p>
    <label>Laboratory result
      <select data-testid="lab-question-result" disabled={locked} value={selection} onChange={e=>{stop();select(e.target.value);edit('');}}>
        <option value="">Choose a result</option>
        {model.laboratory_observations.map(o=><option key={keyOf(o)} value={keyOf(o)}>
          {o.document_id} v{o.document_version} · {o.observation_reference} · {o.status==='reported_value'?o.value_text+' '+o.unit_code:'Absent: '+o.absent_reason}
        </option>)}
      </select>
    </label>
    {item&&<><label>Your question
      <textarea data-testid="lab-question-text" disabled={locked} value={question} onChange={e=>{stop();edit(e.target.value);}} maxLength={500}/>
    </label>
    <button type="submit" data-testid="lab-question-prepare" disabled={busy||sourceSavePending||locked||pending||!validLabQuestion(question)}>Check question against report</button></>}
    {sourceSavePending&&<p role="status">Finish the current question save or recover its receipt in Investigations before checking this result.</p>}
    <div role="status" aria-live="polite">{pending?'Checking the current report and your access…':receipt&&item&&
      <div data-testid="lab-question-receipt"><strong>Question prepared · not saved</strong>
        <p>{question}</p><p>{item.observation_reference} · {item.document_id} v{item.document_version}</p>
        <details><summary>Source and access receipt</summary><p>Source <code>{item.source_id}</code></p>
          <p>Original SHA-256 <code>{item.source_sha256}</code></p><p>Read receipt <code>{receipt.receipt}</code></p></details>
        <button type="button" data-testid="lab-question-save" disabled={busy||sourceSavePending||locked} onClick={save}>Save this question</button>
      </div>}</div>
  </form>;
}

export function SavedLaboratoryQuestions({session,model,state,busy,sourceSavePending}:{session:RegistrySession;model:SourceWorldModel;state:ViewState;busy:boolean;sourceSavePending:boolean}){
  const locked=['saving','unknown'].includes(state.labQuestionWritePhase);
  return <section aria-label="Saved laboratory questions" data-testid="lab-saved-questions">
    <h4>Saved laboratory questions</h4>
    {state.labQuestionWriteMessage&&<p role="status" data-testid="lab-question-save-status">{state.labQuestionWriteMessage}{state.labQuestionSavedId&&<> <code>{state.labQuestionSavedId}</code></>}</p>}
    {state.labQuestionWritePhase==='unknown'&&<button type="button" data-testid="lab-question-retry" disabled={busy||sourceSavePending} onClick={()=>void session.retryLabQuestion(model)}>Retry original save</button>}
    <button type="button" data-testid="lab-questions-reopen" disabled={busy||sourceSavePending||locked||state.labQuestionListPhase==='loading'} onClick={()=>void session.loadLabQuestions(model)}>Reopen saved laboratory questions</button>
    {state.labQuestionListMessage&&<p role="status">{state.labQuestionListMessage}</p>}
    {state.labQuestionHistory&&<>{state.labQuestionHistory.questions.length===0?<p>No laboratory questions saved for this case.</p>:<ul>{state.labQuestionHistory.questions.map(row=><li key={row.question_id} data-testid="lab-saved-question" data-question-id={row.question_id}>
      <p><strong>{row.question}</strong></p>
      <p>{row.source_context_state==='source_reassessment_required'?'Needs reassessment · the original question is preserved.':'Unreviewed · source context current at last check.'}</p>
      <p>{row.observation_reference} · source version {row.source_version}</p>
      <details><summary>Inspect saved source reference</summary><p>Original source <code>{row.source_id}</code> · SHA-256 <code>{row.source_sha256}</code></p>
        <p>Question <code>{row.question_id}</code></p><p>Context fingerprint <code>{row.source_snapshot_sha256}</code></p></details>
      <QuestionEvidencePanel question={row} state={state} session={session} busy={busy||locked||sourceSavePending}/>
      <LaboratoryCitationReportPanel question={row} state={state} session={session} busy={busy||locked||sourceSavePending}/>
    </li>)}</ul>}</>}
  </section>;
}
