import {test} from 'node:test';
import assert from 'node:assert/strict';
import {RegistrySession} from '../.test-dist/registry-client.js';
import {decodeQuestionEvidenceSearch,decodeQuestionEvidenceLinks} from '../.test-dist/question-evidence-view.js';

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

// Independently authored provider-shaped metadata, never a real publication or patient.
const doi='10.5555/oi-synthetic-001',projection='f'.repeat(64);
const crossrefRecord=(overrides={})=>({citation:doi+'@'+projection,id:doi,version:projection,source_kind:'crossref',
 title:'Independently authored public DOI metadata fixture',licence:'Crossref factual bibliographic metadata; article rights not granted',
 link:'https://doi.org/10.5555%2Foi-synthetic-001',metadata_sha256:metadata,availability:'metadata_only',rights_status:'granted',
 bibliography:{doi,journal:'Fictional methods journal',year:2025,publication_type:'journal-article',authors:['Fictional Author'],
  retrieved_at:'2026-11-03T12:34:56+00:00',record_url:'https://api.crossref.org/works/10.5555%2Foi-synthetic-001',
  rights_basis:'https://www.crossref.org/documentation/retrieve-metadata/',
  access_policy:'https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/',
  adapter_version:'oi.crossref-metadata/1',projection_sha256:projection,acquisition_mode:'protocol_fixture'},...overrides});
const doiSearch=(rows=[crossrefRecord()],overrides={})=>search(rows,{query:doi,...overrides});
const doiLinked=(overrides={})=>linked({citation:crossrefRecord().citation,record:crossrefRecord(),...overrides});

test('Crossref metadata retains native DOI identity and immutable bibliography without becoming appraised content',()=>{
 const found=decodeQuestionEvidenceSearch(doiSearch(),pid,cid,qid,doi);
 assert.deepEqual(found.records,[crossrefRecord()]);
 assert.equal(Object.isFrozen(found.records[0].bibliography),true);
 assert.equal(Object.isFrozen(found.records[0].bibliography.authors),true);
 const history=decodeQuestionEvidenceLinks(links([doiLinked()]),pid,cid,qid);
 assert.equal(history.links[0].record.bibliography.retrieved_at,'2026-11-03T12:34:56+00:00');
 assert.equal(found.content_appraised,false);assert.equal(found.clinical_approval,false);
});

test('Crossref decoding rejects identity, source URL, rights provenance, date and prohibited-content drift',()=>{
 const b=crossrefRecord().bibliography;
 const bad=[crossrefRecord({id:'10.5555/other'}),crossrefRecord({version:'publisher-v1'}),
  crossrefRecord({bibliography:{...b,doi:'10.5555/other'}}),crossrefRecord({bibliography:{...b,projection_sha256:'a'.repeat(64)}}),
  crossrefRecord({link:'https://doi.org/10.5555%2Fother'}),crossrefRecord({link:'https://doi.org.evil.test/10.5555%2Foi-synthetic-001'}),
  crossrefRecord({bibliography:{...b,record_url:'https://evil.test/works/'+doi}}),
  crossrefRecord({bibliography:{...b,rights_basis:'https://evil.test/policy'}}),
  crossrefRecord({bibliography:{...b,access_policy:'https://evil.test/access'}}),
  crossrefRecord({bibliography:{...b,adapter_version:'unknown'}}),crossrefRecord({bibliography:{...b,acquisition_mode:'live_assumed'}}),
  crossrefRecord({bibliography:{...b,acquisition_mode:['protocol_fixture']}}),
  crossrefRecord({bibliography:{...b,retrieved_at:'2026-02-30T12:34:56Z'}}),
  crossrefRecord({bibliography:{...b,retrieved_at:'2026-11-03T12:34:56+01:90'}}),
  crossrefRecord({bibliography:{...b,retrieved_at:'2026-11-03'}}),
  ...['0000-01-01T00:00:00Z','0001-01-01T00:00:00+14:00','9999-12-31T23:59:59-14:00']
   .map(retrieved_at=>crossrefRecord({bibliography:{...b,retrieved_at}})),
  crossrefRecord({bibliography:{...b,authors:['hidden\u202Eauthor']}}),
  crossrefRecord({bibliography:{...b,year:true}}),crossrefRecord({bibliography:{...b,year:1499}}),
  crossrefRecord({bibliography:{...b,abstract:'Prohibited provider abstract canary'}}),
  crossrefRecord({abstract:'Prohibited provider abstract canary'}),
  crossrefRecord({source_kind:'fictional'}),crossrefRecord({source_kind:'unreviewed-provider'})];
 for(const row of bad)assert.throws(()=>decodeQuestionEvidenceSearch(doiSearch([row]),pid,cid,qid,doi));
});

