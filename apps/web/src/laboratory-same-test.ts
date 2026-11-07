/** Read-only, bounded grouping of exact current laboratory originals by literal LOINC code.
 *
 * This is NOT a clinical trend, comparable assay assertion, converted unit,
 * reference interval, diagnosis, evidence appraisal, or clinical approval.
 * The authorized World Model reader supplies source custody and permissions.
 * Legacy/unbound locators stay in the ordinary results reader, not this group.
 */
import type {SourceWorldModel,WorldLaboratoryObservation} from './source-world-model.js';

const OBSERVATION=/^Observation\/[A-Za-z0-9.-]{1,64}$/;
const MAX_GROUPS=12;
const MAX_ROWS=20;

type Lab=WorldLaboratoryObservation;
export type SameTestReportGroup=Readonly<{
  loinc_code:string;source_count:number;result_count:number;
  rows:readonly Lab[];hidden_result_count:number;
}>;
export type SameTestReportView=Readonly<{
  groups:readonly SameTestReportGroup[];
  group_count:number;
  hidden_group_count:number;
  excluded_reference_count:number;
}>;

function sameOriginal(current:ReadonlyMap<string,SourceWorldModel['current_sources'][number]>, item:Lab):boolean{
  const source=current.get(item.source_id);
  return Boolean(source&&source.state==='current'&&source.kind==='laboratory'&&
    item.source_sha256===source.sha256&&item.document_version===source.version&&
    item.document_id===source.document_id&&
    OBSERVATION.test(item.observation_reference)&&
    source.specimen_id&&item.specimen_reference==='Specimen/'+source.specimen_id&&
    item.report_reference==='DiagnosticReport/'+source.document_id);
}

export function sameTestReportGroups(model:SourceWorldModel):SameTestReportView{
  // Never rely on a result reference alone: Observation IDs are bundle-local.
  const byOriginal=new Map(model.laboratory_observations.map(item=>[
    JSON.stringify([item.source_id,item.observation_reference]),item]));
  const current=new Map(model.current_sources.map(source=>[source.source_id,source] as const));
  const eligible=new Map<string,{rows:Lab[];sources:Set<string>}>();
  let excluded=0;
  for(const step of model.laboratory_timeline){
    const item=byOriginal.get(JSON.stringify([step.source_id,step.observation_reference]));
    if(!item||!sameOriginal(current,item)){
      excluded++;
      continue;
    }
    let group=eligible.get(item.loinc_code);
    if(!group){group={rows:[],sources:new Set()};eligible.set(item.loinc_code,group);}
    group.rows.push(item);
    group.sources.add(item.source_id);
  }
  // A repeated result within one original does not represent independent reports.
  const groups=Array.from(eligible,([loinc_code,{rows,sources}])=>({
    loinc_code,source_count:sources.size,result_count:rows.length,
    rows:Object.freeze(rows.slice(0,MAX_ROWS)),hidden_result_count:Math.max(0,rows.length-MAX_ROWS),
  })).filter(g=>g.source_count>=2).sort((a,b)=>a.loinc_code.localeCompare(b.loinc_code));
  return Object.freeze({groups:Object.freeze(groups.slice(0,MAX_GROUPS)),
    group_count:groups.length,hidden_group_count:Math.max(0,groups.length-MAX_GROUPS),
    excluded_reference_count:excluded});
}
