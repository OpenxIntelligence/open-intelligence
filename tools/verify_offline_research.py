"""Execute inspected tests with process/network effects denied before discovery."""
from pathlib import Path
import os
import sys
import unittest

root = Path(sys.argv[1]).resolve()
start = sys.argv[2]
pattern = sys.argv[3]
os.chdir(root)
sys.path.insert(0, str(root / "src"))
sys.path.insert(0, str(root / "tools" / "research"))
blocked = []
def deny_effects(event, args):
    if event in {"socket.connect", "socket.connect_ex", "socket.getaddrinfo",
                 "urllib.Request", "subprocess.Popen", "os.system", "os.posix_spawn"}:
        blocked.append(event)
        raise RuntimeError("Offline review denied " + event)
sys.addaudithook(deny_effects)
# h5py's platform.uname()[...] calls can lazily spawn `uname -p` in Python 3.12.
# Use the kernel-provided machine value for that cached informational field.
# The process/network audit hook stays installed and unchanged before imports.
import platform
platform.uname().processor = os.uname().machine
if os.environ.get('OI_REQUIRE_HDF5') == '1':
    import h5py
    import numpy
    assert (numpy.__version__, h5py.__version__) == ('2.3.5', '3.15.1')
suite = unittest.defaultTestLoader.discover(start, pattern=pattern)
result = unittest.TextTestRunner(verbosity=2).run(suite)
print("OFFLINE_RECEIPT", {"root": root.name, "tests": result.testsRun,
    "failures": len(result.failures), "errors": len(result.errors),
    "skipped": len(result.skipped), "blocked_effect_attempts": blocked,
    "dependency_versions": {name: getattr(sys.modules.get(name), '__version__', None)
                            for name in ('numpy', 'h5py')},
    "processor_metadata_source": "os.uname().machine; no subprocess"})
raise SystemExit(0 if result.wasSuccessful() and not blocked else 1)
