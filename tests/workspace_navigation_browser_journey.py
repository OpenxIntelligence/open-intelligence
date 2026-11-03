"""Real-browser regression for the connected patient/clinician navigation.

Run with ``python tests/workspace_navigation_browser_journey.py``. The app uses a
temporary SQLite database seeded with the repository's independently authored
fictional examples. Questions, evidence assessments and a draft are submitted
through the actual forms; no API handlers or browser requests are mocked.

Uses the existing stdlib ChromeSession helper and an installed Chrome/Chromium.
OI_CHROME_EXECUTABLE can select a browser. OI_UI_ARTIFACT_DIR selects the directory
for PNGs, navigation-report.json and process diagnostics. A missing browser is a
failure, never a successful skip. No live model or literature service is enabled.
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit
from urllib.request import urlopen

from browser_journey import ChromeSession, free_port, wait_for


ROOT = Path(__file__).resolve().parents[1]
FORM_IDS = (
    "case-create-form", "source-upload-form", "question-form", "draft-form",
    "model-investigation-form", "evidence-import-form", "evidence-assessment-form",
    "evidence-withdraw-form", "option-form", "option-dependency-form",
    "option-task-form", "option-threat-form", "option-review-form",
    "bibliography-form", "literature-search-form", "import-form",
)
WATCHED_IDS = FORM_IDS + (
    "case-heading", "event-list", "source-list", "question-list", "snapshot-list",
    "model-investigation-question", "source-choice", "evidence-choice",
    "source-file", "source-upload-preview", "source-dialog", "compare-dialog",
    "patient-mission", "world-model-detail",
)
GUARDED_FIELDS = (
    "draft-observations", "draft-summary", "draft-assumptions", "evidence-rationale",
    "evidence-withdraw-reason", "option-description",
)
CLINICIAN_GLOBAL = ("workspace", "patients", "overview", "research", "setup")
CHART_PAGES = ("overview", "timeline", "documents", "investigations", "evidence", "options", "updates")
PATIENT_PAGES = ("home", "records", "questions", "documents", "updates", "setup")
QUESTIONS = (
    "Which original Alpha source needs clarification in this fictional navigation journey?",
    "What uncertainty remains in the second fictional Alpha source-review question?",
)
PREVIEW_TEXT = (
    "OI-SYNTHETIC-REPORT/1\nPatient: CASE-ALPHA\nDocument: NAV-PREVIEW\n"
    "Type: pathology\nEvent-Date: 2026-01-07\nIssued-At: 2026-01-08\n"
    "Specimen: NAV-FICTIONAL\n"
    "Finding: navigation-marker|not-reported|An independently authored fictional "
    "marker was not tested; café <script>literal source text</script>.\n"
)


class RecordedChromeSession(ChromeSession):
    """Keep useful CDP events while the existing helper awaits command replies."""

    def __init__(self, websocket_url: str):
        self.requests: list[dict] = []
        self.browser_errors: list[dict] = []
        self.browser_log: list[dict] = []
        super().__init__(websocket_url)

    def receive_frame(self) -> bytes | None:
        frame = super().receive_frame()
        if frame is not None:
            message = json.loads(frame)
            params = message.get("params", {})
            method = message.get("method")
            if method == "Network.requestWillBeSent":
                request = params["request"]
                parsed = urlsplit(request["url"])
                if parsed.path.startswith("/api/"):
                    self.requests.append({"method": request["method"], "path": parsed.path})
            elif method == "Runtime.exceptionThrown":
                self.browser_errors.append({"kind": "uncaught", "details": params["exceptionDetails"]})
            elif method == "Runtime.consoleAPICalled" and params.get("type") == "error":
                self.browser_errors.append({
                    "kind": "console.error",
                    "arguments": [argument.get("value", argument.get("description"))
                                  for argument in params.get("args", [])],
                })
            elif method == "Log.entryAdded" and params.get("entry", {}).get("level") == "error":
                entry = params["entry"]
                self.browser_log.append({key: entry.get(key) for key in ("source", "text", "url")})
        return frame


def browser_executable() -> str:
    selected = os.environ.get("OI_CHROME_EXECUTABLE")
    if selected:
        candidate = shutil.which(selected)
        if candidate:
            return candidate
        raise AssertionError(f"OI_CHROME_EXECUTABLE is not executable: {selected}; browser journey NOT verified")
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        candidate = shutil.which(name)
        if candidate:
            return candidate
    raise AssertionError(
        "No Chrome/Chromium executable on the runner; browser journey NOT verified. "
        "Install a browser or set OI_CHROME_EXECUTABLE."
    )


def stop_process(process: subprocess.Popen | None, *, process_group: bool = False) -> None:
    if process is None:
        return
    try:
        if process_group:
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            if process_group:
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
        except ProcessLookupError:
            pass
        process.wait(timeout=5)


class NavigationJourney:
    def __init__(self, cd: RecordedChromeSession, url: str, output: Path, temporary: Path, report: dict):
        self.cd, self.url, self.output, self.temporary, self.report = cd, url, output, temporary, report

    def check(self, condition, label: str, details=None) -> None:
        entry = {"check": label, "passed": bool(condition)}
        if details is not None:
            entry["details"] = details
        self.report["checks"].append(entry)
        if not condition:
            raise AssertionError(f"{label}: {details}" if details is not None else label)

    def js(self, expression: str, *arguments):
        if arguments or expression.lstrip().startswith("() =>"):
            expression = "(" + expression + ")(" + ",".join(json.dumps(arg) for arg in arguments) + ")"
        return self.cd.evaluate(expression)

    def settle(self) -> None:
        self.js("new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(resolve, 100))))")

    def state(self, case: str = "CASE-ALPHA") -> dict:
        with urlopen(self.url + "api/cases/" + case + "/state", timeout=5) as response:
            return json.load(response)

    def ready(self, case: str = "CASE-ALPHA") -> None:
        self.cd.wait(
            "document.body?.dataset.workspaceState === 'ready' && "
            "document.querySelector('#case-picker')?.value === " + json.dumps(case) +
            " && document.querySelector('#source-list .source-card') !== null",
            "selected fictional case and connected entry host",
        )
        self.js("""window.__oiNavigationVisible = element => !!element &&
          !element.closest('[hidden], [inert]') && element.getClientRects().length > 0 &&
          getComputedStyle(element).visibility !== 'hidden'""")
        self.settle()

    def open_ancestors(self, selector: str) -> None:
        self.js("""selector => {
          const item = document.querySelector(selector);
          if (!item) throw Error('Missing control: ' + selector);
          const parents = [];
          for (let parent = item.parentElement; parent; parent = parent.parentElement)
            if (parent.tagName === 'DETAILS' && !parent.open) parents.unshift(parent);
          for (const parent of parents) parent.querySelector(':scope > summary').click();
        }""", selector)

    def click_nav(self, page: str, *, chart: bool = False) -> None:
        selector = ("#chart-navigation" if chart else "#workspace-nav") + ' a[href="#' + page + '"]'
        self.open_ancestors(selector)
        self.check(self.js("selector => window.__oiNavigationVisible(document.querySelector(selector))", selector),
                   "Navigation link is exposed: " + page)
        self.js("selector => { const link = document.querySelector(selector); link.focus(); link.click(); }", selector)
        self.assert_page(page)

    def mode(self, audience: str) -> None:
        self.js("""audience => {
          const control = document.querySelector('#experience-picker');
          control.value = audience; control.dispatchEvent(new Event('change', {bubbles:true}));
        }""", audience)
        self.cd.wait("document.documentElement.dataset.audience === " + json.dumps(audience), audience + " preview")

    def press_key(self, key: str, key_code: int) -> None:
        # Match the existing ui_glance_journey native-disclosure keyboard flow:
        # Enter requires its character/keypress event to activate a summary.
        events = ("rawKeyDown", "char", "keyUp") if key == "Enter" else ("keyDown", "keyUp")
        for event_type in events:
            event = {
                "type": event_type, "key": key, "code": key,
                "windowsVirtualKeyCode": key_code, "nativeVirtualKeyCode": key_code,
            }
            if event_type == "char":
                event.update({"text": "\r", "unmodifiedText": "\r"})
            self.cd.command("Input.dispatchKeyEvent", event)

    def mobile_keyboard(self, audience: str) -> None:
        # Do not open the menu with the DOM navigation helpers: that hid the
        # former Tab trap, which prevented default and focused a hidden link.
        self.check(self.js("innerWidth === 390 && !document.querySelector('.section-menu').open"),
                   "390px keyboard journey starts with the mobile menu closed: " + audience)
        self.js("document.querySelector('#case-picker').focus()")
        self.press_key("Tab", 9)
        focus = self.js("""() => ({
          id:document.activeElement.id, tag:document.activeElement.tagName,
          summary:document.activeElement === document.querySelector('.section-menu > summary'),
          visible:window.__oiNavigationVisible(document.activeElement),
          open:document.querySelector('.section-menu').open
        })""")
        self.check(focus["summary"] and focus["visible"] and not focus["open"],
                   "Real Tab moves from the case picker to the visible closed-menu summary: " + audience, focus)
        self.press_key("Enter", 13)
        self.cd.wait("document.querySelector('.section-menu').open", "native Enter opens mobile navigation")
        self.check(self.js("document.activeElement === document.querySelector('.section-menu > summary')"),
                   "Native Enter opens the menu while retaining summary focus: " + audience)
        self.press_key("Tab", 9)
        self.check(self.js("document.activeElement === document.querySelector('#workspace-nav a') && window.__oiNavigationVisible(document.activeElement)"),
                   "The next real Tab reaches the first visible navigation link: " + audience)

    def assert_page(self, page: str) -> None:
        self.cd.wait(
            "[...document.querySelectorAll('.workspace-page[data-page]')]"
            ".filter(page => !page.hidden && !page.inert).map(page => page.dataset.page).join(',') === " + json.dumps(page),
            "only the " + page + " page is active",
        )
        result = self.js("""() => {
          const pages = [...document.querySelectorAll('.workspace-page[data-page]')];
          const active = pages.filter(window.__oiNavigationVisible);
          const inactive = pages.filter(page => !active.includes(page));
          const badFocus = [];
          for (const page of inactive) {
            const control = page.querySelector('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), summary');
            if (control) { control.focus(); if (document.activeElement === control) badFocus.push(page.dataset.page); }
          }
          return {visible:active.map(page => page.dataset.page),
            unprotected:inactive.filter(page => !page.hidden || !page.inert).map(page => page.dataset.page),
            badFocus, audience:document.documentElement.dataset.audience,
            localVisible:window.__oiNavigationVisible(document.querySelector('#chart-navigation')),
            globalCurrent:[...document.querySelectorAll('#workspace-nav a[aria-current]')].map(link => link.hash.slice(1)),
            localCurrent:[...document.querySelectorAll('#chart-navigation a[aria-current]')].map(link => link.hash.slice(1))};
        }""")
        self.check(result["visible"] == [page], "Exactly one rendered page: " + page, result["visible"])
        self.check(not result["unprotected"] and not result["badFocus"],
                   "Inactive pages are hidden, inert and reject focus: " + page, result)
        self.check(result["localVisible"] == (result["audience"] == "clinician" and page in CHART_PAGES),
                   "Chart navigation is scoped to the selected chart: " + page)
        global_page = "overview" if result["audience"] == "clinician" and page in CHART_PAGES else page
        self.check(result["globalCurrent"] == [global_page] and
                   (not result["localVisible"] or result["localCurrent"] == [page]),
                   "Current destinations are announced in their own navigation: " + page, result)

    def navigate_chart(self, page: str) -> None:
        self.mode("clinician")
        self.click_nav("overview")
        if page != "overview":
            self.click_nav(page, chart=True)

    def submit(self, form: str, values: dict) -> None:
        self.open_ancestors("#" + form)
        self.check(self.js("id => window.__oiNavigationVisible(document.getElementById(id))", form),
                   "Original form is visible before submission: " + form)
        self.js("""(form, values) => {
          for (const [id, value] of Object.entries(values)) {
            const control = document.getElementById(id);
            if (!control) throw Error('Missing original input: ' + id);
            control.value = value; control.dispatchEvent(new Event('input', {bubbles:true}));
            if (control.tagName === 'SELECT') control.dispatchEvent(new Event('change', {bubbles:true}));
          }
          const target = document.getElementById(form);
          if (!target.checkValidity()) throw Error('Original form validation failed: ' + form);
          target.requestSubmit();
        }""", form, values)

    def inventory(self) -> None:
        result = self.js("""() => {
          const ids = [...document.querySelectorAll('[id]')].map(element => element.id);
          return {forms:[...document.forms].map(form => form.id).sort(),
            duplicates:ids.filter((id, index) => ids.indexOf(id) !== index),
            detached:[...document.forms].filter(form => !form.isConnected).map(form => form.id),
            dialogs:['source-dialog','compare-dialog'].every(id => !document.getElementById(id).closest('.workspace-page'))};
        }""")
        self.check(result["forms"] == sorted(FORM_IDS), "All 16 original forms remain connected", result["forms"])
        self.check(not result["duplicates"] and not result["detached"], "Control IDs are unique and forms are attached", result)
        self.check(result["dialogs"], "Original source dialogs remain outside hidden pages")

    def capture(self, filename: str, *, navigation_open: bool = False) -> None:
        if not navigation_open:
            self.js("""if (matchMedia('(max-width: 60rem)').matches) {
              const menu = document.querySelector('.section-menu'); if (menu) menu.open = false;
            }""")
        self.js("window.scrollTo(0, 0)")
        self.settle()
        shot = self.cd.command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
        (self.output / filename).write_bytes(base64.b64decode(shot["data"]))
        self.report["screenshots"].append(filename)

    def edit_state(self) -> dict:
        return self.js("""() => ({
          controls:[...document.querySelectorAll('form input, form select, form textarea')].map(control => ({
            form:control.form.id, id:control.id, type:control.type, value:control.value,
            checked:control.checked, files:control.files ? [...control.files].map(file => ({name:file.name,size:file.size,type:file.type})) : null
          })).sort((a,b) => JSON.stringify(a).localeCompare(JSON.stringify(b))),
          preview:document.querySelector('#source-upload-preview').textContent,
          previewHidden:document.querySelector('#source-preview-details').hidden,
          disclosures:['source-intake','source-preview-details','world-model-detail','evidence-tools']
            .map(id => ({id,open:document.getElementById(id).open}))
        })""")

    def run(self) -> None:
        self.report["stage"] = "initial navigation and real form submissions"
        self.ready()
        self.check(self.js("document.body.classList.contains('workspace-shell')"), "Connected host mounts the new shell")
        self.assert_page("workspace")
        self.check(self.js("document.documentElement.dataset.audience") == "clinician", "Initial preview is clinician")
        self.inventory()
        self.js("""ids => { window.__oiNavigationNodes = ids.map(id => [id, document.getElementById(id)]); }""", WATCHED_IDS)
        self.check(self.js("""(() => {
          const global = document.querySelector('#workspace-nav'), local = document.querySelector('#chart-navigation');
          return global !== local && !global.contains(local) && !local.contains(global) &&
            global.getAttribute('aria-label') !== local.getAttribute('aria-label');
        })()"""), "Global and chart navigation are distinct labelled landmarks")
        self.check(self.js("[...document.querySelectorAll('#workspace-nav a')].map(a => a.hash.slice(1))") == list(CLINICIAN_GLOBAL),
                   "Clinician global navigation has the agreed destinations")

        self.mode("patient")
        self.click_nav("home")
        self.check(self.js("[...document.querySelectorAll('#workspace-nav a')].map(a => a.hash.slice(1))") == list(PATIENT_PAGES),
                   "Patient global navigation has the agreed destinations")
        self.check(self.js("[...document.querySelectorAll('form')].filter(window.__oiNavigationVisible).length") == 0,
                   "Patient Home exposes no clinical authoring forms")
        self.click_nav("questions")
        before = self.state()
        for question in QUESTIONS:
            self.submit("question-form", {"question-text": question})
            self.cd.wait("document.querySelector('#question-list').textContent.includes(" + json.dumps(question) + ")",
                         "patient question persisted and rendered")
        created = self.state()
        self.check(len(created["questions"]) == len(before["questions"]) + 2,
                   "Patient question submissions persist through the real backend")
        question_ids = {question["question"]: question["id"] for question in created["questions"]}
        question_id = question_ids[QUESTIONS[1]]
        self.check(all(question in question_ids for question in QUESTIONS), "Exact authored question text survives persistence")
        self.check(not self.js("window.__oiNavigationVisible(document.querySelector('#draft-form'))") and
                   not self.js("window.__oiNavigationVisible(document.querySelector('#model-investigation-form'))"),
                   "Patient Questions exposes questions and reports without clinician authoring forms")

        self.navigate_chart("evidence")
        self.submit("evidence-import-form", {"evidence-text": (ROOT / "examples/synthetic/demo-evidence.txt").read_text()})
        self.cd.wait("document.querySelectorAll('#evidence-source-choice option').length === 1", "original fictional evidence registered")
        evidence_id = self.js("document.querySelector('#evidence-source-choice').value")
        self.submit("evidence-assessment-form", {
            "evidence-question-choice": str(question_id), "evidence-source-choice": evidence_id,
            "evidence-relation": "context", "evidence-applicability": "limited",
            "evidence-rationale": "Independently authored context for a navigation regression; no clinical applicability is established.",
        })
        self.cd.wait("document.querySelectorAll('#evidence-assessment-list .finding').length === 1", "real fictional assessment")
        self.click_nav("investigations", chart=True)
        self.submit("draft-form", {
            "question-choice": str(question_id),
            "draft-observations": "The original fictional Alpha reports need source review; this saved draft makes no clinical conclusion.",
            "draft-assumptions": "Source wording and uncertainty remain inspectable in their original versions.",
        })
        self.cd.wait("document.querySelectorAll('#snapshot-list .snapshot').length === 1", "source-bound draft persisted")
        saved = self.state()
        self.check(len(saved["snapshots"]) == 1 and saved["snapshots"][0]["question_id"] == question_id,
                   "Original clinician draft handler remains connected after patient preview")
        snapshot_id = saved["snapshots"][0]["id"]

        self.report["stage"] = "same-case input, node and source-preview preservation"
        self.js("""qid => {
          const question = document.querySelector('#question-choice'); question.value = String(qid);
          question.dispatchEvent(new Event('change', {bubbles:true}));
          document.querySelectorAll('#source-choice input').forEach((input,index) => input.checked = index === 0);
          document.querySelectorAll('#evidence-choice input').forEach(input => input.checked = true);
          const model = document.querySelector('#model-investigation-question');
          model.value = [...model.options].find(option => option.value !== model.value).value;
          model.dispatchEvent(new Event('change', {bubbles:true}));
          document.querySelector('#question-text').value = 'Unsaved Alpha question preserved across destinations.';
          document.querySelector('#draft-observations').value = 'Unsaved Alpha-only observations must stay in this original form.';
          document.querySelector('#draft-summary').value = 'An unsubmitted fictional hypothesis, not a clinical finding.';
          document.querySelector('#draft-assumptions').value = 'Keep missing and uncertain source states distinct.';
        }""", question_id)
        self.cd.wait("document.querySelector('#composer-context-fingerprint').value.length === 64 && !document.querySelector('#model-investigation-run').disabled",
                     "non-default Composer question has genuine current source context")
        self.check(self.js("document.querySelectorAll('#evidence-choice input:checked').length") == 1,
                   "Preservation fixture includes a real selected evidence assessment")
        self.click_nav("evidence", chart=True)
        self.open_ancestors("#evidence-rationale")
        self.open_ancestors("#evidence-withdraw-reason")
        self.js("""document.querySelector('#evidence-rationale').value = 'Unsaved Alpha assessment rationale remains on the same case.';
          document.querySelector('#evidence-withdraw-reason').value = 'Unsubmitted fictional withdrawal reason.'""")
        self.click_nav("options", chart=True)
        self.open_ancestors("#option-description")
        self.js("document.querySelector('#option-description').value = 'Unsaved fictional discussion item; no recommendation or order.'")
        self.click_nav("documents", chart=True)
        self.open_ancestors("#report-text")
        self.open_ancestors("#source-file")
        self.js("text => document.querySelector('#report-text').value = text", PREVIEW_TEXT)
        source = self.temporary / "navigation-original-preview.txt"
        source.write_text(PREVIEW_TEXT, encoding="utf-8", newline="")
        document = self.cd.command("DOM.getDocument")
        file_node = self.cd.command("DOM.querySelector", {"nodeId": document["root"]["nodeId"], "selector": "#source-file"})
        self.cd.command("DOM.setFileInputFiles", {"files": [str(source)], "nodeId": file_node["nodeId"]})
        self.cd.wait("!document.querySelector('#source-preview-details').hidden", "real disk-file preview decoded locally")
        self.check(self.js("document.querySelector('#source-upload-preview').textContent") == PREVIEW_TEXT,
                   "Preview preserves original UTF-8 and LF text")
        self.check(self.js("document.querySelectorAll('#source-upload-preview script').length") == 0,
                   "Source markup remains literal text")
        self.js("""document.querySelector('#source-preview-details').open = true;
          document.querySelector('#source-upload-confirm').click();
          document.querySelector('#world-model-detail').open = true;
          document.querySelector('#evidence-tools').open = true;
          window.__oiNavigationControlNodes = [...document.querySelectorAll('form input, form select, form textarea')];""")
        self.settle()
        inputs = self.edit_state()
        stored = self.state()
        sequence = self.js("refreshSequence")
        request_index = len(self.cd.requests)
        for page in CLINICIAN_GLOBAL:
            self.click_nav(page)
            if page == "overview":
                for chart in CHART_PAGES:
                    self.click_nav(chart, chart=True)
        self.mode("patient")
        for page in PATIENT_PAGES:
            self.click_nav(page)
        self.mode("clinician")
        self.click_nav("overview")
        self.click_nav("investigations", chart=True)

        # A same-case Open action is navigation, including when only unguarded
        # question/import fields and a source file are pending. Leaving guarded
        # narratives populated would mask an accidental case-change refresh.
        guarded_values = self.js("ids => Object.fromEntries(ids.map(id => [id, document.getElementById(id).value]))", GUARDED_FIELDS)
        self.js("ids => ids.forEach(id => document.getElementById(id).value = '')", GUARDED_FIELDS)
        for origin, rows in (("workspace", "#recent-patients .dashboard-row"), ("patients", "#incoming-list .question")):
            self.click_nav(origin)
            before_open = self.edit_state()
            before_sequence = self.js("refreshSequence")
            before_requests = len(self.cd.requests)
            self.check(self.js("""selector => {
              const row = [...document.querySelectorAll(selector)].find(row => row.textContent.includes('CASE-ALPHA'));
              return window.__oiNavigationVisible(row?.querySelector('button'));
            }""", rows), "Selected Alpha has a visible original Open action in " + origin)
            self.js("""selector => [...document.querySelectorAll(selector)]
              .find(row => row.textContent.includes('CASE-ALPHA')).querySelector('button').click()""", rows)
            self.ready()
            self.assert_page("overview")
            self.check(self.edit_state() == before_open,
                       "Opening the selected case from " + origin + " preserves unguarded fields, selections and the source preview")
            self.check(self.js("refreshSequence") == before_sequence,
                       "Opening the selected case from " + origin + " does not refresh the case")
            self.check(not [request for request in self.cd.requests[before_requests:] if request["path"].endswith("/state")],
                       "Opening the selected case from " + origin + " does not request case state")
        self.js("values => Object.entries(values).forEach(([id,value]) => document.getElementById(id).value = value)", guarded_values)
        self.click_nav("investigations", chart=True)
        self.settle()
        self.check(self.edit_state() == inputs, "Every original form value, question, binding, disclosure and selected file survives navigation")
        self.check(self.js("window.__oiNavigationNodes.every(([id, element]) => element.isConnected && document.getElementById(id) === element)"),
                   "All original forms and observer targets retain exact DOM identity")
        self.check(self.js("window.__oiNavigationControlNodes.every(element => element.isConnected)"),
                   "Navigation retains original controls, including selected source and evidence checkboxes")
        self.check(self.js("refreshSequence") == sequence, "Page and preview navigation never refresh the case")
        navigation_requests = self.cd.requests[request_index:]
        self.check(not [request for request in navigation_requests if request["method"] not in {"GET", "HEAD", "OPTIONS"}],
                   "Page and preview navigation issue no API writes", navigation_requests)
        self.check(not [request for request in navigation_requests if request["path"].endswith("/state")],
                   "Page and preview navigation do not reload case state", navigation_requests)
        self.check(self.state() == stored, "Navigation leaves durable case state unchanged")
        self.inventory()

        self.report["stage"] = "local search and guarded case switching"
        self.click_nav("patients")
        self.js("""value => { const search = document.querySelector('#patient-search'); search.value = value;
          search.dispatchEvent(new Event('input', {bubbles:true})); }""", "case-beta")
        rows = "[...document.querySelectorAll('#incoming-list .question')].filter(window.__oiNavigationVisible)"
        self.check(self.js(rows + ".length") == 1 and self.js(rows + "[0].textContent.includes('CASE-BETA')"),
                   "Patient search filters existing case references locally, without case sensitivity")
        self.js("""(() => { const search = document.querySelector('#patient-search'); search.value = 'no-such-fictional-workspace';
          search.dispatchEvent(new Event('input', {bubbles:true})); })()""")
        self.check(self.js(rows + ".length") == 0 and self.js("/no.+match/i.test(document.querySelector('#patient-search-count').textContent)"),
                   "No-match patient search gives explicit empty-state feedback")
        self.js("""(() => { const search = document.querySelector('#patient-search'); search.value = '';
          search.dispatchEvent(new Event('input', {bubbles:true})); })()""")
        self.check(self.js(rows + ".length") == 2, "Clearing search restores both original patient cards")
        self.js("""[...document.querySelectorAll('#incoming-list .question')]
          .find(row => row.textContent.includes('CASE-BETA')).querySelector('button').click()""")
        self.cd.wait("document.querySelector('#notice').textContent.includes('unfinished investigation draft')", "existing dirty-draft guard veto")
        self.check(self.js("document.querySelector('#case-picker').value") == "CASE-ALPHA" and
                   self.js("document.querySelector('#draft-observations').value").startswith("Unsaved Alpha-only"),
                   "Rejected case switch retains Alpha and its unsaved narrative")
        self.check(self.js("window.__oiNavigationVisible(document.querySelector('#notice'))"), "Guard feedback is visible from the patient directory")
        self.js("ids => ids.forEach(id => document.getElementById(id).value = '')", GUARDED_FIELDS)
        self.js("""[...document.querySelectorAll('#incoming-list .question')]
          .find(row => row.textContent.includes('CASE-BETA')).querySelector('button').click()""")
        self.ready("CASE-BETA")
        self.check(self.js("document.querySelector('#source-list').textContent.includes('PATH-BETA') && !document.querySelector('#source-list').textContent.includes('ALPHA')"),
                   "Accepted switch renders only Beta source records")
        self.check(self.js("document.querySelector('#question-text').value === '' && document.querySelector('#report-text').value === '' && document.querySelector('#question-choice').options.length === 0"),
                   "Accepted switch clears unsaved question/import fields and previous question choices")
        self.check(self.js("document.querySelector('#source-file').files.length === 0 && document.querySelector('#source-upload-preview').textContent === '' && !document.querySelector('#source-upload-confirm').checked && document.querySelector('#source-upload-submit').disabled"),
                   "Accepted switch clears previous-case file preview and import confirmation")
        self.check(self.js("document.querySelector('#composer-context-fingerprint').value === '' && document.querySelector('#model-investigation-run').disabled"),
                   "No previous-case Composer fingerprint remains usable on Beta")
        self.check(not self.js("document.querySelector('#question-list').textContent.includes('Alpha')"), "No Alpha question remains in Beta's rendered chart")
        self.js("""(() => { const picker = document.querySelector('#case-picker'); picker.value = 'CASE-ALPHA';
          picker.dispatchEvent(new Event('change', {bubbles:true})); })()""")
        self.ready()
        self.check(self.state() == stored, "Alpha's persisted questions, sources, evidence and saved report survive case switching")

        self.report["stage"] = "source dialogs, browser history and legacy deep links"
        self.navigate_chart("overview")
        self.js("(() => { const action = document.querySelector('#assertion-list .source-jump'); action.focus(); action.click(); })()")
        self.cd.wait("document.querySelector('#source-dialog').open && document.querySelector('#dialog-text mark.source-highlight') !== null", "exact source-line dialog")
        self.check(self.js("document.querySelector('#dialog-text mark').textContent.includes('Finding:')"), "Source action retains exact authored finding highlight")
        self.check(self.js("document.querySelector('#dialog-text').textContent.startsWith('OI-SYNTHETIC-REPORT/1')"), "Source viewer retains original report text")
        self.capture("clinician-source-dialog-1440.png")
        self.cd.command("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27})
        self.cd.command("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27})
        self.cd.wait("!document.querySelector('#source-dialog').open", "native Escape closes the original source dialog")
        self.click_nav("timeline", chart=True)
        self.click_nav("documents", chart=True)
        self.js("history.back()")
        self.assert_page("timeline")
        self.js("history.back()")
        self.assert_page("overview")
        self.js("history.forward()")
        self.assert_page("timeline")
        self.js("history.forward()")
        self.assert_page("documents")
        for fragment, page, audience in (
            ("#patient-view", "records", "patient"), ("#patient-mission", "records", "patient"),
            ("#sources", "documents", "patient"), ("#source-intake", "documents", "patient"),
            ("#import", "documents", "patient"), ("#incoming-board", "patients", "clinician"),
            ("#assertions", "overview", "clinician"), ("#patient-mission", "overview", "clinician"),
            ("#world-model-detail", "overview", "clinician"),
            ("#model-investigation-heading", "investigations", "clinician"),
            ("#workspace-start", "setup", "clinician"), ("#bibliography", "research", "clinician"),
        ):
            self.js("hash => location.hash = hash", fragment)
            self.assert_page(page)
            self.check(self.js("document.documentElement.dataset.audience") == audience, "Legacy link selects the appropriate experience: " + fragment)
            self.check(self.js("id => window.__oiNavigationVisible(document.getElementById(id))", fragment[1:]),
                       "Legacy target is revealed, including containing disclosures: " + fragment)
        self.navigate_chart("investigations")
        self.js("hash => location.hash = hash", "#snapshot-" + str(snapshot_id))
        self.assert_page("investigations")
        self.js("window.__oiBeforeNavigationReload = true")
        self.cd.command("Page.reload")
        self.cd.wait("window.__oiBeforeNavigationReload !== true && document.body?.dataset.workspaceState === 'ready'", "fresh document on a saved-report deep link")
        self.ready()
        self.assert_page("investigations")
        self.cd.wait("document.activeElement?.id === " + json.dumps("snapshot-" + str(snapshot_id)),
                     "late-rendered saved report receives deep-link focus after reload")
        self.check(self.js("id => { const r = document.getElementById(id).getBoundingClientRect(); return r.top >= -1 && r.top < innerHeight; }", "snapshot-" + str(snapshot_id)),
                   "Reload reveals the saved report after its asynchronous case render")
        self.mode("patient")
        self.click_nav("home")
        self.js("hash => location.hash = hash", "#snapshot-" + str(snapshot_id))
        self.assert_page("questions")
        self.check(self.js("id => window.__oiNavigationVisible(document.getElementById(id))", "snapshot-" + str(snapshot_id)),
                   "Saved-report fragment reveals the same report in patient Questions")
        self.js("location.hash = '#patient-view'; window.__oiBeforeNavigationReload = true")
        self.cd.command("Page.reload")
        self.cd.wait("window.__oiBeforeNavigationReload !== true && document.body?.dataset.workspaceState === 'ready'", "fresh document on a legacy patient link")
        self.ready()
        self.assert_page("records")
        self.check(self.js("document.documentElement.dataset.audience") == "patient", "Direct legacy patient link survives reload")

        # Unlike a same-document hash change, startup must wait for the original
        # case render/entry adapter before revealing nested disclosure targets.
        for target_id, page, audience in (
            ("source-intake", "documents", "patient"),
            ("world-model-detail", "overview", "clinician"),
            ("world-model-detail", "records", "patient"),
            ("new-case-panel", "setup", "patient"),
        ):
            self.mode(audience)
            self.js("""hash => { location.hash = hash; window.__oiBeforeNavigationReload = true; }""", "#" + target_id)
            self.cd.command("Page.reload")
            self.cd.wait("window.__oiBeforeNavigationReload !== true && document.body?.dataset.workspaceState === 'ready'",
                         "fresh document on disclosure deep link " + target_id)
            self.ready()
            self.assert_page(page)
            self.check(self.js("document.documentElement.dataset.audience") == audience,
                       "Disclosure reload retains its preview experience: #" + target_id + " / " + audience)
            disclosure = self.js("""id => {
              const target = document.getElementById(id), details = [];
              for (let item = target; item; item = item.parentElement)
                if (item.tagName === 'DETAILS') details.push({id:item.id || '(record group)', open:item.open});
              return {details, visible:window.__oiNavigationVisible(target),
                inactive:!!target.closest('[hidden], [inert]')};
            }""", target_id)
            self.check(disclosure["visible"] and not disclosure["inactive"] and
                       bool(disclosure["details"]) and all(item["open"] for item in disclosure["details"]),
                       "Direct reload opens the target and every disclosure ancestor: #" + target_id, disclosure)

        # A skip fragment present at startup must initialize the shell before
        # later skip-link clicks use the existing focus-only shortcut.
        for audience, landing, destinations in (("clinician", "workspace", CLINICIAN_GLOBAL), ("patient", "home", PATIENT_PAGES)):
            self.mode(audience)
            self.js("location.hash = '#main-content'; window.__oiBeforeNavigationReload = true")
            self.cd.command("Page.reload")
            self.cd.wait("window.__oiBeforeNavigationReload !== true && document.body?.dataset.workspaceState === 'ready'",
                         "fresh document on initial skip fragment in " + audience + " preview")
            self.ready()
            self.assert_page(landing)
            self.check(self.js("document.body.classList.contains('workspace-shell')") and
                       self.js("document.documentElement.dataset.audience") == audience and
                       self.js("[...document.querySelectorAll('#workspace-nav a')].map(link => link.hash.slice(1))") == list(destinations),
                       "Direct #main-content initializes the correct preview, landing page and navigation: " + audience)
            before_skip = self.js("refreshSequence")
            self.js("""(() => { const skip = document.querySelector('a.skip-link[href="#main-content"]');
              skip.focus(); skip.click(); })()""")
            self.cd.wait("document.activeElement?.id === 'main-content'", "skip link focuses the existing main landmark")
            self.check(self.js("document.body.dataset.page") == landing and self.js("refreshSequence") == before_skip,
                       "An initialized skip link focuses main without navigating or refreshing: " + audience)
        self.inventory()

        self.report["stage"] = "desktop and narrow-width navigation"
        for width, height in ((1440, 1000), (390, 844), (320, 740)):
            self.cd.command("Emulation.setDeviceMetricsOverride", {
                "width": width, "height": height, "deviceScaleFactor": 1, "mobile": False,
            })
            self.cd.wait("window.innerWidth === " + str(width), "viewport width " + str(width))
            for audience, pages in (("clinician", CLINICIAN_GLOBAL), ("patient", PATIENT_PAGES)):
                self.mode(audience)
                if width == 390:
                    self.mobile_keyboard(audience)
                for page in pages:
                    self.click_nav(page)
                    self.check_layout(width, audience, page)
                    if width < 1440 and page in {"workspace", "home"}:
                        self.capture(f"{audience}-navigation-{width}.png", navigation_open=True)
                    if page in {"workspace", "overview", "home", "records", "questions"}:
                        self.capture(f"{audience}-{page}-{width}.png")
                    if audience == "clinician" and page == "overview":
                        for chart in CHART_PAGES[1:]:
                            self.click_nav(chart, chart=True)
                            if chart == "documents":
                                self.open_ancestors("#source-file")
                            if chart == "investigations":
                                self.open_ancestors("#draft-observations")
                            self.check_layout(width, audience, chart)
                            if chart in {"documents", "investigations"}:
                                self.capture(f"{audience}-{chart}-{width}.png")
            self.check(self.js("[...document.querySelectorAll('form input, form select, form textarea')].every(control => control.isConnected)"),
                       f"All original controls remain attached at {width}px")
        self.inventory()
        self.settle()
        expected_writes = [
            {"method": "POST", "path": "/api/cases/CASE-ALPHA/questions"},
            {"method": "POST", "path": "/api/cases/CASE-ALPHA/questions"},
            {"method": "POST", "path": "/api/evidence/imports"},
            {"method": "POST", "path": "/api/cases/CASE-ALPHA/evidence-assessments"},
            {"method": "POST", "path": "/api/cases/CASE-ALPHA/snapshots"},
        ]
        actual_writes = [request for request in self.cd.requests if request["method"] not in {"GET", "HEAD", "OPTIONS"}]
        self.check(actual_writes == expected_writes,
                   "Only the five explicit original form submissions wrote to the API in the entire journey", actual_writes)
        self.check(self.state() == stored, "History, reloads, case switching and responsive navigation preserve durable Alpha state")
        self.check(not self.cd.browser_errors, "No uncaught JavaScript exceptions or console errors", self.cd.browser_errors)
        self.report["stage"] = "complete"

    def check_layout(self, width: int, audience: str, page: str) -> None:
        self.open_ancestors("#workspace-nav")
        self.settle()
        result = self.js("""() => {
          const clipped = [];
          for (const control of document.querySelectorAll('button, input:not([type=hidden]), select, textarea, summary, nav a')) {
            if (!window.__oiNavigationVisible(control)) continue;
            let rect = control.getBoundingClientRect();
            if (rect.left < -1 || rect.right > innerWidth + 1) {
              // A deliberate internal scrolling navigation remains usable when
              // its focused link can be brought fully into view.
              control.scrollIntoView({block:'nearest',inline:'nearest'});
              rect = control.getBoundingClientRect();
              if (rect.left < -1 || rect.right > innerWidth + 1)
                clipped.push({id:control.id,tag:control.tagName,text:control.textContent.trim().slice(0,70),left:rect.left,right:rect.right});
            }
          }
          return {width:innerWidth,scrollWidth:document.documentElement.scrollWidth,clipped,
            previewVisible:window.__oiNavigationVisible(document.querySelector('#experience-picker')),
            caseVisible:window.__oiNavigationVisible(document.querySelector('#case-picker')),
            globalLinks:[...document.querySelectorAll('#workspace-nav a')].filter(window.__oiNavigationVisible).length};
        }""")
        result.update({"audience": audience, "page": page})
        self.report["responsive"].append(result)
        self.check(result["scrollWidth"] <= width + 1 and not result["clipped"],
                   f"Page and controls fit {width}px: {audience}/{page}", result)
        self.check(result["previewVisible"] and result["caseVisible"] and
                   result["globalLinks"] == len(PATIENT_PAGES if audience == "patient" else CLINICIAN_GLOBAL),
                   f"Case, preview and all global destinations are reachable at {width}px: {audience}/{page}")


def main() -> None:
    output = Path(os.environ.get("OI_UI_ARTIFACT_DIR", ROOT / ".ui-artifacts" / "navigation")).resolve()
    output.mkdir(parents=True, exist_ok=True)
    report = {
        "scope": "Independently authored fictional inputs; real composed host and handlers; no live services",
        "status": "running", "stage": "browser startup", "checks": [], "screenshots": [], "responsive": [],
    }
    browser = server = cd = None
    try:
        chrome = browser_executable()
        with tempfile.TemporaryDirectory(prefix="oi-navigation-", ignore_cleanup_errors=True) as temporary:
            temporary = Path(temporary)
            app_port, debug_port = free_port(), free_port()
            url = f"http://127.0.0.1:{app_port}/"
            env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
            with (output / "navigation-server.log").open("w") as server_log, (output / "navigation-browser.log").open("w") as browser_log:
                try:
                    server = subprocess.Popen([
                        sys.executable, str(ROOT / "run_open_intelligence.py"), "--db", str(temporary / "case.sqlite"),
                        "--port", str(app_port), "--with-examples",
                    ], cwd=ROOT, env=env, stdout=server_log, stderr=subprocess.STDOUT)
                    wait_for(lambda: urlopen(url, timeout=1).status == 200, "connected seeded workspace server")
                    flags = [
                        chrome, "--headless=new", "--disable-gpu", "--disable-dev-shm-usage",
                        "--disable-background-networking", "--no-first-run", "--disable-extensions",
                        "--no-default-browser-check", "--remote-allow-origins=*",
                        f"--remote-debugging-port={debug_port}", f"--user-data-dir={temporary / 'chrome'}",
                    ]
                    if hasattr(os, "geteuid") and os.geteuid() == 0:
                        flags.append("--no-sandbox")
                    browser = subprocess.Popen(flags + ["about:blank"], stdout=browser_log, stderr=subprocess.STDOUT, start_new_session=True)
                    targets = wait_for(lambda: json.load(urlopen(f"http://127.0.0.1:{debug_port}/json/list", timeout=1)), "Chrome DevTools page")
                    page = next((target for target in targets if target.get("type") == "page"), None)
                    if page is None:
                        raise AssertionError("Chromium did not expose a page target; browser journey NOT verified")
                    cd = RecordedChromeSession(page["webSocketDebuggerUrl"])
                    for domain in ("Page", "Runtime", "DOM", "Network", "Log"):
                        cd.command(domain + ".enable")
                    report["browser"] = cd.command("Browser.getVersion")
                    cd.command("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
                    cd.command("Page.navigate", {"url": url})
                    NavigationJourney(cd, url, output, temporary, report).run()
                    report["status"] = "passed"
                except Exception:
                    if cd is not None:
                        try:
                            shot = cd.command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
                            (output / "navigation-failure.png").write_bytes(base64.b64decode(shot["data"]))
                            report["screenshots"].append("navigation-failure.png")
                            report["diagnostic"] = cd.evaluate("""({url:location.href,ready:document.readyState,
                              audience:document.documentElement.dataset.audience,state:document.body?.dataset,
                              notice:document.querySelector('#notice')?.textContent,
                              intake:document.querySelector('#source-upload-status')?.textContent,
                              visiblePages:[...document.querySelectorAll('.workspace-page')].filter(page=>!page.hidden).map(page=>page.dataset.page)})""")
                        except Exception as diagnostic_error:
                            report["diagnostic_error"] = str(diagnostic_error)
                    raise
                finally:
                    if cd is not None:
                        report["api_requests"] = cd.requests
                        report["browser_errors"] = cd.browser_errors
                        report["browser_log_errors"] = cd.browser_log
                        cd.close()
                    stop_process(browser, process_group=True)
                    stop_process(server)
    except Exception as error:
        report["status"] = "failed"
        report["failure"] = str(error)
        raise
    finally:
        (output / "navigation-report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        "PASS: patient/clinician navigation, all 16 original forms, real question/evidence/draft persistence, "
        "exact-node and unsaved input/file preservation, no navigation writes or refreshes, local search, "
        "guarded and same-case switching, native mobile Tab/Enter, source dialog/Escape, "
        "history, initial skip links and disclosure/report deep links, "
        "1440/390/320px layouts and browser error capture. Artifacts: " + str(output)
    )


if __name__ == "__main__":
    main()
