"""Fixtures for tests/config: run code in a fresh Python interpreter.

The startup-import guard and the import-everything check need a pristine
``sys.modules``, so they run in a child interpreter rather than in the
pytest process, where other tests have already imported half the app.

The child process:

* inherits the harness environment. The root conftest has already pointed
  HOME/USERPROFILE at the throw-away ``_QT_TEST_home_*`` directory and
  removed every ``*_API_KEY``, so the child never touches the real
  ``~/.quant_terminal``.
* gets ``PYTHONPATH=<the src dir pytest imported app from>``. This beats
  the editable-install ``.pth`` (which points at the main checkout), so a
  worktree run tests its own sources. The child verifies this before
  reporting.
* blocks every non-localhost socket connect/getaddrinfo, so an import-time
  network call fails loudly instead of leaving the machine.
* reports through a JSON file, because app modules print to stdout at
  import time.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

import app

APP_DIR = Path(app.__file__).resolve().parent
SRC_DIR = APP_DIR.parent

CHILD_PRELUDE = '''\
import json
import socket
import sys
from pathlib import Path

SRC_DIR = Path(sys.argv[1]).resolve()
RESULT_FILE = Path(sys.argv[2])

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0", "", None}


def _is_local(host):
    if isinstance(host, (bytes, bytearray)):
        host = host.decode(errors="ignore")
    if host in _LOCAL_HOSTS:
        return True
    return isinstance(host, str) and (host.startswith("127.") or host.lower() == "localhost")


def _host_of(address):
    return address[0] if isinstance(address, tuple) and address else address


_real_connect = socket.socket.connect
_real_connect_ex = socket.socket.connect_ex
_real_getaddrinfo = socket.getaddrinfo


def _guarded_connect(self, address):
    if getattr(socket, "AF_UNIX", None) != self.family and not _is_local(_host_of(address)):
        raise RuntimeError(f"network access blocked in test child: connect({address!r})")
    return _real_connect(self, address)


def _guarded_connect_ex(self, address):
    if getattr(socket, "AF_UNIX", None) != self.family and not _is_local(_host_of(address)):
        raise RuntimeError(f"network access blocked in test child: connect_ex({address!r})")
    return _real_connect_ex(self, address)


def _guarded_getaddrinfo(host, *args, **kwargs):
    if not _is_local(host):
        raise RuntimeError(f"network access blocked in test child: getaddrinfo({host!r})")
    return _real_getaddrinfo(host, *args, **kwargs)


socket.socket.connect = _guarded_connect
socket.socket.connect_ex = _guarded_connect_ex
socket.getaddrinfo = _guarded_getaddrinfo


def app_location():
    """Resolved path of the imported ``app`` package (must be under SRC_DIR)."""
    import app

    return str(Path(app.__file__).resolve())


def write_result(obj):
    RESULT_FILE.write_text(json.dumps(obj, sort_keys=True), encoding="utf-8")

'''


def _child_env() -> dict:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = os.pathsep.join([str(SRC_DIR)] + ([existing] if existing else []))
    env["PYTHONDONTWRITEBYTECODE"] = "1"  # never litter src/ with __pycache__
    env["PYTHONIOENCODING"] = "utf-8"  # app modules print non-ASCII at import time
    env["QT_QPA_PLATFORM"] = "offscreen"
    return env


@pytest.fixture(scope="module")
def run_child(tmp_path_factory):
    """Return ``run(name, body) -> dict``: run ``body`` in a fresh interpreter.

    ``body`` runs after :data:`CHILD_PRELUDE`, so it can use ``SRC_DIR``,
    ``app_location()`` and ``write_result(obj)``. It must call
    ``write_result``; the parsed JSON is returned. If the child exits
    non-zero or writes no result, the call raises RuntimeError with the
    tail of its output. It never returns partial data.
    """

    def run(name: str, body: str, *, timeout: float = 240) -> dict:
        work = tmp_path_factory.mktemp(name)
        script = work / f"{name}_child.py"
        result_file = work / "result.json"
        script.write_text(CHILD_PRELUDE + textwrap.dedent(body), encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(script), str(SRC_DIR), str(result_file)],
            cwd=str(work),
            env=_child_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        if proc.returncode != 0 or not result_file.exists():
            raise RuntimeError(
                f"child {name!r} failed (rc={proc.returncode}, result written={result_file.exists()})\n"
                f"--- stdout (tail) ---\n{proc.stdout[-4000:]}\n--- stderr (tail) ---\n{proc.stderr[-4000:]}"
            )
        result = json.loads(result_file.read_text(encoding="utf-8"))
        location = Path(result["app_location"])
        if SRC_DIR not in location.parents:
            raise RuntimeError(f"child {name!r} imported app from {location}, expected it under {SRC_DIR}")
        return result

    return run
