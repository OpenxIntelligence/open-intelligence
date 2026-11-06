import type {SavedLabQuestion} from './laboratory-question.js';
import type {SourceWorldModel} from './source-world-model.js';
import {readLaboratoryCitationReport} from './laboratory-citation-report.js';
import {citationEvidenceTimestamp} from './evidence-timestamp.js';

export type InspectionSnapshot = Readonly<{
  snapshot_id:string; captured_report_sha256:string; captured_at:string; citation_count:number;
  captured_source_context_state:'current_unreviewed_question'|'source_reassessment_required';
}>;
const digest=(s:unknown):s is string=>typeof s==='string'&&s.length===64&&/^[a-f0-9]+$/.test(s);
const snapshotId=(s:unknown):s is string=>typeof s==='string'&&s.length===45&&/^LAB-SNAPSHOT-[A-F0-9]{32}$/.test(s);
function exact(v:unknown,keys:readonly string[]):v is Record<string,unknown>{
  return !!v&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).length===keys.length&&keys.every(k=>Object.hasOwn(v,k));
}
function summary(v:unknown):InspectionSnapshot{
  if(!exact(v,['snapshot_id','captured_report_sha256','captured_at','citation_count','captured_source_context_state'])||
    !snapshotId(v.snapshot_id)||!digest(v.captured_report_sha256)||!citationEvidenceTimestamp(v.captured_at)||
    typeof v.citation_count!=='number'||!Number.isInteger(v.citation_count)||v.citation_count<0||v.citation_count>100||
    (v.captured_source_context_state!=='current_unreviewed_question'&&v.captured_source_context_state!=='source_reassessment_required'))
    throw Error('Invalid inspection snapshot');
  return Object.freeze({...v} as InspectionSnapshot);
}
export function snapshotReceipt(v:unknown,expected:string,status:number){
  if(!exact(v,['snapshot_id','captured_report_sha256','duplicate'])||!snapshotId(v.snapshot_id)||
    v.captured_report_sha256!==expected||![200,201].includes(status)||v.duplicate!==(status===200))
    throw Error('Invalid inspection save receipt');
  return Object.freeze({snapshot_id:v.snapshot_id,captured_report_sha256:expected,duplicate:status===200});
}
export function snapshotHistory(v:unknown,model:SourceWorldModel,q:SavedLabQuestion){
  if(!exact(v,['patient_id','case_id','question_id','source_access_receipt_id','snapshots'])||
    v.patient_id!==model.patient_id||v.case_id!==model.case_id||v.question_id!==q.question_id||
    typeof v.source_access_receipt_id!=='string'||v.source_access_receipt_id.length!==39||!/^ACCESS-[0-9A-F]{32}$/.test(v.source_access_receipt_id)||
    !Array.isArray(v.snapshots)||v.snapshots.length>100)throw Error('Invalid inspection history');
  const rows=v.snapshots.map(summary);
  if(new Set(rows.map(r=>r.snapshot_id)).size!==rows.length)throw Error('Duplicate inspection');
  return Object.freeze(rows);
}
export function reopenedSnapshot(v:unknown,expected:InspectionSnapshot,model:SourceWorldModel,q:SavedLabQuestion){
  if(!exact(v,['snapshot','inspection']))throw Error('Invalid saved inspection');
  const row=summary(v.snapshot);
  if(row.snapshot_id!==expected.snapshot_id||row.captured_report_sha256!==expected.captured_report_sha256||
    row.captured_at!==expected.captured_at||row.citation_count!==expected.citation_count||
    row.captured_source_context_state!==expected.captured_source_context_state)throw Error('Saved inspection changed');
  const report=readLaboratoryCitationReport(v.inspection,model,q);
  if(report.citations.links.length!==row.citation_count||
    (row.captured_source_context_state==='source_reassessment_required'&&report.citations.source_context_state!=='source_reassessment_required'))
    throw Error('Invalid saved inspection context');
  return {snapshot:row,report};
}
