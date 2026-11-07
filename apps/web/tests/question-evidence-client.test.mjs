import {test} from 'node:test';
import assert from 'node:assert/strict';
import {RegistrySession} from '../.test-dist/registry-client.js';
import {decodePassageReviewPreparation} from '../.test-dist/question-evidence-view.js';

// Original fictional metadata and sources. Only the network boundary is replaced.
const token='fictional_evidence_credential_000000000001';
const pid='PAT-EXAMPLE-001',cid='CASE-ALPHA',otherCase='CASE-BETA';
const qid='QUESTION-'+'A'.repeat(32),otherQuestion='QUESTION-'+'D'.repeat(32),sid='SRC-'+'B'.repeat(32);
const contract='oi.pg-source-world-model/1',snapshot='a'.repeat(64),preflight='b'.repeat(64),sha='c'.repeat(64);
const metadata='d'.repeat(64),linkId='EVIDENCE-LINK-'+'E'.repeat(32);
const path='/v1/patients/'+pid+'/cases/'+cid+'/questions/'+qid;
const response=(value,status=200)=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});
const deferred=()=>{let resolve;return{promise:new Promise(r=>resolve=r),resolve:value=>resolve(value)};};
const patient=(id=pid)=>({patient_id:id,origin_org:'FICT-ORG',status:'active',revision:1,created_at:'2026-11-03T10:00:00Z'});
const cases=()=>({patient_id:pid,synthetic:true,source_identity_verified:false,clinical_sources_linked:false,
 mappings:[cid,otherCase].map((id,i)=>({case_id:id,patient_id:pid,source_organization:'FICT-ORG',source_system:'FICT-TEXT',
 source_subject_ref:'FICT-SUBJECT-'+i,review_ref:'FICT-REVIEW-'+i,status:'active',revision:1,
 created_at:'2026-11-03T10:00:00Z',revoked_at:null,source_identity_verified:false,clinical_sources_linked:false,clinical_conclusions:false}))});
const world=(caseId=cid,hash=snapshot)=>({contract,patient_id:pid,case_id:caseId,access_receipt_id:'ACCESS-'+'D'.repeat(32),
 synthetic:true,authority:'source_report_only_unreviewed',clinical_interpretation:false,research_review_invalidation_integrated:false,
 composer_execution_authorized:false,snapshot_fingerprint:hash,as_of_received_at:'2026-11-03T10:00:00Z',
 summary:{current_sources:1,historical_sources:0,current_observations:1,unresolved_observations:1,source_disagreements:0},
 current_sources:[{source_id:sid,document_id:'DOC-FICTIONAL',version:1,sha256:sha,kind:'pathology',event_date:'2026-01-10',issued_at:'2026-01-11',
 received_at:'2026-11-03T10:00:00Z',specimen_id:'SPECIMEN-FICTIONAL',state:'current',supersedes_id:null}],history:[],
 observations:[{source_id:sid,document_id:'DOC-FICTIONAL',document_version:1,source_sha256:sha,source_kind:'pathology',finding_key:'marker',
 reported_state:'not-reported',source_statement:'Independently fictional example.',source_line:8,specimen_id:'SPECIMEN-FICTIONAL',
 event_date:'2026-01-10',issued_at:'2026-01-11',review_state:'not_established',clinical_meaning:null}],
 unresolved_refs:[{source_id:sid,source_line:8}],conflicts:[],limitations:['Independently fictional source context only.']});
const question=(overrides={})=>({question_id:qid,patient_id:pid,case_id:cid,question:'Which fictional source detail needs independent verification?',
 source_id:sid,source_line:8,source_sha256:sha,source_version:1,source_snapshot_sha256:snapshot,source_snapshot_contract:contract,
 preflight_sha256:preflight,created_at:'2026-11-03T10:00:00Z',source_context_state:'current_unreviewed_question',
 human_review_state:'not_submitted',clinical_approval:false,model_executed:false,...overrides});
const questions=(rows=[question(),question({question_id:otherQuestion})])=>({contract:'oi.synthetic-source-questions/2',access_receipt_id:'ACCESS-'+'E'.repeat(32),
 patient_id:pid,case_id:cid,questions:rows,synthetic:true,clinical_review_connected:false,clinical_approval:false});