test('DOI lookup is explicit, acknowledged and forwards only a normalized public identifier',async()=>{
 const calls=[];const s=session(async(url,init)=>{if(url.endsWith('/evidence-doi')){calls.push([url,init]);return response(doiSearch());}return basic(url);});
 await ready(s);assert.equal(calls.length,0);
 assert.equal(typeof s.lookupQuestionDoi,'function','the explicit DOI action must exist');
 await s.lookupQuestionDoi(qid,doi,false);assert.equal(calls.length,0);
 for(const value of ['',question().question,' https://doi.org/'+doi,'https://doi.org/'+doi,doi+'\n',
  '10.5555/'+ 'x'.repeat(193),'10.5555/'+'('.repeat(192)])
  await s.lookupQuestionDoi(qid,value,true);
 assert.equal(calls.length,0);
 await s.lookupQuestionDoi(qid,doi.toUpperCase(),true);
 assert.equal(calls.length,1);assert.equal(calls[0][0],path+'/evidence-doi');
 assert.deepEqual(JSON.parse(calls[0][1].body),{synthetic:true,public_doi_acknowledged:true,doi});
 assert.equal(calls[0][1].credentials,'omit');assert.equal(calls[0][1].cache,'no-store');assert.equal(calls[0][1].redirect,'error');
 assert.ok(!calls[0][1].body.includes(question().question));assert.ok(!calls[0][1].body.includes(pid));
 assert.equal(s.snapshot().evidenceSearchPhase,'ready');assert.deepEqual(s.snapshot().evidenceSearch.records,[crossrefRecord()]);
 assert.equal(s.snapshot().evidenceLinkReceipt,null,'lookup never saves a citation automatically');
});

test('DOI result must be one matching Crossref item and cannot return another source under the requested DOI',async()=>{
 for(const value of [doiSearch([record()]),doiSearch([crossrefRecord(),crossrefRecord()]),doiSearch([]),
  doiSearch([crossrefRecord({id:'10.5555/other'})]),doiSearch(undefined,{query:'10.5555/other'})]){
  const s=session(async(url)=>url.endsWith('/evidence-doi')?response(value):basic(url));await ready(s);
  assert.equal(typeof s.lookupQuestionDoi,'function');await s.lookupQuestionDoi(qid,doi,true);
  assert.equal(s.snapshot().evidenceSearch,null);assert.equal(s.snapshot().evidenceSearchPhase,'error');
 }
});

test('disabled and unavailable DOI lookup clear earlier metadata, redact details and preserve an authored question draft',async()=>{
 for(const status of [403,404,429,502,503]){
  const s=session(async(url)=>url.endsWith('/evidence-doi')?response({detail:'private provider diagnostic'},status):
   url.endsWith('/evidence-search')?response(search()):basic(url));await ready(s);
  s.chooseQuestionDraft(sid,8);s.changeQuestionDraft('Keep this independently authored question while looking up a public DOI.');
  const draft=s.snapshot().questionDraft;await s.searchQuestionEvidence(qid,'fictional');
  assert.equal(typeof s.lookupQuestionDoi,'function');await s.lookupQuestionDoi(qid,doi,true);
  assert.equal(s.snapshot().evidenceSearch,null);assert.equal(s.snapshot().evidenceLinks,null);
  assert.equal(s.snapshot().evidenceSearchPhase,'error');assert.equal(s.snapshot().questionDraft,draft);
  assert.ok(!JSON.stringify(s.snapshot()).includes('private provider diagnostic'));
 }
});

test('late DOI responses cannot restore a changed patient, case, question or rights-restricted view',async()=>{
 for(const change of [s=>s.read('PAT-EXAMPLE-002'),s=>s.loadWorldModel(otherCase),
  s=>s.loadQuestionSourcePacket(otherQuestion),s=>s.disconnect(),s=>s.loadQuestionEvidenceLinks(qid)]){
  const delayed=deferred();const s=session(async(url)=>url.endsWith('/evidence-doi')?delayed.promise:
   url.endsWith('/evidence-links')?response(links([doiLinked({status:'rights_restricted',record:null})])):basic(url));
  await ready(s);assert.equal(typeof s.lookupQuestionDoi,'function');
  const pending=s.lookupQuestionDoi(qid,doi,true);await change(s);delayed.resolve(response(doiSearch()));await pending;
  assert.equal(s.snapshot().evidenceSearch,null);assert.ok(!JSON.stringify(s.snapshot()).includes(crossrefRecord().title));
 }
});

test('DOI citation saves use the existing exact link intent and uncertain retry without another lookup',async()=>{
 const writes=[];let lookups=0,changed=false;
 const s=session(async(url,init)=>{
  if(url.endsWith('/evidence-doi')){lookups++;return response(doiSearch());}
  if(url.endsWith('/evidence-links')&&init.method==='POST'){
   writes.push(init.body);if(writes.length===1)throw Error('committed response lost');
   return response(receipt(true,{citation:crossrefRecord().citation}));
  }
  if(url.endsWith('/world-model'))return response(world(cid,changed?'e'.repeat(64):snapshot));
  if(url.endsWith('/questions'))return response(questions([question(changed?{source_context_state:'source_reassessment_required'}:{})]));
  return response(links([doiLinked()],changed?{source_context_state:'source_reassessment_required'}:{}));
 });
 await ready(s);assert.equal(typeof s.lookupQuestionDoi,'function');await s.lookupQuestionDoi(qid,doi,true);
 await s.saveQuestionEvidence(qid,crossrefRecord().citation);assert.equal(s.snapshot().evidenceLinkPhase,'unknown');
 const intent=s.snapshot().evidenceLinkIntent;await s.lookupQuestionDoi(qid,doi,true);
 assert.equal(lookups,1);assert.equal(s.snapshot().evidenceLinkIntent,intent);
 changed=true;await s.loadWorldModel(cid);await s.loadSavedQuestions(cid);await s.retryQuestionEvidenceLink();
 assert.equal(writes.length,2);assert.equal(writes[0],writes[1]);assert.equal(s.snapshot().evidenceLinkReceipt.duplicate,true);
 assert.equal(JSON.parse(writes[0]).citation,doi+'@'+projection);
});

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
