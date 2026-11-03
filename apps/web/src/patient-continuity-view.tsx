import type {ViewState} from './registry-client';
import {patientContinuity} from './patient-continuity';

export function PatientContinuity({state,onNavigate}:{state:ViewState;onNavigate:(section:string)=>void}){
 const view=patientContinuity(state);
 if(!view)return null;
 return <section className="panel continuity" aria-labelledby="continuity-heading" data-testid="patient-continuity">
  <span className="step">YOUR RECORDS · YOUR QUESTIONS</span>
  <h2 id="continuity-heading">Continue your care preparation</h2>
  <p>Return to your records and questions without starting again. These are preparation steps, not medical advice or completed clinical review.</p>
  <p className="small">Patient <code>{view.patientId}</code>{view.caseId?<> · Case <code>{view.caseId}</code></>:<> · No case context loaded</>}</p>
  <div className="continuity-grid">
   {view.draft&&<div className="continuity-item" data-testid="continuity-draft" data-state={view.draft}>
    <h3>{view.draft==='saved'?'Your question was saved':view.draft==='saving'?'Your question is being saved':view.draft==='needs_attention'?'Check your question save':'Continue your question'}</h3>
    <p>{view.draft==='saved'?'The server confirmed this question. Saving is not clinical review.':view.draft==='saving'?'Wait for confirmation before assuming the question is saved.':view.draft==='needs_attention'?'Return to the question to inspect the outcome and recovery instructions. Do not assume it was saved.':'Your unfinished question remains in this tab. Reloading or disconnecting clears this draft.'}</p>
    <button type="button" data-testid="continuity-resume" onClick={()=>onNavigate('Investigations')}>{view.draft==='saved'?'Return to your question':'Resume your question'}</button>
   </div>}
   <div className="continuity-item" data-testid="continuity-questions">
    <h3>Questions and changed records</h3>
    {view.questions?<>
     <p><strong data-testid="continuity-reassessment">{view.questions.reassessment}</strong> {view.questions.reassessment===1?'question needs':'questions need'} source reassessment.</p>
     <p><strong data-testid="continuity-current">{view.questions.current}</strong> {view.questions.current===1?'question has':'questions have'} current source context, without clinical review.</p>
     {view.questions.reassessment>0&&<p>A supporting record changed. Inspect the question and its sources before using an earlier brief.</p>}
     {view.questions.current+view.questions.reassessment===0&&<p>No saved questions were returned for this case and grant. This does not mean there are no care needs.</p>}
    </>:<p>Question status has not been checked for the current case, or is unavailable. Open Questions to load the authorized history.</p>}
    <button type="button" data-testid="continuity-open-questions" onClick={()=>onNavigate('Investigations')}>Open questions</button>
   </div>
   <div className="continuity-item">
    <h3>Your original records</h3>
    <p>Inspect original documents and their versions, or add another fictional record to an authorized case.</p>
    <button type="button" data-testid="continuity-open-records" onClick={()=>onNavigate('Records')}>Open records</button>
   </div>
  </div>
  <p className="muted small">Only the selected case and last successful reads in this session are represented. Other records or questions may be missing. Each server action checks permission again; nothing is sent to a care team from this panel.</p>
 </section>;
}