const record=(overrides={})=>({citation:'FICT-EVIDENCE-001@1',id:'FICT-EVIDENCE-001',version:'1',source_kind:'fictional',
 title:'Fictional example of preparing a source discussion',licence:'original-synthetic',
 link:'https://example.invalid/fictional/source-discussion',metadata_sha256:metadata,availability:'metadata_only',rights_status:'granted',...overrides});
const envelope=(overrides={})=>({patient_id:pid,case_id:cid,question_id:qid,source_context_state:'current_unreviewed_question',
 source_access_receipt_id:'ACCESS-'+'F'.repeat(32),synthetic:true,model_executed:false,content_appraised:false,clinical_approval:false,...overrides});
const search=(rows=[record()],overrides={})=>({contract:'oi.pg-question-evidence-search/1',...envelope(),query:'fictional',records:rows,...overrides});
const linked=(overrides={})=>({link_id:linkId,citation:record().citation,metadata_sha256:metadata,created_at:'2026-11-03T10:00:00Z',
 actor_label:'ACTOR-FICTIONAL',status:'available',record:record(),...overrides});
const links=(rows=[linked()],overrides={})=>({contract:'oi.pg-question-evidence-links/1',...envelope(),links:rows,...overrides});
const receipt=(duplicate=false,overrides={})=>({link_id:linkId,citation:record().citation,metadata_sha256:metadata,duplicate,...overrides});
const basic=url=>response(url.endsWith('/world-model')?world(url.includes(otherCase)?otherCase:cid):
 url.endsWith('/questions')?questions():links());
function session(transport){return new RegistrySession(async(url,init)=>{
 if(url.endsWith('/case-bindings'))return response(cases());
 if(url.startsWith('/v1/patients/')&&!url.includes('/cases/'))return response(patient(url.split('/').at(-1)));
 return transport(url,init);
});}
async function ready(s){s.connect(token);await s.read(pid);await s.loadCases();await s.loadWorldModel(cid);await s.loadSavedQuestions(cid);}

test('manual evidence search stays question-scoped and displays only validated fictional metadata',async()=>{
 const calls=[];const s=session(async(url,init)=>{if(url.endsWith('/evidence-search')){calls.push([url,init]);return response(search());}return basic(url);});
 await ready(s);
 assert.equal(typeof s.searchQuestionEvidence,'function','the saved-question evidence action must exist');
 await s.searchQuestionEvidence(qid,'fictional');
 assert.equal(s.snapshot().evidenceQuestionId,qid);assert.equal(s.snapshot().evidenceSearchPhase,'ready');
 assert.deepEqual(s.snapshot().evidenceSearch.records,[record()]);
 assert.equal(Object.isFrozen(s.snapshot().evidenceSearch.records[0]),true);
 assert.equal(calls[0][0],path+'/evidence-search');
 assert.deepEqual(JSON.parse(calls[0][1].body),{synthetic:true,query:'fictional'});
 assert.equal(calls[0][1].headers.Authorization,'Bearer '+token);
 assert.equal(calls[0][1].credentials,'omit');assert.equal(calls[0][1].cache,'no-store');assert.equal(calls[0][1].redirect,'error');
 assert.ok(!calls[0][1].body.includes(question().question),'the manual query never incorporates patient-derived question text');
});

test('saving a citation binds exact catalog metadata and canonical question context then refreshes server links',async()=>{
 const posts=[];let saved=false,reads=0;
 const s=session(async(url,init)=>{if(url.endsWith('/evidence-search'))return response(search());
  if(url.endsWith('/evidence-links')){if(init.method==='POST'){posts.push([url,JSON.parse(init.body)]);saved=true;return response(receipt(),201);}
   reads++;return response(links(saved?[linked()]:[]));}return basic(url);});
 await ready(s);await s.searchQuestionEvidence(qid,'fictional');await s.saveQuestionEvidence(qid,record().citation);
 assert.equal(s.snapshot().evidenceLinkPhase,'saved');assert.deepEqual(s.snapshot().evidenceLinkReceipt,receipt());
 assert.equal(posts.length,1);assert.equal(posts[0][0],path+'/evidence-links');
 const {request_key,...body}=posts[0][1];assert.match(request_key,/^[A-Za-z0-9._:-]{3,128}$/);
 assert.deepEqual(body,{synthetic:true,citation:'FICT-EVIDENCE-001@1',expected_metadata_sha256:metadata,
  source_snapshot_contract:contract,expected_source_snapshot_sha256:snapshot,expected_preflight_sha256:preflight});
 assert.equal(reads,1);assert.equal(s.snapshot().evidenceLinks.links[0].link_id,linkId);
 assert.equal(s.snapshot().evidenceSearch,null,'fresh linked metadata replaces the earlier search cache');
});

