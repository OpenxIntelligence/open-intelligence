import {test} from 'node:test';
import assert from 'node:assert/strict';
import {parseSourceWorldModel} from '../.test-dist/source-world-model.js';
import {decodeComposerPreflight} from '../.test-dist/composer-preflight-view.js';

// Independently authored fictional contract fixtures; no biological dataset.
const patient='PAT-CONTEXT-FICTIONAL', caseId='CASE-CONTEXT';
const sourceId='SRC-'+'A'.repeat(32), secondSourceId='SRC-'+'B'.repeat(32);
const question='Which source supports this fictional finding?';
const clone=value=>structuredClone(value);
function fixture(oncology){
 const source={source_id:sourceId,document_id:'DOC-CONTEXT',version:1,
  sha256:'a'.repeat(64),kind:'pathology',event_date:'2026-01-10',
  issued_at:'2026-01-24',received_at:'2026-02-01T12:00:00Z',
  specimen_id:'SPEC-FICTIONAL-ONE',state:'current',supersedes_id:null};
 const observation={source_id:sourceId,document_id:source.document_id,
  document_version:1,source_sha256:source.sha256,source_kind:source.kind,
  finding_key:'fictional-finding',reported_state:'pending',
  source_statement:'Independently fictional finding; result remains pending.',
  source_line:8,specimen_id:source.specimen_id,event_date:source.event_date,
  issued_at:source.issued_at,review_state:'not_established',clinical_meaning:null,
  ...(oncology===undefined?{}:{oncology})};
 return {contract:'oi.pg-source-world-model/1',patient_id:patient,case_id:caseId,
  access_receipt_id:'ACCESS-'+'A'.repeat(32),synthetic:true,
  authority:'source_report_only_unreviewed',clinical_interpretation:false,
  research_review_invalidation_integrated:false,composer_execution_authorized:false,
  snapshot_fingerprint:'b'.repeat(64),as_of_received_at:source.received_at,
  summary:{current_sources:1,historical_sources:0,current_observations:1,
   current_laboratory_observations:0,unresolved_observations:1,source_disagreements:0},
  current_sources:[source],history:[],observations:[observation],
  laboratory_observations:[],laboratory_timeline:[],
  unresolved_refs:[{source_id:sourceId,source_line:8}],conflicts:[],
  limitations:['Independently fictional source context; no clinical interpretation.']};
}
function decoded(raw=fixture()){
 return parseSourceWorldModel(raw,patient,caseId);
}
function anchor(observation){
 return {source_id:observation.source_id,document_id:observation.document_id,
  version:observation.document_version,sha256:observation.source_sha256,
  line:observation.source_line,finding_key:observation.finding_key,
  reported_state:observation.reported_state,statement:observation.source_statement,
  kind:observation.source_kind,event_date:observation.event_date,
  issued_at:observation.issued_at,specimen_id:observation.specimen_id,
  ...(observation.oncology===undefined?{}:{oncology:clone(observation.oncology)})};
}
function preflight(world,observation=world.observations[0]){
 return {contract:'oi.synthetic-source-composer-preflight/2',
  source_snapshot_contract:'oi.pg-source-world-model/1',
  access_receipt_id:'ACCESS-'+'C'.repeat(32),patient_id:world.patient_id,
  case_id:world.case_id,question,source_snapshot_sha256:world.snapshot_fingerprint,
  selected_source:anchor(observation),source_context_only:true,
  biomedical_evidence_rights_verified:false,model_execution_authorized:false,
  durable_question_created:false,durable_review_connected:false,clinical_approval:false,
  clinical_interpretation:'not_performed',
  reassessment_policy:'revalidate_source_and_authority_before_any_future_write',
  limitations:'Fictional preflight only; no model execution or clinical authorization.',
  preflight_sha256:'c'.repeat(64)};
}
const decode=(value,world,selection)=>decodeComposerPreflight(value,world,selection,question);

for(const [name,oncology] of [
 ['untyped',undefined],['unassigned',{role:'primary',episode_id:null}],
 ['assigned',{role:'metastasis',episode_id:'EP-FICTIONAL'}],
]){
 test(`accepts an exact ${name} finding copied from the decoded snapshot`,()=>{
  const world=decoded(fixture(oncology)),selection=clone(world.observations[0]);
  // A copied selection is valid; reference identity and property order are not contracts.
  const reordered=Object.fromEntries(Object.entries(selection).reverse());
  const value=preflight(world,reordered),before=clone(value);
  const result=decode(value,world,reordered);
  assert.deepEqual(result,before);
  assert.ok(Object.isFrozen(result));
  assert.ok(Object.isFrozen(result.selected_source));
  assert.equal(result.model_execution_authorized,false);
  assert.equal(result.clinical_approval,false);
  assert.deepEqual(value,before,'Decoding must not rewrite the incoming response');
 });
}

