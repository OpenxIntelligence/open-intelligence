import {before,test} from 'node:test';
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {build} from 'vite';
import {parseSourceWorldModel} from '../.test-dist/source-world-model.js';
import {projection} from './laboratory-projection-fixture.mjs';
import {twoReports} from './laboratory-same-test-fixture.mjs';

let LaboratorySameTestPanel;
before(async()=>{
 const outDir='.test-dist/laboratory-same-test-ui';
 await build({configFile:false,logLevel:'silent',build:{ssr:resolve('src/laboratory-same-test-panel.tsx'),
   outDir,emptyOutDir:true,rollupOptions:{output:{entryFileNames:'comparison.mjs'}}}});
 ({LaboratorySameTestPanel}=await import(pathToFileURL(resolve(outDir,'comparison.mjs')).href));
});
const panel=(raw,busy=false)=>renderToStaticMarkup(createElement(LaboratorySameTestPanel,{
  model:parseSourceWorldModel(raw,raw.patient_id,raw.case_id),onRecords(){},busy,
}));

test('grouped same-code reports preserve source literal values and are explicitly not clinical trends',()=>{
 const html=panel(twoReports());
 assert.match(html,/data-testid="laboratory-same-test"/);
 assert.match(html,/same laboratory test code across current originals/i);
 assert.match(html,/LOINC 777-3/);
 assert.match(html,/FICTIONAL-REPORT-A/);
 assert.match(html,/FICTIONAL-REPORT-B/);
 assert.match(html,/4\.20/);
 assert.match(html,/mg\/L/);
 assert.match(html,/not-performed/);
 assert.match(html,/do <strong>not<\/strong> establish comparable assays/);
 assert.match(html,/No calculation, diagnosis or clinical review is performed/);
 assert.equal((html.match(/data-testid="laboratory-same-test-row"/g)||[]).length,4);
});

test('one report produces an explicit non-comparison, not a false empty patient chart',()=>{
 const html=panel(projection());
 assert.match(html,/Same laboratory test code across current originals \(0\)/);
 assert.match(html,/No same-code results from two independent current originals/);
 assert.match(html,/full source-reported result list remains above/);
});

test('same-code inspection exposes each coded answer’s system, version and specimen collection time',()=>{
 const raw=twoReports(true);
 const original=raw.laboratory_observations.find(row=>row.status==='reported_coded');
 const sibling=raw.laboratory_observations.at(-1);
 original.coded_result={...original.coded_result,version:'fixture-A'};
 sibling.coded_result={...sibling.coded_result,version:'fixture-B'};
 const html=panel(raw);
 assert.match(html,/Result code system:/);
 assert.match(html,/urn:oi:synthetic:lab-results/);
 assert.match(html,/fixture-A/);
 assert.match(html,/fixture-B/);
 assert.match(html,/Specimen collected/);
 assert.ok(html.includes(sibling.specimen_collected_at));
});

test('source-provided specimen text stays escaped and an unauthorized navigation affordance stays disabled',()=>{
 const html=panel(twoReports(),true);
 assert.ok(html.includes('Fictional &lt;script&gt;plasma&lt;/script&gt;'));
 assert.ok(!html.includes('<script>'));
 assert.match(html,/data-testid="laboratory-same-test-records"[^>]*disabled=""/);
});

test('legacy source labels remain visible in full results but are not silently treated as FHIR-bound comparisons',()=>{
 const raw=twoReports(),item=raw.laboratory_observations.at(-1);
 item.report_reference='Source-provided legacy report locator';
 const html=panel(raw);
 assert.match(html,/Same laboratory test code across current originals \(0\)/);
 assert.match(html,/1 result entries use legacy or non-local source references/);
 assert.ok(!html.includes('data-testid="laboratory-same-test-row"'));
});

test('grouped reader makes unit, specimen and result-kind differences visible without promising a trend',()=>{
 const html=panel(twoReports());
 assert.match(html,/data-testid="laboratory-same-test-context"/);
 assert.match(html,/reported numeric units differ/i);
 assert.match(html,/source-reported specimen descriptions differ/i);
 assert.match(html,/numbered, coded or absent results differ/i);
 assert.match(html,/not a numeric or clinical trend/i);
});

test('matching source labels still state that clinical comparability is unverified',()=>{
 const raw=twoReports();
 const specimen=raw.laboratory_observations[0].specimen_type_text;
 for(const row of raw.laboratory_observations){
   row.specimen_type_text=specimen;
   row.status='reported_value';row.value_text='1.00';row.unit_code='10*9/L';row.absent_reason=null;
   raw.laboratory_timeline.find(x=>x.source_id===row.source_id&&
     x.observation_reference===row.observation_reference).status='reported_value';
 }
 const html=panel(raw);
 assert.match(html,/No difference detected in these listed source fields/);
 assert.match(html,/clinical comparability remains unverified/i);
});
