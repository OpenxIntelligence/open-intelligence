"""PR238 source-question scenarios on the canonical React/PG World Model.

All responses come from the built application and actual disposable PostgreSQL.
Only operator fixture grants are changed; no API response or question is mocked.
"""

import base64
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path

from browser_journey import wait_for


_OBSERVE_BRIEFS = r"""() => {
  if (window.__oiBriefChecks) throw Error('Source brief observer already installed');
  const actualFetch=window.fetch, actualCreate=URL.createObjectURL;
  const state={reads:[],blobs:0};
  state.restore=() => {
    window.fetch=actualFetch;URL.createObjectURL=actualCreate;delete window.__oiBriefChecks;
  };
  URL.createObjectURL=function(blob){state.blobs++;return actualCreate.call(this,blob);};
  window.fetch=async (input,init) => {
    const path=new URL(input instanceof Request?input.url:input,location.href).pathname;
    const response=await actualFetch.call(window,input,init);
    if (/\/questions\/QUESTION-[0-9A-F]{32}\/brief$/.test(path)) {
      // Observe actual server bytes without replacing content or retaining credentials.
      const payload=await response.clone().json();
      state.reads.push({status:response.status,path,...(response.status===200?{
        contract:payload.contract,question:payload.question,selected_source:payload.selected_source,
        source_snapshot_sha256:payload.source_snapshot_sha256,access_receipt_id:payload.access_receipt_id,
        body:payload.body,body_sha256:payload.body_sha256,clinical_approval:payload.clinical_approval,
        model_executed:payload.model_executed,biomedical_evidence_included:payload.biomedical_evidence_included
      }:{})});
    }
    return response;
  };
  window.__oiBriefChecks=state;
  return true;
}"""


