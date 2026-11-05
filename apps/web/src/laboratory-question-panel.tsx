import {useEffect,useRef,useState} from 'react';
import type {RegistrySession} from './registry-client';
import type {SourceWorldModel} from './source-world-model';
import {validLabQuestion} from './laboratory-question';
import type {LabPreparation} from './laboratory-question';

export function LaboratoryQuestionPanel({session,model,busy}:{session:RegistrySession;model:SourceWorldModel;busy:boolean}){
  const [selection,select]=useState(''),[question,edit]=useState(''),[pending,setPending]=useState(false);
  const [receipt,setReceipt]=useState<LabPreparation|null>(null),active=useRef<AbortController|null>(null);
  const stop=()=>{active.current?.abort();active.current=null;setPending(false);setReceipt(null);};
  useEffect(()=>()=>{active.current?.abort();active.current=null;},[]);
  const keyOf=(o:SourceWorldModel['laboratory_observations'][number])=>o.source_id+'|'+o.observation_reference;
  const item=model.laboratory_observations.find(o=>keyOf(o)===selection);
  const prepare=async()=>{
    if(!item||busy||active.current||!validLabQuestion(question))return;
    const control=new AbortController();active.current=control;setPending(true);setReceipt(null);
    try{
      const result=await session.prepareLabQuestion(model,item.source_id,item.observation_reference,question,control.signal);
      if(active.current===control)setReceipt(result);
    }finally{if(active.current===control){active.current=null;setPending(false);}}
  };
  return <form className="lab-question-form" aria-label="Question about a laboratory result" onSubmit={e=>{e.preventDefault();void prepare();}}>
    <h4>Prepare a question about a result</h4>
    <p>Choose a result and write what you want to ask your care team. This checks the question against the current report. It does not save or send it.</p>
    <label>Laboratory result
      <select data-testid="lab-question-result" value={selection} onChange={e=>{stop();select(e.target.value);edit('');}}>
        <option value="">Choose a result</option>
        {model.laboratory_observations.map(o=><option key={keyOf(o)} value={keyOf(o)}>
          {o.document_id} v{o.document_version} · {o.observation_reference} · {o.status==='reported_value'?o.value_text+' '+o.unit_code:'Absent: '+o.absent_reason}
        </option>)}
      </select>
    </label>
    {item&&<><label>Your question
      <textarea data-testid="lab-question-text" value={question} onChange={e=>{stop();edit(e.target.value);}} maxLength={500}/>
    </label>
    <button type="submit" data-testid="lab-question-prepare" disabled={busy||pending||!validLabQuestion(question)}>Check question against report</button></>}
    <div role="status" aria-live="polite">{pending?'Checking the current report and your access…':receipt&&item&&
      <div data-testid="lab-question-receipt"><strong>Question prepared · not saved</strong>
        <p>{question}</p><p>{item.observation_reference} · {item.document_id} v{item.document_version}</p>
        <details><summary>Source and access receipt</summary><p>Source <code>{item.source_id}</code></p>
          <p>Original SHA-256 <code>{item.source_sha256}</code></p><p>Read receipt <code>{receipt.receipt}</code></p></details>
      </div>}</div>
  </form>;
}
