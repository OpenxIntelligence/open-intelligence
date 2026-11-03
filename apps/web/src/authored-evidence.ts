/** Human-authored fictional evidence contracts. No model or clinical authority. */
import {decodeSourceQuestion} from './source-questions-view.js';
import type {SourceQuestion} from './source-questions-view.js';
import type {ComposerSource} from './composer-preflight-view.js';
import type {RegistrySession} from './registry-client.js';

export type ContentItem='abstract'|'api_output'|'full_text';
export type Permission='allowed'|'denied'|'unknown';
export type Permissions=Readonly<Record<string,Readonly<Record<string,Permission>>>>;
export type Relation='supports'|'contradicts'|'context'|'unknown';
export type Applicability='applicable'|'limited'|'not_applicable'|'unknown';
export type EvidenceVersion=Readonly<{
 evidence_id:string;evidence_key:string;version:number;sha256:string;statement_line:number;
 content_item:ContentItem;rights_sha256:string;permissions:Permissions;
 state:'current'|'superseded'|'withdrawn';title:string|null;issued_at:string;statement:string|null;created_at:string;
}>;
export type EvidenceAssessment=Readonly<{
 assessment_id:string;question_id:string;evidence_id:string;evidence_sha256:string;rights_sha256:string;
 source_snapshot_sha256:string;preflight_sha256:string;relation:Relation;applicability:Applicability;
 quote:string|null;quote_start:number|null;rationale:string|null;actor_label:string;created_at:string;
 state:'current_unreviewed'|'reassessment_required'|'content_withheld';
}>;
export type ReportState='current_unreviewed'|'historical_reassessment_required'|'content_withheld';
export type ReportSummary=Readonly<{
 report_id:string;question_id:string;prepared_at:string;body_sha256:string;snapshot_sha256:string;state:ReportState;
}>;
export type EvidencePacket=Readonly<{
 contract:'oi.h1-question-evidence/1';patient_id:string;case_id:string;question:SourceQuestion;
 source_snapshot_sha256:string;access_receipt_id:string;evidence:readonly EvidenceVersion[];
 assessments:readonly EvidenceAssessment[];reports:readonly ReportSummary[];packet_sha256:string;
 synthetic:true;human_review_state:'not_performed';clinical_approval:false;model_executed:false;
}>;
export type EvidenceOriginal=Readonly<{
 contract:'oi.h1-evidence-original/1';patient_id:string;case_id:string;evidence_id:string;
 sha256:string;original_text:string;access_receipt_id:string;synthetic:true;
}>;
export type ReportSnapshot=Readonly<{
 question:SourceQuestion;selected_source:ComposerSource;
 comparisons:readonly Readonly<{assessment:EvidenceAssessment;evidence:EvidenceVersion}>[];
 prepared_at:string;actor_label:string;
}>;
export type EvidenceReport=Readonly<{
 contract:'oi.h1-evidence-report/1';patient_id:string;case_id:string;question_id:string;report_id:string;
 prepared_at:string;state:ReportState;body:string|null;body_sha256:string;snapshot:ReportSnapshot|null;
 snapshot_sha256:string;access_receipt_id:string;synthetic:true;human_review_state:'not_performed';
 clinical_approval:false;model_executed:false;
}>;
export type EvidenceWriteKind='import'|'assessment'|'withdrawal'|'report';
export type EvidenceWriteIntent=Readonly<{
 patient_id:string;case_id:string;question_id:string;kind:EvidenceWriteKind;path:string;body:string;
}>;
export type EvidenceReceipt=Readonly<Record<string,string|number|boolean>>;

