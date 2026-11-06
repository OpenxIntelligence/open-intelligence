import type {SourceWorldModel,WorldObservation} from './source-world-model.js';

export function isDraftOrigin(item:WorldObservation):boolean {
  return item.reported_state==='reported' && item.oncology?.role==='primary' && item.oncology.episode_id!==null;
}

export function draftCommand(world:SourceWorldModel,origin:WorldObservation):string {
  if(!world.observations.includes(origin)||!isDraftOrigin(origin))throw Error('Choose a current primary source');
  return JSON.stringify({synthetic:true,source_id:origin.source_id,source_line:origin.source_line,
    source_version:origin.document_version,source_sha256:origin.source_sha256,snapshot_sha256:world.snapshot_fingerprint});
}

export type Draft=Readonly<{episode_id:string;created_by:string;created_at:string;source_id:string;source_line:number;
  source_version:number;source_sha256:string;document_id:string;event_date:string;issued_at:string;
  source_label:string;statement:string;source_state:'current'|'superseded';basis_sha256:string;
  basis_state:'current'|'reassessment_required';review_state:'unreviewed_draft'}>;

function fields(value:unknown,keys:readonly string[]):Record<string,unknown>{
  if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).length!==keys.length||
     !keys.every(k=>Object.hasOwn(value,k)))throw Error('Invalid episode draft response');
  return value as Record<string,unknown>;
}
const id=(v:unknown):v is string=>typeof v==='string' && /^EPISODE-[A-F0-9]{32}$/.test(v) && v===v.trim();
export function readDraftReceipt(value:unknown,world:SourceWorldModel){
  const v=fields(value,['patient_id','case_id','episode_id','duplicate']);
  if(v.patient_id!==world.patient_id||v.case_id!==world.case_id||!id(v.episode_id)||typeof v.duplicate!=='boolean')
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
    const d=fields(raw,['episode_id','created_by','created_at','source_id','source_line','source_version',
      'source_sha256','document_id','event_date','issued_at','source_label','statement','source_state',
      'basis_sha256','basis_state','review_state']);
    const source=typeof d.source_id==='string'?sources.get(d.source_id):undefined;
    if(!id(d.episode_id)||ids.has(d.episode_id)||!source||source.version!==d.source_version||
       source.sha256!==d.source_sha256||source.document_id!==d.document_id||source.state!==d.source_state||
       source.event_date!==d.event_date||source.issued_at!==d.issued_at||typeof d.source_line!=='number'||
       !Number.isSafeInteger(d.source_line)||d.source_line<1||d.source_line>10000||
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
      if(!o||!isDraftOrigin(o)||o.oncology?.episode_id!==d.source_label||o.source_statement!==d.statement)
        throw Error('Draft differs from its source');
    }
    ids.add(d.episode_id);anchors.add(key);
    return Object.freeze({...d} as Draft);
  });
}
