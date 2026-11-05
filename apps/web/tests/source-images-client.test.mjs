import {test} from 'node:test';
import assert from 'node:assert/strict';
import {RegistrySession} from '../.test-dist/registry-client.js';
import {deferred,digest} from './authored-evidence-fixtures.mjs';
import {patientId,caseId,sourceId,questionId,reportId,imageId,accessId,original,image,images,
 sourceIndex,response,binary,transportForImages,readyImages,captureDownload} from './source-images-fixtures.mjs';

test('current imaging source explicitly loads its canonical image index without fetching originals or writing',async()=>{
 const requests=[];const s=new RegistrySession(transportForImages((url,init)=>{requests.push({url,init});}));
 await readyImages(s);const before=requests.length;await s.loadSourceImages?.(sourceId);
 assert.equal(s.snapshot().sourceImagesPhase,'ready','the existing source owner needs an image inspection capability');
 assert.deepEqual(s.snapshot().sourceImages,images());
 assert.equal(requests.length,before+1);assert.equal(requests.at(-1).url,`/v1/patients/${patientId}/cases/${caseId}/sources/${sourceId}/images`);
 assert.equal(requests.at(-1).init.method,'GET');assert.equal(requests.at(-1).init.cache,'no-store');
 assert.equal(requests.at(-1).init.credentials,'omit');assert.equal(s.snapshot().sourceImageDownload,null);
});

test('image list rejects wrong identities, digests, duplicate objects and impossible original bounds',async()=>{
 for(const change of [p=>p.patient_id='PAT-OTHER',p=>p.case_id='CASE-BETA',p=>p.source_id='SRC-'+'B'.repeat(32),
  p=>p.images[0].source_id='SRC-'+'B'.repeat(32),p=>p.images[0].case_id='CASE-BETA',
  p=>p.images[0].sha256='not-a-digest',p=>p.images.push({...p.images[0]}),p=>p.images[0].byte_count=2_097_153,
  p=>p.access_receipt_id='not-a-receipt',p=>p.images[0].study_date='2026-01-11']){
  const bad=images();change(bad);const s=new RegistrySession(transportForImages(url=>url.endsWith('/images')?response(bad):undefined));
  await readyImages(s);await s.loadSourceImages?.(sourceId);
  assert.equal(s.snapshot().sourceImagesPhase,'error','an unqualified image index must fail closed');
  assert.equal(s.snapshot().sourceImages,null);assert.equal(s.snapshot().sourceImageDownload,null);
 }
});

test('image controls cannot request non-imaging, superseded or unknown source versions',async()=>{
 for(const kind of ['pathology','superseded','unknown']){
  let requests=0;const source=()=>{const value=sourceIndex();if(kind==='pathology')value.sources[0].kind='pathology';
   if(kind==='superseded'){value.sources[0].state='superseded';value.source_reported_assertions=[];}return value;};
  const s=new RegistrySession(transportForImages(url=>{if(url.includes('/images'))requests++;},source));
  await readyImages(s);await s.loadSourceImages?.(kind==='unknown'?'SRC-'+'B'.repeat(32):sourceId);
  assert.equal(s.snapshot().sourceImagesPhase,'error');assert.equal(s.snapshot().sourceImages,null);assert.equal(requests,0);
 }
});

test('original image download makes a fresh separately authorized binary read and preserves exact bytes',async()=>{
 const calls=[];const fresh='ACCESS-'+'E'.repeat(32);
 const s=new RegistrySession(transportForImages((url,init)=>{if(url.includes('/images'))calls.push({url,init});
  if(url.endsWith('/images/'+imageId))return binary(original,{'X-OI-Access-Receipt':fresh});}));
 await readyImages(s);await s.loadSourceImages?.(sourceId);
 const {blobs,links,revoked}=await captureDownload(()=>s.downloadSourceImage?.(sourceId,imageId));
 assert.equal(blobs.length,1,'only freshly authorized verified original bytes may create a download');
 assert.deepEqual(Buffer.from(await blobs[0].arrayBuffer()),original);assert.equal(blobs[0].type,'application/dicom');
 assert.equal(links.length,1);assert.ok(links[0].name.endsWith('.dcm'));assert.equal(revoked.length,1);
 assert.equal(calls.length,2);assert.equal(calls[1].init.method,'GET');
 assert.equal(calls[1].init.headers.Accept,'application/dicom');assert.equal(calls[1].init.cache,'no-store');
 assert.equal(s.snapshot().sourceImageDownload.access_receipt_id,fresh);
 assert.equal(s.snapshot().sourceImageDownload.sha256,digest(original));assert.equal(s.snapshot().sourceImageDownload.byte_count,original.length);
 assert.equal(s.snapshot().sourceImageDownload.image_id,imageId);assert.equal(s.snapshot().sourceImageDownloadPhase,'ready');
 assert.equal(Object.hasOwn(s.snapshot().sourceImageDownload,'bytes'),false,'do not retain original binary in session state');
});

