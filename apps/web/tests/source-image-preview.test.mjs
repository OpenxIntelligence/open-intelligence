import {test} from 'node:test';
import assert from 'node:assert/strict';
import {RegistrySession} from '../.test-dist/registry-client.js';
import {deferred,digest} from './authored-evidence-fixtures.mjs';
import {patientId,caseId,sourceId,imageId,original,previewPng,response,
 images,previewBinary,transportForImages,readyImages} from './source-images-fixtures.mjs';

test('non-diagnostic preview makes a fresh authorized PNG read without turning it into a download',async()=>{
 const calls=[];const fresh='ACCESS-'+'E'.repeat(32);
 const s=new RegistrySession(transportForImages((url,init)=>{
  if(url.includes('/images'))calls.push({url,init});
  if(url.endsWith('/images/'+imageId+'/preview'))return previewBinary(previewPng,{'X-OI-Access-Receipt':fresh});
 }));
 await readyImages(s);await s.loadSourceImages(sourceId);await s.previewSourceImage(sourceId,imageId);
 assert.equal(s.snapshot().sourceImagePreviewPhase,'ready');
 assert.equal(s.snapshot().sourceImagePreview.access_receipt_id,fresh);
 assert.equal(s.snapshot().sourceImagePreview.original_sha256,digest(original));
 assert.deepEqual(Buffer.from(s.snapshot().sourceImagePreview.png_bytes),previewPng);
 assert.equal(s.snapshot().sourceImageDownload,null,'preview is not an original-file download');
 assert.equal(calls.at(-1).url,'/v1/patients/'+patientId+'/cases/'+caseId+'/sources/'+sourceId+'/images/'+imageId+'/preview');
 assert.equal(calls.at(-1).init.headers.Accept,'image/png');assert.equal(calls.at(-1).init.cache,'no-store');
});

test('preview fails closed on wrong source digest, mode, type, receipt, bounds or PNG header',async()=>{
 const badHeader=Buffer.from(previewPng);badHeader[0]=0;
 const hugeWidth=Buffer.from(previewPng);hugeWidth.writeUInt32BE(1025,16);
 const missingPixels=Buffer.concat([previewPng.subarray(0,33),previewPng.subarray(-12)]);
 const cases=[
  ()=>previewBinary(missingPixels),
  ()=>previewBinary(previewPng.subarray(0,-1)),
  ()=>previewBinary(previewPng,{'Content-Length':String(previewPng.length+1)}),
  ()=>previewBinary(previewPng,{'X-OI-Original-SHA256':'0'.repeat(64)}),
  ()=>previewBinary(previewPng,{'X-OI-Preview-Mode':'diagnostic'}),
  ()=>previewBinary(previewPng,{'Content-Type':'text/html'}),
  ()=>previewBinary(previewPng,{'X-OI-Access-Receipt':'private-preview-receipt'}),
  ()=>previewBinary(previewPng,{'Content-Length':'1200001'}),
  ()=>previewBinary(badHeader),
  ()=>previewBinary(hugeWidth),
 ];
 for(const bad of cases){
  const s=new RegistrySession(transportForImages(url=>url.endsWith('/preview')?bad():undefined));
  await readyImages(s);await s.loadSourceImages(sourceId);await s.previewSourceImage(sourceId,imageId);
  assert.equal(s.snapshot().sourceImagePreviewPhase,'error');
  assert.equal(s.snapshot().sourceImagePreview,null);
  assert.ok(!JSON.stringify(s.snapshot()).includes('private-preview-receipt'));
 }
});

test('denied fresh preview cannot reuse an earlier preview',async()=>{
 let denied=false;
 const s=new RegistrySession(transportForImages(url=>denied&&url.endsWith('/preview')?
  response({detail:'PRIVATE PREVIEW'},404):undefined));
 await readyImages(s);await s.loadSourceImages(sourceId);await s.previewSourceImage(sourceId,imageId);
 assert.equal(s.snapshot().sourceImagePreviewPhase,'ready');
 denied=true;await s.previewSourceImage(sourceId,imageId);
 assert.equal(s.snapshot().sourceImagePreview,null);assert.equal(s.snapshot().sourceImagePreviewPhase,'error');
 assert.ok(!JSON.stringify(s.snapshot()).includes('PRIVATE PREVIEW'));
});

test('preview requires the exact currently inspected image and discards a late response after dismissal',async()=>{
 let requests=0;const waiting=deferred();
 const s=new RegistrySession(transportForImages(url=>{
  if(url.endsWith('/preview')){requests++;return waiting.promise;}
 }));
 await readyImages(s);
 await s.previewSourceImage(sourceId,imageId);assert.equal(requests,0);
 await s.loadSourceImages(sourceId);
 await s.previewSourceImage(sourceId,'IMG-'+'F'.repeat(32));assert.equal(requests,0);
 const loading=s.previewSourceImage(sourceId,imageId);
 assert.equal(s.snapshot().sourceImagePreviewPhase,'loading');
 s.dismissSourceImages();waiting.resolve(previewBinary());await loading;
 assert.equal(s.snapshot().sourceImagePreview,null);assert.equal(s.snapshot().sourceImages,null);
});

test('original access denial clears visible CT pixels and rejects a delayed preview under the same grant',async()=>{
 const waiting=deferred();
 let hold=false;
 const s=new RegistrySession(transportForImages(url=>{
  if(url.endsWith('/preview')&&hold)return waiting.promise;
  if(url.endsWith('/images/'+imageId))return response({},404);
 }));
 await readyImages(s);await s.loadSourceImages(sourceId);
 await s.previewSourceImage(sourceId,imageId);
 assert.ok(s.snapshot().sourceImagePreview);
 await s.downloadSourceImage(sourceId,imageId);
 assert.equal(s.snapshot().sourceImagePreview,null);
 hold=true;
 const late=s.previewSourceImage(sourceId,imageId);
 await s.downloadSourceImage(sourceId,imageId);
 waiting.resolve(previewBinary());await late;
 assert.equal(s.snapshot().sourceImagePreview,null);
 assert.equal(s.snapshot().sourceImageDownloadPhase,'error');
});


test('MR original custody does not initiate or accept a CT preview',async()=>{
 const projection=images();projection.images[0].modality='MR';let previewRequests=0;
 const s=new RegistrySession(transportForImages(url=>{
  if(url.endsWith('/images'))return response(projection);
  if(url.endsWith('/preview')){previewRequests++;return previewBinary();}
 }));
 await readyImages(s);await s.loadSourceImages(sourceId);await s.previewSourceImage(sourceId,imageId);
 assert.equal(previewRequests,0);assert.equal(s.snapshot().sourceImagePreview,null);
 assert.match(s.snapshot().sourceImagePreviewMessage,/MR preview is unavailable/);
 const {readSourceImagePreview}=await import('../.test-dist/source-images.js');
 await assert.rejects(()=>readSourceImagePreview(previewBinary(),projection.images[0]),/modality/);
});
