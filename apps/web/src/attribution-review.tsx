import {useState} from 'react';
import type {RegistrySession,ViewState} from './registry-client';
import {validReturnReason} from './review-queue-view';
import type {ReviewQueueItem} from './review-queue-view';
import type {WorldObservation} from './source-world-model';

function Passage({item}:{item:WorldObservation}){
 return <div><p><strong>{item.document_id} v{item.document_version}, line {item.source_line}</strong>
  {' · '}{item.oncology?.episode_id??'Episode unassigned'} · {item.reported_state}</p>
  <blockquote>{item.source_statement}</blockquote></div>;
}

export function AttributionReview({state,session,question,disabled}:{
 state:ViewState;session:RegistrySession;question:ReviewQueueItem;disabled:boolean;
}){
 const [selected,setSelected]=useState('');
 const [reason,setReason]=useState('');
 const model=state.worldModel;
 if(!question.queue_fingerprint||state.worldPhase!=='ready'||!model||
    model.patient_id!==question.patient_id||model.case_id!==question.case_id||
    model.snapshot_fingerprint!==question.source_snapshot_sha256)return null;
 const anchor=model.observations.find(o=>o.source_id===question.source_id&&o.source_line===question.source_line);
 if(!anchor?.specimen_id||anchor.oncology?.role!=='metastasis')return null;
 const peers=model.observations.filter(o=>o.document_id!==anchor.document_id&&o.event_date===anchor.event_date&&
   o.specimen_id===anchor.specimen_id&&o.finding_key===anchor.finding_key&&o.oncology?.role==='metastasis'&&
   o.oncology.episode_id!==anchor.oncology!.episode_id);
 if(!peers.length)return null;
 const key=(o:WorldObservation)=>o.source_id+':'+o.source_line;
 const peer=peers.find(o=>key(o)===selected);
 return <details data-testid="attribution-review"><summary>Compare reported origins for {anchor.finding_key}</summary>
  <p>Specimen {anchor.specimen_id} · {anchor.event_date}</p><Passage item={anchor}/>
  <label>Second report <select value={selected} disabled={disabled} onChange={event=>{setSelected(event.target.value);setReason('');}}>
   <option value="">Select a source passage</option>
   {peers.map(o=><option key={key(o)} value={key(o)}>{o.document_id} v{o.document_version}, line {o.source_line} · {o.oncology?.episode_id??'Episode unassigned'}</option>)}
  </select></label>
  {peer&&<><Passage item={peer}/>
   <label>Why does the origin remain unresolved?
    <textarea value={reason} disabled={disabled} maxLength={600} onChange={event=>setReason(event.target.value)}/>
   </label>
   <button type="button" disabled={disabled||!validReturnReason(reason)}
    onClick={()=>void session.returnReviewQuestion(question.question_id,question.queue_fingerprint!,reason,peer)}>
    Record unresolved attribution
   </button></>}
 </details>;
}
