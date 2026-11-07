import {projection,codedProjection} from './laboratory-projection-fixture.mjs';

export function twoReports(coded=false){
 const w=coded?codedProjection():projection(),a=w.current_sources[0];
 const b={...a,source_id:'SRC-'+'B'.repeat(32),document_id:'FICTIONAL-REPORT-B',
   sha256:'c'.repeat(64),specimen_id:'FICTIONAL-SPECIMEN-B',
   event_date:'2026-05-03',issued_at:'2026-05-04'};
 const original=w.laboratory_observations[0];
 const row={...original,source_id:b.source_id,source_sha256:b.sha256,
   document_id:b.document_id,document_version:b.version,
   observation_reference:'Observation/FICTIONAL-OBS-B',
   specimen_reference:'Specimen/FICTIONAL-SPECIMEN-B',
   specimen_type_text:'Other fictional sample',
   specimen_collected_at:'2026-05-03T09:00:00-04:00',
   report_reference:'DiagnosticReport/FICTIONAL-REPORT-B',
   effective_at:'2026-05-03T09:05:00-04:00',issued_at:'2026-05-04T12:00:00Z',
   ...(coded?{}:{value_text:'4.20',unit_code:'mg/L'})};
 w.current_sources.push(b);
 w.laboratory_observations.push(row);
 w.laboratory_timeline.unshift({source_id:row.source_id,observation_reference:row.observation_reference,
   loinc_code:row.loinc_code,effective_at:row.effective_at,issued_at:row.issued_at,
   specimen_reference:row.specimen_reference,status:row.status,clinical_interpretation:'not_performed'});
 w.summary.current_sources=2;w.summary.current_observations=4;
 w.summary.current_laboratory_observations=4;
 return w;
}
