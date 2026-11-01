"""LangGraph/SQLite process-boundary experiment on ORIGINAL FICTIONAL state only.
No model API, medical data, deployment or application dependency integration.
Tests include negative controls: persistence is not authorization/idempotency.
"""
from __future__ import annotations
import argparse, importlib.metadata, json, os, sqlite3, subprocess, sys, tempfile, uuid
from pathlib import Path
from typing import TypedDict

class State(TypedDict, total=False):
    case_id: str
    source_version: int
    guarded: bool
    idempotent: bool
    status: str

def child(root: Path, case_id: str, phase: str, guarded: bool, idempotent: bool) -> None:
    from langgraph.graph import StateGraph, START, END
    from langgraph.types import interrupt, Command
    from langgraph.checkpoint.sqlite import SqliteSaver
    def record(kind: str) -> None:
        with (root/(case_id+'.events')).open('a') as f: f.write(kind+'\n')
    def policy() -> dict:
        return json.loads((root/(case_id+'.policy')).read_text())
    def allowed(s: State) -> bool:
        p=policy()
        return bool(p['grant']) and p['source_version']==s['source_version']
    def prepare(s: State) -> dict:
        record('prepare'); return {'status':'prepared'}
    def review(s: State) -> dict:
        record('before_interrupt')
        answer=interrupt({'case_id':s['case_id'],'source_version':s['source_version']})
        if not answer['approve']: return {'status':'rejected'}
        if s['guarded'] and not allowed(s): return {'status':'blocked'}
        return {'status':'approved'}
    def emit(s: State) -> dict:
        if s['status']!='approved': return {}
        if s['guarded'] and not allowed(s): return {'status':'blocked'}
        record('emit_attempt')
        key=case_id+':report' if s['idempotent'] else str(uuid.uuid4())
        with sqlite3.connect(root/'effects.db') as db:
            db.execute('CREATE TABLE IF NOT EXISTS effects(key TEXT PRIMARY KEY, case_id TEXT)')
            db.execute('INSERT OR IGNORE INTO effects VALUES (?,?)',(key,case_id))
        # Simulated process death AFTER an external effect commits, before graph checkpoint.
        flag=root/(case_id+'.crash')
        if flag.exists():
            flag.unlink();os._exit(70)
        return {'status':'completed'}
    builder=StateGraph(State)
    builder.add_node('prepare',prepare);builder.add_node('review',review);builder.add_node('emit',emit)
    builder.add_edge(START,'prepare');builder.add_edge('prepare','review');builder.add_edge('review','emit');builder.add_edge('emit',END)
    config={'configurable':{'thread_id':case_id}}
    with SqliteSaver.from_conn_string(str(root/'checkpoints.db')) as saver:
        graph=builder.compile(checkpointer=saver)
        if phase=='inspect':
            output=dict(graph.get_state(config).values)
        else:
            value={'case_id':case_id,'source_version':1,'guarded':guarded,'idempotent':idempotent} if phase=='begin' else (None if phase=='continue' else Command(resume={'approve':phase=='approve'}))
            res=graph.invoke(value,config,durability='sync')
            output={'status':res.get('status'),'interrupted':bool(res.get('__interrupt__'))}
        print(json.dumps(output))

