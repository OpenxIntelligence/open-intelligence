#!/usr/bin/env bash
# Run only after the caller creates a fresh Linux network namespace.
# The upstream wildcard sockets remain unchanged; this is synthetic test confinement.
set -euo pipefail

if [ "$#" -lt 5 ] || [ "$#" -gt 6 ]; then
  echo "Usage: run_confined_pacsnode.sh BINARY REPO RUN_DIR PARENT_NETNS PYTHON_BIN [security|lifecycle]" >&2
  exit 2
fi
pacs_binary=$1
pacs_repo=$2
pacs_run_directory=$3
pacs_parent_namespace=$4
pacs_python=$5
pacs_mode=${6:-security}
case "$pacs_mode" in
  security|lifecycle) ;;
  *) echo "HOLD: unknown evaluation mode" >&2; exit 2 ;;
esac

if [[ ! "$pacs_parent_namespace" =~ ^net:\[[1-9][0-9]*\]$ ]] || \
   [ "$(readlink /proc/self/ns/net)" = "$pacs_parent_namespace" ]; then
  echo "HOLD: a fresh network namespace is required before starting PACS." >&2
  exit 1
fi
if [ ! -x "$pacs_binary" ] || [ ! -x "$pacs_python" ] || \
   [ ! -d "$pacs_repo/tools/imaging" ] || [ ! -d "$pacs_run_directory" ]; then
  echo "HOLD: required executable or evaluation directory is unavailable." >&2
  exit 1
fi
# The parent must provide a new empty directory. Never reuse persisted PACS settings.
"$pacs_python" - "$pacs_run_directory" <<'PY'
from pathlib import Path
import sys
if any(Path(sys.argv[1]).iterdir()):
    raise SystemExit('HOLD: evaluation directory is not empty')
PY

ip link set lo up
"$pacs_python" - <<'PY'
import json
import subprocess
links = json.loads(subprocess.check_output(['ip', '-j', 'link', 'show'], timeout=3))
if len(links) != 1 or links[0].get('ifname') != 'lo' or 'UP' not in links[0].get('flags', []):
    raise SystemExit('HOLD: only an active loopback interface is permitted')
PY

mkdir -p "$pacs_repo/verification-artifacts"
cd "$pacs_run_directory"
"$pacs_binary" generate-config standalone
# The pinned generator enables optional admin/viewer plugins. Disable those
# runtime routes without modifying the pinned vendor source or binary.
"$pacs_python" - <<'PY'
from hashlib import sha256
from pathlib import Path
import re
import tomllib
path = Path('config.toml')
original = path.read_text()
config = tomllib.loads(original)
if config['database']['url'] != 'sqlite://./data/pacsnode.db':
    raise SystemExit('HOLD: generated backend is not the expected standalone profile')
changed, count = re.subn(r'^enabled = \[[^\n]*\]$', 'enabled = []', original, flags=re.MULTILINE)
if count != 1 or tomllib.loads(changed)['plugins']['enabled'] != []:
    raise SystemExit('HOLD: optional plugin configuration could not be bounded')
path.write_text(changed)
print('Synthetic standalone configuration SHA-256:', sha256(changed.encode()).hexdigest())
PY

export PACS_SERVER__HTTP_PORT=18042
export PACS_SERVER__DICOM_PORT=11112
export PACS_SERVER__STORAGE_TRANSFER_SYNTAX=1.2.840.10008.1.2.1
export PYTHONPATH="$pacs_repo/src"
pacs_evidence_prefix=pacsnode
if [ "$pacs_mode" = lifecycle ]; then pacs_evidence_prefix=pacsnode-lifecycle; fi
printf '%s\n' "$PACS_SERVER__STORAGE_TRANSFER_SYNTAX" > "$pacs_repo/verification-artifacts/$pacs_evidence_prefix-test-storage-transfer-syntax.txt"
sha256sum config.toml > "$pacs_repo/verification-artifacts/$pacs_evidence_prefix-test-config-sha256.txt"
if [ "$pacs_mode" = lifecycle ]; then
  # A single Python owner starts, reaps and restarts the retained-store process.
  # It receives the fresh generated configuration exactly once.
  cd "$pacs_repo"
  exec "$pacs_python" -m tools.imaging.pacsnode_lifecycle_process \
    --binary "$pacs_binary" --run-directory "$pacs_run_directory" \
    --parent-namespace "$pacs_parent_namespace" \
    --output "$pacs_repo/verification-artifacts/pacsnode-lifecycle.json"
fi
"$pacs_binary" > "$pacs_repo/verification-artifacts/pacsnode-stdout.txt" 2>&1 &
server_pid=$!
cleanup() {
  kill "$server_pid" 2>/dev/null || true
  for pacs_cleanup_attempt in {1..30}; do
    if ! kill -0 "$server_pid" 2>/dev/null; then break; fi
    sleep 0.1
  done
  # A vendor process that ignores TERM must not hold a failed workflow open.
  kill -KILL "$server_pid" 2>/dev/null || true
  wait "$server_pid" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

cd "$pacs_repo"
# HTTP readiness alone is insufficient: upstream keeps it running after a DIMSE
# listener failure. Require both actual server-owned sockets before evaluation.
"$pacs_python" - "$server_pid" "$pacs_parent_namespace" <<'PY'
import http.client
import sys
import time
from tools.imaging.network_confinement import capture_network_evidence
deadline = time.monotonic() + 45
while time.monotonic() < deadline:
    connection = http.client.HTTPConnection('127.0.0.1', 18042, timeout=2)
    try:
        connection.request('GET', '/health')
        healthy = connection.getresponse().status == 200
        evidence = capture_network_evidence(int(sys.argv[1]), sys.argv[2])
        if healthy and evidence['namespace_confined']:
            break
    except (OSError, ValueError, http.client.HTTPException):
        pass
    finally:
        connection.close()
    time.sleep(0.5)
else:
    raise SystemExit('HOLD: both confined PACS listeners did not become ready')
PY

"$pacs_python" -m tools.imaging.pacsnode_security_evaluation \
  --base-url http://127.0.0.1:18042 \
  --server-pid "$server_pid" \
  --parent-namespace "$pacs_parent_namespace" \
  --output "$pacs_repo/verification-artifacts/pacsnode-real-dicomweb.json" \
  --assessment-output "$pacs_repo/verification-artifacts/imaging-release-hold-assessment.json"
