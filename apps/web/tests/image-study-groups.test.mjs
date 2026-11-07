import {test} from 'node:test';
import assert from 'node:assert/strict';
import {groupSourceImages} from '../.test-dist/image-study-groups.js';
const image=(id,study,series)=>Object.freeze({image_id:id,study_uid:study,series_uid:series,modality:'CT',study_date:'2026-11-04',source_id:'SRC-TEST',sha256:'a'.repeat(64),byte_count:1000,sop_uid:id});
test('grouping preserves source order, object identity, and all originals exactly once',()=>{
 const images=Object.freeze([image('A','1.2','1.2.1'),image('B','1.2','1.2.2'),image('C','1.2','1.2.1'),image('D','3.4','3.4.1')]);
 const groups=groupSourceImages(images);
 assert.deepEqual(groups.map(s=>[s.study_uid,s.series.map(x=>[x.series_uid,x.images.map(y=>y.image_id)])]),[
  ['1.2',[['1.2.1',['A','C']],['1.2.2',['B']]]],['3.4',[['3.4.1',['D']]]]
 ]);
 assert.equal(groups[0].series[0].images[0],images[0]);
 assert.equal(groups[0].series[0].images[1],images[2]);
 assert.deepEqual(images.map(x=>x.image_id),['A','B','C','D']);
});
test('identical series UIDs under separate study UIDs never cross-contaminate',()=>{
 const groups=groupSourceImages([image('A','1.2','7.7'),image('B','3.4','7.7')]);
 assert.equal(groups.length,2);
 assert.deepEqual(groups.map(x=>x.series[0].images.map(y=>y.image_id)),[['A'],['B']]);
});
test('empty index produces no synthetic study or empty series',()=>{
 assert.deepEqual(groupSourceImages([]),[]);
});
test('groups are immutable presentation snapshots and do not modify source objects',()=>{
 const images=Object.freeze([image('A','1.2','1.2.1')]);
 const groups=groupSourceImages(images);
 assert.ok(Object.isFrozen(groups));assert.ok(Object.isFrozen(groups[0]));
 assert.ok(Object.isFrozen(groups[0].series));assert.ok(Object.isFrozen(groups[0].series[0].images));
 assert.equal(groups[0].series[0].images[0],images[0]);
});
