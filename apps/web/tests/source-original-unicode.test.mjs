import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {verifyOriginal} from '../.test-dist/source-intake.js';
test('original viewer rejects a surrogate alias encoding to the same replacement bytes',async()=>{
 const raw='OI-SYNTHETIC-REPORT/1\nPatient: CASE-UNICODE\nFinding: context|reported|Fictional text.\n';
 const hash=createHash('sha256').update(raw+'\ufffd').digest('hex');
 const source={source_id:'SRC-'+'A'.repeat(32),document_id:'UNICODE-TEST',version:1,state:'current',sha256:hash};
 const original={...source,case_id:'CASE-UNICODE',original_text:raw+'\ud800',synthetic:true,clinical_review_state:'not_established'};
 await assert.rejects(()=>verifyOriginal(original,'CASE-UNICODE',source));
});