test('unloaded questions, invalid queries and citations outside the inspected result cannot write',async()=>{
 let searches=0,writes=0;
 const s=session(async(url,init)=>{if(url.endsWith('/evidence-search')){searches++;return response(search());}
  if(url.endsWith('/evidence-links')&&init.method==='POST')writes++;return basic(url);});
 s.connect(token);await s.read(pid);await s.searchQuestionEvidence(qid,'fictional');assert.equal(searches,0);
 await s.loadCases();await s.loadWorldModel(cid);await s.loadSavedQuestions(cid);
 for(const query of ['', ' fictional', 'fictional ', 'x'.repeat(201), 'hidden\u202Equery','line\nbreak',
  'line\u2028break','paragraph\u2029break'])await s.searchQuestionEvidence(qid,query);
 assert.equal(searches,0);await s.searchQuestionEvidence(qid,'fictional');
 await s.saveQuestionEvidence(otherQuestion,record().citation);await s.saveQuestionEvidence(qid,'FICT-UNKNOWN@1');
 assert.equal(writes,0);
});

test('a stale question permits catalog inspection but never a new citation save',async()=>{
 let writes=0;const s=session(async(url,init)=>{
  if(url.endsWith('/questions'))return response(questions([question({source_context_state:'source_reassessment_required'})]));
  if(url.endsWith('/evidence-search'))return response(search(undefined,{source_context_state:'source_reassessment_required'}));
  if(url.endsWith('/evidence-links')){if(init.method==='POST')writes++;return response(links(undefined,{source_context_state:'source_reassessment_required'}));}
  return basic(url);});
 await ready(s);await s.searchQuestionEvidence(qid,'fictional');assert.equal(s.snapshot().evidenceSearchPhase,'ready');
 await s.saveQuestionEvidence(qid,record().citation);assert.equal(writes,0);
 await s.loadQuestionEvidenceLinks(qid);assert.equal(s.snapshot().evidenceLinksPhase,'ready');
});

test('unsafe URLs, forged flags, duplicate records and mismatched scope fail before displaying metadata',async()=>{
 const bad=[search(undefined,{patient_id:'PAT-OTHER-001'}),search(undefined,{case_id:otherCase}),
  search(undefined,{question_id:otherQuestion}),search(undefined,{query:'a different query'}),
  search(undefined,{model_executed:true}),search(undefined,{content_appraised:true}),search(undefined,{clinical_approval:true}),
  search(undefined,{synthetic:false}),search(undefined,{source_access_receipt_id:'ACCESS-'+'A'.repeat(32)+'\n'}),
  search([record({citation:'FICT-OTHER@1'})]),search([record({metadata_sha256:metadata+'\n'})]),
  search([record({title:'hidden\u202Etitle'})]),search([record({rights_status:'unknown'})]),search([record({abstract:'unpermitted text'})]),
  search([record(),record()]),search(Array.from({length:26},(_,i)=>record({id:'FICT-'+i,citation:'FICT-'+i+'@1'}))),
  ...['javascript:alert(1)','http://example.invalid/fictional/a','https://user:pass@example.invalid/fictional/a',
   'https://example.invalid.evil.test/fictional/a','https://example.invalid/fictional/../private',
   'https://example.invalid/fictional/a\n','https://example.invalid/fictional/a?secret=1'].map(link=>search([record({link})]))];
 for(const value of bad){const s=session(async(url)=>url.endsWith('/evidence-search')?response(value):basic(url));
  await ready(s);await s.searchQuestionEvidence(qid,'fictional');assert.equal(s.snapshot().evidenceSearch,null);
  assert.equal(s.snapshot().evidenceSearchPhase,'error');}
});

