import {test} from 'node:test';
import assert from 'node:assert/strict';
import {buildImagingChronology} from '../.test-dist/imaging-report-chronology.js';
const report=(source_id, event_date, extra={})=>Object.freeze({
  source_id,document_id:'REPORT-'+source_id,kind:'imaging',version:1,event_date,
  issued_at:event_date+'T12:00:00Z',received_at:event_date+'T13:00:00Z',
  state:'current',sha256:'a'.repeat(64),specimen_id:null,supersedes_id:null,...extra,
});
test('chronology sorts recorded report dates descending and never sorts by source state',()=>{
 const src=Object.freeze([report('OLD','2026-01-03',{state:'superseded'}),report('NEW','2026-02-20'),report('EARLIER','2025-12-30')]);
 const groups=buildImagingChronology(src);
 assert.deepEqual(groups.map(g=>g.date),['2026-02-20','2026-01-03','2025-12-30']);
 assert.equal(groups[1].reports[0],src[0]);
});
test('two versions on one date stay separate and keep source order',()=>{
 const src=Object.freeze([report('A','2026-02-20'),report('B','2026-02-20',{document_id:'REPORT-A',version:2,state:'superseded',supersedes_id:'A'})]);
 const groups=buildImagingChronology(src);
 assert.equal(groups.length,1);assert.deepEqual(groups[0].reports.map(x=>x.source_id),['A','B']);
 assert.equal(groups[0].reports[0],src[0]);assert.equal(groups[0].reports[1],src[1]);
});
test('different kinds with same document are excluded, never relabeled',()=>{
 const src=[report('IM','2026-02-20'),report('PAT','2026-01-05',{kind:'pathology',document_id:'REPORT-IM'})];
 assert.deepEqual(buildImagingChronology(src).flatMap(g=>g.reports.map(r=>r.source_id)),['IM']);
 assert.equal(src[1].kind,'pathology');
});
test('no permitted imaging source returns no dates; result and inputs remain immutable',()=>{
 assert.deepEqual(buildImagingChronology([]),[]);
 const src=Object.freeze([report('A','2026-01-01')]);
 const groups=buildImagingChronology(src);
 assert.ok(Object.isFrozen(groups));assert.ok(Object.isFrozen(groups[0]));assert.ok(Object.isFrozen(groups[0].reports));
 assert.equal(groups[0].reports[0],src[0]);
});
