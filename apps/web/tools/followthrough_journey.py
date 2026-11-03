"""Real React/HTTP/PostgreSQL acceptance for saved-question follow-through.

Imported by the existing Chromium journey. Operator grants use its independently
fictional patient; all questions, tasks, receipts and lists come from the actual
application. Fault injection discards, delays or explicitly corrupts a copy of
a real HTTP response; original responses and injected values remain distinct.
"""
import base64
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path


READ_ACTIONS = {'patient_read', 'case_binding_read', 'source_read', 'question_read',
                'followthrough_read'}
WRITE_ACTIONS = {'followthrough_create', 'followthrough_update'}
TITLE_DONE = 'Prepare the fictional source discussion'
TITLE_OPEN = 'Revisit the fictional source amendment'
TITLE_DEFERRED = 'Arrange a later fictional records discussion'
TITLE_SECOND_QUESTION = 'Prepare the fictional second question discussion'

_OBSERVE = r"""() => {
  if(window.__oiFollowthroughChecks) throw Error('Task observer already installed');
  const actualFetch=window.fetch;
  const state={writes:[],reads:[],timestampFaults:[],corruptNextTimestamp:null,dropNextWrite:false,holdNextRead:false,
    held:false,released:0,release:null};
  state.restore=()=>{state.release?.();window.fetch=actualFetch;delete window.__oiFollowthroughChecks;};
  window.fetch=async(input,init)=>{
    const path=new URL(input instanceof Request?input.url:input,location.href).pathname;
    const watched=/\/followthrough(?:\/TASK-[0-9A-F]{32}\/transitions)?$/.test(path);
    const method=(init?.method??(input instanceof Request?input.method:'GET')).toUpperCase();
    const response=await actualFetch.call(window,input,init);
    if(!watched)return response;
    const payload=await response.clone().json();
    if(method==='POST'){
      // Bodies are synthetic intent, never Authorization headers or credentials.
      state.writes.push({path,body:JSON.parse(init.body),status:response.status,payload});
      if(state.dropNextWrite&&response.status===201){
        state.dropNextWrite=false;
        throw new TypeError('Synthetic delivery loss after the actual server committed');
      }
    }else if(method==='GET'){
      state.reads.push({path,status:response.status,payload});
      if(state.corruptNextTimestamp&&response.status===200){
        const {field,value}=state.corruptNextTimestamp;
        state.corruptNextTimestamp=null;
        const changed=structuredClone(payload),task=changed.tasks[0];
        if(!task)throw Error('Timestamp control requires an actual saved task');
        const target=field==='created_at'?task:task.history.at(-1);
        const original=target[field];target[field]=value;
        state.timestampFaults.push({field,original,injected:value,task_id:task.task_id,
          access_receipt_id:payload.access_receipt_id,original_status:response.status});
        return new Response(JSON.stringify(changed),{status:response.status,headers:{'Content-Type':'application/json'}});
      }
      if(state.holdNextRead){
        state.holdNextRead=false;state.held=true;
        await new Promise(resolve=>{state.release=resolve;});
        state.held=false;state.release=null;state.released++;
      }
    }
    return response;
  };
  window.__oiFollowthroughChecks=state;
  return true;
}"""


def navigate(cd, section):
    cd.evaluate("[...document.querySelectorAll('nav button')].find(e=>e.textContent.startsWith("
                + json.dumps(section) + ")).click()")
    selectors = {'Investigations': '[data-view=investigations]',
                 'Journey': '[data-view=journey]', 'Records': '[data-testid=records-workspace]',
                 'Overview': '[data-testid=patient-card]'}
    cd.wait('Boolean(document.querySelector(' + json.dumps(selectors[section]) + '))',
            section + ' workspace for follow-through')


def fill(cd, selector, value):
    cd.evaluate("(()=>{const e=document.querySelector(" + json.dumps(selector) + ");"
                "if(!e)throw Error('Missing task input');"
                "const p=e.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;"
                "Object.getOwnPropertyDescriptor(p,'value').set.call(e," + json.dumps(value) + ");"
                "e.dispatchEvent(new Event('input',{bubbles:true}));})()")


def click(cd, selector):
    # An earlier real request may still be settling after workspace navigation.
    # Use the harness's bounded wait, including disabled ancestor fieldsets.
    cd.wait('(()=>{const e=document.querySelector(' + json.dumps(selector)
            + ");return Boolean(e)&&!e.matches(':disabled');})()", 'enabled task control ' + selector)
    cd.evaluate('document.querySelector(' + json.dumps(selector) + ').click()')


def select_case(cd, case_id):
    expression = ("[...document.querySelectorAll('.world-cases li')].find(e=>"
                  "e.querySelector('code')?.textContent===" + json.dumps(case_id) + ")")
    cd.wait('(()=>{const e=' + expression
            + ";const button=e?.querySelector('[data-testid=world-load]');"
            + "return Boolean(button)&&!button.matches(':disabled');})()",
            'enabled authorized case ' + case_id)
    cd.evaluate(expression + ".querySelector('[data-testid=world-load]').click()")
    cd.wait("document.querySelector('[data-testid=world-projection] > p code')?.textContent==="
            + json.dumps(case_id), 'current case World Model')


