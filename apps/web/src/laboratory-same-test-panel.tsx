import {codedResultLabel} from './laboratory-coding-view';
import {sameTestReportGroups} from './laboratory-same-test.js';
import type {SourceWorldModel,WorldLaboratoryObservation} from './source-world-model';

type Props={model:SourceWorldModel;onRecords?:()=>void;busy?:boolean};

function LiteralResult({result}:{result:WorldLaboratoryObservation}){
  if(result.status==='reported_value')return <><strong>{result.value_text}</strong> <code>{result.unit_code}</code> (source UCUM)</>;
  if(result.status==='reported_coded')return <span>{codedResultLabel(result.coded_result)}</span>;
  return <>Result absent · source reason: <strong>{result.absent_reason}</strong></>;
}

/** Read-only secondary organization of the currently authorized World Model.
 * No numeric delta, unit conversion, clinical comparison or new source read.
 */
export function LaboratorySameTestPanel({model,onRecords,busy=false}:Props){
  const view=sameTestReportGroups(model);
  return <details className="laboratory-same-test" data-testid="laboratory-same-test">
    <summary>Same laboratory test code across current originals ({view.group_count})</summary>
    <p className="small">This groups only exact source-local FHIR results sharing the same LOINC test code across separate original reports. It preserves the source timeline order. Matching codes do <strong>not</strong> establish comparable assays, specimens, units, reference ranges or a medical trend. No calculation, diagnosis or clinical review is performed.</p>
    {view.group_count===0?<p>No same-code results from two independent current originals were available for this case. The full source-reported result list remains above.</p>:
      <p role="status" data-testid="laboratory-same-test-summary">{view.group_count} test {view.group_count===1?'code':'codes'} across independently stored current originals; showing {view.groups.length} groups.</p>}
    {view.groups.map(group=><section key={group.loinc_code} aria-label={'Source reports for LOINC '+group.loinc_code}>
      <h5>LOINC {group.loinc_code} · {group.source_count} original reports · {group.result_count} result entries</h5>
      {group.hidden_result_count>0&&<p data-testid="laboratory-same-test-partial">Showing the first {group.rows.length} in the source timeline; {group.hidden_result_count} additional result entries remain in the complete laboratory list above. This is a partial display, not a complete comparison.</p>}
      <ol className="laboratory-same-test-rows">{group.rows.map(item=><li key={item.source_id+':'+item.observation_reference} data-testid="laboratory-same-test-row">
        <p><time dateTime={item.effective_at}>{item.effective_at}</time> · <strong>{item.document_id}</strong> v{item.document_version}</p>
        <p data-testid="laboratory-same-test-value"><LiteralResult result={item}/></p>
        <p>Specimen: {item.specimen_type_text} · {item.specimen_reference}</p>
        <details><summary>Exact original identity</summary><dl>
          <dt>Source ID</dt><dd><code>{item.source_id}</code></dd>
          <dt>Source SHA-256</dt><dd><code>{item.source_sha256}</code></dd>
          <dt>Observation</dt><dd><code>{item.observation_reference}</code></dd>
          <dt>Diagnostic report</dt><dd><code>{item.report_reference}</code></dd>
          <dt>Issued</dt><dd><time dateTime={item.issued_at}>{item.issued_at}</time></dd>
        </dl></details>
      </li>)}</ol>
    </section>)}
    {view.hidden_group_count>0&&<p data-testid="laboratory-same-test-hidden-groups">{view.hidden_group_count} additional same-code groups are not shown here. Use the complete laboratory filters above.</p>}
    {view.excluded_reference_count>0&&<p role="status" data-testid="laboratory-same-test-excluded">{view.excluded_reference_count} result entries use legacy or non-local source references and are excluded from this grouped display. Their original source-reported values remain visible in the complete laboratory list above; inspect them in Records before relying on their context.</p>}
    {onRecords&&<button type="button" data-testid="laboratory-same-test-records" onClick={onRecords} disabled={busy}>Inspect exact report versions in Records</button>}
    <p className="small">Source-reported and unreviewed. No clinical comparability or treatment implication has been established.</p>
  </details>;
}
