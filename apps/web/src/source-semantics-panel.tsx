import {useEffect,useRef,useState} from 'react';
import type {RegistrySession} from './registry-client';
import type {SourceWorldModel} from './source-world-model';
import type {SourceSemantics} from './source-semantics';

export function SourceSemanticsPanel({session,model,busy}:{session:RegistrySession;model:SourceWorldModel;busy:boolean}){
  const [packet,setPacket]=useState<SourceSemantics|null>(null);
  const [message,setMessage]=useState('');
  const [loading,setLoading]=useState(false);
  const active=useRef(true);
  useEffect(()=>{active.current=true;return()=>{active.current=false;};},[]);
  async function load(){
    setPacket(null);setLoading(true);setMessage('Checking the current sources and access…');
    try{
      const value=await session.readSourceSemantics(model);
      if(active.current){setPacket(value);setMessage('Source classifications checked. Clinical review has not been performed.');}
    }catch{if(active.current)setMessage('Source classifications unavailable. Refresh the case to check records and access.');}
    finally{if(active.current)setLoading(false);}
  }
  return <details data-testid="source-semantics-panel"><summary>Evidence types and source traceability</summary>
    <p>These classifications describe what the records report. “Present” means an entry exists; it does not mean a disease is present or a result is normal. Original missing-result reasons are preserved.</p>
    <button type="button" disabled={busy||loading} onClick={()=>void load()}>Check source classifications</button>
    <p role="status">{message}</p>
    {packet&&<>
      <p>{packet.records.length} source entries checked. {packet.records.length>50?'Showing the first 50.':''}</p>
      <ul>{packet.records.slice(0,50).map(r=><li key={r.record_id}>
        <strong>{r.evidence_status}</strong> · source state: {r.original_state}
        <details><summary>Exact source reference</summary><p><code>{r.record_id}</code></p>
          <p>Source SHA-256: <code>{r.source_sha256}</code></p>
          <p>Reported information · <code>{r.concept_id}</code> version {r.concept_version}</p>
        </details>
      </li>)}</ul>
    </>}
  </details>;
}
