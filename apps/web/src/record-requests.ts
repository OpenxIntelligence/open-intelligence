import {parseSourceIndex,sourceIndexPath} from './source-contracts.js';
import type {CaseBinding, SourceIndex, SourceVersion} from './source-contracts.js';
import {citationEvidenceTimestamp} from './evidence-timestamp.js';

export const requestKinds = ['clinical','pathology','laboratory','imaging','molecular','other'] as const;
export type RequestKind = typeof requestKinds[number];
type ReceiptStatus = 'not_received'|'source_current_unreviewed'|'source_superseded_reconciliation_required'|'binding_revoked_not_usable';
export type RequestFields = Readonly<{kind:RequestKind; record_label:string; source_organization:string}>;
export type RequestRow = RequestFields & Readonly<{
  request_id:string; status:'requested'|'received'|'cancelled'; receipt_status:ReceiptStatus;
  source:SourceVersion|null;
}>;
export type RequestsView = Readonly<{
  history?:Readonly<{requestId:string; entries:readonly HistoryEntry[]}>;
  rows:readonly RequestRow[]|null; busy:boolean; message:string; retryCreate:boolean; retryFields:RequestFields|null;
}>;

const exact = (v:unknown,keys:string[]):v is Record<string,unknown> =>
  v!==null && typeof v==='object' && !Array.isArray(v) &&
  Object.keys(v).length===keys.length && keys.every(key=>Object.hasOwn(v,key));
const kind = (v:unknown):v is RequestKind => requestKinds.some(k=>k===v);
const id = (v:unknown,re:RegExp):v is string => typeof v==='string' && re.exec(v)?.[0]===v;
const requestId = (v:unknown):v is string => id(v,/^RECORD-[A-F0-9]{32}$/);
const label = (v:unknown,limit:number):v is string => typeof v==='string' && Boolean(v.trim()) &&
  [...v].length<=limit && !/[\u0000-\u001f\u007f]/.test(v);
export const validRequestFields = (v:RequestFields) => kind(v.kind) && label(v.record_label,140) && label(v.source_organization,100);

function invalid():never {throw Error('Invalid record request response');}
export function readRequests(v:unknown,index:SourceIndex):readonly RequestRow[] {
  if(!exact(v,['patient_id','requests','synthetic','external_request_sent','source_receipts_enabled']) ||
     v.patient_id!==index.patient_id || v.synthetic!==true || v.external_request_sent!==false ||
     v.source_receipts_enabled!==true || !Array.isArray(v.requests)) return invalid();
  const seen=new Set<string>();
  return Object.freeze(v.requests.map((r:unknown):RequestRow=>{
    if(!exact(r,['request_id','patient_id','kind','record_label','source_organization','status','revision','created_at','updated_at','receipt_status','source_reference','external_request_sent']) ||
       r.patient_id!==index.patient_id || !requestId(r.request_id) || seen.has(r.request_id) ||
       !kind(r.kind) || !label(r.record_label,140) || !label(r.source_organization,100) ||
       r.external_request_sent!==false || !citationEvidenceTimestamp(r.created_at) || !citationEvidenceTimestamp(r.updated_at)) return invalid();
    seen.add(r.request_id);
    const {status,receipt_status,source_reference:ref}=r;
    let source:SourceVersion|null=null;
    if(status==='received'){
      if(typeof r.revision!=='number' || !Number.isSafeInteger(r.revision) || r.revision<2 || r.revision>257 || (receipt_status!=='source_current_unreviewed' && receipt_status!=='source_superseded_reconciliation_required' &&
         receipt_status!=='binding_revoked_not_usable') || (receipt_status==='binding_revoked_not_usable' && ref!==null)) return invalid();
      if(ref!==null){
        if(!exact(ref,['case_id','source_id','version','sha256']) || !id(ref.case_id,/^CASE-[A-Z0-9-]{1,35}$/) ||
           !id(ref.source_id,/^SRC-[A-F0-9]{32}$/) || !id(ref.sha256,/^[0-9a-f]{64}$/) ||
           typeof ref.version!=='number' || !Number.isSafeInteger(ref.version) || ref.version<1) return invalid();
        // The list spans cases. Reveal identifiers only through the open case's exact authorized metadata.
        if(ref.case_id===index.case_id)
          source=index.sources.find(s=>s.source_id===ref.source_id && s.version===ref.version && s.sha256===ref.sha256 && s.kind===r.kind &&
            s.state===(receipt_status==='source_current_unreviewed'?'current':'superseded'))??null;
      }
    }else if((status!=='requested' && status!=='cancelled') || r.revision!==(status==='requested'?1:2) ||
             receipt_status!=='not_received' || ref!==null) return invalid();
    return Object.freeze({request_id:r.request_id,status,receipt_status:receipt_status as ReceiptStatus,
      kind:r.kind,record_label:r.record_label,source_organization:r.source_organization,source});
  }));
}

