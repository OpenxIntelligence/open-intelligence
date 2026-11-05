const patient='PAT-FICTIONAL-LAB',caseId='CASE-FICTIONAL-LAB',sourceId='SRC-'+'A'.repeat(32),hash='b'.repeat(64);
function projection(){
 const src={source_id:sourceId,document_id:'FICTIONAL-REPORT-A',version:1,sha256:hash,kind:'laboratory',event_date:'2026-04-03',issued_at:'2026-04-04',received_at:'2026-11-04T10:00:00Z',specimen_id:'FICTIONAL-SPECIMEN-A',state:'current',supersedes_id:null};
 const observations=['0','-0.25',null].map((value,i)=>({source_id:sourceId,document_id:src.document_id,document_version:1,source_sha256:hash,observation_reference:'Observation/FICTIONAL-OBS-'+i,loinc_code:'777-3',effective_at:'2026-04-03T09:0'+i+':00-04:00',issued_at:'2026-04-04T12:00:00Z',specimen_reference:'Specimen/FICTIONAL-SPECIMEN-A',specimen_type_text:'Fictional <script>plasma</script>',specimen_collected_at:'2026-04-03T09:00:00-04:00',report_reference:'DiagnosticReport/FICTIONAL-REPORT-A',status:value===null?'reported_absent':'reported_value',value_text:value,unit_code:value===null?null:'10*9/L',absent_reason:value===null?'not-performed':null,source_reported:true,review_state:'not_established',clinical_review:'not_performed',clinical_meaning:null}));
 const timeline=observations.map(o=>({source_id:o.source_id,observation_reference:o.observation_reference,loinc_code:o.loinc_code,effective_at:o.effective_at,issued_at:o.issued_at,specimen_reference:o.specimen_reference,status:o.status,clinical_interpretation:'not_performed'})).reverse();
 return {contract:'oi.pg-source-world-model/1',patient_id:patient,case_id:caseId,access_receipt_id:'ACCESS-'+'C'.repeat(32),synthetic:true,authority:'source_report_only_unreviewed',clinical_interpretation:false,research_review_invalidation_integrated:false,composer_execution_authorized:false,snapshot_fingerprint:'d'.repeat(64),as_of_received_at:src.received_at,summary:{current_sources:1,historical_sources:0,current_observations:3,current_laboratory_observations:3,unresolved_observations:1,source_disagreements:0},current_sources:[src],history:[],observations:[],laboratory_observations:observations,laboratory_timeline:timeline,unresolved_refs:[],conflicts:[],limitations:['Independently fictional; source-reported only.']};
}
export {patient,caseId,sourceId,hash,projection};

// The local observation and test identifiers stay fixed when the result variant changes.
export const fictionalCoding={system:'urn:oi:synthetic:lab-results',code:'FIC.a-01_2',
  version:'V1.0-fixture',display:'Literal  <img src=x> & "label"'};
export function codedProjection(coding=fictionalCoding){
 const w=projection(),o=w.laboratory_observations[0];
 Object.assign(o,{status:'reported_coded',value_text:null,unit_code:null,absent_reason:null,coded_result:{...coding}});
 w.laboratory_timeline.find(t=>t.observation_reference===o.observation_reference).status=o.status;
 return w;
}
