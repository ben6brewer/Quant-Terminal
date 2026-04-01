# Quant Terminal Crash Diagnosis — Handoff Document

## The Problem

PySide6 desktop app segfaults on macOS when switching between modules. The crash is **real heap corruption** (use-after-free) confirmed by macOS malloc on PySide6 6.8.1 (`malloc: Corruption of free object: msizes N/0 disagree`). On PySide6 6.10.x it manifests as `PySide::SignalManager::retrieveMetaObject(_object*) → NULL (0x0)` in all 6 native .ips crash reports (in `~/Library/Logs/DiagnosticReports/Retired/Python-2026-03-2*.ips`).

## Environment

- macOS Sonoma 14.4.1, Apple M1 (ARM64)
- Python 3.12.13 (ARM64 via `/opt/homebrew`, previously x86_64 via `/usr/local`)
- PySide6 6.10.2 / shiboken6 6.10.2 (tested 6.8.1, 6.10.1, 6.10.2)
- pyqtgraph 0.14.0, numpy 2.4.4, pandas 2.3.3, pyarrow 22.0.0
- yfinance 1.0 (curl_cffi 0.13.0) — isolated in subprocesses via subprocess.run()

## Crash Pattern

- Always after 3-10 successful module open/close cycles
- Always during widget construction, rendering, or basic Qt operations on the main thread
- Crash site is random (QWidget, QCheckBox, QPushButton, QGraphicsWidget, QGraphicsObject, QStackedWidget.addWidget, PlotDataItem, ProbabilityTableView, etc.)
- All dispatches verified running on main_thread=YES
- faulthandler shows only main thread crashing; background threads idle

## What Was Tested and Eliminated

| # | Theory | Test | Result |
|---|--------|------|--------|
| 1 | curl_cffi heap corruption | Subprocess isolation via `subprocess.run()` — curl_cffi never loaded in Qt process | Still crashes |
| 2 | Rosetta x86→ARM translation | Switched to ARM64 Python (`/opt/homebrew/bin/python3.12`) | Still crashes |
| 3 | shiboken6 6.10.1 regression | Upgraded to 6.10.2 (has threading fix for retrieveMetaObject) | Still crashes |
| 4 | PySide6 6.10.x regression | Downgraded to PySide6 6.8.1 | Still crashes (but revealed malloc corruption error instead of segfault) |
| 5 | ProcessPoolExecutor daemon threads | Replaced with subprocess.run() (zero daemon threads in Qt process) | Still crashes |
| 6 | Python garbage collector | Disabled GC entirely (`gc.disable()`) | Still crashes |
| 7 | deleteLater double-free | Removed ALL deleteLater() calls on workers/threads across 8 files | Still crashes |
| 8 | QThread lifecycle | Made all data fetching synchronous (no QThread at all) | Still crashes |
| 9 | Module destruction | Previously tested with destruction disabled entirely | Still crashes |
| 10 | Wrong-thread signals | All dispatches verified main_thread=YES via debug_crash.py | Not the cause |
| 11 | pyqtgraph unsupported MRO | Disabled all pyqtgraph chart creation, kept only QWidget-based table | Still crashes (9 successful switches before crash) |
| 12 | Guard Malloc | `DYLD_INSERT_LIBRARIES=/usr/lib/libgmalloc.dylib` | Too slow — app doesn't reach crash before user has to kill it |
| 13 | MallocStackLogging | `MallocStackLogging=lite` | App froze without generating .ips crash report |
| 14 | MallocScribble + MallocGuardEdges | Tested earlier on x86_64 | Crash stack was identical, didn't shift crash site |
| 15 | lldb | Attempted native debugging | Hangs on Rosetta (x86_64). Not re-attempted on ARM64 |
| 16 | numpy yanked version | Upgraded from yanked 2.4.0 to 2.4.4 | Still crashes |

## What We Know For Certain

1. **Real heap corruption** — macOS malloc confirms use-after-free (`msizes N/0 disagree` on PySide6 6.8.1)
2. **NOT threading** — crashes with zero threads (synchronous execution)
3. **NOT pyqtgraph** — crashes without any pyqtgraph widgets
4. **NOT PySide6 version** — crashes on 6.8.1, 6.10.1, 6.10.2
5. **NOT architecture** — crashes on both x86_64 (Rosetta) and ARM64 (native)
6. **NOT GC** — crashes with gc.disable()
7. **NOT deleteLater** — crashes without any deleteLater calls
8. **NOT curl_cffi** — crashes with curl_cffi isolated in subprocesses
9. **Accumulates over module switches** — always takes 3-10 cycles before crash
10. **Always on main thread** — single-threaded crash in C++ widget code