test('fresh rights-restricted rows erase search titles and earlier reads cannot restore them',async()=>{
 const delayed=deferred();let searches=0;
 const s=session(async(url)=>url.endsWith('/evidence-search')?(++searches===1?response(search()):delayed.promise):
  url.endsWith('/evidence-links')?response(links([linked({status:'rights_restricted',record:null})])):basic(url));
 await ready(s);await s.searchQuestionEvidence(qid,'fictional');assert.equal(s.snapshot().evidenceSearch.records.length,1);
 const pending=s.searchQuestionEvidence(qid,'fictional');await s.loadQuestionEvidenceLinks(qid);
 delayed.resolve(response(search()));await pending;
 assert.equal(s.snapshot().evidenceSearch,null);assert.equal(s.snapshot().evidenceLinks.links[0].record,null);
 assert.ok(!JSON.stringify(s.snapshot()).includes(record().title));assert.ok(!JSON.stringify(s.snapshot()).includes(record().link));
});

test('redacted link contracts never retain a title or silently accept inconsistent identity',async()=>{
 const bad=[links([linked({status:'rights_restricted'})]),links([linked({status:'available',record:null})]),
  links([linked({record:record({metadata_sha256:'e'.repeat(64)})})]),links([linked({citation:'FICT-OTHER@1'})]),
  links([linked({actor_label:'bad actor\n'})]),links([linked({link_id:linkId+'\n'})]),
  links([linked(),linked()]),links([linked({status:'unknown',record:null})]),links(undefined,{clinical_approval:true})];
 for(const value of bad){const s=session(async(url)=>url.endsWith('/evidence-links')?response(value):basic(url));
  await ready(s);await s.loadQuestionEvidenceLinks(qid);assert.equal(s.snapshot().evidenceLinks,null);
  assert.equal(s.snapshot().evidenceLinksPhase,'error');}
});

test('patient, case, question and credential changes reject late evidence reads',async()=>{
 for(const change of [s=>s.read('PAT-EXAMPLE-002'),s=>s.loadWorldModel(otherCase),
  s=>s.loadQuestionSourcePacket(otherQuestion),s=>s.disconnect()]){
  const delayed=deferred();const s=session(async(url)=>url.endsWith('/evidence-search')?delayed.promise:basic(url));
  await ready(s);const pending=s.searchQuestionEvidence(qid,'fictional');await change(s);
  delayed.resolve(response(search()));await pending;assert.equal(s.snapshot().evidenceSearch,null);assert.equal(s.snapshot().evidenceLinks,null);
 }
});

test('lost save keeps byte-identical recovery after a same-case amendment',async()=>{
 const posts=[];let changed=false;
 const s=session(async(url,init)=>{if(url.endsWith('/evidence-search'))return response(search());
  if(url.endsWith('/evidence-links')&&init.method==='POST'){posts.push([url,init.body]);if(posts.length===1)throw Error('response lost after commit');return response(receipt(true));}
  if(url.endsWith('/world-model'))return response(world(cid,changed?'e'.repeat(64):snapshot));
  if(url.endsWith('/questions'))return response(questions([question(changed?{source_context_state:'source_reassessment_required'}:{})]));
  return response(links(undefined,changed?{source_context_state:'source_reassessment_required'}:{}));});
 await ready(s);await s.searchQuestionEvidence(qid,'fictional');await s.saveQuestionEvidence(qid,record().citation);
 assert.equal(s.snapshot().evidenceLinkPhase,'unknown');const intent=s.snapshot().evidenceLinkIntent;
 changed=true;await s.loadWorldModel(cid);await s.loadSavedQuestions(cid);
 assert.equal(s.snapshot().evidenceLinkIntent,intent);await s.retryQuestionEvidenceLink();
 assert.deepEqual(posts[1],posts[0]);assert.equal(s.snapshot().evidenceLinkReceipt.duplicate,true);
 assert.equal(s.snapshot().evidenceLinks.source_context_state,'source_reassessment_required');
});

