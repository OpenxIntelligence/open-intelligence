import {useRef,useState} from 'react';
import type {RegistrySession} from './registry-client';
import type {SourceWorldModel} from './source-world-model';
import {draftCommand,isDraftOrigin,readDraftReceipt,readDrafts,type Draft} from './episode-drafts';

export function EpisodeDraftPanel({session,world,busy,onRecords}:{session:RegistrySession;world:SourceWorldModel;busy:boolean;onRecords?:()=>void}){
  const [drafts,setDrafts]=useState<Draft[]|null>(null);
  const [selected,setSelected]=useState('');
  const [message,setMessage]=useState('');
  const [pending,setPending]=useState(false);
  const running=useRef(false);
  const origins=world.observations.filter(isDraftOrigin);
  const origin=origins.find(o=>o.source_id+':'+o.source_line===selected);
  async function run(create:boolean){
    if(running.current||busy||(create&&!origin))return;
    running.current=true;setPending(true);setMessage('');setDrafts(null);
    try{
      let saved:string|undefined;
      if(create&&origin){
        const reply=await session.episodeDraftRequest(world,draftCommand(world,origin));
        if(reply.status===409)throw Error('Source changed or a draft already exists. Refresh Journey and reopen saved drafts.');
        if(reply.status!==200&&reply.status!==201)throw Error('Check access and reopen saved drafts before retrying.');
        saved=readDraftReceipt(reply.body,world,reply.status);
      }
      const reply=await session.episodeDraftRequest(world);
      if(reply.status!==200)throw Error('Saved drafts could not be read. Recheck access and retry.');
      const rows=readDrafts(reply.body,world);
      if(saved&&!rows.some(d=>d.episode_id===saved&&d.source_id===origin?.source_id&&d.source_line===origin.source_line))throw Error('Reopen saved drafts to verify the receipt.');
      setDrafts(rows);setMessage(saved?'Episode draft saved.':'');
    }catch(error){
      setMessage(error instanceof Error&&error.message.startsWith('Source changed')?error.message:
        'Unable to verify saved drafts. Refresh Journey and reopen drafts before retrying.');
    }finally{running.current=false;setPending(false);}
  }
  return <section aria-label="Episode drafts">
    <h3>Episode drafts</h3>
    <p>Start a draft from a reported primary cancer. It keeps the original source line for review.</p>
    <button disabled={busy||pending} onClick={()=>void run(false)}>Open saved episode drafts</button>
    {origins.length>0&&<div><label>Originating statement <select value={selected} disabled={busy||pending}
      onChange={e=>setSelected(e.target.value)}><option value="">Choose a primary finding</option>
      {origins.map(o=><option key={o.source_id+':'+o.source_line} value={o.source_id+':'+o.source_line}>
        {o.oncology?.episode_id} · {o.finding_key} · {o.document_id} v{o.document_version} · line {o.source_line}
      </option>)}</select></label>{origin&&<blockquote>{origin.source_statement}</blockquote>}
      <button disabled={!origin||busy||pending} onClick={()=>void run(true)}>Save episode draft</button></div>}
    <p role="status">{message}</p>
    {drafts?.length===0&&<p>No episode drafts saved for this case.</p>}
    {drafts&&drafts.length>0&&<ul>{drafts.map(d=><li key={d.episode_id} data-testid="saved-episode-draft">
      <strong>{d.source_label}</strong> · Unreviewed draft · {d.basis_state==='current'?'Current source basis':'Reassessment required'}
      <blockquote>{d.statement}</blockquote>
      <p>{d.document_id} v{d.source_version} · line {d.source_line} · {d.source_state} original</p>
      <details><summary>Draft and source identifiers</summary><p>Draft <code>{d.episode_id}</code> · created by {d.created_by} at {d.created_at}</p>
        <p>Source <code>{d.source_id}</code> · SHA-256 <code>{d.source_sha256}</code></p></details>
    </li>)}</ul>}
    {Boolean(drafts?.length)&&onRecords&&<button type="button" disabled={busy||pending}
      onClick={onRecords}>Inspect original report versions in Records</button>}
  </section>;
}
