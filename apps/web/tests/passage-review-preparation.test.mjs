import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {decodePassageReviewPreparation} from '../.test-dist/question-evidence-view.js';

// Independently fictional, hand-specified expected original; no production
// encoder constructs either expected provenance or expected packet digests.
const pid='PAT-EXAMPLE-001', cid='CASE-ALPHA';
const source='SRC-'+'B'.repeat(32), questionId='QUESTION-'+'A'.repeat(32);
const quote='Fictional marker pending — α العربية 🧬.';
const question='Which fictional marker needs independent verification?';
const selection={source_id:source,document_id:'DOC-MANUAL',source_version:1,
 original_sha256:'c'.repeat(64),annotation_revision_id:'ANN-'+'F'.repeat(32),
 annotation_revision:1,review_sha256:'d'.repeat(64),selected_by:'ACTOR-FICTIONAL',
 selected_at:'2026-11-03T10:00:00Z',selected_state:'pending',quote,line:2,page:2,
 classification_origin:'user_selected',clinical_review:'not_performed',
 anchor_sha256:'e'.repeat(64),selection_state:'current_unreviewed_selection'};
const record={citation:'FICT-EVIDENCE-001@1',id:'FICT-EVIDENCE-001',version:'1',
 source_kind:'fictional',title:'Fictional evidence metadata — α 🧬',licence:'original-synthetic',
 link:'https://example.invalid/fictional/source-discussion',metadata_sha256:'d'.repeat(64),
 availability:'metadata_only',rights_status:'granted'};
const link={link_id:'EVIDENCE-LINK-'+'E'.repeat(32),citation:record.citation,
 metadata_sha256:record.metadata_sha256,created_at:'2026-11-03T10:00:00Z',
 actor_label:'ACTOR-FICTIONAL',status:'available',record};
function fresh(){return structuredClone({contract:'oi.pg-passage-review-preparation/1',
 patient_id:pid,case_id:cid,question_id:questionId,source_id:source,question_text:question,
 source_context_state:'current_unreviewed_question',source_access_receipt_id:'ACCESS-'+'F'.repeat(32),
 synthetic:true,model_executed:false,content_appraised:false,clinical_approval:false,
 selection,links:[link],human_review_state:'not_performed',next_step:'independent_verification_required'});}
function ordered(value){
 if(Array.isArray(value))return value.map(ordered);
 if(value!==null&&typeof value==='object')return Object.fromEntries(Object.entries(value)
  .sort(([a],[b])=>a<b?-1:a>b?1:0).map(([k,v])=>[k,ordered(v)]));
 return value;
}
function seal(packet){
 const {packet_sha256:_,source_access_receipt_id:__,...content}=packet;
 const ascii=JSON.stringify(ordered(content)).replace(/[\u007f-\uffff]/g,
  char=>'\\u'+char.charCodeAt(0).toString(16).padStart(4,'0'));
 return {...packet,packet_sha256:createHash('sha256').update(ascii).digest('hex')};
}
function saved(selected=selection){
 const {anchor_sha256,selection_state,...anchor}=selected;
 return {anchor:{...anchor,patient_id:pid,case_id:cid,extraction_method:'pypdf-text-v1',
  extraction_sha256:'b'.repeat(64),selection_key:'finding-one'},anchor_sha256,selection_state,
  source_state:'current',latest_annotation_revision_id:selection_state==='current_unreviewed_selection'
   ?anchor.annotation_revision_id:'ANN-'+'A'.repeat(32)};
}
const decode=(packet,expected=saved())=>Promise.resolve().then(()=>decodePassageReviewPreparation(
 packet,pid,cid,source,questionId,expected.anchor_sha256,question,
 expected.anchor.quote,expected.anchor.line,expected.anchor.annotation_revision,expected));

test('valid Unicode review packet matches an independently calculated Python contract digest',async()=>{
 const packet=seal(fresh());
 // Filled once from Python json.dumps(sort_keys=True,separators=(",",":")),
 // independently of this test's serializer and the production decoder.
 assert.equal(packet.packet_sha256,'e0d1a2d4d07fec972f2141204cf3479da0d390fe158f9287edb3411214585c5c');
 const result=await decode(packet);
 assert.equal(result.selection.quote,quote);
 assert.equal(result.links[0].record.title,'Fictional evidence metadata — α 🧬');
 assert.equal(result.clinical_approval,false);
});

test('a fresh access receipt is excluded from content identity but no other field is',async()=>{
 const packet=seal(fresh());packet.source_access_receipt_id='ACCESS-'+'1'.repeat(32);
 const result=await decode(packet);assert.equal(result.packet_sha256,seal(fresh()).packet_sha256);
});

