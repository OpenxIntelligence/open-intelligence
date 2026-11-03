"""PR238 source-question scenarios on the canonical React/PG World Model.

All responses come from the built application and actual disposable PostgreSQL.
Only operator fixture grants are changed; no API response or question is mocked.
"""

import base64
from contextlib import contextmanager
import json


class SourceQuestionChecks:
    def __init__(self, cd, source_id):
        self.cd = cd
        self.original_source_id = source_id
        self.original_question_id = None

    def navigate(self, section):
        self.cd.evaluate("[...document.querySelectorAll('nav button')].find(e=>e.textContent.startsWith("
                         + json.dumps(section) + ")).click()")
        if section == 'Investigations':
            self.cd.wait("Boolean(document.querySelector('[data-view=investigations]'))",
                         'one canonical Investigations workspace')
            assert self.cd.evaluate("document.querySelectorAll('[data-testid=source-question-panel]').length===1")
        elif section == 'Records':
            self.cd.wait("Boolean(document.querySelector('[data-testid=records-workspace]'))", 'Records workspace')

    def prepare(self, source_id, line):
        self.cd.evaluate("[...document.querySelectorAll('[data-testid=world-observation]')].find(e=>e.textContent.includes("
                         + json.dumps(source_id) + ")).querySelector('[data-testid=composer-preflight]').click()")
        self.cd.wait("document.querySelector('[data-testid=composer-context]')?.textContent.includes("
                     + json.dumps(source_id) + ")", 'exact current source context prepared')
        preview = self.cd.evaluate("document.querySelector('[data-testid=composer-context]').textContent")
        assert f'line {line}' in preview
        assert 'oi.pg-source-world-model/1' in preview
        assert 'This preview alone does not' in preview and 'execute a model' in preview

    def save(self):
        self.cd.evaluate("document.querySelector('[data-testid=save-source-question]').click()")
        self.cd.wait("document.querySelector('[data-testid=saved-source-question]')?.textContent.includes('Question saved')",
                     'persistent source-linked question without clinical approval')
        value = self.cd.evaluate("document.querySelector('[data-testid=saved-source-question] code').textContent")
        assert value.startswith('QUESTION-') and len(value) == 41
        return value

    def history(self, expected):
        self.cd.evaluate("document.querySelector('[data-testid=load-source-questions]').click()")
        self.cd.wait("document.querySelector('[data-testid=source-question-history]')?.textContent.includes("
                     + json.dumps(expected) + ")", 'authorized question history and current source state')
        return self.cd.evaluate("document.querySelector('[data-testid=source-question-history]').textContent")

    def start(self):
        self.navigate('Investigations')
        assert self.cd.evaluate("!document.querySelector('[data-testid=composer-context]')")
        self.prepare(self.original_source_id, 8)
        self.original_question_id = self.save()
        history = self.history('Current source context')
        assert self.original_question_id in history and self.original_source_id in history
        assert 'Clinical approval: none' in history

    def after_amendment(self, replacement_source_id):
        self.navigate('Investigations')
        history = self.history('Source changed')
        assert self.original_question_id in history and self.original_source_id in history
        assert replacement_source_id not in history
        # The unchanged displayed v1 observation must be rejected by the server's fresh fingerprint.
        self.cd.evaluate("document.querySelector('[data-testid=composer-preflight]').click()")
        self.cd.wait("document.querySelector('[data-testid=composer-status]').textContent.includes('original source changed')",
                     'stale source fingerprint cannot prepare a replacement context')
        assert self.cd.evaluate("!document.querySelector('[data-testid=composer-context]') && !document.querySelector('[data-testid=world-projection]')")
        self.navigate('Records')

    def finish(self, replacement_source_id, credentials, write_grants, screenshots):
        self.navigate('Investigations')
        self.prepare(replacement_source_id, 9)
        replacement_question = self.save()
        assert replacement_question != self.original_question_id
        history = self.history('Current source context')
        assert self.cd.evaluate("document.querySelectorAll('.question-items li').length===2")
        assert self.original_question_id in history and replacement_question in history
        assert self.original_source_id in history and replacement_source_id in history
        assert 'Source changed' in history and 'Current source context' in history
        assert 'Clinical approval: none' in history

        # Patient-authored question: the original source/case are fixed by the
        # current World Model, but the question text is intentionally editable.
        # One session draft must survive same-patient navigation; no upload,
        # localStorage, extra clinical ledger or model execution is involved.
        custom = 'Which original fictional report and line support this recorded marker status?'
        self.cd.evaluate("document.querySelector('[data-testid=choose-question-draft]').click()")
        self.cd.wait("Boolean(document.querySelector('[data-testid=question-draft-editor]'))",
                     'authoring form bound to the current source observation')
        self.cd.evaluate("""(() => {
          const input = document.querySelector('[data-testid=question-draft]');
          const set = Object.getOwnPropertyDescriptor(
            HTMLTextAreaElement.prototype,'value').set;
          set.call(input, """ + json.dumps(custom) + """);
          input.dispatchEvent(new Event('input',{bubbles:true}));
        })()""")
        self.cd.wait("document.querySelector('[data-testid=question-draft]').value==="
                     + json.dumps(custom), 'literal editable question received')
        self.navigate('Records')
        self.navigate('Investigations')
        assert self.cd.evaluate("document.querySelector('[data-testid=question-draft]').value==="
                                + json.dumps(custom))
        assert self.cd.evaluate("!document.querySelector('[data-testid=composer-context]')")
        self.cd.evaluate("document.querySelector('[data-testid=prepare-custom-question]').click()")
        self.cd.wait("document.querySelector('[data-testid=composer-context]')?.textContent.includes("
                     + json.dumps(custom) + ")",
                     'exact custom text returned through existing source preflight')
        assert self.cd.evaluate("document.querySelector('[data-testid=composer-context]').textContent.includes("
                                + json.dumps(replacement_source_id) + ")")
        custom_question = self.save()
        assert custom_question not in (self.original_question_id,replacement_question)
        custom_history = self.history(custom)
        assert custom_question in custom_history
        assert self.cd.evaluate("document.querySelectorAll('.question-items li').length===3")
        assert 'Clinical approval: none' in custom_history
        assert self.cd.evaluate("localStorage.length===0 && sessionStorage.length===0")

        screenshots.mkdir(parents=True, exist_ok=True)
        self.cd.command('Emulation.setDeviceMetricsOverride', {'width':1440,'height':1100,'deviceScaleFactor':1,'mobile':False})
        self.cd.wait('window.innerWidth===1440', 'question panel desktop viewport')
        self.cd.evaluate("document.querySelector('[data-testid=source-question-panel]').scrollIntoView({block:'start'})")
        clip = self.cd.evaluate("""(() => {
          const r=document.querySelector('[data-testid=source-question-panel]').getBoundingClientRect();
          return {x:r.left+scrollX,y:r.top+scrollY,width:r.width,height:r.height,scale:1};
        })()""")
        image = self.cd.command('Page.captureScreenshot', {'format':'png','captureBeyondViewport':True,'clip':clip})
        (screenshots/'h1-source-questions-desktop.png').write_bytes(base64.b64decode(image['data']))
        self.cd.command('Emulation.setDeviceMetricsOverride', {'width':390,'height':844,'deviceScaleFactor':1,'mobile':False})
        self.cd.wait('window.innerWidth===390', 'question panel narrow viewport')
        assert self.cd.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1')
        self.cd.command('Emulation.setDeviceMetricsOverride', {'width':1440,'height':1100,'deviceScaleFactor':1,'mobile':False})

        # History has its own permission, independent of Composer context access.
        credentials[0]['actions'].remove('composer_context_read')
        write_grants()
        assert replacement_question in self.history('Current source context')
        credentials[0]['actions'].remove('question_read')
        write_grants()
        self.cd.evaluate("document.querySelector('[data-testid=load-source-questions]').click()")
        self.cd.wait("document.querySelector('[data-testid=questions-status]').textContent.includes('unavailable')",
                     'independent question-read denial clears history')
        assert self.cd.evaluate("!document.querySelector('[data-testid=source-question-history]')")
        credentials[0]['actions'].append('question_read')
        write_grants()
        self.cd.evaluate("document.querySelector('[data-testid=composer-preflight]').click()")
        self.cd.wait("document.querySelector('[data-testid=composer-status]').textContent.includes('Composer context unavailable')",
                     'independent Composer denial clears source context')
        assert self.cd.evaluate("!document.querySelector('[data-testid=composer-context]') && !document.querySelector('[data-testid=world-projection]')")
        credentials[0]['actions'].append('composer_context_read')
        write_grants()
        self.cd.evaluate("document.querySelector('[data-testid=world-load]').click()")
        self.cd.wait("Boolean(document.querySelector('[data-testid=world-projection]'))", 'fresh canonical source view restored')
        self.navigate('Journey')
        print('PASS SOURCE QUESTIONS: canonical source-line preflight; durable question and history; amendment requires reassessment without moving original anchor; explicit v2 context/question and patient-authored verified third question; independent question-read and Composer denial; actual desktop panel capture and narrow containment; no model execution or clinical approval.')


@contextmanager
def exercise(cd, source_id, credentials, write_grants):
    previous_actions = list(credentials[0]['actions'])
    try:
        credentials[0]['actions'] = sorted(set(previous_actions) |
            {'composer_context_read','question_create','question_read'})
        write_grants()
        checks = SourceQuestionChecks(cd, source_id)
        checks.start()
        yield checks
    finally:
        credentials[0]['actions'] = previous_actions
        write_grants()
