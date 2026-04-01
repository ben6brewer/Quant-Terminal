"""Crash debugging instrumentation for diagnosing segfaults.

Activate by calling install_crash_debugging() before app.exec().
All output goes to ~/.quant_terminal/crash_debug.log.

Safe to leave enabled — negligible performance impact.
Remove this file once the crash is diagnosed and fixed.
"""

import atexit
import datetime
import faulthandler
import sys
import threading
from pathlib import Path

LOG_PATH = Path.home() / ".quant_terminal" / "crash_debug.log"

# Module-level ref to keep the log file open for faulthandler
_log_file = None


def install_crash_debugging():
    """Install all crash debugging layers. Call once before app.exec()."""
    global _log_file

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Open in write mode to start fresh each run, unbuffered so writes survive crashes
    _log_file = open(LOG_PATH, "w", buffering=1)  # line-buffered

    _write(f"=== Crash debug session started: {datetime.datetime.now()} ===")
    _write(f"Python: {sys.version}")
    _write(f"Platform: {sys.platform}")

    # Layer 1: faulthandler — prints all-thread Python traceback on SIGSEGV/SIGBUS/SIGFPE
    faulthandler.enable(file=_log_file, all_threads=True)
    _write("faulthandler enabled (will dump all threads on segfault)")

    # Layer 2: Qt message handler — captures Qt internal warnings to disk
    _install_qt_message_handler()

    # Layer 3: Thread-safe dispatch verification (no monkey-patching!)
    _install_dispatch_verification()

    _write("All debug layers installed.\n")

    atexit.register(_on_exit)


def _write(msg: str):
    """Write a timestamped line to the crash log."""
    if _log_file and not _log_file.closed:
        ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        _log_file.write(f"[{ts}] {msg}\n")


def _on_exit():
    """Clean exit marker — if this appears in the log, the app exited normally."""
    _write("=== Clean exit ===")
    if _log_file and not _log_file.closed:
        _log_file.close()


# ── Layer 2: Qt Message Handler ──────────────────────────────────────────


def _install_qt_message_handler():
    from PySide6.QtCore import QtMsgType, qInstallMessageHandler

    _severity_map = {
        QtMsgType.QtDebugMsg: "DEBUG",
        QtMsgType.QtInfoMsg: "INFO",
        QtMsgType.QtWarningMsg: "WARNING",
        QtMsgType.QtCriticalMsg: "CRITICAL",
        QtMsgType.QtFatalMsg: "FATAL",
    }

    def _handler(mode, context, message):
        severity = _severity_map.get(mode, "UNKNOWN")
        loc = ""
        if context.file:
            loc = f" ({context.file}:{context.line})"
        _write(f"[Qt-{severity}]{loc} {message}")

        # Also print to stderr so it's visible in terminal
        print(f"[Qt-{severity}]{loc} {message}", file=sys.stderr)

    qInstallMessageHandler(_handler)
    _write("Qt message handler installed")


# ── Layer 3: Thread-Safe Dispatch Verification ───────────────────────────


def _install_dispatch_verification():
    """Add a thread-check directly in BaseModule._on_worker_thread_done.

    Does NOT monkey-patch the method (which broke PySide6's receiver
    detection). Instead, wraps only the non-signal-connected method.
    """
    from app.ui.modules.base_module import BaseModule

    _orig_thread_done = BaseModule._on_worker_thread_done

    def _verified_thread_done(self):
        is_main = threading.current_thread() is threading.main_thread()
        worker_type = type(self._worker).__name__ if self._worker else "None"
        has_result = self._worker.result is not None if self._worker else False
        has_error = self._worker.error_msg is not None if self._worker else False
        _write(
            f"[DISPATCH] {type(self).__name__}._on_worker_thread_done: "
            f"worker={worker_type}, result={'yes' if has_result else 'no'}, "
            f"error={'yes' if has_error else 'no'}, "
            f"main_thread={'YES' if is_main else 'NO *** WRONG THREAD ***'}"
        )
        return _orig_thread_done(self)

    BaseModule._on_worker_thread_done = _verified_thread_done
    _write("Dispatch verification installed (no signal monkey-patching)")
