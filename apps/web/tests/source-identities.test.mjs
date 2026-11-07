import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readSourceIdentities} from '../.test-dist/laboratory-fhir.js';
const row={identity_id:'IDENT-'+'A'.repeat(32),source_organization:'ORG-FICT',source_system:'SYS-FICT',source_subject_ref:'SUB-FICT',
 review_ref:'REVIEW-FICT',created_by:'ACTOR-FICT',created_at:'2026-11-01T00:00:00Z',status:'linked',primary_identity:true};
const data={patient_id:'PAT-FICT',case_id:'CASE-FICT',identities:[row]};
test('identity list retains an explicit held association without granting import',()=>{
 const held={...row,identity_id:'IDENT-'+'B'.repeat(32),primary_identity:false,status:'quarantined'};
 const rows=readSourceIdentities({...data,identities:[row,held]},data.patient_id,data.case_id);
 assert.equal(rows[1].status,'quarantined');assert.ok(Object.isFrozen(rows));
});
test('identity list rejects scope drift duplicate identifiers and unsupported states',()=>{
 for(const bad of [{...data,patient_id:'PAT-OTHER'},{...data,case_id:'CASE-OTHER'},
  {...data,identities:[row,row]},{...data,identities:[{...row,status:'approved'}]},
  {...data,identities:[{...row,primary_identity:false}]},{...data,identities:[{...row,source_system:'\n'}]}])
  assert.throws(()=>readSourceIdentities(bad,data.patient_id,data.case_id));
});
