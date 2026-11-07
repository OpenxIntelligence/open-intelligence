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
export type ReportedContextDifference=
  'specimen_descriptions'|'result_kinds'|'numeric_units'|'absence_reasons'|
  'coded_system_versions'|'coded_answer_codes';
export type SameTestReportGroup=Readonly<{
  loinc_code:string;source_count:number;result_count:number;
  rows:readonly Lab[];hidden_result_count:number;
  context_differences:readonly ReportedContextDifference[];
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

/** Literal differences over the *whole* eligible group, including undisplayed rows.
 * An empty list is never evidence of medical or analytical comparability.
 */
function reportedContextDifferences(rows:readonly Lab[]):readonly ReportedContextDifference[]{
  const differences:ReportedContextDifference[]=[];
  const differs=(values:readonly string[])=>new Set(values).size>1;
  if(differs(rows.map(r=>r.specimen_type_text)))differences.push('specimen_descriptions');
  if(differs(rows.map(r=>r.status)))differences.push('result_kinds');
  const numeric=rows.filter(r=>r.status==='reported_value');
  if(differs(numeric.map(r=>r.status==='reported_value'?r.unit_code:'')))
    differences.push('numeric_units');
  const absent=rows.filter(r=>r.status==='reported_absent');
  if(differs(absent.map(r=>r.status==='reported_absent'?r.absent_reason:'')))
    differences.push('absence_reasons');
  const coded=rows.filter(r=>r.status==='reported_coded');
  if(differs(coded.map(r=>r.status==='reported_coded'?JSON.stringify([
    r.coded_result.system,r.coded_result.version??null]):'')))
    differences.push('coded_system_versions');
  if(differs(coded.map(r=>r.status==='reported_coded'?r.coded_result.code:'')))
    differences.push('coded_answer_codes');
  return Object.freeze(differences);
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
    context_differences:reportedContextDifferences(rows),
  })).filter(g=>g.source_count>=2).sort((a,b)=>a.loinc_code.localeCompare(b.loinc_code));
  return Object.freeze({groups:Object.freeze(groups.slice(0,MAX_GROUPS)),
    group_count:groups.length,hidden_group_count:Math.max(0,groups.length-MAX_GROUPS),
    excluded_reference_count:excluded});
}
