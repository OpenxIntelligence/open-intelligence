import {test} from 'node:test';
import assert from 'node:assert/strict';
import {DocumentClient,parsePreview} from '../.test-dist/reviewed-documents.js';
const SID='SRC-'+'A'.repeat(32), ANN='ANN-'+'B'.repeat(32);
const saved={source_id:SID,version:1,annotation_revision_id:ANN,duplicate:false};
const preview={filename:'fictional.txt',sha256:'a'.repeat(64),byte_count:12,media_type:'text/plain; charset=utf-8',text:'Fictional',lines:[{line:1,text:'Fictional'}],clinical_review:'not_performed',annotation_method:'manual-exact-line-selection',extraction_method:'utf8-plain-text-v1'};
test('preview validates numbered lines and does not imply clinical review',()=>{
 assert.equal(parsePreview(preview).text,'Fictional');
 for(const delta of [{clinical_review:'approved'},{lines:[{line:2,text:'Fictional'}]},{filename:'../file.txt'},{sha256:'bad'}])assert.throws(()=>parsePreview({...preview,...delta}));
});
test('unknown writes retain exact payload for explicit retry only',async()=>{
 const calls=[];let fails=true;const c=new DocumentClient(async(path,body)=>{calls.push([path,body]);if(fails)throw Error('lost');return{status:201,body:saved}});
 const payload={synthetic:true,findings:[{quote:'Literal'}]};await c.save('',payload);payload.findings[0].quote='changed';
 assert.equal(c.snapshot().phase,'uncertain');assert.equal(calls.length,1);fails=false;await c.retry();
 assert.equal(calls[0][1],calls[1][1]);assert.equal(c.snapshot().receipt.annotation_revision_id,ANN);assert.equal(c.snapshot().pending,null);
});
test('malformed success remains uncertain and cannot be silently replaced',async()=>{
 const c=new DocumentClient(async()=>({status:201,body:{source_id:'forged'}}));await c.save('',{synthetic:true});
 const pending=c.snapshot().pending;await c.save('',{different:true});assert.equal(c.snapshot().pending,pending);assert.equal(c.snapshot().phase,'uncertain');
});
test('disposing a context prevents a delayed response from restoring data',async()=>{
 let resolve;const c=new DocumentClient(()=>new Promise(r=>resolve=r));const work=c.preview({});c.dispose();resolve({status:200,body:preview});await work;assert.equal(c.snapshot().preview,null);
});
test('denied reads clear originals previews and pending intents',async()=>{
 let deny=false;const c=new DocumentClient(async()=>deny?{status:404,body:{detail:'Document unavailable'}}:{status:200,body:preview});
 await c.preview({});assert.ok(c.snapshot().preview);deny=true;await c.preview({});assert.equal(c.snapshot().preview,null);assert.equal(c.snapshot().pending,null);
});
