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

    def inspect_quote(self, question_id, *, current, expected_text=''):
        # These are actual built React responses from the current canonical PG
        # source owner; no fabricated quote, status, or HTTP response.
        self.cd.evaluate(
          "Array.from(document.querySelectorAll('.question-items li')).find(e=>e.textContent.includes("
          +json.dumps(question_id)
          +")).querySelector('[data-testid=source-quote-packet-open]').click()")
        if current:
            self.cd.wait(
                "document.querySelector('[data-testid=source-quote-literal]')?.textContent.includes("
                +json.dumps(expected_text)+")",
                'authorized literal original quotation for selected current question')
            panel=self.cd.evaluate(
                "document.querySelector('[data-testid=source-quote-packet]').textContent")
            assert question_id in panel
            assert 'not a clinical assessment' in panel
            assert 'Biomedical literature appraisal' in panel
            assert 'signed decisions are not established' in panel
            assert self.cd.evaluate("document.querySelectorAll('[data-testid=source-quote-literal] script').length===0")
        else:
            self.cd.wait(
                "Boolean(document.querySelector('[data-testid=source-quote-stale]'))",
                'historical question remains inspectable without stale quote')
            assert self.cd.evaluate(
                "!document.querySelector('[data-testid=source-quote-literal]')")
            assert self.original_source_id in self.cd.evaluate(
                "document.querySelector('[data-testid=source-quote-packet]').textContent")

    def start(self):
        self.navigate('Investigations')
        assert self.cd.evaluate("!document.querySelector('[data-testid=composer-context]')")
        self.prepare(self.original_source_id, 8)
        self.original_question_id = self.save()
        history = self.history('Current source context')
        assert self.original_question_id in history and self.original_source_id in history
        assert 'Clinical approval: none' in history
        self.inspect_quote(self.original_question_id,current=True,
            expected_text='Fictional café <script>literal</script>.')

    def after_amendment(self, replacement_source_id):
        self.navigate('Investigations')
        history = self.history('Source changed')
        assert self.original_question_id in history and self.original_source_id in history
        assert replacement_source_id not in history
        self.inspect_quote(self.original_question_id,current=False)
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
        self.inspect_quote(self.original_question_id,current=False)
        self.inspect_quote(replacement_question,current=True,
            expected_text='Amended fictional marker is reported negative.')
        # The independently granted quote-packet action can be revoked while
        # ordinary question history remains separately readable.
        credentials[0]['actions'].remove('review_packet_read')
        write_grants()
        self.cd.evaluate(
          "Array.from(document.querySelectorAll('.question-items li')).find(e=>e.textContent.includes("
          +json.dumps(replacement_question)
          +")).querySelector('[data-testid=source-quote-packet-open]').click()")
        self.cd.wait(
          "document.querySelector('[data-testid=source-quote-packet-status]').textContent.includes('unavailable')",
          'source-quote privilege revoked, no residual quote')
        assert self.cd.evaluate("!document.querySelector('[data-testid=source-quote-packet]')")
        assert replacement_question in self.history('Current source context')
        credentials[0]['actions'].append('review_packet_read')
        write_grants()
        self.inspect_quote(replacement_question,current=True,
            expected_text='Amended fictional marker is reported negative.')

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
        print('PASS SOURCE QUESTIONS: canonical source-line preflight; durable question and history; current/immutable original source-review packet with literal quote; amended v1 quote withheld; v2 quote restored; distinct quote grant revocation, question-read and Composer denial; desktop/narrow containment; no clinical approval.')


@contextmanager
def exercise(cd, source_id, credentials, write_grants):
    previous_actions = list(credentials[0]['actions'])
    try:
        credentials[0]['actions'] = sorted(set(previous_actions) |
            {'composer_context_read','question_create','question_read','review_packet_read'})
        write_grants()
        checks = SourceQuestionChecks(cd, source_id)
        checks.start()
        yield checks
    finally:
        credentials[0]['actions'] = previous_actions
        write_grants()