def artifacts_directory():
    root = Path(__file__).resolve().parents[3]
    path = Path(os.environ.get('OI_WEB_ARTIFACT_DIR', root / 'apps/web/.evidence'))
    path.mkdir(parents=True, exist_ok=True)
    return path


def capture_failure(cd, name):
    """Bounded synthetic-only diagnostics; never serialize input values or headers."""
    try:
        path = artifacts_directory()
        image = cd.command('Page.captureScreenshot', {'format': 'png'})
        (path / (name + '.png')).write_bytes(base64.b64decode(image['data']))
        info = cd.evaluate("({text:document.querySelector('main')?.textContent.slice(0,16000),"
                           "writes:window.__oiFollowthroughChecks?.writes.map(x=>({path:x.path,status:x.status})),"
                           "reads:window.__oiFollowthroughChecks?.reads.map(x=>({path:x.path,status:x.status}))})")
        (path / (name + '.json')).write_text(json.dumps(info, indent=2) + '\n', encoding='utf-8')
    except Exception:
        print('Follow-through failure capture unavailable; original failure retained.')


class FollowthroughChecks:
    def __init__(self, cd, patient_id, case_id, question_id, source_id):
        self.cd, self.patient_id, self.case_id = cd, patient_id, case_id
        self.question_id, self.source_id = question_id, source_id
        self.task_ids = {}
        self.before_amendment = None
        self.first_write = None

    def row(self, task_id):
        return '[data-testid=followthrough-task][data-task-id="' + task_id + '"]'

    def wait_task(self, task_id, status, revision):
        selector = self.row(task_id)
        self.cd.wait('document.querySelector(' + json.dumps(selector) + ')?.dataset.status==='
                     + json.dumps(status) + ' && document.querySelector(' + json.dumps(selector)
                     + ')?.dataset.revision===' + json.dumps(str(revision)),
                     'real task ' + status + ' revision ' + str(revision))

    def projection(self):
        value = self.cd.evaluate('window.__oiFollowthroughChecks.reads.at(-1)')
        assert value['status'] == 200
        payload = value['payload']
        assert payload['contract'] == 'oi.pg-question-followthrough/1'
        assert (payload['patient_id'], payload['case_id']) == (self.patient_id, self.case_id)
        assert payload['synthetic'] is True
        assert payload['clinical_approval'] is False
        assert payload['external_notification_sent'] is False
        assert payload['evaluated_on'] == datetime.now(timezone.utc).date().isoformat()
        return payload

    def refresh(self, expected_count=3):
        previous = self.cd.evaluate('window.__oiFollowthroughChecks.reads.length')
        click(self.cd, '[data-testid=followthrough-refresh]')
        self.cd.wait('window.__oiFollowthroughChecks.reads.length===' + str(previous + 1)
                     + " && document.querySelector('[data-testid=followthrough-status]')?.dataset.phase==='ready'"
                     + " && document.querySelectorAll('[data-testid=followthrough-task]').length==="
                     + str(expected_count), 'fresh authorized task projection')
        return self.projection()

    def create(self, title, *, lose_delivery=False, question_id=None, owner=''):
        question_id = question_id or self.question_id
        selector = '.question-items li[data-question-id="' + question_id + '"] [data-testid=followthrough-open-create]'
        click(self.cd, selector)
        fields = {'title': title, 'detail': 'Collect the existing fictional source references.',
                  'owner': owner, 'due-date': (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat(),
                  'trigger': 'When another source arrives', 'reason': 'Recorded for the fictional discussion.'}
        for name, value in fields.items():
            fill(self.cd, '[data-testid=followthrough-' + name + ']', value)
        before = self.cd.evaluate('window.__oiFollowthroughChecks.writes.length')
        if lose_delivery:
            self.cd.evaluate('window.__oiFollowthroughChecks.dropNextWrite=true')
        click(self.cd, '[data-testid=followthrough-create]')
        self.cd.wait('window.__oiFollowthroughChecks.writes.length===' + str(before + 1),
                     'actual create response observed')
        first = self.cd.evaluate('window.__oiFollowthroughChecks.writes.at(-1)')
        assert first['status'] == 201 and first['payload']['duplicate'] is False
        assert first['body']['synthetic'] is True
        assert first['body']['source_snapshot_contract'] == 'oi.pg-source-world-model/1'
        assert first['payload']['question_id'] == question_id
        if lose_delivery:
            self.cd.wait("document.querySelector('[data-testid=followthrough-write-status]')?.dataset.phase==='unknown'",
                         'committed response loss has explicit uncertain outcome')
            assert self.cd.evaluate("!document.querySelector('[data-testid=followthrough-receipt]')")
            assert self.cd.evaluate("document.querySelectorAll('[data-testid=followthrough-task]').length===0")
            assert title in self.cd.evaluate("document.querySelector('[data-testid=followthrough-recovery]').textContent")
            assert self.cd.evaluate("[...document.querySelectorAll('[data-testid=followthrough-title]')].every(e=>e.matches(':disabled'))")
            navigate(self.cd, 'Overview')
            assert self.cd.evaluate("Boolean(document.querySelector('[data-testid=continuity-followthrough-recovery]'))")
            assert self.cd.evaluate("document.querySelector('[data-testid=continuity-followthrough-refresh]').matches(':disabled')")
            assert self.cd.evaluate("!document.querySelector('[data-testid=continuity-followthrough-count-all]')")
            click(self.cd, '[data-testid=continuity-recover-followthrough]')
            self.cd.wait("Boolean(document.querySelector('[data-testid=followthrough-recovery]'))",
                         'Overview returns to the original uncertain-write recovery')
            assert title in self.cd.evaluate("document.querySelector('[data-testid=followthrough-recovery]').textContent")
            assert self.cd.evaluate('window.__oiFollowthroughChecks.writes.length') == before + 1
            click(self.cd, '[data-testid=followthrough-retry]')
            self.cd.wait('window.__oiFollowthroughChecks.writes.length===' + str(before + 2),
                         'same write retried against actual server')
            replay = self.cd.evaluate('window.__oiFollowthroughChecks.writes.at(-1)')
            assert replay['body'] == first['body'] and replay['path'] == first['path']
            assert replay['status'] == 200
            assert replay['payload'] == {**first['payload'], 'duplicate': True}
            self.first_write = first
        task_id = first['payload']['task_id']
        self.wait_task(task_id, 'created', 1)
        visible_receipt = self.cd.evaluate("document.querySelector('[data-testid=followthrough-receipt]').textContent")
        assert task_id in visible_receipt and first['payload']['event_id'] in visible_receipt
        assert self.cd.evaluate("document.querySelector('[data-testid=followthrough-receipt]').dataset.duplicate") == str(lose_delivery).lower()
        rows = self.projection()['tasks']
        assert len([row for row in rows if row['task_id'] == task_id]) == 1
        assert next(row for row in rows if row['task_id'] == task_id)['history'][0]['event_id'] == first['payload']['event_id']
        self.task_ids[title] = task_id
        return task_id

    def transition(self, task_id, status, revision, owner=''):
        selector = self.row(task_id)
        fill(self.cd, selector + ' [data-testid=followthrough-transition-reason]',
             'Recorded fictional work status: ' + status + '.')
        if status == 'assigned':
            fill(self.cd, selector + ' [data-testid=followthrough-transition-owner]', owner)
        action = {'assigned': 'assign', 'acknowledged': 'acknowledge', 'completed': 'complete', 'deferred': 'defer'}[status]
        click(self.cd, selector + ' [data-testid=followthrough-' + action + ']')
        self.wait_task(task_id, status, revision)
        write = self.cd.evaluate('window.__oiFollowthroughChecks.writes.at(-1)')
        assert write['status'] == 201 and write['body']['synthetic'] is True
        assert write['body']['expected_revision'] == revision - 1
        assert write['payload']['revision'] == revision

    def start(self):
        navigate(self.cd, 'Investigations')
        click(self.cd, '[data-testid=load-source-questions]')
        self.cd.wait("document.querySelector('[data-testid=source-question-history]')?.textContent.includes("
                     + json.dumps(self.question_id) + ")", 'existing saved question remains canonical')
        navigate(self.cd, 'Overview')
        assert self.cd.evaluate("document.querySelector('[data-testid=continuity-followthrough-status]').dataset.phase") == 'idle'
        assert self.cd.evaluate("!document.querySelector('[data-testid=continuity-followthrough-count-all]')")
        self.refresh_overview(expected_count=0)
        self.assert_overview_counts({'all': 0, 'recheck': 0, 'overdue': 0, 'unassigned': 0, 'history': 0})
        click(self.cd, '[data-testid=continuity-open-followthrough]')
        self.cd.wait("Boolean(document.querySelector('[data-testid=followthrough-panel]'))",
                     'Overview opens the existing follow-up panel')
        completed = self.create(TITLE_DONE, lose_delivery=True)
        assert self.cd.evaluate('!document.querySelector(' + json.dumps(self.row(completed)
                                + ' [data-testid=followthrough-complete]') + ')')
        # A saved transition belongs to the existing task. It must not consume
        # another, unsaved task draft attached to the same canonical question.
        question = '.question-items li[data-question-id="' + self.question_id + '"]'
        draft_title = 'Unsaved second fictional coordination task'
        draft_detail = 'Keep these authored notes while the existing fictional task changes status.'
        click(self.cd, question + ' [data-testid=followthrough-open-create]')
        fill(self.cd, question + ' [data-testid=followthrough-title]', draft_title)
        fill(self.cd, question + ' [data-testid=followthrough-detail]', draft_detail)
        before_transitions = self.cd.evaluate('window.__oiFollowthroughChecks.writes.length')

        def assert_creation_draft_survives(status):
            # Let committed receipt rendering and its React effects settle;
            # an eventually closed form must not accidentally pass this check.
            self.cd.evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve(true))))')
            form = question + ' [data-testid=followthrough-create-form]'
            assert self.cd.evaluate('Boolean(document.querySelector(' + json.dumps(form) + '))'), (
                'Successful existing-task ' + status + ' discarded the unsaved second-task creation form')
            for name, expected in (('title', draft_title), ('detail', draft_detail)):
                selector = question + ' [data-testid=followthrough-' + name + ']'
                assert self.cd.evaluate('document.querySelector(' + json.dumps(selector) + ').value') == expected, (
                    'Successful existing-task ' + status + ' changed the unsaved creation ' + name)

        self.transition(completed, 'assigned', 2, 'Fictional coordinator')
        assert_creation_draft_survives('assignment')
        assert self.cd.evaluate('!document.querySelector(' + json.dumps(self.row(completed)
                                + ' [data-testid=followthrough-complete]') + ')')
        self.transition(completed, 'acknowledged', 3)
        assert_creation_draft_survives('acknowledgment')
        click(self.cd, question + ' [data-testid=followthrough-cancel]')
        self.cd.wait('!document.querySelector(' + json.dumps(question + ' [data-testid=followthrough-create-form]')
                     + ')', 'explicit cancellation clears only the unsaved second-task draft')
        assert self.cd.evaluate('window.__oiFollowthroughChecks.writes.length') == before_transitions + 2
        assert len(self.projection()['tasks']) == 1, 'An unsaved draft must not create a task'
        self.transition(completed, 'completed', 4)
        self.create(TITLE_OPEN)
        deferred = self.create(TITLE_DEFERRED)
        self.transition(deferred, 'deferred', 2)
        self.transition(deferred, 'assigned', 3, 'Fictional later coordinator')
        self.transition(deferred, 'deferred', 4)
        self.before_amendment = {row['task_id']: row for row in self.projection()['tasks']}
        assert len(self.before_amendment) == 3
        for row in self.before_amendment.values():
            assert (row['question_id'], row['source_id'], row['source_line'], row['source_version']) == (
                self.question_id, self.source_id, 8, 1)
            assert row['source_context_state'] == 'current_unreviewed_question'
            assert row['needs_recheck'] is False and row['clinical_approval'] is False
            assert all(event['actor_label'] == 'ACTOR-0' for event in row['history'])
            selector = self.row(row['task_id']) + ' [data-testid=followthrough-history]'
            assert self.cd.evaluate('document.querySelector(' + json.dumps(selector) + ').children.length') == row['revision']
            history = self.cd.evaluate('document.querySelector(' + json.dumps(selector) + ').textContent')
            assert all(event['event_id'] in history and event['reason'] in history for event in row['history'])
        assert self.before_amendment[self.task_ids[TITLE_OPEN]]['is_overdue'] is True

    def after_amendment(self, replacement_source_id):
        navigate(self.cd, 'Investigations')
        select_case(self.cd, self.case_id)
        self.assert_amendment(replacement_source_id)
        navigate(self.cd, 'Records')

    def assert_amendment(self, replacement_source_id):
        value = self.refresh()
        for row in value['tasks']:
            before = self.before_amendment[row['task_id']]
            for field in ('source_id', 'source_line', 'source_sha256', 'source_version', 'question_id',
                          'source_snapshot_contract', 'source_snapshot_sha256', 'preflight_sha256',
                          'title', 'detail', 'owner_label', 'due_date', 'review_trigger', 'status', 'revision', 'history'):
                assert row[field] == before[field], field
            assert row['source_id'] != replacement_source_id
            assert row['source_context_state'] == 'source_reassessment_required'
            assert row['needs_recheck'] is (row['status'] == 'created')
            selector = self.row(row['task_id'])
            text = self.cd.evaluate('document.querySelector(' + json.dumps(selector) + ').textContent')
            assert self.source_id in text and self.question_id in text
            assert row['source_sha256'] in text
            assert row['needs_recheck'] == self.cd.evaluate('Boolean(document.querySelector('
                + json.dumps(selector + ' [data-testid=followthrough-recheck]') + '))')
        return value

    def assert_attention_filters(self):
        """Filter actual authorized tasks without writes, reads or discarded form state."""
        self.cd.wait("Boolean(document.querySelector('[data-testid=followthrough-attention]'))",
                     'source-bound work attention filters')
        counts = {'all': 3, 'recheck': 1, 'overdue': 1, 'unassigned': 1, 'history': 2}
        for key, count in counts.items():
            selector = '[data-testid=followthrough-filter-' + key + ']'
            assert self.cd.evaluate('document.querySelector(' + json.dumps(selector) + ').dataset.count') == str(count)
        current = self.task_ids[TITLE_OPEN]
        reason = 'Keep this fictional transition note while filtering recorded work.'
        owner = 'Fictional proposed owner'
        fill(self.cd, self.row(current) + ' [data-testid=followthrough-transition-reason]', reason)
        fill(self.cd, self.row(current) + ' [data-testid=followthrough-transition-owner]', owner)
        calls = self.cd.evaluate('({reads:window.__oiFollowthroughChecks.reads.length,writes:window.__oiFollowthroughChecks.writes.length})')
        for key, expected in (
                ('recheck', [current]), ('overdue', [current]), ('unassigned', [current]),
                ('history', [self.task_ids[TITLE_DONE], self.task_ids[TITLE_DEFERRED]]),
                ('all', list(self.task_ids.values()))):
            selector = '[data-testid=followthrough-filter-' + key + ']'
            click(self.cd, selector)
            self.cd.wait('document.querySelector(' + json.dumps(selector) + ").getAttribute('aria-pressed')==='true'",
                         'selected operational filter ' + key)
            visible = self.cd.evaluate("[...document.querySelectorAll('[data-testid=followthrough-task]')].filter(e=>e.getClientRects().length>0).map(e=>e.dataset.taskId)")
            assert sorted(visible) == sorted(expected), (key, visible, expected)
            # Even a hidden task remains mounted with the exact authored draft.
            for name, value in (('reason', reason), ('owner', owner)):
                control = self.row(current) + ' [data-testid=followthrough-transition-' + name + ']'
                assert self.cd.evaluate('document.querySelector(' + json.dumps(control) + ').value') == value
            assert self.cd.evaluate('({reads:window.__oiFollowthroughChecks.reads.length,writes:window.__oiFollowthroughChecks.writes.length})') == calls
        # A real response with a new receipt resets the filter; it is not an effect-time stale frame.
        click(self.cd, '[data-testid=followthrough-filter-history]')
        self.refresh()
        assert self.cd.evaluate("document.querySelector('[data-testid=followthrough-filter-all]').getAttribute('aria-pressed')") == 'true'
        assert self.cd.evaluate("[...document.querySelectorAll('[data-testid=followthrough-task]')].filter(e=>e.getClientRects().length>0).length") == 3
        # Keyboard activation uses an actual input event rather than calling click().
        self.cd.evaluate("document.querySelector('[data-testid=followthrough-filter-recheck]').focus()")
        self.cd.command('Input.dispatchKeyEvent', {'type': 'rawKeyDown', 'key': 'Enter', 'code': 'Enter', 'windowsVirtualKeyCode': 13})
        self.cd.command('Input.dispatchKeyEvent', {'type': 'char', 'text': '\r', 'unmodifiedText': '\r', 'key': 'Enter', 'code': 'Enter', 'windowsVirtualKeyCode': 13})
        self.cd.command('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': 'Enter', 'code': 'Enter', 'windowsVirtualKeyCode': 13})
        self.cd.wait("document.querySelector('[data-testid=followthrough-filter-recheck]').getAttribute('aria-pressed')==='true'",
                     'keyboard-select source-changed work')
        assert self.cd.evaluate("document.activeElement.dataset.testid") == 'followthrough-filter-recheck'
        print('PASS FOLLOWTHROUGH ATTENTION: actual source-amended task flags; overlapping counts; exact historical rows; no filter HTTP calls; preserved transition drafts; new-receipt reset; keyboard activation.')

    def assert_timestamp_rejection(self):
        """A corrupted copy of a real read cannot retain actionable task history."""
        original_tasks = self.projection()['tasks']
        writes = self.cd.evaluate('window.__oiFollowthroughChecks.writes.length')
        for field, value in (('created_at', '2026-02-30T10:00:00Z'),
                             ('recorded_at', '2026-11-03T24:00:00Z'),
                             ('recorded_at', '2026-11-03T10:00:00.1234567Z')):
            self.cd.evaluate('window.__oiFollowthroughChecks.corruptNextTimestamp='
                             + json.dumps({'field': field, 'value': value}))
            click(self.cd, '[data-testid=followthrough-refresh]')
            self.cd.wait("document.querySelector('[data-testid=followthrough-status]')?.dataset.phase==='error'",
                         'invalid timestamp removes actionable task history')
            assert self.cd.evaluate("!document.querySelector('[data-testid=followthrough-task]')")
            assert self.cd.evaluate("!document.querySelector('[data-testid=followthrough-attention]')")
            assert self.cd.evaluate("!document.querySelector('[data-testid=followthrough-history]')")
            assert self.cd.evaluate("!document.querySelector('[data-testid=followthrough-transition-reason]')")
            assert self.cd.evaluate('window.__oiFollowthroughChecks.writes.length') == writes
            assert self.projection()['tasks'] == original_tasks
            restored = self.refresh()
            assert restored['tasks'] == original_tasks
            for task in original_tasks:
                self.wait_task(task['task_id'], task['status'], task['revision'])
                selector = self.row(task['task_id'])
                displayed = self.cd.evaluate("[...document.querySelector(" + json.dumps(selector)
                    + ").querySelectorAll('[data-testid=followthrough-history] time')].map(e=>"
                      "({dateTime:e.getAttribute('datetime'),text:e.textContent}))")
                assert displayed == [{'dateTime': event['recorded_at'], 'text': event['recorded_at']}
                                     for event in task['history']]
                text = self.cd.evaluate('document.querySelector(' + json.dumps(selector) + ').textContent')
                assert all(task[field] in text for field in ('source_id', 'source_sha256', 'question_id'))
            assert self.cd.evaluate('window.__oiFollowthroughChecks.writes.length') == writes
        print('PASS FOLLOWTHROUGH TIMESTAMPS: three explicitly corrupted copies of real authorized reads '
              'withhold task history, counts and transition controls; fresh valid reads restore exact '
              'original tasks and timestamps without writes or grant changes.')

    def assert_overview_counts(self, counts):
        self.cd.wait("document.querySelector('[data-testid=continuity-followthrough-status]')?.dataset.phase==='ready'",
                     'Overview has an authorized last-read task summary')
        for key, count in counts.items():
            selector = '[data-testid=continuity-followthrough-count-' + key + ']'
            assert self.cd.evaluate('document.querySelector(' + json.dumps(selector) + ').dataset.count') == str(count)

    def refresh_overview(self, *, expected_count):
        """Hold a real GET response to verify loading clears the old summary."""
        before = self.cd.evaluate('({reads:window.__oiFollowthroughChecks.reads.length,writes:window.__oiFollowthroughChecks.writes.length})')
        self.cd.evaluate('window.__oiFollowthroughChecks.holdNextRead=true')
        click(self.cd, '[data-testid=continuity-followthrough-refresh]')
        self.cd.wait('window.__oiFollowthroughChecks.held', 'Overview requested the actual case task list')
        assert self.cd.evaluate("document.querySelector('[data-testid=continuity-followthrough-status]').dataset.phase") == 'loading'
        assert self.cd.evaluate("!document.querySelector('[data-testid=continuity-followthrough-count-all]') && !document.querySelector('[data-testid=continuity-followthrough-task]')")
        assert self.cd.evaluate("document.querySelector('[data-testid=continuity-followthrough-refresh]').matches(':disabled')")
        self.cd.evaluate('window.__oiFollowthroughChecks.release()')
        self.cd.wait("document.querySelector('[data-testid=continuity-followthrough-status]')?.dataset.phase==='ready'",
                     'Overview displays the completed authorized task read')
        assert self.cd.evaluate('window.__oiFollowthroughChecks.reads.length') == before['reads'] + 1
        assert self.cd.evaluate('window.__oiFollowthroughChecks.writes.length') == before['writes']
        value = self.projection()
        assert len(value['tasks']) == expected_count
        assert self.cd.evaluate('window.__oiFollowthroughChecks.reads.at(-1).path') == (
            '/v1/patients/' + self.patient_id + '/cases/' + self.case_id + '/followthrough')
        return value

    def assert_overview_work(self, current_question_id, screenshots):
        """Two real questions share one case summary without changing task ownership."""
        assert current_question_id != self.question_id
        # Earlier independent question/review denial checks deliberately clear
        # question history. Restore it with an actual authorized read before
        # opening the second question's task form; task reads do not grant it.
        click(self.cd, '[data-testid=load-source-questions]')
        self.cd.wait("document.querySelector('[data-testid=source-question-history]')?.textContent.includes("
                     + json.dumps(current_question_id) + ")", 'fresh second-question history after prior denial')
        second = self.create(TITLE_SECOND_QUESTION, question_id=current_question_id,
                             owner='Fictional second question coordinator')
        before = self.cd.evaluate('({reads:window.__oiFollowthroughChecks.reads.length,writes:window.__oiFollowthroughChecks.writes.length})')
        navigate(self.cd, 'Overview')
        self.assert_overview_counts({'all': 4, 'recheck': 1, 'overdue': 2, 'unassigned': 1, 'history': 2})
        previews = self.cd.evaluate("[...document.querySelectorAll('[data-testid=continuity-followthrough-task]')].map(e=>({task:e.dataset.taskId,question:e.dataset.questionId,text:e.textContent}))")
        assert {row['task'] for row in previews} == {self.task_ids[TITLE_OPEN], second}
        assert {row['question'] for row in previews} == {self.question_id, current_question_id}
        assert any('Fictional second question coordinator' in row['text'] for row in previews)
        assert all(TITLE_DONE not in row['text'] and TITLE_DEFERRED not in row['text'] for row in previews)
        assert self.cd.evaluate('({reads:window.__oiFollowthroughChecks.reads.length,writes:window.__oiFollowthroughChecks.writes.length})') == before
        value = self.refresh_overview(expected_count=4)
        self.assert_overview_counts({'all': 4, 'recheck': 1, 'overdue': 2, 'unassigned': 1, 'history': 2})
        assert value['evaluated_on'] in self.cd.evaluate("document.querySelector('[data-testid=continuity-followthrough-evaluated-on]').textContent")
        screenshots.mkdir(parents=True, exist_ok=True)
        for width, height, suffix in ((1440, 1100, 'desktop'), (390, 844, 'mobile')):
            self.cd.command('Emulation.setDeviceMetricsOverride', {
                'width': width, 'height': height, 'deviceScaleFactor': 1, 'mobile': False})
            self.cd.wait('window.innerWidth===' + str(width), 'Overview task viewport')
            assert self.cd.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1')
            self.cd.evaluate("document.querySelector('[data-testid=continuity-followthrough]').scrollIntoView({block:'center'})")
            image = self.cd.command('Page.captureScreenshot', {'format': 'png'})
            (screenshots / ('h1-overview-followthrough-' + suffix + '.png')).write_bytes(base64.b64decode(image['data']))
        self.cd.command('Emulation.setDeviceMetricsOverride', {
            'width': 1440, 'height': 1100, 'deviceScaleFactor': 1, 'mobile': False})
        click(self.cd, '[data-testid=continuity-open-followthrough]')
        self.cd.wait('document.querySelectorAll(\'[data-testid=followthrough-task]\').length===4',
                     'Overview returns to the same four persisted tasks')
        assert self.cd.evaluate('window.__oiFollowthroughChecks.writes.length') == before['writes']
        return value

    def finish(self, replacement_source_id, credentials, write_grants, screenshots, *, current_question_id):
        navigate(self.cd, 'Investigations')
        value = self.assert_amendment(replacement_source_id)
        self.assert_attention_filters()
        self.assert_timestamp_rejection()
        value = self.assert_overview_work(current_question_id, screenshots)
        # A failed fresh read must remove old task text and transition controls.
        credentials[0]['actions'].remove('followthrough_read')
        write_grants()
        click(self.cd, '[data-testid=followthrough-refresh]')
        self.cd.wait("document.querySelector('[data-testid=followthrough-status]')?.textContent.includes('unavailable')",
                     'independent task-read denial clears prior view')
        assert self.cd.evaluate("!document.querySelector('[data-testid=followthrough-task]')")
        assert self.cd.evaluate("!document.querySelector('[data-testid=followthrough-attention]')")
        navigate(self.cd, 'Overview')
        assert self.cd.evaluate("document.querySelector('[data-testid=continuity-followthrough-status]').dataset.phase") == 'error'
        assert self.cd.evaluate("!document.querySelector('[data-testid=continuity-followthrough-count-all]') && !document.querySelector('[data-testid=continuity-followthrough-task]')")
        assert self.cd.evaluate("Boolean(document.querySelector('[data-testid=continuity-reassessment]'))"), 'Independent task denial must preserve readable question context'
        card = self.cd.evaluate("document.querySelector('[data-testid=continuity-followthrough]').textContent")
        for row in value['tasks']:
            assert row['title'] not in card and row['task_id'] not in card
        credentials[0]['actions'].append('followthrough_read')
        write_grants()
        self.refresh_overview(expected_count=4)
        click(self.cd, '[data-testid=continuity-open-followthrough]')
        self.cd.wait('document.querySelectorAll(\'[data-testid=followthrough-task]\').length===4',
                     'restored task authority returns the same work')
        click(self.cd, '[data-testid=followthrough-filter-recheck]')
        screenshots.mkdir(parents=True, exist_ok=True)
        for width, height, suffix in ((1440, 1100, 'desktop'), (390, 844, 'mobile')):
            self.cd.command('Emulation.setDeviceMetricsOverride', {
                'width': width, 'height': height, 'deviceScaleFactor': 1, 'mobile': False})
            self.cd.wait('window.innerWidth===' + str(width), 'task viewport')
            assert self.cd.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1')
            self.cd.evaluate('document.querySelector(' + json.dumps(self.row(self.task_ids[TITLE_OPEN]))
                             + ").scrollIntoView({block:'center'})")
            image = self.cd.command('Page.captureScreenshot', {'format': 'png'})
            (screenshots / ('h1-followthrough-' + suffix + '.png')).write_bytes(base64.b64decode(image['data']))
            self.cd.evaluate("document.querySelector('[data-testid=followthrough-attention]').scrollIntoView({block:'start'})")
            image = self.cd.command('Page.captureScreenshot', {'format': 'png'})
            (screenshots / ('h1-followthrough-attention-' + suffix + '.png')).write_bytes(base64.b64decode(image['data']))
        self.cd.command('Emulation.setDeviceMetricsOverride', {
            'width': 1440, 'height': 1100, 'deviceScaleFactor': 1, 'mobile': False})
        (screenshots / 'h1-followthrough-receipts.json').write_text(json.dumps({
            'patient_id': self.patient_id, 'case_id': self.case_id, 'question_id': self.question_id,
            'first_create_receipt': self.first_write['payload'],
            'timestamp_fault_injection': self.cd.evaluate('window.__oiFollowthroughChecks.timestampFaults'),
            'task_summary': [{'task_id': row['task_id'], 'status': row['status'], 'revision': row['revision'],
                              'source_id': row['source_id'], 'needs_recheck': row['needs_recheck'],
                              'history_events': [event['event_id'] for event in row['history']]} for row in value['tasks']],
            'synthetic': True, 'clinical_approval': False,
        }, indent=2) + '\n', encoding='utf-8')
        navigate(self.cd, 'Journey')
        print('PASS FOLLOWTHROUGH: actual saved question to PostgreSQL tasks; lost committed response '
              'recovered with the exact request and one receipt; assignment, acknowledgment, completion, '
              'deferral and reassignment history; a second-task draft survives existing-task assignment '
              'and acknowledgment until explicit cancellation; source amendment flags only open work and retains '
              'original source/hash/history; independent read denial clears content; desktop/mobile capture.')
        print('PASS OVERVIEW FOLLOWTHROUGH: unchecked versus verified empty; two saved questions in one case; '
              'exact operational counts and recorded owner; read-only refresh with held-response clearing; '
              'uncertain-write recovery navigation; denied-read removal preserves questions; desktop/mobile capture.')


