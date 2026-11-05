import {useEffect,useRef,useState} from 'react';
import type {RegistrySession} from './registry-client';
import type {SourceIndex} from './source-contracts';
import {parseLinkedSources,parseLinkReceipt,prepareSourceLink} from './encounter-source-links';
import type {LinkIntent,LinkPage} from './encounter-source-links';

type VisitChoice = Readonly<{id:number;service_date:string;external_key:string}>;
type Props = {session:RegistrySession;patientId:string;index:SourceIndex;
  onOpenOriginal:(sourceId:string,trigger:HTMLButtonElement)=>void};

// Retain just the prepared pointer and key if the network loses the reply.
// The registry replaces the patient object when access or identity changes.
const unresolved = new WeakMap<object,Map<string,LinkIntent>>();

export function EncounterSourceLinks({session,patientId,index,onOpenOriginal}:Props) {
  const patient=session.snapshot().patient;
  const [visits,setVisits]=useState<readonly VisitChoice[]|null>(null);
  const [visitNext,setVisitNext]=useState<number|null>(null);
  const [visit,setVisit]=useState(0);
  const [sourceId,setSourceId]=useState('');
  const [page,setPage]=useState<LinkPage|null>(null);
  const [message,setMessage]=useState('');
  const [refreshNeeded,setRefreshNeeded]=useState(false);
  const [busy,setBusy]=useState(false);
  const sequence=useRef(0), inFlight=useRef(false);
  const pending=patient?unresolved.get(patient)?.get(index.case_id):undefined;
  useEffect(()=>()=>{sequence.current++;},[index]);
  const current=(seq:number)=>seq===sequence.current && session.snapshot().patient===patient &&
    session.snapshot().sourceIndex===index;
  function begin() {
    if(inFlight.current || !patient || patient.patient_id!==patientId || session.snapshot().sourceIndex!==index) return null;
    inFlight.current=true;
    setBusy(true);
    setMessage('');
    setRefreshNeeded(false);
    return ++sequence.current;
  }
  function finish(seq:number) {
    if(current(seq)) {inFlight.current=false;setBusy(false);}
  }
  async function loadVisits(after=0) {
    const seq=begin();
    if(seq===null)return;
    setPage(null);
    setVisit(0);
    setSourceId('');
    setVisits(null);
    setVisitNext(null);
    try {
      const result=await session.encounterChart(patientId).visits(after);
      if(current(seq)) {setVisits(result.encounters);setVisitNext(result.next_after_id);}
    } catch {
      if(current(seq)) setMessage('Visits could not be loaded. Check access and try again.');
    } finally {finish(seq);}
  }
  async function readPage(id:number,after:number,seq:number) {
    const raw=await session.encounterSourceRequest(patientId,id,index.case_id,after);
    if(current(seq)) setPage(parseLinkedSources(raw,index,id,after));
  }
  async function readLinks(after=0) {
    const seq=begin();
    if(seq===null)return;
    setPage(null);
    try {await readPage(visit,after,seq);}
    catch {
      if(current(seq)) {setRefreshNeeded(true);setMessage('Visit links could not be verified against these case records.');}
    }
    finally {finish(seq);}
  }
  async function attach() {
    if(!patient || !visit || (pending && pending.encounterId!==visit))return;
    let intent:LinkIntent;
    try {intent=pending??prepareSourceLink(index,visit,sourceId);}
    catch {setMessage('Select a current source version before linking.');return;}
    const seq=begin();
    if(seq===null)return;
    const intents=unresolved.get(patient)??new Map<string,LinkIntent>();
    unresolved.set(patient,intents);
    intents.set(index.case_id,intent);
    setPage(null);
    try {
      const response=await session.encounterSourceRequest(patientId,visit,index.case_id,null,intent.body);
      parseLinkReceipt(response);
      if(intents.get(index.case_id)===intent) intents.delete(index.case_id);
      if(!current(seq))return;
      setSourceId('');
      try {
        await readPage(visit,0,seq);
        if(current(seq)) setMessage('Source version linked to this visit.');
      } catch {
        if(current(seq)) {setRefreshNeeded(true);setMessage('Link saved. Refresh case records to read the linked version.');}
      }
    } catch(error) {
      const status=error instanceof Error && 'status' in error?error.status:undefined;
      const rejected=status===400||status===401||status===403||status===404||status===409||status===422;
      if(rejected && intents.get(index.case_id)===intent) intents.delete(index.case_id);
      if(current(seq) && rejected) setRefreshNeeded(true);
      if(current(seq)) setMessage(rejected?'Link declined. Refresh the case records and check existing links.':
        'Save outcome unknown. Retry the same source link or check the saved links for this visit.');
    } finally {finish(seq);}
  }
  return <section aria-labelledby="visit-records-heading" data-testid="encounter-source-links">
    <h3 id="visit-records-heading">Visit records</h3>
    <p>Attach the exact version of a case record to the visit where it was used.</p>
    <button type="button" data-testid="encounter-link-visits" disabled={busy} onClick={()=>void loadVisits()}>
      {visits===null?'Choose a visit':'Refresh visits'}
    </button>
    {visits!==null && <>
      {visits.length===0?<p>No visits available.</p>:<label>Visit
        <select data-testid="encounter-link-visit" value={visit||''} disabled={busy} onChange={e=>{
          setVisit(Number(e.target.value));setSourceId('');setPage(null);setMessage('');setRefreshNeeded(false);
        }}>
          <option value="">Choose a visit</option>
          {visits.map(row=><option key={row.id} value={row.id}>{row.service_date} · {row.external_key}</option>)}
        </select></label>}
      {visitNext!==null && <button disabled={busy} onClick={()=>void loadVisits(visitNext)}>Next visits</button>}
    </>}
    {visit>0 && <>
      <button data-testid="encounter-links-read" disabled={busy} onClick={()=>void readLinks()}>Check linked records</button>
      <label>Current source version
        <select data-testid="encounter-link-source" disabled={busy||!!pending} value={sourceId}
          onChange={e=>setSourceId(e.target.value)}>
          <option value="">Choose a source version</option>
          {index.sources.filter(source=>source.state==='current').map(source=>
            <option key={source.source_id} value={source.source_id}>{source.document_id} · v{source.version}</option>)}
        </select>
      </label>
      {pending && <p>An earlier link for visit {pending.encounterId} needs confirmation. The same request can be retried.</p>}
      <button type="button" data-testid="encounter-link-save"
        disabled={busy||(pending?pending.encounterId!==visit:!sourceId)} onClick={()=>void attach()}>
        {pending?'Retry exact source link':'Link this version to the visit'}
      </button>
    </>}
    {message && <p role="status">{message}</p>}
    {refreshNeeded && <button type="button" disabled={busy} onClick={()=>void session.loadSources(index.case_id)}>Refresh case records</button>}
    {page && (page.links.length===0?<p>No linked records for this visit in this case.</p>:<>
      <ul>{page.links.map(({id,source})=><li key={id} data-testid="encounter-linked-source">
        <strong>{source.document_id}</strong> · v{source.version} · {source.state} · {source.kind}{' '}
        <button type="button" data-testid="encounter-link-original"
          onClick={e=>onOpenOriginal(source.source_id,e.currentTarget)}>Inspect linked original</button>
      </li>)}</ul>
      {page.next!==null && <button disabled={busy} onClick={()=>void readLinks(page.next!)}>Next linked records</button>}
    </>)}
  </section>;
}
