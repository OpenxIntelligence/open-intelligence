"""Observe the real focus boundary without modifying application behavior."""
import json
import os
from pathlib import Path
import workspace_navigation_journey as journey

transitions = []
evaluate = journey.ObservedChromeSession.evaluate
focus_menu = "document.querySelector('#menu-toggle').focus()"
snapshot = """(() => {
  const menu = document.querySelector('#menu-toggle'), active = document.activeElement;
  const r = menu.getBoundingClientRect(), x = r.left + r.width / 2, y = r.top + r.height / 2;
  const hit = document.elementFromPoint(x, y), skip = document.querySelector('.skip-link');
  return {width:innerWidth, active:{id:active.id, tag:active.tagName, className:active.className},
    skipFocused:active === skip, skipFocusVisible:skip.matches(':focus-visible'),
    hit:hit ? {id:hit.id, tag:hit.tagName, className:hit.className} : null,
    menuHit:hit === menu || menu.contains(hit), x, y};
})()"""

def observed(self, expression):
    if expression != focus_menu:
        return evaluate(self, expression)
    before = evaluate(self, snapshot)
    result = evaluate(self, expression)
    after = evaluate(self, snapshot)
    transitions.append({'before':before, 'after':after})
    return result

journey.ObservedChromeSession.evaluate = observed
try:
    journey.main()
    recovered = [item for item in transitions
                 if item['before']['skipFocused'] and item['before']['skipFocusVisible']
                 and not item['before']['menuHit'] and item['after']['menuHit']
                 and item['after']['active']['id'] == 'menu-toggle']
    assert recovered, 'Expected focused skip-link overlay was not reproduced'
    print(json.dumps({'verified_focus_transitions':len(recovered), 'transitions':transitions}))
finally:
    output = Path(os.environ['OI_UI_ARTIFACT_DIR'])
    output.mkdir(parents=True, exist_ok=True)
    (output / 'focus-transition-proof.json').write_text(json.dumps(transitions,indent=2)+'\n')