## Native Crash Reports (.ips files)

Six crash reports in `~/Library/Logs/DiagnosticReports/Retired/` (all from PySide6 6.10.1 on x86_64):

All show identical stack:
```
#0  libpyside6.abi3.6.10.dylib  PySide::SignalManager::retrieveMetaObject(_object*)  → NULL (0x0)
#1  QtWidgets.abi3.so           Sbk_<Widget>_Init(...)
```

Widgets hit: QCheckBox, QPushButton, QRadioButton, QGraphicsWidget, QObject.

On PySide6 6.8.1, the same corruption manifests as malloc detecting `msizes N/0 disagree` on freed objects — the corruption damages the freed block's metadata before `retrieveMetaObject` can read it.

## What Has NOT Been Tried

1. **lldb on ARM64** — lldb failed on x86_64/Rosetta but was never tried on ARM64 native Python. This could give a real C++ backtrace.

2. **PyQt6 instead of PySide6** — PyQt6 uses SIP bindings instead of shiboken6. If the crash stops, it's a shiboken6 bug. This is a significant code change (import paths differ).

3. **Dummy data (no subprocess.run)** — Test with hardcoded/dummy DataFrames instead of fetching real data. This would isolate whether the subprocess.run + pickle round-trip corrupts data.

4. **Different module** — All testing was done with RateProbabilityModule. Test with a completely different module to confirm it's not RateProbability-specific.

5. **Minimal reproduction** — Create a tiny PySide6 app that just creates/destroys QWidgets in a loop. If it crashes, it's a PySide6/macOS bug, not app code.

6. **Address Sanitizer** — Build Python with ASan to catch the exact corruption. Requires compiling Python from source.

7. **Older pyqtgraph** — Try pyqtgraph 0.13.x to rule out a 0.14.0 regression.

8. **Process the data without rendering** — Fetch data and process it but don't create/update any widgets. Would isolate whether corruption is in data processing vs widget code.

## Current State of Code Changes (branch `bb`)

### Changes kept (independently correct):
- `yahoo_finance_service.py` — subprocess isolation via subprocess.run() (no daemon threads)
- `calculation_worker.py` — removed dead legacy signal emissions
- `base_module.py` — removed deleteLater on workers/threads, fixed zombie thread cleanup
- `config.py` — DATA_FETCH_THREADS = False
- `statistics_service.py`, `metals_yfinance_service.py`, `ticker_metadata_service.py` — route through safe_download()
- 7 other files — removed deleteLater on workers/threads (ticker_list_panel, asset_class_returns, depth_chart, live_update_manager, rate_probability, portfolio_construction x2, monte_carlo, transaction_log_table x2)

### Diagnostic changes still in place (should revert):
- `rate_probability_module.py` — pyqtgraph charts commented out + hasattr guards (REVERT)
- `main.py` — faulthandler re-enabled (KEEP)

### Environment changes:
- Python switched from x86_64 (`/usr/local`) to ARM64 (`/opt/homebrew`) — old venv backed up at `.venv_x86_backup`
- PySide6 upgraded from 6.10.1 → 6.10.2
- numpy upgraded from yanked 2.4.0 → 2.4.4

## Debug Infrastructure

- `src/app/debug_crash.py` — faulthandler + Qt message handler + dispatch verification
- Logs to `~/.quant_terminal/crash_debug.log`
- Native crash reports: `~/Library/Logs/DiagnosticReports/Retired/Python-2026-03-2*.ips`

## Recommended Next Steps (in priority order)

1. **Try lldb on ARM64** — `lldb -- .venv/bin/python -m src.app.main` then `run`, switch modules until crash, `bt` for backtrace. This should work now (previously failed on Rosetta).

2. **Minimal reproduction** — Create a 20-line PySide6 script that creates/destroys widgets in a loop (no pyqtgraph, no data, no threads). If it crashes, file a shiboken6 bug.

3. **Test with a different module** — Open a module other than RateProbability to confirm the bug isn't specific to that module's data/rendering code.

4. **Dummy data test** — Replace the service function with one that returns a hardcoded dict. If crash stops, subprocess.run pickle round-trip is corrupting data.

5. **Try PyQt6** — The nuclear option. If it works, we know shiboken6 has a fundamental bug on macOS ARM64.