test('independent metadata read denial preserves an uncertain write for exact authorized recovery',async()=>{
 for(const status of [403,404]){
  const posts=[];const s=session(async(url,init)=>{
   if(url.endsWith('/evidence-search'))return response(search());
   if(url.endsWith('/evidence-links')){
    if(init.method==='POST'){posts.push(init.body);if(posts.length===1)throw Error('response lost');return response(receipt(true));}
    return response({detail:'restricted private title'},status);
   }
   return basic(url);
  });
  await ready(s);await s.searchQuestionEvidence(qid,'fictional');await s.saveQuestionEvidence(qid,record().citation);
  const intent=s.snapshot().evidenceLinkIntent;await s.loadQuestionEvidenceLinks(qid);
  assert.equal(s.snapshot().evidenceLinkIntent,intent,'read permission cannot discard independent write recovery');
  assert.equal(s.snapshot().evidenceLinkPhase,'unknown');assert.equal(s.snapshot().evidenceLinksPhase,'error');
  assert.equal(s.snapshot().evidenceSearch,null);assert.equal(s.snapshot().evidenceLinks,null);
  assert.ok(!JSON.stringify(s.snapshot()).includes(record().title));assert.ok(!JSON.stringify(s.snapshot()).includes('restricted private title'));
  await s.retryQuestionEvidenceLink();assert.equal(posts[1],posts[0]);
  assert.equal(s.snapshot().evidenceLinkReceipt.duplicate,true);assert.equal(s.snapshot().evidenceLinkPhase,'saved');
 }
});

test('a denied exact retry cannot resolve or discard the earlier unknown commit',async()=>{
 for(const status of [400,403,404,409,413,422]){
  const posts=[];const s=session(async(url,init)=>{
   if(url.endsWith('/evidence-search'))return response(search());
   if(url.endsWith('/evidence-links')&&init.method==='POST'){
    posts.push(init.body);if(posts.length===1)throw Error('response lost after commit');
    return posts.length===2?response({detail:'restricted private title'},status):response(receipt(true));
   }
   return basic(url);
  });
  await ready(s);await s.searchQuestionEvidence(qid,'fictional');await s.saveQuestionEvidence(qid,record().citation);
  const intent=s.snapshot().evidenceLinkIntent;await s.retryQuestionEvidenceLink();
  assert.equal(s.snapshot().evidenceLinkIntent,intent,'current denial cannot establish the original commit outcome');
  assert.equal(s.snapshot().evidenceLinkPhase,'unknown');assert.equal(s.snapshot().evidenceLinkReceipt,null);
  assert.ok(!JSON.stringify(s.snapshot()).includes('restricted private title'));
  await s.saveQuestionEvidence(qid,record().citation);assert.equal(posts.length,2);
  await s.retryQuestionEvidenceLink();assert.equal(posts.length,3);
  assert.equal(posts[1],posts[0]);assert.equal(posts[2],posts[0]);assert.equal(s.snapshot().evidenceLinkPhase,'saved');
 }
});

test('malformed or mismatched success retains exact recovery instead of a successful citation',async()=>{
 const bad=[receipt(false,{citation:'FICT-OTHER@1'}),receipt(false,{metadata_sha256:'e'.repeat(64)}),
  receipt(false,{duplicate:'yes'}),receipt(false,{link_id:linkId+'\n'}),receipt(true)];
 for(const value of bad){const posts=[];const s=session(async(url,init)=>{
  if(url.endsWith('/evidence-search'))return response(search());
  if(url.endsWith('/evidence-links')&&init.method==='POST'){posts.push(init.body);return response(posts.length===1?value:receipt(true),posts.length===1?201:200);}
  return basic(url);});
  await ready(s);await s.searchQuestionEvidence(qid,'fictional');await s.saveQuestionEvidence(qid,record().citation);
  assert.equal(s.snapshot().evidenceLinkPhase,'unknown');assert.equal(s.snapshot().evidenceLinkReceipt,null);
  await s.retryQuestionEvidenceLink();assert.equal(posts[1],posts[0]);assert.equal(s.snapshot().evidenceLinkPhase,'saved');}
});

