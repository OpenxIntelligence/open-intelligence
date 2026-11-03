import {StrictMode, useEffect, useRef, useState, useSyncExternalStore} from 'react';
import {createRoot} from 'react-dom/client';
import {RegistrySession} from './registry-client';
import {RecordsPanel} from './records-panel';
import type {ReadingView} from './records-panel';
import './styles.css';

const session = new RegistrySession();
const sections = ['Overview', 'Records', 'Journey', 'Investigations', 'Review'] as const;
type Section = typeof sections[number];
const planned: readonly Section[] = ['Journey', 'Investigations', 'Review'];

function App() {
  const state = useSyncExternalStore(session.subscribe, session.snapshot);
  const [token, setToken] = useState('');
  const [patientId, setPatientId] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [requestKey, setRequestKey] = useState(() => crypto.randomUUID());
  const [readiness, setReadiness] = useState<'checking' | 'ready' | 'unavailable'>('checking');
  const [section, setSection] = useState<Section>('Overview');
  const [view, setView] = useState<ReadingView>('patient');
  const title = useRef<HTMLHeadingElement>(null);
  const moveFocus = useRef(false);
  const keyForReceipt = useRef(requestKey);
  const busy = state.phase === 'creating' || state.phase === 'reading';
  const clinical = view === 'clinical';

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 5000);
    fetch('/health/ready', {signal: controller.signal, credentials: 'omit', redirect: 'error', cache: 'no-store'})
      .then(async response => {
        const value = await response.json();
        if (active) setReadiness(response.ok && value.status === 'ready' ? 'ready' : 'unavailable');
      })
      .catch(() => { if (active) setReadiness('unavailable'); });
    return () => { active = false; controller.abort(); clearTimeout(timer); };
  }, []);
  useEffect(() => { if (state.created) setPatientId(state.created.patient_id); }, [state.created]);
  useEffect(() => { if (!state.connected) { setPatientId(''); setConfirmed(false); } }, [state.connected]);
  useEffect(() => {
    const clear = () => session.disconnect();
    window.addEventListener('pagehide', clear);
    return () => window.removeEventListener('pagehide', clear);
  }, []);
  useEffect(() => {
    if (moveFocus.current) { title.current?.focus(); moveFocus.current = false; }
  }, [section]);

  function navigate(next: Section) {
    if (next === section) { title.current?.focus(); return; }
    moveFocus.current = true;
    setSection(next);
  }
  function disconnect() {
    session.disconnect();
    setToken(''); setPatientId(''); setConfirmed(false);
    navigate('Overview');
  }
  function label(name: Section) {
    if (name === 'Overview') return clinical ? 'Workspace' : 'Home';
    if (name === 'Records') return clinical ? 'Source records' : 'My records';
    return name;
  }
  const heading = section === 'Overview'
    ? clinical ? 'Clinical workspace' : 'Your health, with context.'
    : section === 'Records' ? clinical ? 'Source records' : 'My records' : section;

  const access = <section className="panel session-panel" aria-labelledby="access-heading">
    <p className="eyebrow">SESSION</p>
    <h2 id="access-heading">{state.connected ? 'Session connected' : 'Connect your session'}</h2>
    {!state.connected ? <>
      <p>Use an operator-issued credential for this development workspace. It stays in this tab and is cleared on disconnect or reload.</p>
      <form onSubmit={event => { event.preventDefault(); session.connect(token); setToken(''); }}>
        <label htmlFor="credential">Synthetic access credential</label>
        <input id="credential" name="credential" type="password" autoComplete="off" autoCapitalize="none"
          spellCheck={false} value={token} onChange={event => setToken(event.target.value)} required minLength={32} maxLength={256}/>
        <button type="submit" className="primary">Connect credential</button>
      </form>
    </> : <>
      <p className="session-status">Credential present · grants checked by server</p>
      <p className="small">Access is checked on every request. A connected session does not grant access to every patient.</p>
      <button type="button" onClick={disconnect}>Disconnect and clear</button>
    </>}
  </section>;

  return <div className="app" data-view={view}>
    <a className="skip" href="#main">Skip to workspace</a>
    <aside className="rail" aria-label="Workspace navigation">
      <div className="rail-top">
        <div className="brand"><span className="mark" aria-hidden="true">oi</span><span>Open<br/>Intelligence</span></div>
        <div className="view-choice">
          <label htmlFor="reading-view">Reading view</label>
          <select id="reading-view" value={view} onChange={event => setView(event.target.value as ReadingView)} aria-describedby="reading-view-help">
            <option value="patient">Patient view</option><option value="clinical">Clinical view</option>
          </select>
          <p id="reading-view-help">Changes the layout, not your access.</p>
        </div>
      </div>
      <nav className="primary-nav" aria-label={clinical ? 'Clinical workspace' : 'Patient workspace'}>
        <div className="working-navigation">{sections.filter(name => !planned.includes(name)).map(name =>
          <button type="button" key={name} data-section={name} aria-current={section === name ? 'page' : undefined} onClick={() => navigate(name)}>
            <span>{label(name)}</span><span className="nav-description">{name === 'Overview' ? clinical ? 'Identity & access' : 'Start here' : 'Documents & source history'}</span>
          </button>)}</div>
        <details className="planned-navigation" open={planned.includes(section)}>
          <summary>More workspaces <span>Not connected</span></summary>
          <div>{planned.map(name => <button type="button" key={name} data-section={name} aria-current={section === name ? 'page' : undefined} onClick={() => navigate(name)}>{name}</button>)}</div>
        </details>
      </nav>
      <div className="rail-note"><strong>Every record has a source.</strong><span>Keep the original wording, history and review status in view.</span></div>
    </aside>

    <div className="body">
      <header className="topbar">
        <span>{clinical ? 'Clinical reading view' : 'Patient reading view'} <span className="muted">/ {label(section)}</span></span>
        <span className={'connection ' + readiness} data-testid="readiness">{readiness === 'checking' ? 'Checking API' : readiness === 'ready' ? 'PostgreSQL API ready' : 'API unavailable'}</span>
      </header>
      {state.patient && <div className="context-surface">
        <section className="patient-context" data-testid="patient-context" aria-label="Selected patient">
          <div className="patient-context-identity"><span className="eyebrow">SELECTED PATIENT</span><strong className="patient-key">{state.patient.patient_id}</strong></div>
          <div className="patient-context-meta"><span><span className="muted">Organization</span> <strong>{state.patient.origin_org}</strong></span><span className="badge">Registry: {state.patient.status}</span></div>
          <button className="quiet" type="button" disabled={busy} onClick={() => void session.read(state.patient!.patient_id)}>Recheck access</button>
        </section>
        <nav className="chart-nav" aria-label="Patient chart">
          <span>Patient chart</span>
          <button type="button" data-section="Overview" aria-current={section === 'Overview' ? 'page' : undefined} onClick={() => navigate('Overview')}>Overview</button>
          <button type="button" data-section="Records" aria-current={section === 'Records' ? 'page' : undefined} onClick={() => navigate('Records')}>Records</button>
          {state.sourceIndex && <span className="chart-case">{state.sourceIndex.case_id}</span>}
        </nav>
      </div>}

      <main id="main" tabIndex={-1}>
        <div className="page-heading">
          <div><p className="eyebrow">{section === 'Overview' ? 'OPEN INTELLIGENCE' : state.patient ? 'PATIENT CHART' : 'WORKSPACE'}</p>
            <h1 id="workspace-title" tabIndex={-1} ref={title}>{heading}</h1>
            <p className="lede">{section === 'Overview'
              ? clinical ? 'Open the right patient. Inspect the source, version and context.' : 'Find the records available to you and understand where they came from.'
              : section === 'Records' ? 'Original source history and the statements it reports.' : 'This workflow is not connected to the H1 workspace yet.'}</p>
          </div>
          <span className="development-label">Development · fictional identities only</span>
        </div>
        <p className={'status global-status ' + (state.phase === 'error' ? 'error' : '')} role="status" aria-live="polite" data-testid="status" hidden={state.phase === 'ready' && (section !== 'Overview' || state.sourceIndex !== null)}>{state.message}</p>
        {section !== 'Overview' && !state.connected && access}

        {section === 'Records' ? <RecordsPanel key={state.patient?.patient_id ?? 'no-patient'} state={state} view={view}
          onOverview={() => navigate('Overview')} onLoadCases={() => void session.loadCases()} onLoadSources={caseId => void session.loadSources(caseId)}/>
          : section !== 'Overview' ? <section className="panel empty-state" data-testid="unconnected-workflow">
            <span className="badge">Not connected</span><h2>{section} is not connected</h2>
            <p>The reference application retains this workflow. It has not yet been connected to this patient workspace.</p>
            <p>No patient conclusions or clinical actions are available here.</p>
            <button type="button" onClick={() => navigate('Overview')}>Return to {clinical ? 'workspace' : 'home'}</button>
          </section> : <>
            <div className="overview-layout">
              <div className="overview-primary">
                {state.patient && <section className="panel patient" data-testid="patient-card" aria-labelledby="identity-heading">
                  <div className="section-heading"><div><p className="eyebrow">LATEST SUCCESSFUL REGISTRY RESPONSE</p><h2 id="identity-heading">{clinical ? 'Patient identity' : 'Your record starts here'}</h2></div><span className="badge">{state.patient.status}</span></div>
                  <dl className="identity-details">
                    <div className="identity-id"><dt>Patient ID</dt><dd>{state.patient.patient_id}</dd></div>
                    <div><dt>Organization</dt><dd>{state.patient.origin_org}</dd></div>
                    <div><dt>Registry status</dt><dd>{state.patient.status}</dd></div>
                    <div><dt>Revision</dt><dd>{state.patient.revision}</dd></div>
                    <div><dt>Created</dt><dd><time dateTime={state.patient.created_at}>{state.patient.created_at}</time></dd></div>
                  </dl>
                  <p>{clinical ? 'Identity metadata from the last successful request. Source access is checked separately.' : 'This identifies the record you have opened. Records are checked separately when you open them.'}</p>
                  <div className="actions"><button className="primary" type="button" onClick={() => navigate('Records')}>{clinical ? 'Open source records' : 'View my records'}</button><button type="button" disabled={busy} onClick={() => void session.read(state.patient!.patient_id)}>Recheck current access</button></div>
                </section>}
                <section className="panel patient-open" aria-labelledby="patient-heading">
                  <p className="eyebrow">{state.patient ? 'CHANGE PATIENT' : 'PATIENT RECORD'}</p><h2 id="patient-heading">{clinical ? 'Open an authorized identity' : state.patient ? 'Open another record' : 'Open your record'}</h2>
                  <p>Enter the exact patient ID provided for this workspace. {state.patient ? 'Opening a record clears the current selection while access is checked.' : 'Your session needs permission for that specific identity.'}</p>
                  <form className="patient-open-form" onSubmit={event => { event.preventDefault(); void session.read(patientId); }}>
                    <div><label htmlFor="patient-id">Patient ID</label><input id="patient-id" value={patientId} onChange={event => setPatientId(event.target.value)} autoComplete="off" spellCheck={false} disabled={!state.connected || state.phase === 'creating'} required maxLength={128}/></div>
                    <button type="submit" className="primary" disabled={!state.connected || busy}>{state.phase === 'reading' ? 'Checking access…' : 'Open patient'}</button>
                  </form>
                </section>
              </div>
              <div className="overview-support">
                {access}
                <section className="reading-guide" aria-labelledby="reading-heading"><h2 id="reading-heading">{clinical ? 'Source context, kept together' : 'Know what you are reading'}</h2>
                  <ul><li><strong>Original wording.</strong> Reported statements remain tied to their source.</li><li><strong>Visible history.</strong> Current and earlier document versions stay distinct.</li><li><strong>Clear review status.</strong> Reported information is not a clinical conclusion.</li></ul>
                </section>
              </div>
            </div>
            <details className="panel create-panel"><summary>Create a fictional patient identity</summary>
              <p>This uses the existing registry. No names or clinical details are accepted. Creating an identity does not grant permission to read it.</p>
              <form onSubmit={event => { event.preventDefault(); keyForReceipt.current = requestKey; void session.create(requestKey, confirmed); }}>
                <label htmlFor="request-key">Creation request key</label><input id="request-key" value={requestKey} readOnly/>
                <p className="muted small">Keep the same key when retrying an uncertain response. The server prevents duplicate identities.</p>
                <label className="check"><input id="synthetic-confirm" type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} disabled={!state.connected || busy}/>This is an independently fictional identity, not a real person.</label>
                <div className="actions"><button type="submit" disabled={!state.connected || !confirmed || busy} className="primary">Create fictional identity</button><button type="button" disabled={busy || !state.created || keyForReceipt.current !== requestKey} onClick={() => { setRequestKey(crypto.randomUUID()); setConfirmed(false); }}>Start a different creation</button></div>
              </form>
              {state.created && <p data-testid="created-id">{state.created.duplicate ? 'Existing identity recovered: ' : 'Identity created: '}<code>{state.created.patient_id}</code><br/>The operator must separately grant access to this ID before it can be read.</p>}
            </details>
          </>}
        <footer><p><strong>Development workspace.</strong> Fictional identities only. This is not a clinical service or professional sign-off.</p><span>Open Intelligence</span></footer>
      </main>
    </div>
  </div>;
}

createRoot(document.getElementById('root')!).render(<StrictMode><App/></StrictMode>);
