"""Exercise two versions of an independently authored cancer report through Records and Journey."""
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

CASE = 'CASE-WEB-EPISODES'
FIXTURES = Path(__file__).resolve().parents[3] / 'examples/synthetic'


def exercise(cd, patient_id, token, credentials, write_grants, artifacts):
    previous = list(credentials[0]['actions'])
    credentials[0]['actions'] = sorted(set(previous) | {
        'patient_read', 'case_binding_create', 'case_binding_read', 'source_import',
        'source_read', 'source_original_read', 'composer_context_read', 'episode_draft_read', 'episode_draft_create',
    })
    write_grants()

    def operator(path, payload=None):
        req = Request('http://127.0.0.1:8000/v1/patients/' + patient_id + path,
                      data=None if payload is None else json.dumps(payload).encode(),
                      headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
        with urlopen(req, timeout=8) as response:
            return json.load(response)

    def navigate(name):
        cd.evaluate('[...document.querySelectorAll("nav button")].find(e=>e.textContent.startsWith('
                    + json.dumps(name) + ')).click()')

    def case_button(row, button):
        return ('[...document.querySelectorAll(' + json.dumps(row) + ')].find(e=>e.textContent.includes('
                + json.dumps(CASE) + '))?.querySelector(' + json.dumps('[data-testid=' + button + ']') + ')')

    def select_case(tab, list_button, row, load_button):
        navigate(tab)
        selector = 'document.querySelector(' + json.dumps('[data-testid=' + list_button + ']') + ')'
        cd.wait(selector + ' && !' + selector + '.disabled', 'available ' + tab + ' case lookup')
        cd.evaluate(selector + '.click()')
        button = case_button(row, load_button)
        cd.wait(button + ' && !' + button + '.disabled', 'available episode case in ' + tab)
        cd.evaluate(button + '.click()')

    def inspect_original(version, literal):
        button = ('[...document.querySelectorAll("[data-testid=open-original]")].find(e=>e.textContent==='
                  + json.dumps(f'Inspect original v{version}') + ')')
        cd.wait(button + ' && !' + button + '.disabled', 'exact original available')
        cd.evaluate(button + '.click()')
        cd.wait('document.querySelector("[data-testid=server-original]")?.textContent===' + json.dumps(literal),
                'original version and attribution retained')

    nodule_preflight = ('[...document.querySelectorAll("[data-testid=world-observation]")]'
                        '.find(e=>e.querySelector("strong").textContent==="nodule")'
                        '.querySelector("[data-testid=composer-preflight]")')
    source_path = '/cases/' + CASE + '/sources'
    try:
        operator('/case-bindings', {'synthetic': True, 'case_id': CASE, 'source_organization': 'FICT-ORIGIN',
                 'source_system': 'FICT-TEXT', 'source_subject_ref': 'FICT-EPISODE', 'review_ref': 'FICT-REVIEW'})
        originals = []
        selected_ids = []
        for version in (1, 2):
            path = FIXTURES / f'oncology-episodes-v{version}.txt'
            raw = path.read_bytes()
            literal = raw.decode('utf-8')
            originals.append(literal)
            select_case('Records', 'load-cases', '[data-testid=case-row]', 'load-sources')
            cd.wait('document.querySelector("[data-testid=source-index]")?.textContent.includes('
                    + json.dumps(CASE) + ')', 'episode source index')
            cd.evaluate('document.querySelector("[data-testid=record-import-disclosure]").open=true')
            cd.command('DOM.enable')
            root = cd.command('DOM.getDocument')['root']['nodeId']
            node = cd.command('DOM.querySelector', {'nodeId': root, 'selector': '#original-file'})['nodeId']
            cd.command('DOM.setFileInputFiles', {'nodeId': node, 'files': [str(path)]})
            cd.wait('document.querySelector("[data-testid=local-original]")?.textContent===' + json.dumps(literal),
                    'exact episode report preview')
            assert len(operator(source_path)['sources']) == version - 1
            cd.evaluate("document.querySelector('#original-confirm').click()")
            cd.evaluate('document.querySelector("[data-testid=import-original]").click()')
            cd.wait(f'document.querySelectorAll("[data-testid=source-version]").length==={version}',
                    'confirmed episode import')
            current = next(s for s in operator(source_path)['sources'] if s['state'] == 'current')
            assert current['version'] == version and current['sha256'] == hashlib.sha256(raw).hexdigest()
            if selected_ids:
                assert current['supersedes_id'] == selected_ids[-1]
            selected_ids.append(current['source_id'])
            select_case('Journey', 'world-load-cases', '.world-cases li', 'world-load')
            cd.wait('document.querySelector("[data-testid=world-projection]")?.textContent.includes('
                    + json.dumps(current['source_id']) + ')', 'fresh episode projection')
            groups = cd.evaluate('''Object.fromEntries([...document.querySelectorAll(
                'section[aria-label="Source-reported cancer episodes"] > section')].map(section=>[
                section.querySelector('h4').textContent,[...section.querySelectorAll('[data-testid=world-observation]')]
                .map(row=>[row.querySelector('strong').textContent,row.querySelector('[data-testid=world-reported-state]').textContent,
                           row.querySelector('small').textContent])]))''')
            expected = {'Episode EP-A': [('breast', 'reported')], 'Episode EP-B': [('colon', 'reported')]}
            expected.setdefault('Episode unassigned' if version == 1 else 'Episode EP-B', []).append(('nodule', 'indeterminate'))
            assert {k: sorted((key,state) for key,state,_ in items) for k,items in groups.items()} == expected, groups
            assert all(current['source_id'] in anchor and f'v{version}' in anchor for items in groups.values() for _,_,anchor in items)
            if version == 1:
                for line in (8, 9):
                    value = json.dumps(current['source_id'] + ':' + str(line))
                    cd.evaluate("(() => {const s=document.querySelector('section[aria-label=\"Episode drafts\"] select');"
                                + "s.value=" + value + ";s.dispatchEvent(new Event('change',{bubbles:true}));})()")
                    button = "[...document.querySelectorAll('button')].find(b=>b.textContent==='Save episode draft')"
                    cd.wait(button + ' && !' + button + '.disabled', 'selected explicit primary origin')
                    cd.evaluate(button + '.click()')
                    cd.wait(f'document.querySelectorAll("[data-testid=saved-episode-draft]").length==={line-7}',
                            'explicit episode draft saved and re-read')
                draft_ids = cd.evaluate("""[...document.querySelectorAll('[data-testid=saved-episode-draft] details')]
                    .map(d=>d.querySelector('code').textContent)""")
                assert len(set(draft_ids)) == 2
            else:
                cd.evaluate("[...document.querySelectorAll('button')].find(b=>b.textContent==='Open saved episode drafts').click()")
                cd.wait('document.querySelectorAll("[data-testid=saved-episode-draft]").length===2', 'reopened original drafts')
                returned = cd.evaluate("""[...document.querySelectorAll('[data-testid=saved-episode-draft]')]
                    .map(d=>[d.querySelector('details code').textContent,d.textContent])""")
                assert [r[0] for r in returned] == draft_ids
                assert all('Reassessment required' in body and 'DOC-ALPHA v1' in body
                           and 'superseded original' in body and selected_ids[0] in body for _,body in returned)
            cd.evaluate(nodule_preflight + '.click()')
            expected_context = 'Source-reported metastasis · ' + ('Episode unassigned' if version == 1 else 'EP-B') + ' · indeterminate'
            cd.wait('document.querySelector("[data-testid=composer-context]")?.textContent.includes('
                    + json.dumps(expected_context) + ')', 'episode and uncertainty survive source-only preflight')

        select_case('Records', 'load-cases', '[data-testid=case-row]', 'load-sources')
        for version, original in enumerate(originals, start=1):
            inspect_original(version, original)

        # Compare a second report against the current EP-A line. Both versions
        # of DOC-ALPHA are in custody, but only v2 belongs in the comparison.
        comparison = (originals[0].split('Oncology-Finding:', 1)[0].replace('DOC-ALPHA', 'DOC-COMPARE')
                      + 'Oncology-Finding: breast|primary|EP-A|negative|Fictional contrasting statement.\n')
        added = operator(source_path, {'synthetic': True, 'original_text': comparison})
        select_case('Journey', 'world-load-cases', '.world-cases li', 'world-load')
        cd.wait('document.querySelectorAll("[data-testid=world-conflict]").length===1',
                'episode-specific disagreement from two current originals')
        cd.evaluate('document.querySelector("[data-testid=world-conflict] summary").click()')
        rows = cd.evaluate("""[...document.querySelectorAll('[data-testid=world-conflict] details[open] li')]
            .map(row=>[row.querySelector('code').textContent,row.querySelector('blockquote').textContent,
                       row.textContent])""")
        by_source = {source_id: (quote, text) for source_id, quote, text in rows}
        assert len(rows) == 2 and set(by_source) == {selected_ids[-1], added['source_id']}, rows
        quote, label = by_source[selected_ids[-1]]
        assert quote == 'Fictional breast primary.' and 'DOC-ALPHA v2 · line 9' in label, rows
        quote, label = by_source[added['source_id']]
        assert quote == 'Fictional contrasting statement.' and 'DOC-COMPARE v1 · line 8' in label, rows

        # A protected action and an explicit projection refresh can each discover
        # withdrawal. Both must also clear the previously inspected original in Records.
        # Reopen the original so the following denial also exercises the Records cache.
        select_case('Records', 'load-cases', '[data-testid=case-row]', 'load-sources')
        inspect_original(2, originals[-1])
        navigate('Journey')
        load = case_button('.world-cases li', 'world-load')
        cd.wait(load + ' && !' + load + '.disabled', 'episode case retained from Records')
        cd.evaluate(load + '.click()')
        cd.wait('document.querySelector("[data-testid=world-projection]")?.textContent.includes('
                + json.dumps(selected_ids[-1]) + ')', 'current amended episode before preflight denial')
        credentials[0]['actions'].remove('source_read')
        write_grants()
        cd.evaluate(nodule_preflight + '.click()')
        cd.wait('document.querySelector("[data-testid=composer-status]")?.textContent.includes("unavailable under current authority")',
                'source-only preflight denied after source withdrawal')
        navigate('Records')
        assert not cd.evaluate('Boolean(document.querySelector("[data-testid=source-index], [data-testid=server-original]"))')
        credentials[0]['actions'].append('source_read')
        write_grants()
        select_case('Records', 'load-cases', '[data-testid=case-row]', 'load-sources')
        inspect_original(2, originals[-1])
        navigate('Journey')
        cd.wait(load + ' && !' + load + '.disabled', 'prior case available for permission recheck')
        credentials[0]['actions'].remove('source_read')
        write_grants()
        cd.evaluate(load + '.click()')
        cd.wait('document.querySelector("[data-testid=world-status]")?.textContent.includes("unavailable or revoked")'
                + ' && !document.querySelector("[data-testid=world-projection]")', 'episode projection revoked')
        navigate('Records')
        assert not cd.evaluate('Boolean(document.querySelector("[data-testid=source-index], [data-testid=server-original]"))')
        (artifacts / 'oncology-episodes.json').write_text(json.dumps({
            'synthetic': True, 'case_id': CASE, 'source_ids': selected_ids,
            'source_sha256': [hashlib.sha256(s.encode()).hexdigest() for s in originals],
            'durable_episode_draft_ids': draft_ids, 'amended_basis_flagged': True,
            'primary_episodes': ['EP-A', 'EP-B'], 'nodule_episode_history': [None, 'EP-B'],
            'nodule_reported_state': 'indeterminate', 'source_only_preflights': 2,
            'compared_current_originals': [selected_ids[-1], added['source_id']],
            'historical_original_verified': True, 'denied_read_cleared_records': True,
            'denied_preflight_cleared_records': True,
        }, indent=2) + '\n')
        print('PASS ONCOLOGY EPISODES: file uploads, distinct primaries, amendment with retained uncertainty, source-only question context, exact originals and revocation.')
    finally:
        credentials[0]['actions'] = previous
        write_grants()
        navigate('Overview')
