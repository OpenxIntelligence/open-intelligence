"""Real-browser checks and screenshots of original fictional case fixtures only.

Uses the existing dependency-free CDP harness. Run with PYTHONPATH=src.
OI_UI_ARTIFACT_DIR selects the screenshot directory; no network evidence calls.
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
from urllib.request import urlopen

from browser_journey import ChromeSession, free_port, wait_for

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    chrome = next((p for name in ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser')
                   if (p := shutil.which(name))), None)
    if not chrome:
        raise AssertionError('Chromium unavailable: UI is not verified')
    output = Path(os.environ.get('OI_UI_ARTIFACT_DIR', ROOT / '.ui-artifacts'))
    output.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'))
    errors: list[str] = []
    report: dict = {'data': 'Independently authored fictional fixtures only', 'checks': [], 'errors': errors}

    def check(condition: bool, label: str) -> None:
        report['checks'].append({'check': label, 'passed': bool(condition)})
        if not condition:
            errors.append(label)

    with tempfile.TemporaryDirectory(prefix='oi-glance-', ignore_cleanup_errors=True) as temp:
        db = str(Path(temp) / 'case.sqlite')
        subprocess.run([sys.executable, '-m', 'open_intelligence', 'seed', '--db', db],
                       cwd=ROOT, env=env, check=True, stdout=subprocess.DEVNULL)
        app_port, debug_port = free_port(), free_port()
        server = subprocess.Popen([sys.executable, '-m', 'open_intelligence', 'serve', '--db', db,
                                   '--port', str(app_port)], cwd=ROOT, env=env,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        browser = None
        cd = None
        try:
            url = f'http://127.0.0.1:{app_port}/'
            wait_for(lambda: urlopen(url, timeout=1).status == 200, 'seeded local application')
            flags = [chrome, '--headless=new', '--disable-gpu', '--disable-dev-shm-usage',
                     '--disable-background-networking', '--no-first-run', '--disable-extensions',
                     '--no-default-browser-check', '--remote-allow-origins=*',
                     f'--remote-debugging-port={debug_port}', f'--user-data-dir={temp}/chrome']
            if hasattr(os, 'geteuid') and os.geteuid() == 0:
                flags.append('--no-sandbox')
            browser = subprocess.Popen(flags + ['about:blank'], stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL, start_new_session=True)
            targets = wait_for(lambda: json.load(urlopen(
                f'http://127.0.0.1:{debug_port}/json/list', timeout=1)), 'Chromium target')
            page = next(x for x in targets if x.get('type') == 'page')
            cd = ChromeSession(page['webSocketDebuggerUrl'])
            cd.command('Page.enable')
            cd.command('Runtime.enable')
            cd.command('Emulation.setDeviceMetricsOverride', {
                'width': 1440, 'height': 900, 'deviceScaleFactor': 1, 'mobile': False})
            cd.command('Page.navigate', {'url': url})
            cd.wait("document.querySelector('#case-heading')?.textContent === 'Fictional case Alpha'",
                    'Alpha loaded')
            cd.wait("document.querySelectorAll('#assertion-list .finding').length > 0", 'source findings')
            cd.evaluate('window.scrollTo(0,0)')

            def capture(name: str) -> None:
                image = cd.command('Page.captureScreenshot', {'format': 'png', 'captureBeyondViewport': False})
                (output / name).write_bytes(base64.b64decode(image['data']))

            capture('desktop-overview.png')
            layout = cd.evaluate("""(() => {
              const facts = document.querySelector('#assertions');
              const authoring = document.querySelector('#investigations');
              const first = document.querySelector('#assertion-list .source-jump');
              return {
                factsFirst: !!(facts.compareDocumentPosition(authoring) & Node.DOCUMENT_POSITION_FOLLOWING),
                firstSourceBottom: first?.getBoundingClientRect().bottom,
                factsTop: facts.getBoundingClientRect().top,
                authoringTop: authoring.getBoundingClientRect().top,
                width: innerWidth, scrollWidth: document.documentElement.scrollWidth,
                sourceCount: document.querySelectorAll('#assertion-list .source-jump').length,
                findingCount: document.querySelectorAll('#assertion-list .finding').length
              };
            })()""")
            report['desktop'] = layout
            check(layout['factsFirst'], 'Source facts precede authoring in reading order')
            check(layout['factsTop'] < layout['authoringTop'], 'Source facts precede authoring visually')
            check(0 < (layout['firstSourceBottom'] or 10000) <= 900, 'First exact-source action is above the fold at 1440x900')
            check(layout['sourceCount'] == layout['findingCount'], 'Every finding retains an exact-source action')
            check(layout['scrollWidth'] <= layout['width'], 'Desktop has no page-level horizontal overflow')

            cd.evaluate("document.querySelector('#assertion-list .source-jump').click()")
            cd.wait("document.querySelector('#source-dialog').open && !!document.querySelector('#dialog-text mark.source-highlight')",
                    'highlighted original source')
            check('Finding:' in cd.evaluate("document.querySelector('#dialog-text mark').textContent"),
                  'Source action opens the exact authored finding line')
            check('FICTIONAL' in cd.evaluate("document.querySelector('#source-dialog').textContent"),
                  'Source dialog itself carries fictional-data label')
            capture('desktop-source.png')
            cd.command('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'Escape', 'code': 'Escape', 'windowsVirtualKeyCode': 27})
            cd.command('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': 'Escape', 'code': 'Escape', 'windowsVirtualKeyCode': 27})
            cd.wait("!document.querySelector('#source-dialog').open", 'Escape closes source')

            disclosure = cd.evaluate("!!document.querySelector('#evidence-tools > summary')")
            check(disclosure, 'Evidence registration uses an explicit native disclosure')
            if disclosure:
                check(cd.evaluate("!document.querySelector('#evidence-tools').open"), 'Raw evidence input starts collapsed')
                cd.evaluate("document.querySelector('#evidence-tools > summary').focus()")
                cd.wait("document.activeElement === document.querySelector('#evidence-tools > summary')",
                        'native disclosure receives keyboard focus')
                # Native Enter activation needs its character/keypress event,
                # not just synthetic keyDown/keyUp without character input.
                cd.command('Input.dispatchKeyEvent', {'type': 'rawKeyDown', 'key': 'Enter', 'code': 'Enter', 'windowsVirtualKeyCode': 13})
                cd.command('Input.dispatchKeyEvent', {'type': 'char', 'text': '\r', 'unmodifiedText': '\r', 'key': 'Enter', 'code': 'Enter', 'windowsVirtualKeyCode': 13})
                cd.command('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': 'Enter', 'code': 'Enter', 'windowsVirtualKeyCode': 13})
                cd.wait("document.querySelector('#evidence-tools').open", 'keyboard opens evidence tools')
                check(True, 'Evidence disclosure works with the keyboard')
                cd.evaluate("document.querySelector('#evidence-tools').open = false")

            cd.evaluate("""(() => {
              const picker = document.querySelector('#case-picker');
              picker.value='CASE-BETA'; picker.dispatchEvent(new Event('change'));
            })()""")
            cd.wait("document.querySelector('#case-heading')?.textContent === 'Fictional case Beta'", 'isolated Beta')
            check(not cd.evaluate("document.querySelector('#assertion-list').textContent.includes('PATH-ALPHA')"),
                  'Case switch does not retain Alpha provenance')
            cd.evaluate("""(() => {
              const picker = document.querySelector('#case-picker');
              picker.value='CASE-ALPHA'; picker.dispatchEvent(new Event('change'));
            })()""")
            cd.wait("document.querySelector('#case-heading')?.textContent === 'Fictional case Alpha'", 'return Alpha')
            cd.command('Emulation.setDeviceMetricsOverride', {
                'width': 390, 'height': 844, 'deviceScaleFactor': 1, 'mobile': False})
            cd.evaluate('window.scrollTo(0,0)')
            capture('mobile-overview.png')
            check(cd.evaluate('document.documentElement.scrollWidth <= innerWidth'), '390px viewport has no page overflow')
            check(cd.evaluate("document.querySelector('.top').textContent.includes('FICTIONAL DEMO DATA')"),
                  'Fictional warning remains in the mobile header')
        except Exception as error:
            errors.append(f'{type(error).__name__}: {error}')
            raise
        finally:
            (output / 'verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            if cd:
                cd.close()
            if browser:
                try:
                    os.killpg(browser.pid, signal.SIGTERM)
                    browser.wait(timeout=5)
                except ProcessLookupError:
                    pass
                except subprocess.TimeoutExpired:
                    os.killpg(browser.pid, signal.SIGKILL)
                    browser.wait(timeout=5)
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
    print(json.dumps(report, indent=2))
    if errors:
        raise AssertionError('; '.join(errors))


if __name__ == '__main__':
    main()
