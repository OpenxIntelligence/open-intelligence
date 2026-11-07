"""Inspect semantics through real rendered controls and actual authorized HTTP."""
import json


def inspect(cd, *, historical, status, original_state, fingerprint, source_id):
    view = 'historical' if historical else 'current'
    selector = f'[data-testid=source-semantics-panel][data-view={view}]'
    cd.evaluate(f"document.querySelector({json.dumps(selector)}).open=true")
    cd.evaluate(f"document.querySelector({json.dumps(selector+' [data-testid=source-semantics-load]')}).click()")
    result = selector+' [data-testid=source-semantics-result]'
    cd.wait(f"Boolean(document.querySelector({json.dumps(result)}))", f'{view} source semantics')
    assert cd.evaluate(f"document.querySelector({json.dumps(result)}).dataset.fingerprint") == fingerprint
    assert cd.evaluate(f"document.querySelector({json.dumps(result+' li strong')}).textContent") == status
    assert cd.evaluate(f"document.querySelector({json.dumps(result)}).textContent.includes({json.dumps('source state: '+original_state)})")
    assert cd.evaluate(f"document.querySelector({json.dumps(result)}).textContent.includes({json.dumps(source_id)})")
    assert cd.evaluate(f"document.querySelectorAll({json.dumps(result+' script')}).length===0")
    print(f'PASS {view.upper()} SEMANTICS: real API/UI retains exact fingerprint, source anchor, {original_state} reason and {status} class.')
