import test from 'node:test';
import assert from 'node:assert/strict';
import {draftCommand,readDrafts,readDraftReceipt} from '../.test-dist/episode-drafts.js';

const source={source_id:'SRC-'+'1'.repeat(32),document_id:'DOC-A',version:1,sha256:'1'.repeat(64),
  state:'current',event_date:'2026-02-01',issued_at:'2026-02-02'};
const origin={source_id:source.source_id,source_line:8,source_sha256:source.sha256,document_version:1,
  oncology:{role:'primary',episode_id:'EP-A'},reported_state:'reported',source_statement:'Fictional original.'};
const world={patient_id:'PAT-A',case_id:'CASE-A',snapshot_fingerprint:'2'.repeat(64),
  current_sources:[source],history:[],observations:[origin]};
const draft={episode_id:'EPISODE-'+'A'.repeat(32),created_by:'FICT-ACTOR',created_at:'2026-02-10T12:00:00Z',
  source_id:source.source_id,source_line:8,source_version:1,source_sha256:source.sha256,document_id:'DOC-A',
  event_date:source.event_date,issued_at:source.issued_at,source_label:'EP-A',statement:origin.source_statement,
  source_state:'current',basis_sha256:world.snapshot_fingerprint,basis_state:'current',review_state:'unreviewed_draft'};
const list={patient_id:world.patient_id,case_id:world.case_id,snapshot_sha256:world.snapshot_fingerprint,
  access_receipt_id:'ACCESS-'+'1'.repeat(32),drafts:[draft]};

test('create binds to the explicit current reported primary and exact source snapshot',()=>{
  assert.equal(JSON.parse(draftCommand(world,origin)).source_line,8);
  for(const patch of [{oncology:{role:'primary',episode_id:null}},{oncology:{role:'metastasis',episode_id:'EP-A'}},
      {oncology:undefined},{reported_state:'negative'}]){
    const candidate={...origin,...patch};
    assert.throws(()=>draftCommand({...world,observations:[candidate]},candidate));
  }
  assert.throws(()=>draftCommand(world,{...origin}));
});

test('an independently scoped receipt and exact source basis are required to display a saved draft',()=>{
  assert.equal(readDrafts(list,world)[0].episode_id,draft.episode_id);
  const receipt={patient_id:world.patient_id,case_id:world.case_id,episode_id:draft.episode_id,duplicate:false};
  assert.equal(readDraftReceipt(receipt,world),draft.episode_id);
  assert.throws(()=>readDraftReceipt({...receipt,patient_id:'OTHER'},world));
  for(const patch of [{source_line:9},{source_label:'EP-B'},{statement:'Different text.'},
      {source_sha256:'b'.repeat(64)},{review_state:'clinician_confirmed'},{basis_state:'reassessment_required'}]){
    assert.throws(()=>readDrafts({...list,drafts:[{...draft,...patch}]},world));
  }
  assert.throws(()=>readDrafts({...list,drafts:[draft,draft]},world));
});

test('amended original stays historical and requires reassessment',()=>{
  const amended={...world,snapshot_fingerprint:'3'.repeat(64),observations:[],current_sources:[],
    history:[{...source,state:'superseded'}]};
  const record={...list,snapshot_sha256:amended.snapshot_fingerprint,drafts:[{...draft,
    basis_state:'reassessment_required',source_state:'superseded'}]};
  assert.equal(readDrafts(record,amended)[0].source_version,1);
  assert.throws(()=>readDrafts({...record,drafts:[{...record.drafts[0],basis_state:'current'}]},amended));
  assert.throws(()=>readDrafts(record,world));
});
