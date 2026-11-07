import {useLayoutEffect, useRef, useState} from 'react';
import type {RegistrySession, ViewState} from './registry-client';
import './patient-access.css';

type Props = {
  session: RegistrySession;
  state: ViewState;
  busy: boolean;
  patientId: string;
  onPatientIdChange: (id: string) => void;
  onRead: (form: HTMLFormElement) => void;
  onDisconnect: () => void;
};

export function PatientAccess({session, state, busy, patientId, onPatientIdChange, onRead, onDisconnect}: Props) {
  const [credential, setCredential] = useState('');
  const patientInput = useRef<HTMLInputElement>(null);
  const credentialInput = useRef<HTMLInputElement>(null);
  const focusAfterSubmit = useRef(false);

  useLayoutEffect(() => {
    if (!focusAfterSubmit.current) return;
    focusAfterSubmit.current = false;
    (state.connected ? patientInput : credentialInput).current?.focus();
  }, [state.connected]);

  return <section className="patient-access" aria-label="Patient access">
    <div className="access-columns">
      <section aria-labelledby="access-heading">
        <h2 id="access-heading" data-workspace-anchor="Session access">Session access</h2>
        {state.connected ? <>
          <p className="credential-present">Credential present</p>
          <p>The server checks permission each time you open a patient or a record.</p>
          <button type="button" onClick={() => { focusAfterSubmit.current = true; onDisconnect(); }}>Disconnect and clear</button>
        </> : <form onSubmit={event => {
          event.preventDefault();
          session.connect(credential);
          setCredential('');
          if (session.snapshot().connected) focusAfterSubmit.current = true;
          else credentialInput.current?.focus();
        }}>
          <label htmlFor="credential">Synthetic access credential</label>
          <p id="credential-help">Use the credential from your workspace operator. Closing or reloading this tab clears it.</p>
          <input ref={credentialInput} id="credential" name="credential" type="password" autoComplete="off"
            autoCapitalize="none" spellCheck={false} aria-describedby="credential-help"
            value={credential} onChange={event => setCredential(event.target.value)} required minLength={32} maxLength={256}/>
          <button type="submit" className="primary">Connect credential</button>
        </form>}
      </section>
      <section aria-labelledby="patient-heading">
        <h2 id="patient-heading" data-workspace-anchor="Open patient">Patient lookup</h2>
        <form onSubmit={event => { event.preventDefault(); onRead(event.currentTarget); }}>
          <label htmlFor="patient-id">Patient ID</label>
          <p id="patient-id-help">{state.connected ? 'Enter the exact fictional ID supplied for this patient.' : 'Connect your credential to enable patient lookup.'}</p>
          <input ref={patientInput} id="patient-id" value={patientId} onChange={event => onPatientIdChange(event.target.value)}
            aria-describedby="patient-id-help" autoComplete="off" autoCapitalize="none" spellCheck={false}
            disabled={!state.connected || state.phase === 'creating' || state.suspensionPhase === 'sending' || state.suspensionPhase === 'unknown'} required maxLength={128}/>
          <button type="submit" className="primary" disabled={!state.connected || busy}>
            {state.phase === 'reading' ? 'Opening patient…' : 'Open patient'}
          </button>
        </form>
      </section>
    </div>
    <p className={'status' + (state.phase === 'error' ? ' error' : '')} role="status" aria-live="polite" data-testid="status">{state.message}</p>
  </section>;
}
