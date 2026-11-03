"""Retain browser startup evidence while running an unchanged journey."""
from pathlib import Path
import json
import os
import resource
import runpy
import shutil
import subprocess
import sys

target = Path(sys.argv[1])
output = Path(os.environ.get('OI_UI_ARTIFACT_DIR', 'ui-artifacts')) / 'browser-startup'
output.mkdir(parents=True, exist_ok=True)
chrome = next((p for name in ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser')
               if (p := shutil.which(name))), None)
metadata = {
    'journey':str(target), 'uid':os.geteuid(), 'chrome':chrome,
    'chrome_realpath':str(Path(chrome).resolve()) if chrome else None,
    'runner':{name:os.environ.get(name) for name in ('ImageOS','ImageVersion','RUNNER_OS','RUNNER_ARCH')},
    'nofile_limit':resource.getrlimit(resource.RLIMIT_NOFILE),
    'process_limit':resource.getrlimit(resource.RLIMIT_NPROC),
    'process_count':sum(item.name.isdigit() for item in Path('/proc').iterdir()),
    'tmp_disk_free_bytes':shutil.disk_usage('/tmp').free,
    'browser_launches':[],
}
for name in ('unprivileged_userns_clone', 'apparmor_restrict_unprivileged_userns'):
    path = Path('/proc/sys/kernel') / name
    metadata[name] = path.read_text().strip() if path.exists() else 'absent'
if chrome:
    version = subprocess.run([chrome,'--version'],capture_output=True,text=True,timeout=10)
    metadata['version'] = {'returncode':version.returncode, 'stdout':version.stdout, 'stderr':version.stderr}
original_popen = subprocess.Popen
logs = []
processes = []
def observed_popen(args, *positional, **kwargs):
    if isinstance(args, (list,tuple)) and args and Path(str(args[0])).name in (
            'google-chrome','google-chrome-stable','chromium','chromium-browser'):
        log_path = output / (target.stem + '-chrome-' + str(len(logs)) + '.log')
        handle = log_path.open('w')
        logs.append((log_path,handle))
        kwargs['stdout'] = handle
        kwargs['stderr'] = subprocess.STDOUT
        record = {'command':list(args), 'log':str(log_path)}
        metadata['browser_launches'].append(record)
        try:
            process = original_popen(args,*positional,**kwargs)
        except BaseException as error:
            record['launch_exception'] = type(error).__name__ + ': ' + str(error)
            raise
        record['pid'] = process.pid
        processes.append((record,process))
        return process
    return original_popen(args,*positional,**kwargs)
subprocess.Popen = observed_popen
try:
    runpy.run_path(str(target),run_name='__main__')
finally:
    for record,process in processes:
        record['returncode_after_journey'] = process.poll()
    for path,handle in logs:
        handle.close()
        print('Browser startup log: ' + str(path),flush=True)
        print(path.read_text(errors='replace')[-20000:],flush=True)
    receipt = output / (target.stem + '-diagnostics.json')
    receipt.write_text(json.dumps(metadata,indent=2)+'\n')
    print(json.dumps(metadata),flush=True)