def suite(output: Path) -> None:
    checks=[]
    def check(name: str, actual, expected):
        checks.append({'name':name,'actual':actual,'expected':expected,'pass':actual==expected})
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory)
        def set_policy(case,grant=True,version=1):
            (root/(case+'.policy')).write_text(json.dumps({'grant':grant,'source_version':version}))
        def run(case,phase,guard=True,idem=True,expect=0):
            args=[sys.executable,__file__,'--child',str(root),'--case',case,'--phase',phase]
            if not guard: args.append('--unguarded')
            if not idem: args.append('--non-idempotent')
            env=dict(os.environ,LANGCHAIN_TRACING_V2='false',LANGSMITH_TRACING='false')
            p=subprocess.run(args,text=True,capture_output=True,timeout=40,env=env)
            if p.returncode!=expect:
                raise RuntimeError('Child '+phase+' failed: '+str(p.returncode)+' '+p.stderr[-1500:])
            return json.loads(p.stdout.strip().splitlines()[-1]) if p.stdout.strip() else {}
        def events(case): return (root/(case+'.events')).read_text().splitlines()
        def effects(case):
            if not (root/'effects.db').exists():return 0
            with sqlite3.connect(root/'effects.db') as db:
                exists=db.execute("SELECT 1 FROM sqlite_master WHERE name='effects'").fetchone()
                return db.execute('SELECT count(*) FROM effects WHERE case_id=?',(case,)).fetchone()[0] if exists else 0
        set_policy('FICTIONAL-A')
        a=run('FICTIONAL-A','begin');check('interrupt_persisted_before_process_exit',a['interrupted'],True)
        a=run('FICTIONAL-A','approve');check('resume_in_fresh_process_completes',a['status'],'completed')
        check('completed_prepare_node_not_repeated',events('FICTIONAL-A').count('prepare'),1)
        check('code_before_interrupt_is_reexecuted',events('FICTIONAL-A').count('before_interrupt'),2)
        check('one_completed_effect',effects('FICTIONAL-A'),1)
        set_policy('FICTIONAL-B');run('FICTIONAL-B','begin')
        check('separate_thread_has_no_effect',effects('FICTIONAL-B'),0)
        # Deliberately demonstrate no user authorization in the bare checkpoint API.
        state=run('FICTIONAL-A','inspect')
        check('thread_id_is_not_an_authorization_boundary',state.get('case_id'),'FICTIONAL-A')
        for case,grant,version in [('FICTIONAL-REVOKED',False,1),('FICTIONAL-STALE',True,2)]:
            set_policy(case);run(case,'begin');set_policy(case,grant,version)
            r=run(case,'approve');check(case+'_denied_at_resume',r['status'],'blocked');check(case+'_no_effect',effects(case),0)
        set_policy('FICTIONAL-NO');run('FICTIONAL-NO','begin');r=run('FICTIONAL-NO','reject')
        check('human_rejection_preserved',r['status'],'rejected');check('rejection_no_effect',effects('FICTIONAL-NO'),0)
        set_policy('FICTIONAL-NAIVE');run('FICTIONAL-NAIVE','begin',False);set_policy('FICTIONAL-NAIVE',False)
        run('FICTIONAL-NAIVE','approve',False)
        check('negative_control_checkpoint_alone_allows_revoked_effect',effects('FICTIONAL-NAIVE'),1)
        for idem in (False,True):
            case='FICTIONAL-CRASH-'+str(idem);set_policy(case);run(case,'begin',True,idem)
            (root/(case+'.crash')).write_text('one crash')
            run(case,'approve',True,idem,expect=70)
            check(case+'_effect_committed_before_crash',effects(case),1)
            r=run(case,'continue',True,idem)
            check(case+'_recovery_completed',r['status'],'completed')
            check(case+'_effect_count_after_replay',effects(case),1 if idem else 2)
    packages=[]
    for dist in importlib.metadata.distributions():
        m=dist.metadata
        packages.append({'name':m.get('Name'), 'version':dist.version,
            'declared_license':(m.get('License-Expression') or m.get('License') or '')[:500],
            'license_classifiers':[v for v in m.get_all('Classifier',[]) if v.startswith('License ::')]})
    result={'status':'tested','case_data':'Original fictional identifiers and control flags only',
        'model_calls':0,'checks':checks,'passed':sum(c['pass'] for c in checks),'total':len(checks),
        'packages':sorted(packages,key=lambda p:(p['name'] or '').lower()),
        'interpretation':'Negative controls deliberately expose missing application guards; passing checks are not a clinical/security validation or runtime selection.'}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
    if not all(c['pass'] for c in checks):raise SystemExit(1)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--child',type=Path);ap.add_argument('--case');ap.add_argument('--phase')
    ap.add_argument('--unguarded',action='store_true');ap.add_argument('--non-idempotent',action='store_true')
    ap.add_argument('--output',type=Path,default=Path('research-results/runtime.json'));a=ap.parse_args()
    if a.child:child(a.child,a.case,a.phase,not a.unguarded,not a.non_idempotent)
    else:suite(a.output)
if __name__=='__main__':main()