test('invalid image originals cannot create a Blob or expose a successful read receipt',async()=>{
 const changed=Buffer.from(original);changed[150]^=1;
 const cases=[()=>binary(changed),()=>binary(original,{'Content-Type':'text/html'}),
  ()=>binary(original,{'X-OI-Access-Receipt':'private-untrusted-value'}),
  ()=>binary(original.subarray(0,150)),()=>binary(original,{'Content-Length':'2097153'}),
  ()=>new Response(new Uint8Array(2_097_153),{headers:{'Content-Type':'application/dicom','X-OI-Access-Receipt':accessId}})];
 for(const bad of cases){
  const s=new RegistrySession(transportForImages(url=>url.endsWith('/images/'+imageId)?bad():undefined));
  await readyImages(s);await s.loadSourceImages?.(sourceId);
  const {blobs,links}=await captureDownload(()=>s.downloadSourceImage?.(sourceId,imageId));
  assert.equal(s.snapshot().sourceImageDownloadPhase,'error');assert.equal(s.snapshot().sourceImageDownload,null);
  assert.equal(blobs.length,0);assert.equal(links.length,0);assert.ok(!JSON.stringify(s.snapshot()).includes('private-untrusted-value'));
 }
});

test('image-specific denial clears its disclosure while the same question report and metadata remain independently authorized',async()=>{
 let deny=false;const s=new RegistrySession(transportForImages(url=>deny&&url.endsWith('/images')?response({detail:'PRIVATE IMAGE'},404):undefined));
 await readyImages(s,{evidence:true});const report=s.snapshot().evidenceReport,links=s.snapshot().evidenceLinks;
 assert.equal(report.report_id,reportId);assert.equal(links.question_id,questionId);
 await s.loadSourceImages?.(sourceId);assert.equal(s.snapshot().sourceImagesPhase,'ready');
 deny=true;await s.loadSourceImages(sourceId);
 assert.equal(s.snapshot().sourceImages,null);assert.equal(s.snapshot().sourceImagesPhase,'error');
 assert.equal(s.snapshot().evidenceReport,report);assert.equal(s.snapshot().evidenceLinks,links);
 assert.ok(!JSON.stringify(s.snapshot()).includes('PRIVATE IMAGE'));
});

test('a denied fresh original read cannot reuse previously downloadable bytes or a metadata grant',async()=>{
 let denied=false;const s=new RegistrySession(transportForImages(url=>denied&&url.endsWith('/images/'+imageId)?response({detail:'PRIVATE ORIGINAL'},404):undefined));
 await readyImages(s);await s.loadSourceImages?.(sourceId);
 let captured=await captureDownload(()=>s.downloadSourceImage?.(sourceId,imageId));
 assert.equal(captured.blobs.length,1);denied=true;
 captured=await captureDownload(()=>s.downloadSourceImage(sourceId,imageId));
 assert.equal(captured.blobs.length,0);assert.equal(s.snapshot().sourceImageDownload,null);
 assert.equal(s.snapshot().sourceImageDownloadPhase,'error');assert.ok(!JSON.stringify(s.snapshot()).includes('PRIVATE ORIGINAL'));
});

test('an image original cannot be requested without its exact current inspected image identity',async()=>{
 let originalRequests=0;const s=new RegistrySession(transportForImages(url=>{if(url.endsWith('/images/'+imageId))originalRequests++;}));
 await readyImages(s);await s.downloadSourceImage?.(sourceId,imageId);
 assert.equal(s.snapshot().sourceImageDownloadPhase,'error');assert.equal(originalRequests,0);
 await s.loadSourceImages(sourceId);await s.downloadSourceImage(sourceId,'IMG-'+'F'.repeat(32));
 assert.equal(s.snapshot().sourceImageDownloadPhase,'error');assert.equal(originalRequests,0);
});

for(const transition of ['patient','case','source-refresh','dismiss']){
 test(`late image list after ${transition} change is discarded`,async()=>{
  const waiting=deferred();const s=new RegistrySession(transportForImages(url=>url.endsWith('/images')?waiting.promise:undefined));
  await readyImages(s);const loading=s.loadSourceImages?.(sourceId);
  assert.equal(s.snapshot().sourceImagesPhase,'loading','the new request must actually be in flight');
  if(transition==='patient')await s.read('PAT-EXAMPLE-002');
  if(transition==='case')await s.loadSources('CASE-BETA');
  if(transition==='source-refresh')await s.loadSources(caseId);
  if(transition==='dismiss')s.dismissSourceImages();
  waiting.resolve(response(images()));await loading;
  assert.equal(s.snapshot().sourceImages,null);assert.equal(s.snapshot().sourceImageDownload,null);
 });
}

