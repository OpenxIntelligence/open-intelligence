import {useEffect, useRef, useState} from 'react';
import {requestVeterinary, VeterinaryRequestError} from './veterinary-client';
import type {AnimalSpecies, VeterinaryIntent, VeterinaryResult} from './veterinary-client';

const descriptions: Record<number, string> = {
  401: 'The credential expired or was revoked. Reconnect to continue.',
  403: 'This credential cannot register animals.',
  404: 'This record is unavailable under the current veterinary grant.',
  409: 'Registration conflicts with a previous request. Check the request key and clinic reference.',
  422: 'Check the identifiers and required fields.',
};
type Mode = VeterinaryIntent['kind'];

function RegistryForm({token, onDisconnect}: {token: string; onDisconnect: () => void}) {
  const [mode, setMode] = useState<Mode>('read');
  const [animal, setAnimal] = useState('');
  const [caseId, setCaseId] = useState('');
  const [species, setSpecies] = useState<AnimalSpecies>('dog');
  const [system, setSystem] = useState('');
  const [reference, setReference] = useState('');
  const [key, setKey] = useState<string>(() => crypto.randomUUID());
  const [confirmed, setConfirmed] = useState(false);
  const [result, setResult] = useState<VeterinaryResult | null>(null);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const pending = useRef<AbortController | null>(null);
  useEffect(() => () => { pending.current?.abort(); pending.current = null; }, []);

  function clearResult() { setResult(null); setMessage(''); }
  function select(next: Mode) {
    clearResult(); setMode(next); setConfirmed(false); setCaseId('');
  }
  async function submit() {
    if (pending.current || (mode !== 'read' && !confirmed)) return;
    const intent: VeterinaryIntent = mode === 'read' ? {kind: 'read', animal, caseId: caseId || undefined}
      : mode === 'open' ? {kind: 'open', animal, key}
      : {kind: 'register', species, system, reference, key};
    await run(intent);
  }
  async function run(intent: VeterinaryIntent) {
    if (pending.current) return;
    const control = new AbortController();
    pending.current = control; clearResult(); setBusy(true);
    const timeout = setTimeout(() => control.abort(), 10000);
    try {
      const response = await requestVeterinary(token, intent, control.signal);
      if (pending.current === control) setResult(response);
    } catch (error) {
      if (pending.current !== control) return;
      if (error instanceof VeterinaryRequestError && error.status === 401) { onDisconnect(); return; }
      setMessage(error instanceof VeterinaryRequestError && descriptions[error.status] ||
        (intent.kind === 'read' ? 'The record could not be verified.' : 'The outcome is unknown. Retry with the same inputs and request key.'));
    } finally {
      clearTimeout(timeout);
      if (pending.current === control) { pending.current = null; setBusy(false); }
    }
  }

  return <>
    <div className="actions vet-actions" aria-label="Veterinary registry actions">
      {([['read','Find a record'],['register','Register an animal'],['open','Create a case']] as const).map(([id,title]) =>
        <button type="button" key={id} aria-pressed={mode === id} disabled={busy}
          onClick={() => { if (id !== mode) select(id); }}>{title}</button>)}
    </div>
    <form className="panel" onSubmit={e => {e.preventDefault(); void submit();}} onChange={clearResult}>
      <fieldset disabled={busy}><legend>{mode === 'read' ? 'Find a veterinary record' :
        mode === 'register' ? 'Register a fictional animal' : 'Create a veterinary case'}</legend>
      {mode === 'register' ? <>
        <label htmlFor="vet-species">Species</label><select id="vet-species" value={species}
          onChange={e => setSpecies(e.target.value as AnimalSpecies)}><option value="dog">Dog</option><option value="cat">Cat</option></select>
        <label htmlFor="vet-system">Clinic source system</label><input id="vet-system" value={system} required
          pattern="[a-zA-Z0-9][a-zA-Z0-9_.:\-]{2,127}" onChange={e => setSystem(e.target.value)} autoComplete="off" />
        <label htmlFor="vet-ref">Animal reference in that system</label><input id="vet-ref" value={reference} required
          pattern="[a-zA-Z0-9][a-zA-Z0-9_.:\-]{2,127}" onChange={e => setReference(e.target.value)} autoComplete="off" />
      </> : <>
        <label htmlFor="vet-animal">Animal ID</label><input id="vet-animal" value={animal} required pattern="ANM-[A-F0-9]{32}"
          placeholder="ANM-…" onChange={e => setAnimal(e.target.value)} autoComplete="off" spellCheck={false}/>
        {mode === 'read' && <><label htmlFor="vet-case">Case ID (optional)</label><input id="vet-case" value={caseId}
          pattern="VCASE-[A-F0-9]{32}" placeholder="VCASE-…" onChange={e => setCaseId(e.target.value)} autoComplete="off" spellCheck={false}/></>}
      </>}
      {mode !== 'read' && <>
        <label htmlFor="vet-key">Request key</label><input id="vet-key" value={key} required
          pattern="[a-zA-Z0-9][a-zA-Z0-9_.:\-]{2,127}" onChange={e => setKey(e.target.value)} autoComplete="off"/>
        <p className="muted small">Keep this key to recover the same registration after an interrupted request.</p>
        <label className="check"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)}/>
          This registration is for an independently fictional animal.</label>
      </>}
      <button className="primary" disabled={busy || (mode !== 'read' && !confirmed)}>{busy ? 'Checking…' :
        mode === 'read' ? 'Find record' : mode === 'register' ? 'Register animal' : 'Create case'}</button>
      </fieldset>
    </form>
    <div aria-live="polite" role="status">
      {message && <p className="status error">{message}</p>}
      {result && <section className="panel patient"><h2>{result.kind === 'receipt' ?
        (result.duplicate ? 'Registration recovered' : 'Registration saved') : (result.caseId ? 'Veterinary case' : 'Animal identity')}</h2>
        <dl><div><dt>Animal ID</dt><dd>{result.animal}</dd></div>
          {result.caseId && <div><dt>Case ID</dt><dd>{result.caseId}</dd></div>}
          {result.kind === 'record' && <><div><dt>Species</dt><dd>{result.species}</dd></div>
            <div><dt>Organization</dt><dd>{result.org}</dd></div><div><dt>Registered</dt><dd>{result.created}</dd></div></>}
        </dl>
        {result.kind === 'receipt' && <button onClick={() => {
          select('read'); setAnimal(result.animal); setCaseId(result.caseId ?? '');
          void run({kind: 'read', animal: result.animal, caseId: result.caseId});
        }}>Check current access and open record</button>}
      </section>}
    </div>
  </>;
}

export function VeterinaryWorkspace() {
  const [token, setToken] = useState('');
  const [credential, setCredential] = useState('');
  const [notice, setNotice] = useState('');
  function disconnect() { setToken(''); setCredential(''); setNotice(''); }
  useEffect(() => { window.addEventListener('pagehide', disconnect); return () => window.removeEventListener('pagehide', disconnect); }, []);
  return <main className="vet-workspace"><a href="/">Patient workspace</a><h1>Veterinary registry</h1>
    <p>Register fictional animals and reopen their oncology cases using a clinic’s scoped access.</p>
    {!token ? <form className="panel" onSubmit={e => {e.preventDefault(); setToken(credential); setCredential(''); setNotice('');}}>
      <label htmlFor="vet-token">Synthetic access credential</label><input id="vet-token" type="password"
        autoComplete="off" value={credential} onChange={e => setCredential(e.target.value)}
        required pattern="[A-Za-z0-9._~\-]{32,256}" /><button className="primary">Connect credential</button>
      {notice && <p role="status">{notice}</p>}
    </form> : <><button onClick={disconnect}>Disconnect and clear</button><RegistryForm token={token} onDisconnect={() => {
      disconnect(); setNotice(descriptions[401]);
    }}/></>}
  </main>;
}
