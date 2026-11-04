import {useEffect,useState} from 'react';
import type {RegistrySession,ViewState} from './registry-client';
import {packetInputs,activePacketDraft,canSavePacket} from './second-opinion-packets';
import {patientContinuity} from './patient-continuity';
import './second-opinion-packet-panel.css';

export function SecondOpinionPacketPanel({session,state,onInvestigations}:{
 session:RegistrySession;state:ViewState;onInvestigations:()=>void;
}){
 const [confirmed,setConfirmed]=useState(false);
 const continuity=patientContinuity(state),input=packetInputs(state),draft=activePacketDraft(state);
 useEffect(()=>setConfirmed(false),[state.secondOpinionDraft]);
 if(!continuity)return null;
 const locked=['saving','unknown'].includes(state.secondOpinionWritePhase);
 const list=input&&state.secondOpinionPhase==='ready'&&state.secondOpinionPackets?.case_id===input.case_id&&
  state.secondOpinionPackets.patient_id===input.patient_id?state.secondOpinionPackets:null;
 const toggle=(key:'source_ids'|'question_ids',id:string,checked:boolean)=>{
  const values=draft?.[key]??[];
  session.editSecondOpinionPacket({[key]:checked?[...values,id]:values.filter(value=>value!==id)});
 };
 return <section className="panel packet-panel" data-testid="second-opinion-packets" aria-labelledby="packet-heading">
  <span className="step">SAVED PREPARATION · EXACT RECORD VERSIONS</span>
  <h2 id="packet-heading">Save a second-opinion preparation packet</h2>
  <p>Choose the records and questions to keep together. Saving records a preparation packet only: no referral, recipient verification, record transmission or clinical approval.</p>
  {!input?<div><p>Open the intended case and check its source questions before selecting or reopening packet contents.</p><button type="button" onClick={onInvestigations}>Check case and questions</button></div>:<>
   <p className="small">Selected case <code>{input.case_id}</code>. Only current source-grounded questions can enter a new packet. Historical questions remain in Investigations.</p>
   <details className="packet-compose" open={!!draft||locked}>
    <summary>Choose records and questions</summary>
    <form onSubmit={event=>{event.preventDefault();void session.saveSecondOpinionPacket(confirmed)}}>
     <fieldset disabled={locked}>
      <legend>New preparation packet</legend>
      <label htmlFor="packet-title">Packet title</label>
      <input id="packet-title" data-testid="packet-title" value={draft?.title??''} autoComplete="off" minLength={8} maxLength={300} required
       onChange={event=>session.editSecondOpinionPacket({title:event.target.value})}/>
      <p className="small">Use 8–300 characters, without leading or trailing spaces. No records are selected automatically.</p>
      <fieldset className="packet-options"><legend>Current original records · choose 1–32</legend>
       {input.sources.length===0?<p>No current records were returned for this case.</p>:input.sources.map(source=><label key={source.source_id} className="check packet-option">
        <input type="checkbox" data-testid="packet-source" data-source-id={source.source_id} checked={draft?.source_ids.includes(source.source_id)??false}
         disabled={!draft?.source_ids.includes(source.source_id)&&(draft?.source_ids.length??0)>=32}
         onChange={event=>toggle('source_ids',source.source_id,event.target.checked)}/>
        <span>{source.document_id} · version {source.version}<span className="small packet-source-id">{source.kind} · <code>{source.source_id}</code></span></span>
       </label>)}
      </fieldset>
      <fieldset className="packet-options"><legend>Focused saved questions · choose 1–16</legend>
       {input.questions.length===0?<p>No questions with current matching source context are available. Prepare a source-grounded question in Investigations first.</p>:input.questions.map(question=><label key={question.question_id} className="check packet-option">
        <input type="checkbox" data-testid="packet-question" data-question-id={question.question_id} checked={draft?.question_ids.includes(question.question_id)??false}
         disabled={!draft?.question_ids.includes(question.question_id)&&(draft?.question_ids.length??0)>=16}
         onChange={event=>toggle('question_ids',question.question_id,event.target.checked)}/>
        <span>{question.question}<span className="small packet-source-id">Source version {question.source_version} · line {question.source_line} · <code>{question.source_id}</code></span></span>
       </label>)}
      </fieldset>
      <p className="small">Select each chosen question’s source record above. A question never silently adds its source to the packet.</p>
      <label className="check"><input type="checkbox" data-testid="packet-confirm" checked={confirmed} onChange={event=>setConfirmed(event.target.checked)}/>This selection is independently fictional preparation, not a request to send records.</label>
      <div className="actions"><button className="primary" data-testid="packet-save" disabled={!confirmed||!canSavePacket(state)}>Save preparation packet</button>
       <button type="button" data-testid="packet-clear" disabled={!draft} onClick={()=>session.clearSecondOpinionPacket()}>Clear unsent selection</button></div>
     </fieldset>
    </form>
   </details>
  </>}
  <p role="status" aria-live="polite" data-testid="packet-write-status" data-phase={state.secondOpinionWritePhase}>{state.secondOpinionWriteMessage}</p>
  {state.secondOpinionWritePhase==='unknown'&&<div className="packet-warning" data-testid="packet-recovery"><p>The earlier save may already exist. Retrying uses its original key and exact selection; a fresh read does not resolve the uncertain command.</p>
   <div className="actions"><button type="button" data-testid="packet-retry" disabled={!input||input.case_id!==state.secondOpinionIntent?.case_id} onClick={()=>void session.retrySecondOpinionPacket()}>Recover exact save receipt</button>
    <button type="button" data-testid="packet-abandon" onClick={()=>session.abandonSecondOpinionPacket()}>Abandon local recovery</button></div>
   <p className="small">Abandoning recovery does not undo a saved packet.</p></div>}
  {input&&state.secondOpinionReceipt&&<p data-testid="packet-receipt">{state.secondOpinionReceipt.duplicate?'Recovered packet: ':'Saved packet: '}<code>{state.secondOpinionReceipt.packet_id}</code> · not sent externally</p>}
  <h3>Saved packets</h3>
  <button type="button" data-testid="packet-refresh" disabled={!input||state.secondOpinionPhase==='loading'||state.secondOpinionWritePhase==='saving'}
   onClick={()=>{if(input)void session.loadSecondOpinionPackets(input.case_id)}}>Check saved packets</button>
  <p role="status" aria-live="polite" data-testid="packet-read-status" data-phase={state.secondOpinionPhase}>{state.secondOpinionMessage}</p>
  {list&&(list.packets.length===0?<p data-testid="packet-empty">No saved packets were returned for this case and grant. This is not a record-completeness assessment.</p>:
   <ol className="packet-list">{list.packets.map(packet=><li key={packet.packet_id} data-testid="saved-packet" data-packet-id={packet.packet_id} data-state={packet.preparation_state}>
    <h4>{packet.title}</h4><p>Saved <time dateTime={packet.created_at}>{packet.created_at}</time></p>
    <p>{packet.preparation_state==='source_reassessment_required'?'Source reassessment required. These are the original selections, not a current reviewed packet.':'Current preparation at the last server check. Record completeness and clinical review are not established.'}</p>
    <p className="small">Recipient not verified · no external request sent · no clinical approval</p>
    <details><summary>Inspect {packet.sources.length} selected record versions and {packet.questions.length} saved questions</summary>
     <ul>{packet.sources.map(source=><li key={source.source_id}>{source.document_id} · version {source.version} · {source.state}<br/><code>{source.source_id}</code><br/>SHA-256 <code>{source.sha256}</code></li>)}</ul>
     <ol>{packet.questions.map(question=><li key={question.question_id}><p>{question.question}</p><p className="small">{question.source_context_state==='source_reassessment_required'?'Source reassessment required':'Current source context, unreviewed'} · line {question.source_line} · <code>{question.source_id}</code></p></li>)}</ol>
     <p className="small">Original source snapshot <code>{packet.source_snapshot_sha256}</code></p>
    </details>
   </li>)}</ol>)}
 </section>;
}
