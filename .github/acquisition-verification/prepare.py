"""Reconstruct exactly the locally reviewed candidate; never execute a remote payload."""
import base64
import gzip
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile

BASE='c154bfbc5f99f76801d37903959943659c0b6a71'
TREE='21b2d594c82042fceaa564c041e401b52e1e60d4'
COMMIT='8b70e69b6fa6dd5fdc6276effdd0fce1c05a81ab'
EXPECTED={'apps/web/README.md','apps/web/src/main.tsx','apps/web/src/record-acquisition-view.tsx','apps/web/src/record-acquisition.css','apps/web/src/record-acquisition.ts','apps/web/src/registry-client.ts','apps/web/tests/record-acquisition.test.mjs','apps/web/tools/browser_journey.py','apps/web/tools/record_acquisition_journey.py','docs/engineering/H1_CANONICAL_RECORD_SOURCE_RECEIPT.md'}
def git(*args,**kwargs):
    return subprocess.check_output(['git',*args],**kwargs)
root=Path(__file__).parent
encoded=''.join((root/f'part{i}.txt').read_text().strip() for i in (1,2,3))
assert len(encoded)==24664
patch=gzip.decompress(base64.b64decode(encoded,validate=True))
assert len(patch)==66485
assert hashlib.sha256(patch).hexdigest()=='44e82e1b2f906681a1973064d9214f9766a88ac20a21231fea6dd6c014138a26'
with tempfile.NamedTemporaryFile(suffix='.patch') as file:
    file.write(patch);file.flush()
    git('checkout','--detach',BASE)
    git('apply','--check',file.name)
    git('apply',file.name)
    actual=set(git('diff','--name-only',text=True).splitlines())|set(git('ls-files','--others','--exclude-standard',text=True).splitlines())
    assert actual==EXPECTED,(actual,EXPECTED)
    git('add','--',*sorted(EXPECTED))
    assert git('write-tree',text=True).strip()==TREE
    env=dict(os.environ,GIT_AUTHOR_NAME='Open Intelligence',GIT_AUTHOR_EMAIL='open-intelligence@outlook.com',GIT_COMMITTER_NAME='Open Intelligence',GIT_COMMITTER_EMAIL='open-intelligence@outlook.com',GIT_AUTHOR_DATE='1793706559 +0000',GIT_COMMITTER_DATE='1793706559 +0000')
    candidate=git('commit-tree',TREE,'-p',BASE,'-m','feat(h1): connect record acquisition to the patient workspace',env=env,text=True).strip()
    assert candidate==COMMIT,candidate
    git('checkout','--detach',candidate)
    assert not git('status','--porcelain',text=True).strip()
    print('Verified candidate',candidate,'tree',TREE)