type HistoryEntry = Readonly<{source:SourceVersion; actor:string; occurredAt:string}>;
export function replacementFor(row:RequestRow,index:SourceIndex) {
  const prior=row.source;
  if (!prior || row.receipt_status!=='source_superseded_reconciliation_required') return null;
  const chain=index.sources.filter(s=>s.document_id===prior.document_id).sort((a,b)=>a.version-b.version);
  const start=chain.indexOf(prior);
  if (start<0 || start===chain.length-1) return null;
  for(let i=start+1;i<chain.length;i++) {
    const next=chain[i], prev=chain[i-1];
    if(next.kind!==prior.kind || next.specimen_id!==prior.specimen_id || next.event_date!==prior.event_date ||
       next.version!==prev.version+1 || next.supersedes_id!==prev.source_id || prev.state!=='superseded') return null;
  }
  const last=chain[chain.length-1];
  return last.state==='current'?last:null;
}
export function readReceiptHistory(value:unknown,row:RequestRow,index:SourceIndex):readonly HistoryEntry[] {
  if(!row.source || !exact(value,['patient_id','request_id','receipts','access_receipt_id','synthetic',
       'clinical_approval','external_request_sent']) || value.patient_id!==index.patient_id ||
     value.request_id!==row.request_id || !id(value.access_receipt_id,/^ACCESS-[A-F0-9]{32}$/) ||
     value.synthetic!==true || value.clinical_approval!==false || value.external_request_sent!==false ||
     !Array.isArray(value.receipts) || !value.receipts.length || value.receipts.length>256) return invalid();
  const history:HistoryEntry[]=[];
  const seen=new Set<string>();
  for(const step of value.receipts) {
    if(!exact(step,['kind','source_reference','previous_source_id','reconciliation_id','revision','occurred_at',
        'actor','reason_code','clinical_approval','external_request_sent']) ||
       !exact(step.source_reference,['case_id','source_id','version','sha256']) ||
       step.source_reference.case_id!==index.case_id || step.clinical_approval!==false ||
       step.external_request_sent!==false || !citationEvidenceTimestamp(step.occurred_at) ||
       !id(step.actor,/^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$/) ||
       step.revision!==history.length+2) return invalid();
    const ref=step.source_reference, previous=history.at(-1)?.source;
    const source=index.sources.find(s=>s.source_id===ref.source_id && s.version===ref.version && s.sha256===ref.sha256 &&
      s.document_id===row.source!.document_id && s.kind===row.kind);
    if(!source || step.previous_source_id!==(previous?.source_id??null)) return invalid();
    if(previous) {
      if(step.kind!=='reconciled' || step.reason_code!=='source_amendment' || source.version<=previous.version ||
         !id(step.reconciliation_id,/^RECON-[A-F0-9]{32}$/) || seen.has(step.reconciliation_id)) return invalid();
      seen.add(step.reconciliation_id);
    } else if(step.kind!=='received' || step.reason_code!==null || step.reconciliation_id!==null) return invalid();
    history.push(Object.freeze({source,actor:step.actor,occurredAt:step.occurred_at}));
  }
  if(history.at(-1)?.source.source_id!==row.source.source_id) return invalid();
  return Object.freeze(history);
}