test('uncertain saves block different intents across question selection until explicit abandonment',async()=>{
 const posts=[];const s=session(async(url,init)=>{if(url.endsWith('/evidence-search'))return response(search());
  if(url.endsWith('/evidence-links')&&init.method==='POST'){posts.push(init.body);throw Error('lost');}return basic(url);});
 await ready(s);await s.searchQuestionEvidence(qid,'fictional');await s.saveQuestionEvidence(qid,record().citation);
 const intent=s.snapshot().evidenceLinkIntent;await s.loadQuestionSourcePacket(otherQuestion);
 assert.equal(s.snapshot().evidenceLinkIntent,intent);await s.saveQuestionEvidence(otherQuestion,record().citation);
 assert.equal(posts.length,1);s.abandonQuestionEvidenceLink();assert.equal(s.snapshot().evidenceLinkIntent,null);
 assert.match(s.snapshot().evidenceLinkMessage,/does not cancel|does not undo/i);
 await s.searchQuestionEvidence(qid,'fictional');await s.saveQuestionEvidence(qid,record().citation);
 assert.equal(posts.length,2);assert.notEqual(JSON.parse(posts[0]).request_key,JSON.parse(posts[1]).request_key);
});

test('late original save cannot unlock a newer retry after source refresh',async()=>{
 const old=deferred(),retry=deferred(),posts=[];
 const s=session(async(url,init)=>{if(url.endsWith('/evidence-search'))return response(search());
  if(url.endsWith('/evidence-links')&&init.method==='POST'){posts.push(init.body);return posts.length===1?old.promise:retry.promise;}return basic(url);});
 await ready(s);await s.searchQuestionEvidence(qid,'fictional');const first=s.saveQuestionEvidence(qid,record().citation);
 await s.loadWorldModel(cid);const second=s.retryQuestionEvidenceLink();old.resolve(response(receipt(),201));await first;
 await s.retryQuestionEvidenceLink();await s.saveQuestionEvidence(qid,record().citation);
 assert.equal(posts.length,2);assert.equal(posts[0],posts[1]);assert.equal(s.snapshot().evidenceLinkPhase,'saving');
 retry.resolve(response(receipt(true)));await second;assert.equal(s.snapshot().evidenceLinkReceipt.duplicate,true);
});

test('read and independent save denials clear metadata without displaying server detail',async()=>{
 for(const status of [403,404,503]){let denied=false;const s=session(async(url)=>url.endsWith('/evidence-search')?
  (denied?response({detail:'restricted private title'},status):response(search())):basic(url));
  await ready(s);await s.searchQuestionEvidence(qid,'fictional');denied=true;await s.searchQuestionEvidence(qid,'fictional');
  assert.equal(s.snapshot().evidenceSearch,null);assert.ok(!JSON.stringify(s.snapshot()).includes('restricted private title'));}
 for(const status of [403,404,409,422]){const s=session(async(url,init)=>url.endsWith('/evidence-search')?response(search()):
  url.endsWith('/evidence-links')&&init.method==='POST'?response({detail:'restricted private title'},status):basic(url));
  await ready(s);await s.searchQuestionEvidence(qid,'fictional');await s.saveQuestionEvidence(qid,record().citation);
  assert.equal(s.snapshot().evidenceLinkPhase,'error');assert.equal(s.snapshot().evidenceLinkIntent,null);
  assert.equal(s.snapshot().evidenceSearch,null);assert.ok(!JSON.stringify(s.snapshot()).includes('restricted private title'));}
});

