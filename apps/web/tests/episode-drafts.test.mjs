import test from 'node:test';
import assert from 'node:assert/strict';
import {compareDraftOrigin,draftCommand,readDrafts,readDraftReceipt} from '../.test-dist/episode-drafts.js';

const source={source_id:'SRC-'+'1'.repeat(32),document_id:'DOC-A',version:1,sha256:'1'.repeat(64),
  state:'current',event_date:'2026-02-01',issued_at:'2026-02-02',supersedes_id:null};
const origin={source_id:source.source_id,source_line:8,source_sha256:source.sha256,document_version:1,
  document_id:'DOC-A',finding_key:'breast',
  oncology:{role:'primary',episode_id:'EP-A'},reported_state:'reported',source_statement:'Fictional original.'};
const world={patient_id:'PAT-A',case_id:'CASE-A',snapshot_fingerprint:'2'.repeat(64),
  current_sources:[source],history:[],observations:[origin]};
const draft={episode_id:'EPISODE-'+'A'.repeat(32),created_by:'FICT-ACTOR',created_at:'2026-02-10T12:00:00Z',
  source_id:source.source_id,source_line:8,source_version:1,source_sha256:source.sha256,document_id:'DOC-A',
  finding_key:'breast',
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
  assert.equal(readDraftReceipt(receipt,world,201),draft.episode_id);
  assert.throws(()=>readDraftReceipt({...receipt,patient_id:'OTHER'},world,201));
  assert.throws(()=>readDraftReceipt(receipt,world,200));
  assert.equal(readDraftReceipt({...receipt,duplicate:true},world,200),draft.episode_id);
  for(const patch of [{source_line:9},{finding_key:'colon'},{finding_key:'not a key'},{source_label:'EP-B'},{statement:'Different text.'},
      {source_sha256:'b'.repeat(64)},{review_state:'clinician_confirmed'},{basis_state:'reassessment_required'}]){
    assert.throws(()=>readDrafts({...list,drafts:[{...draft,...patch}]},world));
  }
  assert.throws(()=>readDrafts({...list,drafts:[draft,draft]},world));
});

test('amended original stays historical and requires reassessment',()=>{
  const amended={...world,snapshot_fingerprint:'3'.repeat(64),observations:[],current_sources:[latest],
    history:[{...source,state:'superseded'}]};
  const record={...list,snapshot_sha256:amended.snapshot_fingerprint,drafts:[{...draft,
    basis_state:'reassessment_required',source_state:'superseded'}]};
  assert.equal(readDrafts(record,amended)[0].source_version,1);
  assert.throws(()=>readDrafts({...record,drafts:[{...record.drafts[0],basis_state:'current'}]},amended));
  assert.throws(()=>readDrafts(record,world));
});

const latest={...source,source_id:'SRC-'+'2'.repeat(32),version:2,sha256:'3'.repeat(64),supersedes_id:source.source_id};
function amendment(patch={}){
  const finding={...origin,source_id:latest.source_id,document_version:2,source_sha256:latest.sha256,source_line:15,...patch};
  return {...world,snapshot_fingerprint:'4'.repeat(64),current_sources:[latest],history:[{...source,state:'superseded'}],observations:[finding]};
}

test('episode comparison follows the original finding key across moved lines in the same document',()=>{
  const changed=amendment({oncology:{role:'primary',episode_id:'EP-B'},source_statement:'Fictional amended primary.'});
  const unrelated={...changed.observations[0],source_id:'SRC-'+'3'.repeat(32),document_id:'DOC-B',source_statement:origin.source_statement};
  changed.current_sources.push({...latest,source_id:unrelated.source_id,document_id:'DOC-B',version:1,supersedes_id:null});
  changed.observations.unshift(unrelated);
  const comparison=compareDraftOrigin(draft,changed);
  assert.equal(comparison.finding.source_line,15);
  assert.equal(comparison.finding.source_statement,'Fictional amended primary.');
  assert.equal(comparison.finding.oncology.episode_id,'EP-B');
  assert.equal(comparison.source.source_id,latest.source_id);
  assert.equal(comparison.change,'changed');
  assert.equal(draft.source_label,'EP-A');
});

test('a missing key, untyped finding and explicitly unassigned origin stay distinct',()=>{
  assert.equal(compareDraftOrigin(draft,{...amendment(),observations:[]}).change,'removed');
  for(const oncology of [undefined,{role:'primary',episode_id:null},{role:'metastasis',episode_id:'EP-A'}]){
    const result=compareDraftOrigin(draft,amendment({oncology}));
    assert.equal(result.change,'changed');
    assert.deepEqual(result.finding.oncology,oncology);
  }
  const result=compareDraftOrigin(draft,amendment({reported_state:'negative'}));
  assert.equal(result.change,'changed');
  assert.equal(result.finding.reported_state,'negative');
});

test('unchanged origin does not erase reassessment of the broader source snapshot',()=>{
  assert.equal(compareDraftOrigin(draft,world).change,'same_version');
  const amended=amendment();
  const row={...draft,source_state:'superseded',basis_state:'reassessment_required'};
  const [decoded]=readDrafts({...list,snapshot_sha256:amended.snapshot_fingerprint,drafts:[row]},amended);
  assert.equal(compareDraftOrigin(decoded,amended).change,'unchanged');
  assert.equal(decoded.basis_state,'reassessment_required');
  assert.equal(decoded.review_state,'unreviewed_draft');
});

test('comparison refuses broken history, duplicate keys and substituted source metadata',()=>{
  for(const current_sources of [[],[latest,latest],[{...latest,supersedes_id:null}],
      [{...latest,version:3}],[{...latest,document_id:'DOC-B'}]]){
    assert.throws(()=>compareDraftOrigin(draft,{...amendment(),current_sources}));
  }
  assert.throws(()=>compareDraftOrigin({...draft,source_sha256:'f'.repeat(64)},amendment()));
  const changed=amendment();
  assert.throws(()=>compareDraftOrigin(draft,{...changed,observations:[...changed.observations,...changed.observations]}));
  for(const patch of [{source_sha256:'f'.repeat(64)},{document_version:3},{document_id:'DOC-B'}]){
    assert.throws(()=>compareDraftOrigin(draft,amendment(patch)));
  }
});