for(const [name,alter] of [
 ['well-formed wrong digest',p=>{p.packet_sha256='0'.repeat(64)}],
 ['changed title',p=>{p.links[0].record.title='Changed fictional study title'}],
 ['changed citation author',p=>{p.links[0].actor_label='ACTOR-OTHER'}],
 ['removed citation',p=>{p.links=[]}],
 ['unsealed rights redaction',p=>{p.links[0].status='rights_restricted';p.links[0].record=null}],
])test('rejects '+name+' with unchanged content fingerprint',async()=>{
 const packet=seal(fresh());alter(packet);await assert.rejects(decode(packet));
});

for(const [field,value] of Object.entries({document_id:'DOC-OTHER',source_version:2,
 original_sha256:'a'.repeat(64),annotation_revision_id:'ANN-'+'A'.repeat(32),
 review_sha256:'b'.repeat(64),selected_by:'ACTOR-OTHER',selected_at:'2026-11-04T10:00:00Z',
 selected_state:'negative',page:3}))test('rejects rehashed '+field+' substitution against the saved original',async()=>{
 const packet=fresh();packet.selection[field]=value;await assert.rejects(decode(seal(packet)));
});

for(const field of ['selected_state','selection_state'])test('rejects a rehashed array in selection '+field,async()=>{
 const packet=fresh();
 if(field==='selection_state'){
  packet.source_context_state='source_reassessment_required';packet.next_step='source_reassessment_required';
  packet.selection.selection_state='selection_reassessment_required';
 }
 packet.selection[field]=[packet.selection[field]];await assert.rejects(decode(seal(packet)));
});
test('rejects a rehashed array in source freshness',async()=>{
 const packet=fresh();packet.source_context_state=['source_reassessment_required'];
 packet.selection.selection_state='selection_reassessment_required';packet.next_step='source_reassessment_required';
 await assert.rejects(decode(seal(packet)));
});
test('rejects a rehashed array in redacted citation status',async()=>{
 const packet=fresh();packet.links[0].status=['rights_restricted'];packet.links[0].record=null;
 await assert.rejects(decode(seal(packet)));
});
test('known historical passage cannot be promoted by a freshly rehashed packet',async()=>{
 await assert.rejects(decode(seal(fresh()),saved({...selection,selection_state:'selection_reassessment_required'})));
});
test('a newly stale passage and properly rehashed rights redaction remain inspectable as history',async()=>{
 const packet=fresh();packet.source_context_state='source_reassessment_required';
 packet.selection.selection_state='selection_reassessment_required';packet.next_step='source_reassessment_required';
 packet.links[0].status='rights_restricted';packet.links[0].record=null;
 const result=await decode(seal(packet));assert.equal(result.selection.quote,quote);
 assert.equal(result.links[0].record,null);assert.equal(result.next_step,'source_reassessment_required');
});
test('the 1200-character quote bound counts Unicode characters rather than UTF-16 code units',async()=>{
 const packet=fresh();packet.selection.quote='🧬'.repeat(700);
 const result=await decode(seal(packet),saved({...selection,quote:packet.selection.quote}));
 assert.equal([...result.selection.quote].length,700);
});

test('the accepted packet is a frozen snapshot even if its input mutates while hashing',async()=>{
 const packet=seal(fresh()),original=crypto.subtle.digest;
 let release,started;const hashing=new Promise(resolve=>{started=resolve});
 crypto.subtle.digest=async function(...args){
  const digest=await original.apply(this,args);started();
  return new Promise(resolve=>{release=()=>resolve(digest)});
 };
 try{
  const pending=decode(packet);await hashing;
  packet.selection.page=3;packet.links[0].record.title='Changed while hashing';
  release();const result=await pending;
  assert.equal(result.selection.page,2);assert.equal(result.links[0].record.title,record.title);
  assert.ok(Object.isFrozen(result)&&Object.isFrozen(result.selection)&&Object.isFrozen(result.links));
  assert.ok(Object.isFrozen(result.links[0])&&Object.isFrozen(result.links[0].record));
 }finally{crypto.subtle.digest=original;release?.();}
});
test('failed crypto verification cannot produce a supposedly verified packet',async()=>{
 const original=crypto.subtle.digest;
 crypto.subtle.digest=async()=>{throw Error('Fictional digest service unavailable')};
 try{await assert.rejects(decode(seal(fresh())))}finally{crypto.subtle.digest=original}
});