test('an image index response delivered after the ten-second cancellation cannot restore metadata',async()=>{
 const waiting=deferred();let signal;
 const s=new RegistrySession(transportForImages((url,init)=>{if(url.endsWith('/images')){signal=init.signal;return waiting.promise;}}));
 await readyImages(s);
 const savedTimer=globalThis.setTimeout;let expire,budget;
 globalThis.setTimeout=(callback,milliseconds)=>{expire=callback;budget=milliseconds;return 0;};
 try{
  const loading=s.loadSourceImages(sourceId);assert.equal(budget,10000);
  expire();assert.equal(signal.aborted,true);
  waiting.resolve(response(images()));await loading;
  assert.equal(s.snapshot().sourceImages,null,'a cancelled response cannot republish authorized metadata');
  assert.equal(s.snapshot().sourceImagesPhase,'error','timeout must have a terminal visible state');
  assert.match(s.snapshot().sourceImagesMessage,/timed out/i);
 }finally{globalThis.setTimeout=savedTimer;waiting.resolve(response(images()));}
});

test('cancellation while original-image hashing is pending prevents Blob creation and records timeout',async()=>{
 const entered=deferred(),release=deferred();let signal;
 const s=new RegistrySession(transportForImages((url,init)=>{if(url.endsWith('/images/'+imageId)){signal=init.signal;return binary();}}));
 await readyImages(s);await s.loadSourceImages(sourceId);
 const savedTimer=globalThis.setTimeout,savedDigest=crypto.subtle.digest;let expire,budget;
 globalThis.setTimeout=(callback,milliseconds)=>{expire=callback;budget=milliseconds;return 0;};
 crypto.subtle.digest=async function(...args){const result=await savedDigest.apply(this,args);entered.resolve();await release.promise;return result;};
 try{
  const {blobs,links}=await captureDownload(async()=>{
   const downloading=s.downloadSourceImage(sourceId,imageId);await entered.promise;
   assert.equal(budget,10000);expire();assert.equal(signal.aborted,true);
   release.resolve();await downloading;
  });
  assert.equal(blobs.length,0,'a timed-out digest cannot lead to an original-byte download');
  assert.equal(links.length,0);assert.equal(s.snapshot().sourceImageDownload,null);
  assert.equal(s.snapshot().sourceImageDownloadPhase,'error');
  assert.match(s.snapshot().sourceImageDownloadMessage,/timed out/i);
 }finally{globalThis.setTimeout=savedTimer;crypto.subtle.digest=savedDigest;release.resolve();}
});

for(const transition of ['patient','case','source-refresh','dismiss']){
 test(`late original image after ${transition} change creates no download`,async()=>{
  const waiting=deferred();const s=new RegistrySession(transportForImages(url=>url.endsWith('/images/'+imageId)?waiting.promise:undefined));
  await readyImages(s);await s.loadSourceImages?.(sourceId);
  const {blobs,links}=await captureDownload(async()=>{
   const downloading=s.downloadSourceImage?.(sourceId,imageId);
   assert.equal(s.snapshot().sourceImageDownloadPhase,'loading','fresh original read must actually begin');
   if(transition==='patient')await s.read('PAT-EXAMPLE-002');
   if(transition==='case')await s.loadSources('CASE-BETA');
   if(transition==='source-refresh')await s.loadSources(caseId);
   if(transition==='dismiss')s.dismissSourceImages();
   waiting.resolve(binary());await downloading;
  });
  assert.equal(blobs.length,0);assert.equal(links.length,0);assert.equal(s.snapshot().sourceImageDownload,null);
 });
}

test('ambiguous study, series or instance identities withhold all linked image controls',async()=>{
 for(const conflict of [{study_uid:'2.25.900'}, {sop_uid:image().sop_uid},
                         {series_uid:image().study_uid}, {sop_uid:image().series_uid}]){
  const index=images();
  index.images.push({...image(),image_id:'IMG-'+'E'.repeat(32),sop_uid:'2.25.908',...conflict});
  const session=new RegistrySession(transportForImages(url=>url.endsWith('/images')?response(index):undefined));
  await readyImages(session);await session.loadSourceImages(sourceId);
  assert.equal(session.snapshot().sourceImagesPhase,'error');
  assert.equal(session.snapshot().sourceImages,null);
 }
});
