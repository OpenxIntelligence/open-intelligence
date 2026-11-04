import {visibleLine} from './authored-evidence';
import type {Applicability,EvidenceVersion,Relation} from './authored-evidence';
import type {EvidenceComparisonDraft,EvidenceDraftPatch} from './authored-evidence-session';

export function comparisonIssues(evidence:EvidenceVersion,comparison:EvidenceComparisonDraft,rejectedFields:readonly ('quote'|'rationale')[]){
 const quote=comparison.quote,rationale=comparison.rationale;
 const quoteIssue=rejectedFields.includes('quote')
  ?'Your last passage edit was rejected. The previous accepted passage is still shown; enter a shorter passage or explicitly keep the previous passage.'
  :!quote?'Enter a passage from the selected evidence statement.'
  :Array.from(quote).length>400?'Use no more than 400 Unicode characters.'
  :!evidence.statement?.includes(quote)?'Use text copied exactly from the selected evidence statement.'
  :evidence.statement.indexOf(quote)!==evidence.statement.lastIndexOf(quote)?'Choose a passage that appears only once in the selected evidence statement.'
  :null;
 const rationaleIssue=rejectedFields.includes('rationale')
  ?'Your last rationale edit was rejected. The previous accepted rationale is still shown; enter a shorter rationale or explicitly keep the previous rationale.'
  :Array.from(rationale).length<10?'Write at least 10 visible characters describing your reasoning and uncertainty.'
  :Array.from(rationale).length>600?'Use no more than 600 Unicode characters.'
  :rationale!==rationale.trim()?'Remove leading or trailing whitespace from the rationale.'
  :!visibleLine(rationale)?'Use one visible line without line breaks or hidden control characters.'
  :null;
 const relationIssue=comparison.relation==='supports'&&comparison.applicability==='not_applicable'
  ?'“Supports” cannot be combined with “Not applicable.” Change either the proposed relation or applicability.' : null;
 return {quoteIssue,rationaleIssue,relationIssue};
}

export function EvidenceComparisonEditor({evidence,comparison,rejectedFields,current,locked,onEdit,onAcknowledge,onSave}:{
 evidence:EvidenceVersion;comparison:EvidenceComparisonDraft;rejectedFields:readonly ('quote'|'rationale')[];current:boolean;locked:boolean;
 onEdit:(patch:EvidenceDraftPatch)=>unknown;onAcknowledge:(field:'quote'|'rationale')=>unknown;onSave:()=>unknown;
}){
 const {quoteIssue,rationaleIssue,relationIssue}=comparisonIssues(evidence,comparison,rejectedFields);
 const canAssess=Boolean(current&&evidence.state==='current'&&evidence.statement&&!quoteIssue&&!rationaleIssue&&!relationIssue);
 const readiness=locked?'Saving is unavailable while another evidence action is in progress.'
  :!current?'Saving is unavailable because this question no longer matches the current source context.'
  :quoteIssue??rationaleIssue??relationIssue??(canAssess?'Ready to save this human-authored comparison.':'Complete the comparison before saving.');
 return <>
  <label htmlFor="evidence-quote">Exact unique passage<textarea id="evidence-quote" data-testid="evidence-quote" rows={3} value={comparison.quote} disabled={locked||!current}
   aria-invalid={Boolean(quoteIssue)} aria-describedby={quoteIssue?'evidence-quote-help evidence-quote-error':'evidence-quote-help'} onChange={e=>onEdit({quote:e.target.value})}/></label>
  <p id="evidence-quote-help" className="muted">Choose 1–400 characters appearing once in the stored statement. The original statement line and Unicode character offset are retained.</p>
  {quoteIssue&&<div className="evidence-field-error" id="evidence-quote-error" data-testid="evidence-quote-error" role="alert"><span>{quoteIssue}</span>
   {rejectedFields.includes('quote')&&<button type="button" data-testid="evidence-quote-keep" disabled={locked||!current} onClick={()=>onAcknowledge('quote')}>Keep previous passage</button>}</div>}
  <div className="evidence-form-grid">
   <label htmlFor="evidence-relation">Proposed relation<select id="evidence-relation" data-testid="evidence-relation" value={comparison.relation} disabled={locked||!current}
    aria-invalid={Boolean(relationIssue)} aria-describedby={relationIssue?'evidence-relation-error':undefined} onChange={e=>onEdit({relation:e.target.value as Relation})}><option value="unknown">Unknown</option><option value="supports">Supports</option><option value="contradicts">Contradicts</option><option value="context">Context only</option></select></label>
   <label htmlFor="evidence-applicability">Proposed applicability<select id="evidence-applicability" data-testid="evidence-applicability" value={comparison.applicability} disabled={locked||!current}
    aria-invalid={Boolean(relationIssue)} aria-describedby={relationIssue?'evidence-relation-error':undefined} onChange={e=>onEdit({applicability:e.target.value as Applicability})}><option value="unknown">Unknown</option><option value="limited">Limited</option><option value="applicable">Applicable</option><option value="not_applicable">Not applicable</option></select></label>
  </div>
  {relationIssue&&<p id="evidence-relation-error" className="evidence-field-error" data-testid="evidence-relation-error" role="alert">{relationIssue}</p>}
  <label htmlFor="evidence-rationale">Your rationale and uncertainty<textarea id="evidence-rationale" data-testid="evidence-rationale" rows={3} value={comparison.rationale} disabled={locked||!current}
   aria-invalid={Boolean(rationaleIssue)} aria-describedby={rationaleIssue?'evidence-rationale-help evidence-rationale-error':'evidence-rationale-help'} onChange={e=>onEdit({rationale:e.target.value})}/></label>
  <p id="evidence-rationale-help" className="muted">One visible line, 10–600 characters. Saving a proposal does not establish clinical relevance or approve a decision.</p>
  {rationaleIssue&&<div className="evidence-field-error" id="evidence-rationale-error" data-testid="evidence-rationale-error" role="alert"><span>{rationaleIssue}</span>
   {rejectedFields.includes('rationale')&&<button type="button" data-testid="evidence-rationale-keep" disabled={locked||!current} onClick={()=>onAcknowledge('rationale')}>Keep previous rationale</button>}</div>}
  <button type="button" className="primary" data-testid="evidence-assess" disabled={locked||!canAssess} aria-describedby="evidence-assess-readiness" onClick={()=>onSave()}>Save human-authored comparison</button>
  <p id="evidence-assess-readiness" data-testid="evidence-assess-readiness" className={canAssess?'muted':'evidence-field-error'} role="status" aria-live="polite">{readiness}</p>
 </>;
}