test('credential revocation and patient or case changes discard delayed saves and recovery',async()=>{
 for(const change of [s=>s.read('PAT-EXAMPLE-002'),s=>s.loadWorldModel(otherCase),s=>s.disconnect()]){
  const delayed=deferred();const s=session(async(url,init)=>url.endsWith('/evidence-search')?response(search()):
   url.endsWith('/evidence-links')&&init.method==='POST'?delayed.promise:basic(url));
  await ready(s);await s.searchQuestionEvidence(qid,'fictional');const pending=s.saveQuestionEvidence(qid,record().citation);
  await change(s);delayed.resolve(response(receipt(),201));await pending;
  assert.equal(s.snapshot().evidenceLinkIntent,null);assert.equal(s.snapshot().evidenceLinkReceipt,null);assert.equal(s.snapshot().evidenceLinks,null);
 }
 const s=session(async(url)=>url.endsWith('/evidence-search')?response({},401):basic(url));
 await ready(s);await s.searchQuestionEvidence(qid,'fictional');assert.equal(s.snapshot().connected,false);
 assert.equal(s.snapshot().evidenceQuestionId,null);
});

test('evidence envelopes enforce content type and streaming size before showing text',async()=>{
 for(const reply of [()=>new Response(JSON.stringify(search()),{headers:{'Content-Type':'text/html'}}),
  ()=>new Response(' '.repeat(1048577),{headers:{'Content-Type':'application/json'}})]){
  const s=session(async(url)=>url.endsWith('/evidence-search')?reply():basic(url));
  await ready(s);await s.searchQuestionEvidence(qid,'fictional');assert.equal(s.snapshot().evidenceSearch,null);
  assert.equal(s.snapshot().evidenceSearchPhase,'error');}
});

test('passage review-preparation packet preserves exact original, refuses stale or promoted science and redacts rights',()=>{
 const anchor='e'.repeat(64),questionText='Which fictional marker needs independent verification?';
 const selection={
  source_id:sid,document_id:'DOC-MANUAL',source_version:1,original_sha256:sha,
  annotation_revision_id:'ANN-'+'F'.repeat(32),annotation_revision:1,review_sha256:metadata,
  selected_by:'ACTOR-FICTIONAL',selected_at:'2026-11-03T10:00:00Z',selected_state:'pending',
  quote:'Marker pending.',line:2,page:2,classification_origin:'user_selected',
  clinical_review:'not_performed',anchor_sha256:anchor,selection_state:'current_unreviewed_selection'
 };
 const packet={...envelope(),contract:'oi.pg-passage-review-preparation/1',
  source_id:sid,question_text:questionText,selection,links:[linked()],
  human_review_state:'not_performed',next_step:'independent_verification_required',
  packet_sha256:'f'.repeat(64)};
 const decode=value=>decodePassageReviewPreparation(value,pid,cid,sid,qid,anchor,questionText,
  selection.quote,selection.line,selection.annotation_revision);
 const current=decode(packet);
 assert.equal(current.selection.quote,'Marker pending.');
 assert.equal(current.links[0].record.availability,'metadata_only');
 assert.equal(current.content_appraised,false);
 assert.equal(current.clinical_approval,false);
 assert.equal(current.human_review_state,'not_performed');
 assert.equal(Object.isFrozen(current.links),true);
 for(const altered of [
  {...packet,question_text:'A different question'},
  {...packet,source_id:'SRC-'+'A'.repeat(32)},
  {...packet,packet_sha256:'invalid'},
  {...packet,clinical_approval:true},
  {...packet,content_appraised:true},
  {...packet,model_executed:true},
  {...packet,human_review_state:'approved'},
  {...packet,next_step:'source_reassessment_required'},
  {...packet,selection:{...selection,quote:'Different unverified quotation.'}},
  {...packet,selection:{...selection,line:3}},
  {...packet,selection:{...selection,annotation_revision:2}},
  {...packet,selection:{...selection,classification_origin:'model_inferred'}},
  {...packet,links:[{...linked(),status:'rights_restricted'}]},
 ])assert.throws(()=>decode(altered),'forged or stale preparation must not render');
 const historical={...packet,source_context_state:'source_reassessment_required',
  selection:{...selection,selection_state:'selection_reassessment_required'},
  next_step:'source_reassessment_required',
  links:[{...linked(),status:'rights_restricted',record:null}]};
 const resumed=decode(historical);
 assert.equal(resumed.selection.quote,selection.quote);
 assert.equal(resumed.links[0].record,null);
 assert.equal(resumed.next_step,'source_reassessment_required');
 assert.throws(()=>decode({...historical,next_step:'independent_verification_required'}));
});
