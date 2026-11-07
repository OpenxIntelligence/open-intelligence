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

    def click_draft(label):
        buttons = json.dumps('section[aria-label="Episode drafts"] button')
        button = f'[...document.querySelectorAll({buttons})].find(b=>b.textContent==={json.dumps(label)})'
        cd.wait(button + ' && !' + button + '.disabled', label)
        cd.evaluate(button + '.click()')

    def read_drafts():
        return cd.evaluate("""[...document.querySelectorAll('[data-testid=saved-episode-draft]')]
          .map(row=>({label:row.querySelector('strong').textContent,id:row.querySelector('details code').textContent,
                     statement:row.querySelector('blockquote').textContent,body:row.textContent}))""")

    nodule_preflight = ('[...document.querySelectorAll("[data-testid=world-observation]")]'
                        '.find(e=>e.querySelector("strong").textContent==="nodule")'
                        '?.querySelector("[data-testid=composer-preflight]")')
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
                click_draft('Open saved episode drafts')
                cd.wait('document.body.textContent.includes("No episode drafts saved for this case.")',
                        'newly authorized case has no drafts')
                for count, line in enumerate((8, 9), start=1):
                    value = json.dumps(current['source_id'] + ':' + str(line))
                    cd.evaluate("""(() => {const s=document.querySelector('section[aria-label="Episode drafts"] select');"""
                                + "s.value=" + value + ";s.dispatchEvent(new Event('change',{bubbles:true}));})()")
                    click_draft('Save episode draft')
                    cd.wait(f'document.querySelectorAll("[data-testid=saved-episode-draft]").length==={count}',
                            'explicit episode draft saved and re-read')
                rows = read_drafts()
                draft_ids = {r['label']:r['id'] for r in rows}
                assert set(draft_ids) == {'EP-A','EP-B'} and len(set(draft_ids.values())) == 2
            else:
                # The current report is still visible under source_read, but the
                # draft list itself would disclose statements from the old report.
                click_draft('Open saved episode drafts')
                cd.wait('document.querySelectorAll("[data-testid=saved-episode-draft]").length===2',
                        'both original episode drafts visible before grant withdrawal')
                assert {r['label']:r['id'] for r in read_drafts()} == draft_ids
                credentials[0]['actions'].remove('source_original_read')
                write_grants()
                try:
                    click_draft('Open saved episode drafts')
                    cd.wait('document.querySelector("[data-testid=world-status]")?.textContent.includes("Episode draft access unavailable")',
                            'historical draft lookup rechecks original-read permission')
                    assert not read_drafts()
                    assert not cd.evaluate('Boolean(document.querySelector("[data-testid=world-projection], [data-testid=server-original]"))')
                finally:
                    credentials[0]['actions'].append('source_original_read')
                    write_grants()
                select_case('Journey', 'world-load-cases', '.world-cases li', 'world-load')
                click_draft('Open saved episode drafts')
                cd.wait('document.querySelectorAll("[data-testid=saved-episode-draft]").length===2',
                        'historical drafts reopened after fresh original-read authority')
                rows = read_drafts()
                assert {r['label']:r['id'] for r in rows} == draft_ids
            for row in rows:
                line, statement = {'EP-A':(8,'Fictional breast primary.'),'EP-B':(9,'Fictional colon primary.')}[row['label']]
                assert row['statement'] == statement and 'Unreviewed draft' in row['body']
                assert f'DOC-ALPHA v1 · line {line}' in row['body'] and selected_ids[0] in row['body']
                expected_basis = 'Current source basis' if version == 1 else 'Reassessment required'
                assert expected_basis in row['body']
                expected_comparison = 'The originating report is unchanged.' if version == 1 else 'The originating finding is unchanged in this version.'
                assert expected_comparison in row['body']
            cd.evaluate("document.querySelector('[data-testid=episode-open-original]').click()")
            cd.wait('document.querySelector("[data-testid=server-original]")?.textContent===' + json.dumps(originals[0]),
                    'episode opens its exact original without another source selection')
            cd.wait('document.activeElement===document.querySelector("#opened-original")',
                    'episode original heading receives keyboard focus')
            if version == 1:
                select_case('Journey', 'world-load-cases', '.world-cases li', 'world-load')
                click_draft('Open saved episode drafts')
                cd.wait('document.querySelectorAll("[data-testid=saved-episode-draft]").length===2',
                        'drafts visible before separate original-read withdrawal')
                credentials[0]['actions'].remove('source_original_read')
                write_grants()
                try:
                    cd.evaluate("document.querySelector('[data-testid=episode-open-original]').click()")
                    cd.wait('document.querySelector("[data-testid=records-status]")?.textContent.includes("Original unavailable")',
                            'direct episode inspection rechecks original-read authority')
                    assert not cd.evaluate('Boolean(document.querySelector("[data-testid=server-original]"))')
                finally:
                    credentials[0]['actions'].append('source_original_read')
                    write_grants()
            if version == 2:
                inspect_original(2, originals[1])
            select_case('Journey', 'world-load-cases', '.world-cases li', 'world-load')
            cd.wait(nodule_preflight + ' && !' + nodule_preflight + '.disabled', 'current nodule available for preflight')
            cd.evaluate(nodule_preflight + '.click()')
            expected_context = 'Source-reported metastasis · ' + ('Episode unassigned' if version == 1 else 'EP-B') + ' · indeterminate'
            cd.wait('document.querySelector("[data-testid=composer-context]")?.textContent.includes('
                    + json.dumps(expected_context) + ')', 'episode and uncertainty survive source-only preflight')

        # Leave the v2 original open so both downstream withdrawal checks
        # also cover previously disclosed bytes in Records.
        select_case('Records', 'load-cases', '[data-testid=case-row]', 'load-sources')
        inspect_original(2, originals[-1])

        # A protected action and an explicit projection refresh can each discover
        # withdrawal. Both must also clear the previously inspected original in Records.
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
        credentials[0]['actions'] = sorted(set(credentials[0]['actions']) | {
            'source_read', 'question_create', 'question_read', 'review_queue_read', 'review_return'})
        write_grants()
        consult = (FIXTURES / 'episode-origin-consult-v1.txt').read_text()
        second = operator(source_path, {'synthetic': True, 'original_text': consult})
        select_case('Journey', 'world-load-cases', '.world-cases li', 'world-load')
        cd.wait('document.querySelector("[data-testid=world-projection]")?.textContent.includes('
                + json.dumps(second['source_id']) + ')', 'independent consultation in Journey')
        primary = ('[...document.querySelectorAll("[data-testid=world-observation]")]'
                   '.find(e=>e.querySelector("strong").textContent==="nodule" && e.textContent.includes('
                   + json.dumps(selected_ids[-1]) + '))')
        cd.evaluate(primary + '.querySelector("[data-testid=composer-preflight]").click()')
        def element(selector):
            return 'document.querySelector(' + json.dumps(selector) + ')'
        save = element('[data-testid=save-source-question]')
        cd.wait(save + ' && !' + save + '.disabled', 'first source question prepared')
        cd.evaluate(save + '.click()')
        cd.wait('Boolean(' + element('[data-testid=saved-source-question]') + ')', 'source question saved')
        navigate('Review')
        cd.wait('Boolean(' + element('[data-testid=load-review-queue]') + ')', 'review opened')
        cd.evaluate(element('[data-testid=load-review-queue]') + '.click()')
        form = element('[data-testid=attribution-review]')
        cd.wait('Boolean(' + form + ')', 'eligible second report in Review')
        cd.evaluate(form + '.open=true')
        cd.evaluate('(()=>{const s=' + form + '.querySelector("select");s.selectedIndex=1;'
                    's.dispatchEvent(new Event("change",{bubbles:true}));})()')
        cd.wait(form + '.querySelectorAll("blockquote").length===2', 'two quoted original passages')
        quotes = cd.evaluate('[...' + form + '.querySelectorAll("blockquote")].map(e=>e.textContent)')
        assert all(quote in raw for quote, raw in zip(quotes, [originals[-1], consult])), quotes
        reason = 'The fictional reports name different possible origins. Attribution remains unresolved.'
        cd.evaluate(form + '.querySelector("textarea").focus()')
        cd.command('Input.insertText', {'text': reason})
        record = form + '.querySelector("button")'
        cd.wait('!' + record + '.disabled', 'authored comparison reason')
        cd.evaluate(record + '.click()')
        cd.wait('Boolean(' + element('[data-testid=review-return-result]') + ')', 'paired receipt returned')
        operator(source_path, {'synthetic': True, 'original_text': (FIXTURES / 'episode-origin-consult-v2.txt').read_text()})
        select_case('Journey', 'world-load-cases', '.world-cases li', 'world-load')
        reviews = element('section[aria-label="Episode attribution reviews"]')
        cd.wait('Boolean(' + reviews + ')', 'amended source model')
        cd.evaluate(reviews + '.querySelector("button").click()')
        cd.wait(reviews + '.textContent.includes("DOC-CONSULT v1 amended — reassessment required")', 'Journey identifies the affected review')
        cd.evaluate(reviews + '.querySelectorAll("button")[1].click()')
        history = element('[data-testid=review-return-history]')
        cd.wait(history + '?.textContent.includes(' + json.dumps(reason) + ')', 'original reason retained')
        compare = element('[data-testid=inspect-attribution]')
        cd.evaluate(compare + '.click()')
        passages = element('[data-testid=attribution-passages]')
        cd.wait(passages + '?.textContent.includes("DOC-CONSULT v2")', 'two-version attribution comparison')
        consult_side = passages + '.querySelector(' + json.dumps('section[aria-label="DOC-CONSULT"]') + ')'
        quoted = cd.evaluate('[...' + consult_side + '.querySelectorAll("blockquote")].map(node=>node.textContent)')
        amended_consult = (FIXTURES / 'episode-origin-consult-v2.txt').read_text()
        assert len(quoted) == 2 and quoted[0] in consult and quoted[1] in amended_consult, quoted
        assert 'Line 9' in cd.evaluate(consult_side + '.textContent')
        assert 'Episode unassigned' in cd.evaluate(consult_side + '.textContent')
        assert 'Recorded version is current' in cd.evaluate(passages + '.textContent')
        cd.evaluate(consult_side + '.querySelectorAll("button")[1].click()')
        cd.wait(element('[data-testid=server-original]') + '?.textContent===' + json.dumps(amended_consult),
                'comparison opens exact latest consult under fresh original-read authority')
        navigate('Review')
        cd.wait('Boolean(' + element('[data-testid=load-review-queue]') + ')', 'return to review')
        cd.evaluate(element('[data-testid=load-review-queue]') + '.click()')
        cd.wait(history + '?.textContent.includes(' + json.dumps(reason) + ')', 'history rechecked after current original')
        cd.evaluate(history + '.querySelectorAll("button")[1].click()')
        cd.wait(element('[data-testid=server-original]') + '?.textContent===' + json.dumps(consult),
                'history reopens exact pre-amendment consult under original-read authority')

        # A new amendment changes one primary and removes the other key. The
        # original draft IDs and quotes remain, without inferring a negative result.
        changed_origin = originals[-1].replace('Amends: DOC-ALPHA@1', 'Amends: DOC-ALPHA@2')
        changed_origin = changed_origin.replace('breast|primary|EP-A|reported|Fictional breast primary.',
            'breast|primary|EP-C|indeterminate|Fictional amended breast statement; attribution uncertain.')
        changed_origin = '\n'.join(line for line in changed_origin.splitlines()
                                  if not line.startswith('Oncology-Finding: colon|')) + '\n'
        amended_origin = operator(source_path, {'synthetic': True, 'original_text': changed_origin})
        select_case('Journey', 'world-load-cases', '.world-cases li', 'world-load')
        click_draft('Open saved episode drafts')
        cd.wait('document.querySelectorAll("[data-testid=saved-episode-draft]").length===2',
                'original draft identities survive a changed and removed primary')
        rows = read_drafts()
        assert {row['label']:row['id'] for row in rows} == draft_ids
        first = next(row for row in rows if row['label'] == 'EP-A')
        removed = next(row for row in rows if row['label'] == 'EP-B')
        assert first['statement'] == 'Fictional breast primary.'
        assert 'EP-C' in first['body'] and 'indeterminate' in first['body']
        assert 'The originating finding has changed.' in first['body']
        assert 'The finding key colon is absent from this version.' in removed['body']
        assert all('Reassessment required' in row['body'] and 'Unreviewed draft' in row['body'] for row in rows)
        comparison = element('[data-testid=episode-origin-comparison]')
        cd.evaluate(comparison + '.open=true')
        cd.evaluate(comparison + '.querySelector("[data-testid=episode-open-latest]").click()')
        cd.wait(element('[data-testid=server-original]') + '?.textContent===' + json.dumps(changed_origin),
                'saved episode comparison opens exact latest origin document')
        (artifacts / 'oncology-episodes.json').write_text(json.dumps({
            'synthetic': True, 'case_id': CASE, 'source_ids': selected_ids,
            'source_sha256': [hashlib.sha256(s.encode()).hexdigest() for s in originals],
            'direct_episode_original_verified': True, 'durable_episode_draft_ids': draft_ids, 'amended_basis_flagged': True,
            'historical_drafts_rechecked_original_read': True,
            'compared_consult_versions': [1, 2], 'latest_consult_line': 9,
            'paired_review_reassessment': True, 'consult_original_reopened': True,
            'comparison_current_original_verified': True,
            'draft_origin_comparison': {'latest_source_id': amended_origin['source_id'], 'latest_version': 3,
                'changed_key': 'breast', 'removed_key': 'colon', 'draft_ids_preserved': True,
                'latest_original_verified': True, 'clinical_review_unchanged': True},
            'primary_episodes': ['EP-A', 'EP-B'], 'nodule_episode_history': [None, 'EP-B'],
            'nodule_reported_state': 'indeterminate', 'source_only_preflights': 2,
            'historical_original_verified': True, 'denied_read_cleared_records': True,
            'denied_preflight_cleared_records': True,
        }, indent=2) + '\n')
        print('PASS ONCOLOGY EPISODES: two primaries retain independent unreviewed draft IDs and original lines after amendment; historical statements require fresh original-read permission; exact v1 and v2 originals verified in Records.')
    finally:
        credentials[0]['actions'] = previous
        write_grants()
        navigate('Overview')
