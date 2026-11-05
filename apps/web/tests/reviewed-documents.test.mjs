import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {DocumentClient,parsePreview} from '../.test-dist/reviewed-documents.js';
const SID='SRC-'+'A'.repeat(32), ANN='ANN-'+'B'.repeat(32);
const saved={source_id:SID,version:1,annotation_revision_id:ANN,duplicate:false};
const original=Buffer.from('Fictional');
const upload={synthetic:true,filename:'fictional.txt',original_base64:original.toString('base64')};
const preview={filename:upload.filename,sha256:createHash('sha256').update(original).digest('hex'),byte_count:original.length,media_type:'text/plain; charset=utf-8',text:'Fictional',lines:[{line:1,text:'Fictional'}],clinical_review:'not_performed',annotation_method:'manual-exact-line-selection',extraction_method:'utf8-plain-text-v1'};
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

test('PDF line locations restart at one after blank pages and increment within each page',()=>{
 const pdf={...preview,filename:'locations.pdf',media_type:'application/pdf',extraction_sha256:'c'.repeat(64)};
 const lines=[{line:1,text:'Cover',page:1,page_line:1},{line:2,text:'Label',page:3,page_line:1},
  {line:3,text:'Value',page:3,page_line:2}];
 assert.deepEqual(parsePreview({...pdf,lines}).lines,lines);
 for(const [index,change] of [[1,{page_line:7}],[2,{page_line:1}],[2,{page:2,page_line:1}]]){
  const altered=lines.map((line,i)=>i===index?{...line,...change}:line);
  assert.throws(()=>parsePreview({...pdf,lines:altered}),/PDF line location/);
 }
});
test('malformed success remains uncertain and cannot be silently replaced',async()=>{
 const c=new DocumentClient(async()=>({status:201,body:{source_id:'forged'}}));await c.save('',{synthetic:true});
 const pending=c.snapshot().pending;await c.save('',{different:true});assert.equal(c.snapshot().pending,pending);assert.equal(c.snapshot().phase,'uncertain');
});
test('disposing a context prevents a delayed response from restoring data',async()=>{
 let resolve;const c=new DocumentClient(()=>new Promise(r=>resolve=r));const work=c.preview(upload);c.dispose();resolve({status:200,body:preview});await work;assert.equal(c.snapshot().preview,null);
});
test('denied reads clear originals previews and pending intents',async()=>{
 let deny=false;const c=new DocumentClient(async()=>deny?{status:404,body:{detail:'Document unavailable'}}:{status:200,body:preview});
 await c.preview(upload);assert.ok(c.snapshot().preview);deny=true;await c.preview(upload);assert.equal(c.snapshot().preview,null);assert.equal(c.snapshot().pending,null);
});

test('a new preview must identify the exact uploaded bytes, file and intake methods',async()=>{
 const pdfBytes=Buffer.from([0x25,0x50,0x44,0x46,0xff]);
 const pdfUpload={synthetic:true,filename:'fictional.PDF',original_base64:pdfBytes.toString('base64')};
 const pdf={...preview,filename:pdfUpload.filename,byte_count:pdfBytes.length,sha256:createHash('sha256').update(pdfBytes).digest('hex'),media_type:'application/pdf',extraction_method:'pypdf-text-v1',annotation_method:'manual-exact-extraction-line-selection',extraction_sha256:'c'.repeat(64),lines:[{line:1,page:1,page_line:1,text:'Fictional'}]};
 for(const [file,valid] of [[upload,preview],[pdfUpload,pdf]]){
  let reply=valid;
  const client=new DocumentClient(async(path,body)=>{
   assert.equal(path,'/preview');assert.deepEqual(JSON.parse(body),file);
   return {status:200,body:reply};
  });
  for(const change of [{filename:'other.'+file.filename.split('.').at(-1)},{sha256:'f'.repeat(64)},
     {byte_count:valid.byte_count+1},{media_type:valid===pdf?preview.media_type:pdf.media_type},
     {extraction_method:undefined},{annotation_method:'other'}]){
   reply=valid;await client.preview(file);assert.equal(client.snapshot().preview,valid);
   reply={...valid,...change};await client.preview(file);
   assert.equal(client.snapshot().preview,null,JSON.stringify(change));
   assert.equal(client.snapshot().phase,'error');
  }
 }
});

test('a discarded preview stays cleared if its byte check finishes later',async t=>{
 let signalStart,finishHash;
 const started=new Promise(resolve=>{signalStart=resolve;});
 t.mock.method(crypto.subtle,'digest',()=>new Promise(resolve=>{
  finishHash=()=>resolve(Uint8Array.from(Buffer.from(preview.sha256,'hex')).buffer);
  signalStart();
 }));
 const client=new DocumentClient(async()=>({status:200,body:preview}));
 const pending=client.preview(upload);
 await started;
 assert.equal(client.snapshot().preview,null);
 client.discard();
 finishHash();
 await pending;
 assert.equal(client.snapshot().preview,null);
 assert.match(client.snapshot().message,/discarded/i);
});
