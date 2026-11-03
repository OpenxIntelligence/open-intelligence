import {test,before} from 'node:test';
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {build} from 'vite';
import {RegistrySession} from '../.test-dist/registry-client.js';
import {ready,transportFor,response,packet,questionId,evidenceId,assessmentId} from './authored-evidence-fixtures.mjs';

let EvidenceComparisonEditor;
before(async()=>{
 await build({configFile:false,logLevel:'silent',build:{ssr:resolve('src/evidence-comparison-editor.tsx'),
  outDir:'.test-dist/evidence-comparison-feedback-ui',emptyOutDir:true,
  rollupOptions:{output:{entryFileNames:'editor.mjs'}}}});
 ({EvidenceComparisonEditor}=await import(pathToFileURL(resolve('.test-dist/evidence-comparison-feedback-ui/editor.mjs')).href));
});

async function prepared(){
 const writes=[];
 const s=new RegistrySession(transportFor((url,init)=>{
  if(init.method==='POST'){
   writes.push({url,body:init.body});
   return response({assessment_id:assessmentId,question_id:questionId,duplicate:false},201);
  }
  return response(packet());
 }));
 await ready(s);await s.loadQuestionEvidence(questionId);
 assert.equal(s.selectEvidenceComparison(questionId,evidenceId),true);
 const evidence=s.snapshot().evidencePacket.evidence.find(row=>row.evidence_id===evidenceId);
 return {s,evidence,writes};
}
function render(s,evidence){
 const comparison=s.snapshot().evidenceComparisonDraft;
 return renderToStaticMarkup(createElement(EvidenceComparisonEditor,{evidence,comparison,current:true,locked:false,
  onEdit:patch=>s.editEvidenceComparison(patch),
  onAcknowledge:field=>s.acknowledgeRejectedEvidenceComparisonField(field),
  onSave:()=>s.saveEvidenceComparison()}));
}

test('empty rationale is explained and associated with its field',async()=>{
 const {s,evidence}=await prepared();const html=render(s,evidence);
 assert.match(html,/id="evidence-rationale"[^>]*aria-invalid="true"/);
 assert.match(html,/aria-describedby="evidence-rationale-help evidence-rationale-error"/);
 assert.match(html,/Write at least 10 visible characters/);
 assert.match(html,/data-testid="evidence-assess"[^>]*disabled/);
 assert.match(html,/data-testid="evidence-assess-readiness"/);
});

test('nonmatching and repeated passages explain the exact correction',async()=>{
 const {s,evidence}=await prepared();
 assert.equal(s.editEvidenceComparison({quote:'not in this evidence'}),true);
 assert.match(render(s,evidence),/Use text copied exactly from the selected evidence statement/);
 const repeated='e';assert.equal(evidence.statement.split(repeated).length>2,true);
 assert.equal(s.editEvidenceComparison({quote:repeated}),true);
 assert.match(render(s,evidence),/appears only once/);
});

test('supports plus not-applicable explains the conflicting selections',async()=>{
 const {s,evidence}=await prepared();
 s.editEvidenceComparison({relation:'supports',applicability:'not_applicable',rationale:'This fictional rationale remains explicitly uncertain.'});
 const html=render(s,evidence);
 assert.match(html,/Supports.*cannot be combined.*Not applicable/);
 assert.match(html,/id="evidence-relation"[^>]*aria-invalid="true"/);
 assert.match(html,/id="evidence-applicability"[^>]*aria-invalid="true"/);
 assert.match(html,/data-testid="evidence-assess"[^>]*disabled/);
});

test('rejected oversized rationale retains previous accepted text and blocks save through refresh',async()=>{
 const {s,evidence,writes}=await prepared();
 s.editEvidenceComparison({quote:'café experiment',relation:'supports',applicability:'limited',
  rationale:'This accepted fictional rationale remains uncertain and unreviewed.'});
 const accepted=s.snapshot().evidenceComparisonDraft.rationale;
 assert.equal(s.editEvidenceComparison({rationale:'x'.repeat(601)}),false);
 let draft=s.snapshot().evidenceComparisonDraft;
 assert.equal(draft.rationale,accepted);assert.deepEqual(draft.rejected_fields,['rationale']);
 await s.loadQuestionEvidence(questionId);
 draft=s.snapshot().evidenceComparisonDraft;
 assert.equal(draft.rationale,accepted);assert.deepEqual(draft.rejected_fields,['rationale']);
 await s.saveEvidenceComparison();assert.equal(writes.length,0,'a rejected edit cannot silently submit the previous text');
 const html=render(s,evidence);
 assert.match(html,/last rationale edit was rejected/);
 assert.match(html,/data-testid="evidence-rationale-keep"/);
 assert.match(html,/data-testid="evidence-assess"[^>]*disabled/);
});

test('explicitly keeping previous rationale re-enables the exact accepted comparison',async()=>{
 const {s,evidence,writes}=await prepared();
 s.editEvidenceComparison({quote:'café experiment',relation:'supports',applicability:'limited',
  rationale:'This accepted fictional rationale remains uncertain and unreviewed.'});
 s.editEvidenceComparison({rationale:'x'.repeat(601)});
 assert.equal(s.acknowledgeRejectedEvidenceComparisonField('rationale'),true);
 assert.deepEqual(s.snapshot().evidenceComparisonDraft.rejected_fields,[]);
 const html=render(s,evidence);
 assert.match(html,/Ready to save this human-authored comparison/);
 assert.doesNotMatch(html,/data-testid="evidence-assess"[^>]*disabled/);
 await s.saveEvidenceComparison();assert.equal(writes.length,1);
});

test('a valid correction clears the rejection without requiring acknowledgement',async()=>{
 const {s,evidence}=await prepared();
 s.editEvidenceComparison({rationale:'x'.repeat(601)});
 assert.deepEqual(s.snapshot().evidenceComparisonDraft.rejected_fields,['rationale']);
 assert.equal(s.editEvidenceComparison({rationale:'A corrected fictional rationale with explicit uncertainty.'}),true);
 assert.deepEqual(s.snapshot().evidenceComparisonDraft.rejected_fields,[]);
 assert.doesNotMatch(render(s,evidence),/last rationale edit was rejected/);
});