export const emptyRequests = ():RequestsView => ({rows:null,busy:false,message:'Refresh to check this patient’s requests.',retryCreate:false,retryFields:null});
type Port = {
  index:()=>SourceIndex|null; view:()=>RequestsView; publish:(view:RequestsView)=>void; denied:(status:number)=>void;
  request:(path:string,controller:AbortController,body?:string)=>Promise<Response>;
  json:(response:Response,limit:number)=>Promise<unknown>;
  replaceSources:(fresh:SourceIndex,notice:string)=>void;
};
type CreateIntent = Readonly<{patient:string;caseId:string;body:string;fields:RequestFields}>;
const uncertain = 'The create receipt is uncertain. Retry the exact request to recover its receipt.';

/** A transient disclosure over the registry's authenticated transport. Its only retained
 * command is the exact create intent; a network failure cannot establish non-commit. */
export class RecordRequestSession {
  #index:SourceIndex|null=null;
  #open=false;
  #listAuthorized=false;
  #inflight:AbortController|null=null;
  #pending:CreateIntent|null=null;
  constructor(private port:Port){}
  setContext(index:SourceIndex|null):RequestsView {
    this.#inflight?.abort();this.#inflight=null;this.#open=false;this.#listAuthorized=false;this.#index=index;
    if(index && (index.patient_id!==this.#pending?.patient || index.case_id!==this.#pending?.caseId))this.#pending=null;
    return emptyRequests();
  }
  reset(){this.#pending=null;this.setContext(null);}
  forgetOtherPatient(patient:string){if(this.#pending?.patient!==patient)this.#pending=null;}
  checkBindings(cases:readonly CaseBinding[]){
    const p=this.#pending;
    if(p && !cases.some(c=>c.patient_id===p.patient && c.case_id===p.caseId && c.status==='active'))this.#pending=null;
  }
  open(index:SourceIndex){
    if(this.#index!==index || this.port.index()!==index || this.#open)return;
    this.#open=true;
    this.port.publish(emptyRequests());
  }
  close(index:SourceIndex){
    if(this.#index!==index || !this.#open)return;
    this.#open=false;this.#listAuthorized=false;this.#inflight?.abort();this.#inflight=null;this.port.publish(emptyRequests());
  }
  #available(index:SourceIndex){return this.#open && this.#index===index && this.port.index()===index && !this.#inflight;}
  #path(index:SourceIndex,requestId?:string,action:'receive'|'reconcile'|'receipt-history'='receive'){
    const base='/v1/patients/'+encodeURIComponent(index.patient_id)+'/record-requests';
    const scope='?case_id='+encodeURIComponent(index.case_id);
    return requestId ? base+'/'+requestId+'/'+action+(action==='receive'?'':scope) : base+scope;
  }
  #show(rows:RequestsView['rows'],busy:boolean,message:string){
    const retryCreate=this.#pending!==null && this.#listAuthorized;
    this.port.publish({rows,busy,message,retryCreate,retryFields:retryCreate && !busy && rows?this.#pending!.fields:null});
  }
  async #run(index:SourceIndex,work:(control:AbortController,current:()=>boolean)=>Promise<void>,onError:()=>void){
    const control=new AbortController();this.#inflight=control;
    const current=()=>this.#open && this.#index===index && this.port.index()===index && this.#inflight===control;
    const timeout=setTimeout(()=>control.abort(),10000);
    try{await work(control,current);}
    catch{if(current())onError();}
    finally{clearTimeout(timeout);if(this.#inflight===control)this.#inflight=null;}
  }
  async #reply(control:AbortController,current:()=>boolean,url:string,body?:string,limit=body===undefined?1024*1024:4096){
    if(!current())return null;
    if(control.signal.aborted)throw Error('Timed out');
    const res=await this.port.request(url,control,body);
    if(!current()){void res.body?.cancel().catch(()=>{});return null;}
    if([401,403,404].includes(res.status)){
      this.#pending=null;void res.body?.cancel().catch(()=>{});this.port.denied(res.status);return null;
    }
    if(control.signal.aborted)throw Error('Timed out');
    if(res.status!==200 && res.status!==201){void res.body?.cancel().catch(()=>{});return {status:res.status,value:null};}
    const value=await this.port.json(res,limit);
    if(!current())return null;
    if(control.signal.aborted)throw Error('Timed out');
    return {status:res.status,value};
  }
  async #list(index:SourceIndex,control:AbortController,current:()=>boolean,after:string){
    const reply=await this.#reply(control,current,this.#path(index));
    if(!reply || !current())return;
    if(reply.status!==200)throw Error('List unavailable');
    const rows=readRequests(reply.value,index);
    const sourceReply=await this.#reply(control,current,sourceIndexPath(index.patient_id,index.case_id),undefined,65536);
    if(!sourceReply || !current())return;
    if(sourceReply.status!==200)throw Error('Source index unavailable');
    const fresh=parseSourceIndex(sourceReply.value,index.patient_id,index.case_id);
    // Each authorized read issues a new access receipt. Only a change to the
    // actual source versions or reported statements invalidates the open case.
    if(JSON.stringify(fresh.sources)!==JSON.stringify(index.sources) ||
       JSON.stringify(fresh.source_reported_assertions)!==JSON.stringify(index.source_reported_assertions)){
      this.port.replaceSources(fresh,after);return;
    }
    this.#listAuthorized=true;
    this.#show(rows,false,after || (this.#pending?uncertain:rows.length?'Patient requests checked.':'No record requests are listed for this patient.'));
  }
  async refresh(index:SourceIndex){
    if(!this.#available(index))return;
    await this.#run(index,async(c,current)=>{
      this.#listAuthorized=false;
      this.#show(null,true,'Checking requests and current source versions…');await this.#list(index,c,current,'');
    },()=>this.#show(null,false,'Requests could not be verified. Refresh to check again.'));
  }
  async create(index:SourceIndex,fields:RequestFields){
    if(!this.#available(index) || this.#pending || !this.port.view().rows || !validRequestFields(fields))return;
    const cleaned=Object.freeze({kind:fields.kind,record_label:fields.record_label.trim(),source_organization:fields.source_organization.trim()});
    this.#pending={patient:index.patient_id,caseId:index.case_id,fields:cleaned,body:JSON.stringify({synthetic:true,request_key:crypto.randomUUID(),...cleaned})};
    await this.#write(index,this.#pending.body);
  }
  async retryCreate(index:SourceIndex){
    if(!this.#available(index) || !this.#pending || !this.#listAuthorized)return;
    await this.#write(index,this.#pending.body);
  }
  abandonCreate(index:SourceIndex){
    if(!this.#available(index) || !this.#pending || !this.port.view().rows)return;
    this.#pending=null;this.#show(this.port.view().rows,false,'Retry discarded. This does not undo a request that was already saved.');
  }
  async receive(index:SourceIndex,request:string,sourceId:string){
    if(!this.#available(index) || this.#pending)return;
    const row=this.port.view().rows?.find(r=>r.request_id===request && r.status==='requested');
    const source=index.sources.find(s=>s.source_id===sourceId && s.state==='current' && s.kind===row?.kind);
    if(!row || !source)return;
    await this.#write(index,JSON.stringify({synthetic:true,case_id:index.case_id,source_id:sourceId,
      expected_original:{version:source.version,sha256:source.sha256}}),{request,source});
  }
  async history(index:SourceIndex,row:RequestRow) {
    const rows=this.port.view().rows;
    if(!this.#available(index) || this.#pending || !row.source || !rows?.includes(row)) return;
    await this.#run(index,async(c,current)=>{
      this.#show(null,true,'Checking receipt history…');
      const reply=await this.#reply(c,current,this.#path(index,row.request_id,'receipt-history'));
      if(!reply || !current())return;
      if(reply.status!==200)throw Error('History unavailable');
      const entries=readReceiptHistory(reply.value,row,index);
      this.port.publish({...emptyRequests(),rows,history:{requestId:row.request_id,entries},message:'Receipt history checked.'});
    },()=>this.#show(null,false,'Receipt history unavailable. Refresh requests and source versions.'));
  }
  async reconcile(index:SourceIndex,row:RequestRow,replacement:SourceVersion) {
    if(!this.#available(index) || this.#pending || !this.port.view().rows?.includes(row) ||
       !row.source || replacementFor(row,index)!==replacement)return;
    const previous=row.source.source_id;
    const body=JSON.stringify({synthetic:true,case_id:index.case_id,expected_source_id:previous,
      replacement_source_id:replacement.source_id,reason_code:'source_amendment',
      request_key:[row.request_id,previous,replacement.source_id].join(':')});
    let confirmed=false;
    await this.#run(index,async(c,current)=>{
      this.#show(null,true,'Recording the selected amendment…');
      const reply=await this.#reply(c,current,this.#path(index,row.request_id,'reconcile'),body);
      if(!reply || !current())return;
      const {value,status}=reply;
      if(status===409){this.#show(null,false,'The receipt or source changed. Refresh both before choosing an amendment.');return;}
      if(!exact(value,['request_id','source_id','previous_source_id','version','duplicate','reconciliation_id',
          'clinical_approval','external_request_sent']) || (status!==200 && status!==201) ||
         value.duplicate!==(status===200) || value.request_id!==row.request_id ||
         value.previous_source_id!==previous || value.source_id!==replacement.source_id ||
         value.version!==replacement.version || !id(value.reconciliation_id,/^RECON-[A-F0-9]{32}$/) ||
         value.clinical_approval!==false || value.external_request_sent!==false) throw Error('Unconfirmed reconciliation');
      confirmed=true;
      await this.#list(index,c,current,'Amendment linked. The original receipt is preserved in history.');
    },()=>this.#show(null,false,confirmed?'Amendment saved. Refresh the request history.':
      'Amendment receipt unconfirmed. Refresh before retrying the same selection.'));
  }
  async #write(index:SourceIndex,body:string,receive?:{request:string;source:SourceVersion}){
    let confirmed=false;
    await this.#run(index,async(c,current)=>{
      this.#show(null,true,receive?'Linking the selected source version…':'Saving the local request…');
      const reply=await this.#reply(c,current,this.#path(index,receive?.request),body);
      if(!reply || !current())return;
      const {status,value}=reply;
      if(status>=400 && status<500 && status!==408){
        this.#pending=null;this.#show(null,false,'Request rejected or changed. Refresh the requests and current source versions before trying again.');return;
      }
      if((status!==201 && status!==200) || !exact(value,receive?['request_id','source_id','version','duplicate']:['request_id','duplicate']) ||
         !requestId(value.request_id) || value.duplicate!==(status===200) ||
         (receive && (value.request_id!==receive.request || value.source_id!==receive.source.source_id || value.version!==receive.source.version)))
        throw Error('Unconfirmed receipt');
      confirmed=true;this.#pending=null;
      const notice=receive?'Source receipt confirmed.':status===200?'Original request receipt recovered.':'Local request saved.';
      this.#show(null,true,notice+' Refreshing requests…');await this.#list(index,c,current,notice);
    },()=>this.#show(null,false,confirmed?'Write confirmed, but the list could not be verified. Refresh requests.':
      receive?'The receipt is uncertain. Refresh requests before selecting a source again.':uncertain));
  }
}