const ITEMS=['abstract','api_output','figures','full_text','metadata','terminology'];
const USES=['display','ml_use','redistribute','store'];
const PERMISSIONS=['allowed','denied','unknown'];
const CONTENT=['abstract','api_output','full_text'];
const RELATIONS=['supports','contradicts','context','unknown'];
const APPLICABILITY=['applicable','limited','not_applicable','unknown'];
const REPORT_STATES=['current_unreviewed','historical_reassessment_required','content_withheld'];
const HASH=/^[0-9a-f]{64}$/;
const KEY=/^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$/;
const DOC=/^[A-Z][A-Z0-9-]{1,39}$/;
const evidenceFields=['evidence_id','evidence_key','version','sha256','statement_line','content_item','rights_sha256','permissions','state','title','issued_at','statement','created_at'];
const assessmentFields=['assessment_id','question_id','evidence_id','evidence_sha256','rights_sha256','source_snapshot_sha256','preflight_sha256','relation','applicability','quote','quote_start','rationale','actor_label','created_at','state'];
const reportFields=['report_id','question_id','prepared_at','body_sha256','snapshot_sha256','state'];
const packetFields=['contract','patient_id','case_id','question','source_snapshot_sha256','access_receipt_id','evidence','assessments','reports','packet_sha256','synthetic','human_review_state','clinical_approval','model_executed'];
const fullReportFields=['contract','patient_id','case_id','question_id','report_id','prepared_at','state','body','body_sha256','snapshot','snapshot_sha256','access_receipt_id','synthetic','human_review_state','clinical_approval','model_executed'];
const sourceFields=['source_id','document_id','version','sha256','line','finding_key','reported_state','statement','kind','event_date','issued_at','specimen_id'];
function exact(v:unknown,keys:readonly string[]):v is Record<string,unknown>{return v!==null&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).length===keys.length&&keys.every(k=>Object.hasOwn(v,k));}
function id(v:unknown,prefix:string):v is string{return typeof v==='string'&&new RegExp('^'+prefix+'-[0-9A-F]{32}$').test(v);}
function member(v:unknown,values:readonly string[]):v is string{return typeof v==='string'&&values.includes(v);}
function hex(v:unknown):v is string{return typeof v==='string'&&HASH.test(v);}
function integer(v:unknown,min=1,max=Number.MAX_SAFE_INTEGER):v is number{return typeof v==='number'&&Number.isSafeInteger(v)&&v>=min&&v<=max;}
function utc(v:unknown):v is string{return typeof v==='string'&&v.length<=64&&/^\d{4}-\d{2}-\d{2}T.+(?:Z|[+-]\d{2}:\d{2})$/.test(v)&&Number.isFinite(Date.parse(v));}
function date(v:unknown):v is string{return typeof v==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(v)&&Number.isFinite(Date.parse(v+'T00:00:00Z'))&&new Date(v+'T00:00:00Z').toISOString().slice(0,10)===v;}
function text(v:unknown,min:number,max:number):v is string{
 if(typeof v!=='string'||Array.from(v).length<min||Array.from(v).length>max)return false;
 const bytes=new TextEncoder().encode(v);return new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(bytes)===v;
}
export function visibleLine(v:unknown,min=10,max=600):v is string{return text(v,min,max)&&v===v.trim()&&!/[\p{Cc}\p{Cf}\p{Cs}\p{Zl}\p{Zp}]/u.test(v);}
function flags(v:Record<string,unknown>):boolean{return v.synthetic===true&&v.human_review_state==='not_performed'&&v.clinical_approval===false&&v.model_executed===false;}
export function canonicalEvidenceJson(v:unknown):string{
 if(Array.isArray(v))return '['+v.map(canonicalEvidenceJson).join(',')+']';
 if(v!==null&&typeof v==='object'){const row=v as Record<string,unknown>;return '{'+Object.keys(row).sort().map(k=>JSON.stringify(k)+':'+canonicalEvidenceJson(row[k])).join(',')+'}';}
 if(v===undefined||typeof v==='number'&&!Number.isFinite(v))throw Error('evidence contract');
 return JSON.stringify(v);
}
async function digest(v:string):Promise<string>{const bytes=new TextEncoder().encode(v);if(new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(bytes)!==v)throw Error('evidence bytes');return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');}
export function declaredPermissions(item:ContentItem,display:Permission='allowed',redistribute:Permission='allowed'):Permissions{
 if(!CONTENT.includes(item)||!PERMISSIONS.includes(display)||!PERMISSIONS.includes(redistribute))throw Error('evidence permissions');
 return Object.freeze(Object.fromEntries(ITEMS.map(key=>[key,Object.freeze(Object.fromEntries(USES.map(use=>[use,(['metadata',item].includes(key)?use==='store'?'allowed':use==='display'?display:use==='redistribute'?redistribute:'unknown':'unknown') as Permission])))])));
}
function permissions(v:unknown):Permissions{
 if(!exact(v,ITEMS))throw Error('evidence permissions');
 for(const item of ITEMS){if(!exact(v[item],USES)||!USES.every(use=>member((v[item] as Record<string,unknown>)[use],PERMISSIONS)))throw Error('evidence permissions');}
 return Object.freeze(Object.fromEntries(ITEMS.map(item=>[item,Object.freeze({...v[item] as Record<string,Permission>})])));
}
function allowed(p:Permissions,item:ContentItem,exporting=false):boolean{return ['metadata',item].every(key=>['store','display',...(exporting?['redistribute']:[])].every(use=>p[key]?.[use]==='allowed'));}
function sameQuestion(a:SourceQuestion,b:SourceQuestion):boolean{return Object.keys(a).every(key=>key==='source_context_state'||a[key as keyof SourceQuestion]===b[key as keyof SourceQuestion]);}
async function evidence(v:unknown):Promise<EvidenceVersion>{
 if(!exact(v,evidenceFields)||!id(v.evidence_id,'EVIDENCE')||typeof v.evidence_key!=='string'||!DOC.test(v.evidence_key)||!integer(v.version)||!hex(v.sha256)||!integer(v.statement_line,1,32768)||!member(v.content_item,CONTENT)||!hex(v.rights_sha256)||!member(v.state,['current','superseded','withdrawn'])||!date(v.issued_at)||!utc(v.created_at))throw Error('evidence version');
 const p=permissions(v.permissions);
 if(await digest(canonicalEvidenceJson(p))!==v.rights_sha256)throw Error('evidence rights digest');
 if(v.title===null||v.statement===null){if(v.title!==null||v.statement!==null)throw Error('evidence withholding');}
 else if(!text(v.title,4,180)||!text(v.statement,10,1200)||!allowed(p,v.content_item as ContentItem)||v.state==='withdrawn')throw Error('evidence disclosure');
 return Object.freeze({...v,permissions:p} as EvidenceVersion);
}
function assessment(v:unknown,q:SourceQuestion,e:EvidenceVersion):EvidenceAssessment{
 if(!exact(v,assessmentFields)||!id(v.assessment_id,'ASSESSMENT')||v.question_id!==q.question_id||v.evidence_id!==e.evidence_id||v.evidence_sha256!==e.sha256||v.rights_sha256!==e.rights_sha256||v.source_snapshot_sha256!==q.source_snapshot_sha256||v.preflight_sha256!==q.preflight_sha256||!member(v.relation,RELATIONS)||!member(v.applicability,APPLICABILITY)||v.relation==='supports'&&v.applicability==='not_applicable'||typeof v.actor_label!=='string'||!KEY.test(v.actor_label)||!utc(v.created_at)||!member(v.state,['current_unreviewed','reassessment_required','content_withheld']))throw Error('evidence assessment');
 if(v.state==='content_withheld'){
  if(v.quote!==null||v.quote_start!==null||v.rationale!==null||e.statement!==null)throw Error('evidence withholding');
 }else{
  if(!text(v.quote,1,400)||!integer(v.quote_start,0,1200)||!visibleLine(v.rationale)||e.statement===null)throw Error('evidence quote');
  const words=Array.from(e.statement),literal=Array.from(v.quote);
  if(words.slice(v.quote_start,v.quote_start+literal.length).join('')!==v.quote||e.statement.indexOf(v.quote)!==e.statement.lastIndexOf(v.quote))throw Error('evidence quote position');
  if(v.state==='current_unreviewed'&&(e.state!=='current'||q.source_context_state!=='current_unreviewed_question'))throw Error('evidence freshness');
 }
 return Object.freeze({...v} as EvidenceAssessment);
}
function reportSummary(v:unknown,q:SourceQuestion):ReportSummary{
 if(!exact(v,reportFields)||!id(v.report_id,'REPORT')||v.question_id!==q.question_id||!utc(v.prepared_at)||!hex(v.body_sha256)||!hex(v.snapshot_sha256)||!member(v.state,REPORT_STATES)||q.source_context_state==='source_reassessment_required'&&v.state==='current_unreviewed')throw Error('report history');
 return Object.freeze({...v} as ReportSummary);
}
function unique(values:readonly string[]):void{if(new Set(values).size!==values.length)throw Error('duplicate evidence identity');}

export async function decodeEvidencePacket(value:unknown,expected:SourceQuestion):Promise<EvidencePacket>{
 if(!exact(value,packetFields)||value.contract!=='oi.h1-question-evidence/1'||value.patient_id!==expected.patient_id||value.case_id!==expected.case_id||!hex(value.source_snapshot_sha256)||!id(value.access_receipt_id,'ACCESS')||!hex(value.packet_sha256)||!flags(value)||!Array.isArray(value.evidence)||value.evidence.length>100||!Array.isArray(value.assessments)||value.assessments.length>200||!Array.isArray(value.reports)||value.reports.length>100)throw Error('evidence packet');
 const q=decodeSourceQuestion(value.question,expected.patient_id,expected.case_id);
 if(!member(q.source_context_state,['current_unreviewed_question','source_reassessment_required'])||!sameQuestion(q,expected)||q.source_context_state==='current_unreviewed_question'&&q.source_snapshot_sha256!==value.source_snapshot_sha256)throw Error('evidence question');
 const rows=await Promise.all(value.evidence.map(evidence));unique(rows.map(e=>e.evidence_id));unique(rows.map(e=>e.evidence_key+':'+e.version));
 for(const row of rows){
  const latest=rows.filter(e=>e.evidence_key===row.evidence_key).reduce((a,b)=>a.version>b.version?a:b);
  const expectedState=latest.state==='withdrawn'?'withdrawn':row===latest?'current':'superseded';
  if(row.state!==expectedState)throw Error('evidence lineage');
  if(row.statement!==null&&(latest.state==='withdrawn'||!allowed(latest.permissions,row.content_item)))throw Error('current rights withheld');
 }
 const assessments=value.assessments.map(v=>{
  if(v===null||typeof v!=='object')throw Error('evidence assessment');
  const e=rows.find(e=>e.evidence_id===(v as Record<string,unknown>).evidence_id);if(!e)throw Error('missing evidence');
  return assessment(v,q,e);
 });unique(assessments.map(a=>a.assessment_id));
 const currentFamilies=assessments.filter(a=>a.state==='current_unreviewed').map(a=>rows.find(e=>e.evidence_id===a.evidence_id)!.evidence_key);unique(currentFamilies);
 const reports=value.reports.map(v=>reportSummary(v,q));unique(reports.map(r=>r.report_id));
 const stable={...value};delete stable.access_receipt_id;delete stable.packet_sha256;delete stable.reports;
 if(await digest(canonicalEvidenceJson(stable))!==value.packet_sha256)throw Error('evidence packet digest');
 return Object.freeze({...value,question:q,evidence:Object.freeze(rows),assessments:Object.freeze(assessments),reports:Object.freeze(reports)} as EvidencePacket);
}

function selectedSource(v:unknown,q:SourceQuestion):ComposerSource{
 if(!exact(v,sourceFields)||v.source_id!==q.source_id||v.version!==q.source_version||v.sha256!==q.source_sha256||v.line!==q.source_line||typeof v.document_id!=='string'||!DOC.test(v.document_id)||typeof v.finding_key!=='string'||!/^[a-z][a-z0-9_-]{0,59}$/.test(v.finding_key)||!member(v.reported_state,['reported','negative','pending','indeterminate','not-reported','not-assessed','conflicting'])||!text(v.statement,1,1200)||!member(v.kind,['clinical','pathology','laboratory','imaging','molecular','other'])||!date(v.event_date)||!date(v.issued_at)||(v.specimen_id!==null&&(typeof v.specimen_id!=='string'||!DOC.test(v.specimen_id))))throw Error('report source');
 return Object.freeze({...v} as ComposerSource);
}
export async function decodeEvidenceReport(value:unknown,expected:SourceQuestion,reportId:string,summary?:ReportSummary):Promise<EvidenceReport>{
 if(!exact(value,fullReportFields)||value.contract!=='oi.h1-evidence-report/1'||value.patient_id!==expected.patient_id||value.case_id!==expected.case_id||value.question_id!==expected.question_id||value.report_id!==reportId||!id(value.report_id,'REPORT')||!utc(value.prepared_at)||!member(value.state,REPORT_STATES)||!hex(value.body_sha256)||!hex(value.snapshot_sha256)||!id(value.access_receipt_id,'ACCESS')||!flags(value))throw Error('evidence report');
 if(summary&&(['report_id','question_id','prepared_at','body_sha256','snapshot_sha256'] as const).some(k=>value[k]!==summary[k]))throw Error('report immutable history');
 if(summary&&summary.state!=='current_unreviewed'&&value.state==='current_unreviewed')throw Error('report historical promotion');
 if(value.state==='content_withheld'){
  if(value.body!==null||value.snapshot!==null)throw Error('report withholding');
  return Object.freeze({...value} as EvidenceReport);
 }
 if(!text(value.body,1,131072)||new TextEncoder().encode(value.body).length>131072||await digest(value.body)!==value.body_sha256||!exact(value.snapshot,['question','selected_source','comparisons','prepared_at','actor_label']))throw Error('report bytes');
 const snap=value.snapshot,q=decodeSourceQuestion(snap.question,expected.patient_id,expected.case_id);
 if(!sameQuestion(q,expected)||q.source_context_state!=='current_unreviewed_question'||q.source_snapshot_contract!=='oi.pg-source-world-model/1'||snap.prepared_at!==value.prepared_at||typeof snap.actor_label!=='string'||!KEY.test(snap.actor_label)||!Array.isArray(snap.comparisons)||snap.comparisons.length<1||snap.comparisons.length>20||value.state==='current_unreviewed'&&expected.source_context_state==='source_reassessment_required')throw Error('report snapshot');
 const source=selectedSource(snap.selected_source,q);
 const comparisons=await Promise.all(snap.comparisons.map(async row=>{
  if(!exact(row,['assessment','evidence']))throw Error('report comparison');
  const e=await evidence(row.evidence),a=assessment(row.assessment,q,e);
  if(e.state!=='current'||e.statement===null||a.state!=='current_unreviewed'||!allowed(e.permissions,e.content_item,true))throw Error('report content rights');
  return Object.freeze({assessment:a,evidence:e});
 }));
 unique(comparisons.map(c=>c.assessment.assessment_id));unique(comparisons.map(c=>c.evidence.evidence_key));
 if(await digest(canonicalEvidenceJson(snap))!==value.snapshot_sha256)throw Error('report snapshot digest');
 return Object.freeze({...value,snapshot:Object.freeze({...snap,question:q,selected_source:source,comparisons:Object.freeze(comparisons)})} as EvidenceReport);
}

export async function decodeEvidenceOriginal(value:unknown,question:SourceQuestion,selected:EvidenceVersion):Promise<EvidenceOriginal>{
 if(!exact(value,['contract','patient_id','case_id','evidence_id','sha256','original_text','access_receipt_id','synthetic'])||value.contract!=='oi.h1-evidence-original/1'||value.patient_id!==question.patient_id||value.case_id!==question.case_id||value.evidence_id!==selected.evidence_id||value.sha256!==selected.sha256||!id(value.access_receipt_id,'ACCESS')||value.synthetic!==true||!text(value.original_text,1,32768)||new TextEncoder().encode(value.original_text).length>32768||!value.original_text.startsWith('OI-SYNTHETIC-EVIDENCE/1\n')||/[\r\0]/.test(value.original_text)||await digest(value.original_text)!==selected.sha256)throw Error('evidence original');
 return Object.freeze({...value} as EvidenceOriginal);
}

export function decodeEvidenceReceipt(value:unknown,kind:EvidenceWriteKind,questionId:string,evidenceId?:string):EvidenceReceipt{
 const fields=kind==='import'?['evidence_id','version','duplicate']:kind==='withdrawal'?['withdrawal_id','evidence_id','duplicate']:kind==='assessment'?['assessment_id','question_id','duplicate']:['report_id','question_id','duplicate'];
 if(!exact(value,fields)||typeof value.duplicate!=='boolean')throw Error('evidence receipt');
 if(kind==='import'&&(!id(value.evidence_id,'EVIDENCE')||!integer(value.version)))throw Error('evidence receipt');
 if(kind==='withdrawal'&&(!id(value.withdrawal_id,'WITHDRAWAL')||value.evidence_id!==evidenceId))throw Error('evidence receipt');
 if(kind==='assessment'&&(!id(value.assessment_id,'ASSESSMENT')||value.question_id!==questionId))throw Error('evidence receipt');
 if(kind==='report'&&(!id(value.report_id,'REPORT')||value.question_id!==questionId))throw Error('evidence receipt');
 return Object.freeze({...value} as EvidenceReceipt);
}

function download(text:string,name:string):void{
 const url=URL.createObjectURL(new Blob([text],{type:'text/plain;charset=utf-8'}));
 const link=document.createElement('a');link.href=url;link.download=name;
 try{document.body.append(link);link.click();}finally{link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}
}
export async function downloadEvidenceReport(session:RegistrySession,questionId:string,reportId:string):Promise<void>{
 const value=await session.readEvidenceReport(questionId,reportId);
 if(!value||value.body===null||session.snapshot().evidenceReport!==value)return;
 download(value.body,'open-intelligence-evidence-'+reportId+'.txt');
}
export async function downloadEvidenceOriginal(session:RegistrySession,questionId:string,evidenceId:string):Promise<void>{
 const value=await session.loadEvidenceOriginal(questionId,evidenceId);
 if(!value||session.snapshot().evidenceOriginal!==value)return;
 download(value.original_text,'open-intelligence-evidence-'+evidenceId+'.txt');
}