class SourceQuestionChecks:
    def __init__(self, cd, source_id):
        self.cd = cd
        self.original_source_id = source_id
        self.original_question_id = None
        root = Path(__file__).resolve().parents[3]
        self.artifacts = Path(os.environ.get('OI_WEB_ARTIFACT_DIR', root/'apps/web/.evidence'))
        self.artifacts.mkdir(parents=True, exist_ok=True)
        self.original_download = None
        self.original_download_bytes = None

    def prepare_brief(self, question_id):
        selector = f'.question-items li[data-question-id="{question_id}"] [data-testid=brief-prepare]'
        assert not self.cd.evaluate(f'document.querySelector({json.dumps(selector)}).disabled')
        self.cd.evaluate(f'document.querySelector({json.dumps(selector)}).click()')
        self.cd.wait("document.querySelector('[data-testid=source-brief-body]')?.textContent.includes("
                     + json.dumps(question_id) + ")", 'current saved question produces literal source brief')
        body = self.cd.evaluate("document.querySelector('[data-testid=source-brief-body]').textContent")
        observed = self.cd.evaluate('window.__oiBriefChecks.reads.at(-1)')
        assert observed['status'] == 200 and observed['contract'] == 'oi.synthetic-source-brief/2'
        assert observed['question']['question_id'] == question_id
        assert observed['question']['source_context_state'] == 'current_unreviewed_question'
        assert body == observed['body']
        assert hashlib.sha256(body.encode('utf-8')).hexdigest() == observed['body_sha256']
        assert not observed['clinical_approval'] and not observed['model_executed']
        assert not observed['biomedical_evidence_included']
        assert self.cd.evaluate("document.querySelectorAll('[data-testid=source-brief-body] script').length===0")
        assert 'Human review: not_submitted' in body and 'Clinical approval: false' in body
        return observed

    def download_brief(self, question_id):
        destination = self.artifacts/'source-brief-downloads'/question_id
        destination.mkdir(parents=True, exist_ok=True)
        self.cd.command('Browser.setDownloadBehavior', {'behavior':'allow','downloadPath':str(destination.resolve())})
        count = self.cd.evaluate('window.__oiBriefChecks.reads.length')
        before_receipt = self.cd.evaluate("document.querySelector('[data-testid=brief-access-receipt]').textContent")
        self.cd.evaluate("document.querySelector('[data-testid=brief-download]').click()")
        self.cd.wait(f"window.__oiBriefChecks.reads.length==={count+1} && document.querySelector('[data-testid=brief-access-receipt]')?.textContent!=="
                     + json.dumps(before_receipt)
                     + " && Boolean(document.querySelector('[data-testid=source-brief-body]'))",
                     'download rechecks authority with a new actual source receipt')
        observed = self.cd.evaluate('window.__oiBriefChecks.reads.at(-1)')
        assert observed['status'] == 200 and observed['access_receipt_id'] != before_receipt
        assert observed['question']['question_id'] == question_id
        downloaded = destination/'open-intelligence-source-question-brief.txt'
        wait_for(lambda: downloaded.is_file() and not list(destination.glob('*.crdownload')),
                 'actual Chromium source brief download completes')
        actual = downloaded.read_bytes()
        assert actual == observed['body'].encode('utf-8')
        assert hashlib.sha256(actual).hexdigest() == observed['body_sha256']
        assert question_id.encode() in actual
        assert observed['selected_source']['source_id'].encode() in actual
        assert b'Clinical approval: false' in actual and b'Model executed: false' in actual
        receipt = {key:value for key,value in observed.items() if key != 'body'}
        receipt['download_relative_path'] = str(downloaded.relative_to(self.artifacts))
        receipt['download_bytes'] = len(actual)
        (self.artifacts/f'source-brief-{question_id}.json').write_text(
            json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
        return downloaded, actual

    def revoked_export(self, credentials, write_grants):
        credentials[0]['actions'].remove('source_brief_export')
        write_grants()
        count = self.cd.evaluate('window.__oiBriefChecks.reads.length')
        blobs = self.cd.evaluate('window.__oiBriefChecks.blobs')
        downloads = sorted(self.artifacts.glob('source-brief-downloads/**/*'))
        self.cd.evaluate("document.querySelector('[data-testid=brief-download]').click()")
        self.cd.wait("document.querySelector('[data-testid=brief-status]').textContent.includes('unavailable under current authority')",
                     'fresh download denies withdrawn export permission')
        assert self.cd.evaluate('window.__oiBriefChecks.reads.length') == count+1
        assert self.cd.evaluate('window.__oiBriefChecks.reads.at(-1).status') == 404
        assert self.cd.evaluate('window.__oiBriefChecks.blobs') == blobs
        assert not self.cd.evaluate("Boolean(document.querySelector('[data-testid=source-brief-preview]'))")
        after_downloads = sorted(self.artifacts.glob('source-brief-downloads/**/*'))
        assert after_downloads == downloads, (
            'Revoked export changed the exact source-brief artifact inventory: '
            f"before={[str(path.relative_to(self.artifacts)) for path in downloads]!r}, "
            f"after={[str(path.relative_to(self.artifacts)) for path in after_downloads]!r}"
        )
        assert self.original_download.read_bytes() == self.original_download_bytes
        credentials[0]['actions'].append('source_brief_export')
        write_grants()
        self.cd.evaluate("document.querySelector('[data-testid=world-load]').click()")
        self.cd.wait("Boolean(document.querySelector('[data-testid=world-projection]'))", 'fresh context after export denial')
        self.history('Current source context')
        self.prepare_brief(self.original_question_id)

    def overview_counts(self, *, current, reassessment):
        self.navigate('Overview')
        self.cd.wait("Boolean(document.querySelector('[data-testid=patient-continuity]'))",
                     'patient preparation overview')
        assert self.cd.evaluate("document.querySelector('[data-testid=continuity-current]').textContent") == str(current)
        assert self.cd.evaluate("document.querySelector('[data-testid=continuity-reassessment]').textContent") == str(reassessment)
        assert 'last successful reads' in self.cd.evaluate("document.querySelector('[data-testid=patient-continuity]').textContent")
        # The same authorized patient question history now drives a bounded,
        # nonclinical preparation shortcut. No new question or provider action.
        if reassessment:
            self.cd.wait("Boolean(document.querySelector('[data-testid=continuity-preparation-item][data-kind=question-recheck]'))",
                         'reassessment prompt from the current authorized question history')
            prompt = self.cd.evaluate("document.querySelector('[data-testid=continuity-preparation-item][data-kind=question-recheck]').textContent")
            assert 'source reassessment' in prompt and 'Inspect affected questions' in prompt
            self.cd.evaluate("document.querySelector('[data-testid=continuity-preparation-item][data-kind=question-recheck] button').click()")
        else:
            assert not self.cd.evaluate("Boolean(document.querySelector('[data-testid=continuity-preparation-item][data-kind=question-recheck]'))")
            self.cd.evaluate("document.querySelector('[data-testid=continuity-open-questions]').click()")
        self.cd.wait("Boolean(document.querySelector('[data-view=investigations]'))", 'return to existing questions')

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
                +json.dumps(expected_text)+") && document.querySelector('[data-testid=source-quote-packet]')?.textContent.includes("
                +json.dumps(question_id)+")",
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
                "Boolean(document.querySelector('[data-testid=source-quote-stale]')) && document.querySelector('[data-testid=source-quote-packet]')?.textContent.includes("
                +json.dumps(question_id)+")",
                'historical question remains inspectable without stale quote')
            assert self.cd.evaluate(
                "!document.querySelector('[data-testid=source-quote-literal]')")
            assert self.original_source_id in self.cd.evaluate(
                "document.querySelector('[data-testid=source-quote-packet]').textContent")

    def start(self, credentials, write_grants):
        self.navigate('Investigations')
        assert self.cd.evaluate("!document.querySelector('[data-testid=composer-context]')")
        self.prepare(self.original_source_id, 8)
        self.original_question_id = self.save()
        history = self.history('Current source context')
        assert self.original_question_id in history and self.original_source_id in history
        assert 'Clinical approval: none' in history
        self.overview_counts(current=1, reassessment=0)
        preview = self.prepare_brief(self.original_question_id)
        assert 'Fictional café <script>literal</script>.' in preview['body']
        self.original_download, self.original_download_bytes = self.download_brief(self.original_question_id)
        self.revoked_export(credentials, write_grants)
        self.inspect_quote(self.original_question_id,current=True,
            expected_text='Fictional café <script>literal</script>.')

    def after_amendment(self, replacement_source_id):
        self.navigate('Investigations')
        history = self.history('Source changed')
        assert self.original_question_id in history and self.original_source_id in history
        assert replacement_source_id not in history
        self.overview_counts(current=0, reassessment=1)
        assert self.original_download.read_bytes() == self.original_download_bytes
        assert not self.cd.evaluate("Boolean(document.querySelector('[data-testid=source-brief-preview]'))")
        stale = f'.question-items li[data-question-id="{self.original_question_id}"] [data-testid=brief-prepare]'
        assert self.cd.evaluate(f'document.querySelector({json.dumps(stale)}).disabled')
        count = self.cd.evaluate('window.__oiBriefChecks.reads.length')
        blobs = self.cd.evaluate('window.__oiBriefChecks.blobs')
        self.cd.evaluate(f'document.querySelector({json.dumps(stale)}).click()')
        self.cd.evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve(true))))')
        assert self.cd.evaluate('window.__oiBriefChecks.reads.length') == count
        assert self.cd.evaluate('window.__oiBriefChecks.blobs') == blobs
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
        prepared = self.prepare_brief(replacement_question)
        assert prepared['selected_source']['source_id'] == replacement_source_id
        assert prepared['selected_source']['version'] == 2 and prepared['selected_source']['line'] == 9
        assert 'Amended fictional marker is reported negative.' in prepared['body']
        assert self.original_source_id in prepared['body'], 'Earlier original must remain explicitly historical'
        self.download_brief(replacement_question)
        assert self.original_download.read_bytes() == self.original_download_bytes
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
        self.prepare_brief(replacement_question)

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
        self.navigate('Overview')
        self.cd.wait("document.querySelector('[data-testid=continuity-draft]')?.dataset.state==='unsaved'",
                     'patient overview preserves and offers the unfinished question')
        self.cd.evaluate("document.querySelector('[data-testid=continuity-resume]').click()")
        self.cd.wait("Boolean(document.querySelector('[data-testid=question-draft]'))",
                     'overview resumes the existing question editor')
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
        self.overview_counts(current=2, reassessment=1)
        assert self.cd.evaluate("localStorage.length===0 && sessionStorage.length===0")

        # One authored question must reach BOTH independently authorized readers
        # and the actual downloaded file. Separate feature passes cannot prove
        # that these three owners preserve the same selection when combined.
        self.inspect_quote(custom_question,current=True,
            expected_text='Amended fictional marker is reported negative.')
        quote_panel = self.cd.evaluate(
            "document.querySelector('[data-testid=source-quote-packet]').textContent")
        assert custom in quote_panel and custom_question in quote_panel
        assert replacement_source_id in quote_panel
        authored_brief = self.prepare_brief(custom_question)
        assert authored_brief['question']['question'] == custom
        assert authored_brief['selected_source']['source_id'] == replacement_source_id
        assert authored_brief['selected_source']['version'] == 2
        assert authored_brief['selected_source']['line'] == 9
        assert custom in authored_brief['body']
        assert self.cd.evaluate(
            "document.querySelector('[data-testid=source-quote-packet]').textContent.includes("
            + json.dumps(custom_question) + ")")
        _, authored_bytes = self.download_brief(custom_question)
        assert custom.encode('utf-8') in authored_bytes
        assert self.original_download.read_bytes() == self.original_download_bytes

        # Switching to an older saved question clears the now-inapplicable
        # brief synchronously; reselecting the authored question restores only
        # its own current source. Delayed-response races are separately tested
        # with controlled client transport, not claimed from this browser step.
        self.inspect_quote(self.original_question_id,current=False)
        assert self.cd.evaluate("!document.querySelector('[data-testid=source-brief-preview]')")
        self.prepare_brief(custom_question)
        assert self.cd.evaluate("!document.querySelector('[data-testid=source-quote-packet]')")
        self.inspect_quote(custom_question,current=True,
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
        self.cd.evaluate("document.querySelector('[data-testid=source-quote-packet]').scrollIntoView({block:'start'})")
        image = self.cd.command('Page.captureScreenshot', {'format':'png'})
        (screenshots/'h1-connected-question-desktop.png').write_bytes(base64.b64decode(image['data']))
        self.cd.command('Emulation.setDeviceMetricsOverride', {'width':390,'height':844,'deviceScaleFactor':1,'mobile':False})
        self.cd.wait('window.innerWidth===390', 'question panel narrow viewport')
        assert self.cd.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1')
        assert self.cd.evaluate("document.querySelector('[data-testid=source-brief-preview]').scrollWidth<=document.querySelector('[data-testid=source-brief-preview]').clientWidth+1")
        self.cd.evaluate("document.querySelector('[data-testid=source-brief-preview]').scrollIntoView({block:'start'})")
        image = self.cd.command('Page.captureScreenshot', {'format':'png'})
        (screenshots/'h1-source-brief-mobile.png').write_bytes(base64.b64decode(image['data']))
        self.cd.command('Emulation.setDeviceMetricsOverride', {'width':1440,'height':1100,'deviceScaleFactor':1,'mobile':False})

        self.navigate('Overview')
        self.cd.wait("document.querySelector('[data-testid=continuity-draft]')?.dataset.state==='saved'",
                     'confirmed save is not presented as an unsaved draft')
        self.cd.evaluate("document.querySelector('[data-testid=patient-continuity]').scrollIntoView({block:'start'})")
        image = self.cd.command('Page.captureScreenshot', {'format':'png'})
        (screenshots/'h1-patient-continuity-desktop.png').write_bytes(base64.b64decode(image['data']))
        self.cd.command('Emulation.setDeviceMetricsOverride', {'width':390,'height':844,'deviceScaleFactor':1,'mobile':False})
        self.cd.wait('window.innerWidth===390', 'patient continuity narrow viewport')
        assert self.cd.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1')
        self.cd.evaluate("document.querySelector('[data-testid=continuity-open-questions]').focus()")
        assert self.cd.evaluate("document.activeElement.dataset.testid==='continuity-open-questions'")
        image = self.cd.command('Page.captureScreenshot', {'format':'png'})
        (screenshots/'h1-patient-continuity-mobile.png').write_bytes(base64.b64decode(image['data']))
        self.cd.command('Emulation.setDeviceMetricsOverride', {'width':1440,'height':1100,'deviceScaleFactor':1,'mobile':False})
        self.navigate('Investigations')

        # History has its own permission, independent of Composer context access.
        credentials[0]['actions'].remove('composer_context_read')
        write_grants()
        assert replacement_question in self.history('Current source context')
        self.prepare_brief(replacement_question)
        credentials[0]['actions'].remove('question_read')
        write_grants()
        self.cd.evaluate("document.querySelector('[data-testid=load-source-questions]').click()")
        self.cd.wait("document.querySelector('[data-testid=questions-status]').textContent.includes('unavailable')",
                     'independent question-read denial clears history')
        assert self.cd.evaluate("!document.querySelector('[data-testid=source-question-history]')")
        assert self.cd.evaluate("!document.querySelector('[data-testid=source-brief-preview]')")
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
        print('PASS SOURCE QUESTIONS: canonical source-line preflight; durable question and history; amendment requires reassessment without moving original anchor; explicit v2 context/question and patient-authored third question; independent question-read and Composer denial; desktop and narrow containment; no model execution or clinical approval.')
        print('PASS SOURCE BRIEF: current saved question to literal brief; fresh authenticated text download and exact UTF-8/hash bytes; independent export revocation produces no Blob or file; amended question cannot export; fresh v2 question retains historical original; unchanged prior downloaded bytes; export works independently of Composer grant; source-only/no clinical approval.')
        print('PASS CONNECTED QUESTION: authored literal text -> persisted canonical question -> separately authorized exact original quotation -> freshly authorized actual text download; same question/source/version/line throughout; historical selection clears current brief and reselecting clears the other packet; inspection-grant withdrawal does not grant or revoke export authority; no scientific appraisal or clinical approval.')


@contextmanager
def exercise(cd, source_id, credentials, write_grants):
    previous_actions = list(credentials[0]['actions'])
    try:
        credentials[0]['actions'] = sorted(set(previous_actions) |
            {'composer_context_read','question_create','question_read','source_brief_export','review_packet_read'})
        write_grants()
        cd.evaluate(f'({_OBSERVE_BRIEFS})()')
        checks = SourceQuestionChecks(cd, source_id)
        checks.start(credentials, write_grants)
        yield checks
    finally:
        try:
            cd.evaluate('window.__oiBriefChecks?.restore()')
        finally:
            credentials[0]['actions'] = previous_actions
            write_grants()
