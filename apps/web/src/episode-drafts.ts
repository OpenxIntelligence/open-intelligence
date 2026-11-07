import type {SourceWorldModel,WorldObservation} from './source-world-model.js';
import type {SourceVersion} from './source-contracts.js';

export function isDraftOrigin(item:WorldObservation):boolean {
  return item.reported_state==='reported' && item.oncology?.role==='primary' && item.oncology.episode_id!==null;
}

export function draftCommand(world:SourceWorldModel,origin:WorldObservation):string {
  if(!world.observations.includes(origin)||!isDraftOrigin(origin))throw Error('Choose a current primary source');
  return JSON.stringify({synthetic:true,source_id:origin.source_id,source_line:origin.source_line,
    source_version:origin.document_version,source_sha256:origin.source_sha256,snapshot_sha256:world.snapshot_fingerprint});
}

export type Draft=Readonly<{episode_id:string;created_by:string;created_at:string;source_id:string;source_line:number;
  finding_key:string;
  source_version:number;source_sha256:string;document_id:string;event_date:string;issued_at:string;
  source_label:string;statement:string;source_state:'current'|'superseded';basis_sha256:string;
  basis_state:'current'|'reassessment_required';review_state:'unreviewed_draft'}>;

function fields(value:unknown,keys:readonly string[]):Record<string,unknown>{
  if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).length!==keys.length||
     !keys.every(k=>Object.hasOwn(value,k)))throw Error('Invalid episode draft response');
  return value as Record<string,unknown>;
}
const id=(v:unknown):v is string=>typeof v==='string' && /^EPISODE-[A-F0-9]{32}$/.test(v) && v===v.trim();
export function readDraftReceipt(value:unknown,world:SourceWorldModel,status:number){
  const v=fields(value,['patient_id','case_id','episode_id','duplicate']);
  if(v.patient_id!==world.patient_id||v.case_id!==world.case_id||!id(v.episode_id)||
     (status!==200&&status!==201)||v.duplicate!==(status===200))
    throw Error('Invalid episode draft receipt');
  return v.episode_id;
}
export function readDrafts(value:unknown,world:SourceWorldModel):Draft[]{
  const v=fields(value,['patient_id','case_id','snapshot_sha256','access_receipt_id','drafts']);
  if(v.patient_id!==world.patient_id||v.case_id!==world.case_id||v.snapshot_sha256!==world.snapshot_fingerprint||
     typeof v.access_receipt_id!=='string'||!/^ACCESS-[A-F0-9]{32}$/.test(v.access_receipt_id)||
     !Array.isArray(v.drafts)||v.drafts.length>64)throw Error('Reopen the current patient Journey');
  const ids=new Set<string>(), anchors=new Set<string>();
  const sources=new Map([...world.current_sources,...world.history].map(s=>[s.source_id,s]));
  return v.drafts.map(raw=>{
    const d=fields(raw,['episode_id','created_by','created_at','source_id','source_line','finding_key','source_version',
      'source_sha256','document_id','event_date','issued_at','source_label','statement','source_state',
      'basis_sha256','basis_state','review_state']);
    const source=typeof d.source_id==='string'?sources.get(d.source_id):undefined;
    if(!id(d.episode_id)||ids.has(d.episode_id)||!source||source.version!==d.source_version||
       source.sha256!==d.source_sha256||source.document_id!==d.document_id||source.state!==d.source_state||
       source.event_date!==d.event_date||source.issued_at!==d.issued_at||typeof d.source_line!=='number'||
       !Number.isSafeInteger(d.source_line)||d.source_line<1||d.source_line>10000||
       typeof d.finding_key!=='string'||!/^[a-z][a-z0-9_-]{0,59}$/.test(d.finding_key)||
       typeof d.source_label!=='string'||!/^EP-[A-Z0-9][A-Z0-9-]{0,35}$/.test(d.source_label)||
       typeof d.statement!=='string'||!d.statement||d.statement.length>2400||
       typeof d.created_by!=='string'||!d.created_by||typeof d.created_at!=='string'||!Number.isFinite(Date.parse(d.created_at))||
       typeof d.basis_sha256!=='string'||!/^[0-9a-f]{64}$/.test(d.basis_sha256)||d.review_state!=='unreviewed_draft'||
       d.basis_state!==(d.basis_sha256===world.snapshot_fingerprint?'current':'reassessment_required')||
       (source.state==='superseded'&&d.basis_state==='current'))throw Error('Invalid episode draft basis');
    const key=source.source_id+':'+d.source_line;
    if(anchors.has(key))throw Error('Duplicate episode draft origin');
    if(source.state==='current'){
      const o=world.observations.find(x=>x.source_id===source.source_id&&x.source_line===d.source_line);
      if(!o||!isDraftOrigin(o)||o.finding_key!==d.finding_key||o.oncology?.episode_id!==d.source_label||o.source_statement!==d.statement)
        throw Error('Draft differs from its source');
    }
    ids.add(d.episode_id);anchors.add(key);
    const draft=Object.freeze({...d} as Draft);
    compareDraftOrigin(draft,world);
    return draft;
  });
}

export type DraftOriginComparison=Readonly<{
  source:SourceVersion;finding:WorldObservation|null;
  change:'same_version'|'unchanged'|'changed'|'removed';
}>;

/** Follow one immutable document history and finding key, never an episode label. */
export function compareDraftOrigin(draft:Draft,world:SourceWorldModel):DraftOriginComparison{
  const current=world.current_sources.filter(s=>s.document_id===draft.document_id);
  if(current.length!==1)throw Error('Episode origin lineage unavailable');
  const source=current[0];
  const versions=new Map([...world.current_sources,...world.history].map(s=>[s.source_id,s]));
  let ancestor:SourceVersion|undefined=source;
  while(ancestor&&ancestor.version>draft.source_version){
    const prior:SourceVersion|undefined=ancestor.supersedes_id?versions.get(ancestor.supersedes_id):undefined;
    if(!prior||prior.document_id!==draft.document_id||prior.version!==ancestor.version-1)
      throw Error('Episode origin lineage unavailable');
    ancestor=prior;
  }
  if(!ancestor||ancestor.source_id!==draft.source_id||ancestor.version!==draft.source_version||
     ancestor.sha256!==draft.source_sha256)throw Error('Episode origin lineage unavailable');
  const matches=world.observations.filter(o=>o.source_id===source.source_id&&o.finding_key===draft.finding_key);
  if(matches.length>1)throw Error('Ambiguous episode origin');
  const finding=matches[0]??null;
  if(finding&&(finding.document_id!==source.document_id||finding.document_version!==source.version||
     finding.source_sha256!==source.sha256))throw Error('Episode origin source mismatch');
  const unchanged=finding?.source_statement===draft.statement&&finding.reported_state==='reported'&&
    finding.oncology?.role==='primary'&&finding.oncology.episode_id===draft.source_label;
  const change=source.source_id===draft.source_id?'same_version':!finding?'removed':unchanged?'unchanged':'changed';
  return Object.freeze({source,finding,change});
}
