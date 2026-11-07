import {parseSourceFinding, type SourceFinding} from './source-contracts.js';
import type {ReviewHistoryReceipt, ReviewQueueItem} from './review-queue-view.js';

export type AttributionVersion=Readonly<{
 source_id:string;document_id:string;source_version:number;source_sha256:string;finding:SourceFinding|null;
}>;
type Comparison=Readonly<{recorded:AttributionVersion;latest:AttributionVersion}>;
export type AttributionReassessment=Readonly<{receipt_id:string;comparison_sha256:string;first:Comparison;second:Comparison}>;

function fields(value:unknown,keys:readonly string[]):value is Record<string,unknown>{
 return typeof value==='object'&&value!==null&&!Array.isArray(value)&&
  Object.keys(value).length===keys.length&&keys.every(k=>Object.hasOwn(value,k));
}

function version(raw:unknown):AttributionVersion{
 if(!fields(raw,['source_id','document_id','source_version','source_sha256','finding'])||
    typeof raw.source_id!=='string'||!/^SRC-[0-9A-F]{32}$/.test(raw.source_id)||
    typeof raw.document_id!=='string'||!/^[A-Z][A-Z0-9-]{1,39}$/.test(raw.document_id)||
    typeof raw.source_version!=='number'||!Number.isSafeInteger(raw.source_version)||raw.source_version<1||
    typeof raw.source_sha256!=='string'||!/^[a-f0-9]{64}$/.test(raw.source_sha256))throw Error('source version');
 const finding=raw.finding===null?null:parseSourceFinding(raw.finding);
 if(finding&&(finding.source_id!==raw.source_id||!['reported','negative','indeterminate','conflicting','pending','not-reported','not-assessed'].includes(finding.reported_state)))throw Error('finding');
 return Object.freeze({source_id:raw.source_id,document_id:raw.document_id,
  source_sha256:raw.source_sha256,source_version:raw.source_version,finding});
}

type Anchor={source_id:string;source_version:number;source_sha256:string;source_line:number;document_id?:string};
function comparison(raw:unknown,anchor:Anchor):Comparison{
 if(!fields(raw,['recorded','latest']))throw Error('comparison');
 const recorded=version(raw.recorded), latest=version(raw.latest),old=recorded.finding,now=latest.finding;
 if(!old||old.oncology?.role!=='metastasis'||old.source_line!==anchor.source_line||
    recorded.source_id!==anchor.source_id||recorded.source_sha256!==anchor.source_sha256||
    recorded.source_version!==anchor.source_version||(anchor.document_id&&recorded.document_id!==anchor.document_id)||
    recorded.document_id!==latest.document_id||latest.source_version<recorded.source_version||
    (now&&old.finding_key!==now.finding_key))throw Error('source anchor');
 if(latest.source_version===recorded.source_version){
  if(latest.source_id!==recorded.source_id||latest.source_sha256!==recorded.source_sha256||
     !now||now.source_line!==old.source_line||now.source_statement!==old.source_statement||
     now.reported_state!==old.reported_state||now.oncology?.role!==old.oncology.role||
     now.oncology?.episode_id!==old.oncology.episode_id)throw Error('changed original');
 }else if(latest.source_id===recorded.source_id||latest.source_sha256===recorded.source_sha256)throw Error('amendment');
 return Object.freeze({recorded,latest});
}

export function decodeAttributionReassessment(raw:unknown,question:ReviewQueueItem,receipt:ReviewHistoryReceipt):AttributionReassessment{
 if(!receipt.comparison_source||!fields(raw,['contract','synthetic','clinical_approval','patient_id','case_id',
    'question_id','receipt_id','access_receipt_id','first','second','comparison_sha256'])||
    raw.contract!=='oi.synthetic-attribution-reassessment/2'||typeof raw.comparison_sha256!=='string'||!/^([a-f0-9]{64})$/.test(raw.comparison_sha256)||raw.synthetic!==true||raw.clinical_approval!==false||
    raw.patient_id!==question.patient_id||raw.case_id!==question.case_id||raw.question_id!==question.question_id||
    raw.receipt_id!==receipt.receipt_id||receipt.question_id!==question.question_id||
    typeof raw.access_receipt_id!=='string'||!/^ACCESS-[0-9A-F]{32}$/.test(raw.access_receipt_id))throw Error('review scope');
 const first=comparison(raw.first,question),second=comparison(raw.second,receipt.comparison_source);
 if(first.recorded.document_id===second.recorded.document_id||
    first.recorded.finding!.finding_key!==second.recorded.finding!.finding_key||
    first.recorded.finding!.oncology!.episode_id===second.recorded.finding!.oncology!.episode_id||
    [first.recorded.source_id,first.latest.source_id].some(id=>id===second.recorded.source_id||id===second.latest.source_id))throw Error('recorded pair');
 return Object.freeze({receipt_id:receipt.receipt_id,comparison_sha256:raw.comparison_sha256,first,second});
}
