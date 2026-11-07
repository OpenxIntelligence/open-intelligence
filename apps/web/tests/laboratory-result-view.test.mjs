import {test} from 'node:test';
import assert from 'node:assert/strict';
import {projection} from './laboratory-projection-fixture.mjs';
let subject;
try {subject=await import('../.test-dist/laboratory-result-view.js');} catch(error) {
  if(error.code!=='ERR_MODULE_NOT_FOUND')throw error;
}
const filters={code:'',context:'',status:''};
const rows=()=>projection().laboratory_observations;
const select=(items,selection=filters,page=0)=>{
  assert.equal(typeof subject?.selectLaboratoryResults,'function','laboratory display projection must be implemented');
  return subject.selectLaboratoryResults(items,selection,page);
};

test('laboratory view preserves literal values, units and input ordering without mutating sources',()=>{
  const input=rows().map(Object.freeze),before=JSON.stringify(input);Object.freeze(input);
  const result=select(input);
  assert.deepEqual(result.indices,[0,1,2]);
  assert.equal(input[result.indices[0]].value_text,'0');
  assert.equal(input[result.indices[1]].value_text,'-0.25');
  assert.equal(input[result.indices[2]].value_text,null);
  assert.equal(JSON.stringify(input),before);
});
test('summary counts describe available records, not clinical normality or completeness',()=>{
  assert.deepEqual(select(rows()).summary,{results:3,reports:1,testCodes:1,reported:2,absent:1});
});
test('test-code filtering is exact, never prefix matching',()=>{
  assert.equal(select(rows(),{...filters,code:'777'}).matching,0);
  assert.equal(select(rows(),{...filters,code:'777-3'}).matching,3);
});
test('one code with different units remains separate source rows and keeps literal strings',()=>{
  const input=rows();input.push({...input[0],source_id:'SRC-'+'B'.repeat(32),value_text:'0.00',unit_code:'mg/L'});
  assert.deepEqual(select(input,{...filters,code:'777-3'}).indices,[0,1,2,3]);
  assert.equal(input[3].value_text,'0.00');assert.equal(input[3].unit_code,'mg/L');
  assert.equal(select(input).summary.reports,2);
});
test('same local specimen reference in two originals is never merged',()=>{
  const input=rows();input.push({...input[0],source_id:'SRC-'+'B'.repeat(32)});
  const context=JSON.stringify([input[3].source_id,input[3].specimen_reference]);
  const result=select(input,{...filters,context});
  assert.deepEqual(result.indices,[3]);
  assert.equal(subject.laboratoryContextKey(input[3]),context);
});
test('absence filtering preserves the actual reason and does not coerce zero to absent',()=>{
  const input=rows();const absent=select(input,{...filters,status:'reported_absent'});
  assert.deepEqual(absent.indices,[2]);assert.equal(input[2].absent_reason,'not-performed');
  assert.deepEqual(select(input,{...filters,status:'reported_value'}).indices,[0,1]);
});
test('all supported absence reasons remain source-reported values',()=>{
  const base=rows()[2];const input=['unknown','not-performed','error','masked'].map(absent_reason=>({...base,absent_reason}));
  assert.deepEqual(select(input,{...filters,status:'reported_absent'}).indices,[0,1,2,3]);
  assert.deepEqual(input.map(x=>x.absent_reason),['unknown','not-performed','error','masked']);
});
test('bounded pages preserve every original position once',()=>{
  const input=Array.from({length:53},(_,i)=>({...rows()[0],observation_reference:'Observation/FICTIONAL-'+i}));
  const pages=[0,1,2].map(p=>select(input,filters,p));
  assert.deepEqual(pages.flatMap(p=>p.indices),input.map((_,i)=>i));
  assert.deepEqual(pages.map(p=>[p.start,p.end,p.page]),[[0,25,0],[25,50,1],[50,53,2]]);
});
test('shrinking results clamp a stale page to real results rather than showing an empty table',()=>{
  const result=select(rows(),filters,9);
  assert.equal(result.page,0);assert.deepEqual(result.indices,[0,1,2]);assert.equal(result.start,0);assert.equal(result.end,3);
});
test('invalid or fractional page values cannot skip or duplicate rows',()=>{
  for(const page of [-1,NaN,Infinity,-Infinity,0.9])assert.deepEqual(select(rows(),filters,page).indices,[0,1,2]);
});
test('empty data and unmatched filters produce an explicit empty page',()=>{
  for(const result of [select([]),select(rows(),{...filters,code:'DOES-NOT-EXIST'},2)]){
    assert.equal(result.matching,0);assert.equal(result.page,0);assert.equal(result.start,0);assert.equal(result.end,0);
    assert.deepEqual(result.indices,[]);
  }
});
test('filters compose without changing available-record counts',()=>{
  const input=rows(),context=JSON.stringify([input[0].source_id,input[0].specimen_reference]);
  const result=select(input,{code:'777-3',context,status:'reported_value'});
  assert.deepEqual(result.indices,[0,1]);assert.equal(result.matching,2);assert.equal(result.summary.results,3);
});