@contextmanager
def exercise(cd, patient_id, case_id, question_id, source_id, credentials, write_grants):
    previous = list(credentials[0]['actions'])
    try:
        credentials[0]['actions'] = sorted(set(previous) | READ_ACTIONS | WRITE_ACTIONS)
        write_grants()
        cd.evaluate('(' + _OBSERVE + ')()')
        checks = FollowthroughChecks(cd, patient_id, case_id, question_id, source_id)
        checks.start()
        yield checks
    except Exception:
        capture_failure(cd, 'h1-followthrough-failure')
        raise
    finally:
        try:
            cd.evaluate('window.__oiFollowthroughChecks?.restore()')
        finally:
            credentials[0]['actions'] = previous
            write_grants()


def exercise_case_switch(cd, patient_id, case_id, second_case_id, credentials, write_grants, screenshots,
                         *, current_question_id):
    """Run after existing record-intake checks have created the second case."""
    previous = list(credentials[0]['actions'])
    try:
        credentials[0]['actions'] = sorted(set(previous) | READ_ACTIONS)
        write_grants()
        cd.evaluate('(' + _OBSERVE + ')()')
        navigate(cd, 'Investigations')
        click(cd, '[data-testid=world-load-cases]')
        select_case(cd, case_id)
        checks = FollowthroughChecks(cd, patient_id, case_id, '', '')
        value = checks.refresh(expected_count=4)
        assert {row['title'] for row in value['tasks']} == {TITLE_DONE, TITLE_OPEN, TITLE_DEFERRED, TITLE_SECOND_QUESTION}
        # An actual unsaved current-question draft must also disappear on switch.
        click(cd, '[data-testid=load-source-questions]')
        # Several saved questions share v2. Use the exact question returned by
        # the connected upstream journey, never whichever row sorts first.
        current = ('.question-items li[data-question-id="' + current_question_id
                   + '"] [data-testid=followthrough-open-create]:not(:disabled)')
        cd.wait('Boolean(document.querySelector(' + json.dumps(current) + '))', 'current second-version question')
        click(cd, current)
        draft_title = 'Unsaved fictional Alpha coordination draft'
        fill(cd, '[data-testid=followthrough-title]', draft_title)
        cd.evaluate('window.__oiFollowthroughChecks.holdNextRead=true')
        click(cd, '[data-testid=followthrough-refresh]')
        cd.wait('window.__oiFollowthroughChecks.held', 'real first-case read held before client delivery')
        select_case(cd, second_case_id)
        assert cd.evaluate("!document.querySelector('[data-testid=followthrough-task]')")
        assert cd.evaluate("!document.querySelector('[data-testid=followthrough-receipt]')")
        cd.evaluate('window.__oiFollowthroughChecks.release()')
        cd.wait('window.__oiFollowthroughChecks.released===1', 'delayed first-case response released')
        cd.evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve(true))))')
        assert cd.evaluate("!document.querySelector('[data-testid=followthrough-task]')")
        navigate(cd, 'Overview')
        assert cd.evaluate("!document.querySelector('[data-testid=continuity-followthrough-count-all]') && !document.querySelector('[data-testid=continuity-followthrough-task]')")
        card = cd.evaluate("document.querySelector('[data-testid=continuity-followthrough]').textContent")
        for row in value['tasks']:
            assert row['title'] not in card and row['task_id'] not in card
        click(cd, '[data-testid=continuity-open-followthrough]')
        cd.wait("Boolean(document.querySelector('[data-testid=followthrough-panel]'))", 'second-case follow-up panel')
        checks.case_id = second_case_id
        empty = checks.refresh(expected_count=0)
        assert empty['tasks'] == []
        panel = cd.evaluate("document.querySelector('[data-testid=followthrough-panel]').textContent")
        for row in value['tasks']:
            assert row['task_id'] not in panel and row['title'] not in panel
        assert draft_title not in panel
        assert cd.evaluate("!document.querySelector('[data-testid=followthrough-title]') && "
                           "!document.querySelector('[data-testid=followthrough-retry]')")
        assert cd.evaluate('window.__oiFollowthroughChecks.writes.length===0')
        (screenshots / 'h1-followthrough-case-switch.json').write_text(json.dumps({
            'patient_id': patient_id, 'first_case_id': case_id, 'second_case_id': second_case_id,
            'unsaved_draft_question_id': current_question_id,
            'delayed_real_read_discarded': True, 'second_case_tasks': empty['tasks'],
        }, indent=2) + '\n', encoding='utf-8')
        navigate(cd, 'Overview')
        checks.assert_overview_counts({'all': 0, 'recheck': 0, 'overdue': 0, 'unassigned': 0, 'history': 0})
        print('PASS FOLLOWTHROUGH CASE SWITCH: actual second-case selection clears prior task content, '
              'receipts and drafts; a delayed authorized first-case response cannot restore them; '
              'second-case API list remains empty; no extra case or source fixture introduced.')
    except Exception:
        capture_failure(cd, 'h1-followthrough-case-switch-failure')
        raise
    finally:
        try:
            cd.evaluate('window.__oiFollowthroughChecks?.restore()')
        finally:
            credentials[0]['actions'] = previous
            write_grants()