const mismatches=[
 ['source outside snapshot',o=>{o.source_id=secondSourceId;}],
 ['another line of the same source',o=>{o.source_line=9;}],
 ['another document',o=>{o.document_id='DOC-OTHER';}],
 ['another version',o=>{o.document_version=2;}],
 ['another digest',o=>{o.source_sha256='d'.repeat(64);}],
 ['another specimen',o=>{o.specimen_id='SPEC-FICTIONAL-TWO';}],
 ['lost specimen identity',o=>{o.specimen_id=null;}],
 ['another event date',o=>{o.event_date='2026-01-11';}],
 ['another report date',o=>{o.issued_at='2026-01-25';}],
 ['another modality',o=>{o.source_kind='imaging';}],
 ['another finding key',o=>{o.finding_key='other-finding';}],
 ['pending changed to negative',o=>{o.reported_state='negative';}],
 ['rewritten statement',o=>{o.source_statement='Different fictional statement.';}],
 ['added episode attribution',o=>{o.oncology={role:'primary',episode_id:'EP-OTHER'};}],
];
for(const [name,mutate] of mismatches){
 test(`rejects ${name} even when response and requested selection agree`,()=>{
  const world=decoded(),selection=clone(world.observations[0]);mutate(selection);
  const value=preflight(world,selection),before=JSON.stringify(world);
  assert.throws(()=>decode(value,world,selection),/contract/);
  assert.equal(JSON.stringify(world),before,'A rejection cannot modify the snapshot');
 });
}
for(const [name,mutate] of [
 ['episode',o=>{o.oncology.episode_id='EP-OTHER';}],
 ['role',o=>{o.oncology.role='metastasis';}],
 ['missing attribution',o=>{delete o.oncology;}],
 ['unassigned episode',o=>{o.oncology.episode_id=null;}],
]){
 test(`rejects changed oncology ${name} at the same source and line`,()=>{
  const world=decoded(fixture({role:'primary',episode_id:'EP-FICTIONAL'}));
  const selection=clone(world.observations[0]);mutate(selection);
  assert.throws(()=>decode(preflight(world,selection),world,selection),/contract/);
 });
}
test('rejects a removed source after amendment even with the new snapshot fingerprint',()=>{
 const oldWorld=decoded(),oldSelection=clone(oldWorld.observations[0]);
 const raw=fixture(),original=clone(raw.current_sources[0]);
 raw.history=[{...original,state:'superseded'}];
 raw.current_sources[0]={...original,source_id:secondSourceId,version:2,
  sha256:'e'.repeat(64),issued_at:'2026-02-03',received_at:'2026-02-04T12:00:00Z',
  supersedes_id:sourceId};
 raw.observations[0]={...raw.observations[0],source_id:secondSourceId,document_version:2,
  source_sha256:'e'.repeat(64),issued_at:'2026-02-03'};
 raw.unresolved_refs=[{source_id:secondSourceId,source_line:8}];
 raw.summary.historical_sources=1;raw.snapshot_fingerprint='f'.repeat(64);
 raw.as_of_received_at='2026-02-04T12:00:00Z';
 const current=decoded(raw);
 assert.throws(()=>decode(preflight(current,oldSelection),current,oldSelection),/contract/);
 assert.deepEqual(decode(preflight(current),current,current.observations[0]).selected_source,
  anchor(current.observations[0]));
 assert.deepEqual(oldWorld.observations[0],oldSelection,'Earlier snapshot remains intact');
});
test('rejects an observation when the decoded current snapshot has none',()=>{
 const raw=fixture(),selection=clone(raw.observations[0]);
 raw.observations=[];raw.unresolved_refs=[];
 raw.summary.current_observations=0;raw.summary.unresolved_observations=0;
 const world=decoded(raw);
 assert.throws(()=>decode(preflight(world,selection),world,selection),/contract/);
});
test('does not choose arbitrarily from an ambiguous selection in an invalid caller snapshot',()=>{
 const checked=decoded(),selection=checked.observations[0];
 const world={...checked,observations:[selection,clone(selection)]};
 assert.throws(()=>decode(preflight(world,selection),world,selection),/contract/);
});
test('preserves the requested-selection check when the response matches another valid finding',()=>{
 const raw=fixture(),other={...raw.observations[0],source_line:9,finding_key:'second'};
 raw.observations.push(other);raw.unresolved_refs.push({source_id:sourceId,source_line:9});
 raw.summary.current_observations=2;raw.summary.unresolved_observations=2;
 const world=decoded(raw);
 assert.throws(()=>decode(preflight(world,world.observations[1]),world,world.observations[0]),/contract/);
});
for(const [name,mutate] of [
 ['patient',p=>{p.patient_id='PAT-OTHER';}],
 ['case',p=>{p.case_id='CASE-OTHER';}],
 ['question',p=>{p.question='Another question';}],
 ['snapshot',p=>{p.source_snapshot_sha256='f'.repeat(64);}],
 ['model authorization',p=>{p.model_execution_authorized=true;}],
 ['clinical approval',p=>{p.clinical_approval=true;}],
 ['unknown field',p=>{p.unrecognized=true;}],
 ['unknown anchor field',p=>{p.selected_source.interpretation='invented';}],
]){
 test(`retains the existing ${name} rejection`,()=>{
  const world=decoded(),value=preflight(world);mutate(value);
  assert.throws(()=>decode(value,world,world.observations[0]));
 });
}
test('accepts a source-reported unknown specimen without inventing one',()=>{
 const raw=fixture();raw.current_sources[0].specimen_id=null;raw.observations[0].specimen_id=null;
 const world=decoded(raw),selection=clone(world.observations[0]);
 assert.equal(decode(preflight(world),world,selection).selected_source.specimen_id,null);
});
test('selects the requested source when two current sources share the same line',()=>{
 const raw=fixture(),other={...raw.current_sources[0],source_id:secondSourceId,
  document_id:'DOC-SECOND',sha256:'d'.repeat(64),specimen_id:'SPEC-FICTIONAL-TWO'};
 raw.current_sources.push(other);
 raw.observations.push({...raw.observations[0],source_id:other.source_id,
  document_id:other.document_id,source_sha256:other.sha256,specimen_id:other.specimen_id});
 raw.unresolved_refs.push({source_id:secondSourceId,source_line:8});
 raw.summary.current_sources=2;raw.summary.current_observations=2;raw.summary.unresolved_observations=2;
 const world=decoded(raw),selection=clone(world.observations[1]);
 assert.deepEqual(decode(preflight(world,selection),world,selection).selected_source,anchor(selection));
});
