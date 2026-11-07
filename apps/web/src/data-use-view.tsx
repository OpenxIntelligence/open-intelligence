import {useEffect,useState} from 'react';
import type {RegistrySession} from './registry-client';

export function DataUseView({session}:{session:RegistrySession}){
 const [purpose,setPurpose]=useState<'operations'|'research'>('operations');
 const [result,setResult]=useState<{state:string;revision:number}|null>(null);
 const [message,setMessage]=useState('Not checked. A separate permission is required.');
 const [attempt,setAttempt]=useState(0);
 const [loading,setLoading]=useState(false);
 useEffect(()=>{
  if(!attempt)return;
  const control=new AbortController();setResult(null);setLoading(true);setMessage('Checking current restriction…');
  session.readDataUse(purpose,control.signal).then(value=>{
   if(!control.signal.aborted){setResult(value);setMessage('Snapshot from the latest successful check.');}
  }).catch(()=>{if(!control.signal.aborted)setMessage('Status unavailable. Access may be denied or the service unavailable.');})
   .finally(()=>{if(!control.signal.aborted)setLoading(false);});
  return ()=>control.abort();
 },[session,purpose,attempt]);
 return <details className="panel" data-testid="data-use-panel"><summary>Data-use restrictions</summary>
  <p>Administrative controls for this fictional patient. These restrictions can block existing access; they do not establish patient consent or grant permission.</p>
  <label>Purpose <select value={purpose} onChange={e=>{setResult(null);setMessage('Not checked.');setAttempt(0);setLoading(false);setPurpose(e.target.value as typeof purpose);}}><option value="operations">Operations</option><option value="research">Research</option></select></label>
  <button disabled={loading} onClick={()=>setAttempt(n=>n+1)}>Check restriction</button>
  <p role="status">{message}</p>
  {result&&<p>{result.state==='restricted'?'Restricted':result.state==='unrestricted'?'Restriction lifted; independent access grants still required':'No restriction decision recorded; patient consent is not established'} · Decision revision {result.revision}</p>}
 </details>;
}
