"""Root conftest - test isolation harness, shared fixtures and CLI options.

IMPORT-TIME SIDE EFFECTS (run before ANY ``app`` import, because many app
modules compute cache/settings paths from ``Path.home()`` at import time):

* ``QT_QPA_PLATFORM=offscreen`` (override with ``QT_TEST_QPA_PLATFORM``).
* Windows + offscreen: ``QT_QPA_FONTDIR=%WINDIR%\\Fonts`` unless already set
  (otherwise the font database is empty), and the ``qapp`` fixture pins the
  default font to Segoe UI 9pt (:mod:`fixtures.qt_fonts`).
* ``HOME`` / ``USERPROFILE`` / ``HOMEDRIVE`` / ``HOMEPATH`` point at a fresh
  ``tempfile.mkdtemp(prefix="_QT_TEST_home_")`` directory, so every
  ``~/.quant_terminal`` write lands in a throw-away home.  The directory is
  deleted at exit unless ``QT_TEST_KEEP_HOME=1``.
* Every ``*_API_KEY`` environment variable is removed.
* A nested session (pytester / a subprocess started by a test) reuses the
  already-redirected home (env ``_QT_TEST_HOME_ACTIVE``/``_QT_TEST_REAL_HOME``).

AUTOUSE FIXTURES (every test):

* ``_fred_key_isolation`` - ``FredApiKeyService._api_key = "test_api_key"`` and
  ``env_file_path()`` redirected to ``<tmp_path>/.env`` (the real project
  ``.env`` is never read or written).
* ``_network_guard`` - ``socket.connect``/``getaddrinfo`` to non-localhost
  hosts raise :class:`NetworkBlockedError`, and
  ``YahooFinanceService.safe_download`` / ``safe_ticker_info`` raise it too
  (unless the test monkeypatched ``yfinance.download`` / ``yfinance.Ticker``,
  in which case the call is served in-process by the patched function).
  Lifted for tests marked ``@pytest.mark.network`` (which are skipped unless
  ``--network`` is given).
* ``_nonblocking_dialogs`` - for ``ui`` tests (and any test once QtWidgets is
  imported): ``QDialog.exec``/``QMessageBox`` statics/``QMenu.exec``/file,
  colour and input dialogs return immediately.  Request the
  ``nonblocking_dialogs`` fixture to inspect calls or change the results.

A session guard fails the run if the REAL ``~/.quant_terminal`` tree or the
project ``.env`` changed while tests ran.
"""

from __future__ import annotations

import atexit
import os
import shutil
import socket
import sys
import tempfile
from pathlib import Path, PurePath

# ─────────────────────────────────────────────────────────────────────────────
# Import-time isolation (must stay ABOVE every import of ``app``)
# ─────────────────────────────────────────────────────────────────────────────

os.environ["QT_QPA_PLATFORM"] = os.environ.get("QT_TEST_QPA_PLATFORM", "offscreen")

# On Windows the offscreen QPA looks for fonts in PySide6/lib/fonts (absent),
# so the font database is EMPTY: every glyph is a box and pyqtgraph menus/axes
# intermittently crash with access violations.  Point it at the system fonts
# before any QApplication exists (an explicit QT_QPA_FONTDIR wins).  The qapp
# fixture then pins the default font (see fixtures/qt_fonts.py).
if os.environ["QT_QPA_PLATFORM"] == "offscreen" and os.name == "nt" and not os.environ.get("QT_QPA_FONTDIR"):
    os.environ["QT_QPA_FONTDIR"] = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")

TESTS_DIR: Path = Path(__file__).resolve().parent
PROJECT_ROOT: Path = TESTS_DIR.parent
PROJECT_ENV_FILE: Path = PROJECT_ROOT / ".env"

# A nested session (pytester, or a subprocess started by a test) inherits an
# already-redirected home: reuse it instead of redirecting "home" twice.
_active = os.environ.get("_QT_TEST_HOME_ACTIVE")
NESTED_SESSION: bool = bool(_active) and Path(_active).is_dir() and Path.home().resolve() == Path(_active)
REAL_HOME: Path = Path(os.environ.get("_QT_TEST_REAL_HOME") or Path.home())

if NESTED_SESSION:
    TEST_HOME: Path = Path(_active)
else:
    _already_imported = sorted(m for m in sys.modules if m == "app" or m.startswith("app."))
    if _already_imported:  # pragma: no cover - safety net
        raise RuntimeError(
            "tests/conftest.py must run before any 'app' import, but these were "
            f"already imported: {_already_imported[:10]}"
        )
    TEST_HOME = Path(tempfile.mkdtemp(prefix="_QT_TEST_home_")).resolve()
    os.environ["_QT_TEST_HOME_ACTIVE"] = str(TEST_HOME)
    os.environ["_QT_TEST_REAL_HOME"] = str(REAL_HOME)
    if os.environ.get("QT_TEST_KEEP_HOME") != "1":
        atexit.register(shutil.rmtree, str(TEST_HOME), True)

os.environ["HOME"] = str(TEST_HOME)
os.environ["USERPROFILE"] = str(TEST_HOME)
if os.name == "nt":
    _drive, _tail = os.path.splitdrive(str(TEST_HOME))
    os.environ["HOMEDRIVE"] = _drive
    os.environ["HOMEPATH"] = _tail
if Path.home().resolve() != TEST_HOME:  # pragma: no cover - safety net
    raise RuntimeError(f"Home redirection failed: Path.home()={Path.home()} expected {TEST_HOME}")
if os.path.realpath(os.path.expanduser("~")) != os.path.realpath(str(TEST_HOME)):  # pragma: no cover
    raise RuntimeError("Home redirection failed for os.path.expanduser('~')")

for _var in [k for k in os.environ if k.upper().endswith("_API_KEY")]:
    os.environ.pop(_var, None)

# Make ``golden_utils`` and the ``fixtures`` package importable from anywhere.
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))


def _snapshot_tree(root: Path) -> dict:
    """{relative path: (size, mtime_ns)} for every file under ``root``."""
    snap = {}
    if not root.exists():
        return snap
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            p = Path(dirpath) / fn
            try:
                st = p.stat()
            except OSError:
                continue
            snap[str(p.relative_to(root))] = (st.st_size, st.st_mtime_ns)
    return snap


def _snapshot_real_state() -> dict:
    env = None
    if PROJECT_ENV_FILE.exists():
        st = PROJECT_ENV_FILE.stat()
        env = (st.st_size, st.st_mtime_ns)
    return {"home": _snapshot_tree(REAL_HOME / ".quant_terminal"), "env": env}


_REAL_STATE_BEFORE = _snapshot_real_state()

import pytest  # noqa: E402

from fixtures import NetworkBlockedError  # noqa: E402  (tests/ is on sys.path now)


# ─────────────────────────────────────────────────────────────────────────────
# CLI options, markers, collection
# ─────────────────────────────────────────────────────────────────────────────


def pytest_addoption(parser):
    parser.addoption(
        "--full",
        action="store_true",
        default=False,
        help="Run full test suite including UI tests (@pytest.mark.ui)",
    )
    parser.addoption(
        "--visual",
        action="store_true",
        default=False,
        help="Collect and run visual screenshot tests (@pytest.mark.visual, tests/visual/)",
    )
    parser.addoption(
        "--network",
        action="store_true",
        default=False,
        help="Run tests marked @pytest.mark.network (real network access allowed)",
    )
    parser.addoption(
        "--update-goldens",
        action="store_true",
        default=False,
        help="Rewrite golden files under tests/goldens/ instead of comparing",
    )


def pytest_configure(config):
    import golden_utils

    golden_utils.configure(update=bool(config.getoption("--update-goldens")))


def pytest_ignore_collect(collection_path, config):
    """tests/visual/ is not even collected unless --visual is given."""
    if config.getoption("--visual"):
        return None
    try:
        rel = Path(collection_path).resolve().relative_to(TESTS_DIR)
    except ValueError:
        return None
    if rel.parts and rel.parts[0] == "visual":
        return True
    return None


def pytest_collection_modifyitems(config, items):
    """Deselect visual tests (unless --visual); skip ui (unless --full) and network (unless --network)."""
    if not config.getoption("--visual"):
        kept, deselected = [], []
        for item in items:
            (deselected if item.get_closest_marker("visual") else kept).append(item)
        if deselected:
            config.hook.pytest_deselected(items=deselected)
            items[:] = kept

    run_ui = config.getoption("--full")
    run_network = config.getoption("--network")
    skip_ui = pytest.mark.skip(reason="UI tests require --full flag")
    skip_net = pytest.mark.skip(reason="network tests require --network flag")
    for item in items:
        # Markers only: ``item.keywords`` also holds directory names, so a
        # keyword test would skip everything under tests/ui/.
        if not run_ui and item.get_closest_marker("ui"):
            item.add_marker(skip_ui)
        if not run_network and item.get_closest_marker("network"):
            item.add_marker(skip_net)


def pytest_sessionfinish(session, exitstatus):
    """Fail the run if the REAL home or project .env changed while testing."""
    after = _snapshot_real_state()
    before = _REAL_STATE_BEFORE
    problems = []
    if after["env"] != before["env"]:
        problems.append(f"project .env changed: {before['env']} -> {after['env']}")
    bh, ah = before["home"], after["home"]
    for rel in sorted(set(bh) | set(ah)):
        if bh.get(rel) != ah.get(rel):
            problems.append(f"~/.quant_terminal/{rel}: {bh.get(rel)} -> {ah.get(rel)}")
    if problems:
        session.config._qt_real_state_problems = problems
        if os.environ.get("QT_TEST_ALLOW_REAL_HOME_CHANGES") != "1":
            session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    problems = getattr(config, "_qt_real_state_problems", None)
    if problems:
        terminalreporter.section("REAL USER DATA MODIFIED DURING TESTS", sep="!", red=True)
        for line in problems[:50]:
            terminalreporter.line(line, red=True)
    import golden_utils

    if golden_utils.WRITTEN:
        terminalreporter.section("goldens written (--update-goldens)", sep="-")
        for p in golden_utils.WRITTEN:
            terminalreporter.line(str(p))


# ─────────────────────────────────────────────────────────────────────────────
# Autouse isolation fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _fred_key_isolation(monkeypatch, tmp_path):
    """Fake FRED key; ``.env`` reads/writes go to ``<tmp_path>/.env``."""
    import app.core.paths as paths_mod
    import app.services.fred_api_key_service as fks

    env_file = tmp_path / ".env"
    monkeypatch.setattr(paths_mod, "env_file_path", lambda: env_file)
    monkeypatch.setattr(fks, "env_file_path", lambda: env_file)
    monkeypatch.setattr(fks.FredApiKeyService, "_api_key", "test_api_key")
    yield
    # load_dotenv() may have exported keys from the tmp .env into os.environ
    for var in [k for k in os.environ if k.upper().endswith("_API_KEY")]:
        os.environ.pop(var, None)


_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0", "", None}


def _host_of(address):
    if isinstance(address, tuple) and address:
        return address[0]
    return address  # AF_UNIX path or similar


def _is_local(host) -> bool:
    if isinstance(host, (bytes, bytearray)):
        host = host.decode(errors="ignore")
    if host in _LOCAL_HOSTS:
        return True
    return isinstance(host, str) and (host.startswith("127.") or host.lower() == "localhost")


def _is_local_socket(sock, address) -> bool:
    if getattr(socket, "AF_UNIX", None) is not None and sock.family == socket.AF_UNIX:
        return True
    return _is_local(_host_of(address))


def _yf_patched(attr: str):
    """Return yfinance.<attr> if a test monkeypatched it, else None."""
    yf = sys.modules.get("yfinance")
    if yf is None:
        return None
    fn = getattr(yf, attr, None)
    mod = getattr(fn, "__module__", "") or ""
    if fn is None or mod == "yfinance" or mod.startswith("yfinance."):
        return None
    return fn


@pytest.fixture(autouse=True)
def _network_guard(request, monkeypatch):
    """Block real network access unless the test is marked ``network``."""
    if request.node.get_closest_marker("network"):
        yield
        return

    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_getaddrinfo = socket.getaddrinfo

    def guarded_connect(self, address):
        if not _is_local_socket(self, address):
            raise NetworkBlockedError(f"network access blocked in tests: connect({address!r})")
        return real_connect(self, address)

    def guarded_connect_ex(self, address):
        if not _is_local_socket(self, address):
            raise NetworkBlockedError(f"network access blocked in tests: connect_ex({address!r})")
        return real_connect_ex(self, address)

    def guarded_getaddrinfo(host, *args, **kwargs):
        if not _is_local(host):
            raise NetworkBlockedError(f"network access blocked in tests: getaddrinfo({host!r})")
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)

    from app.services.yahoo_finance_service import YahooFinanceService

    def guarded_safe_download(cls, *args, **kwargs):
        fn = _yf_patched("download")
        if fn is not None:  # test patched yfinance.download -> serve in-process
            return fn(*args, **kwargs)
        raise NetworkBlockedError(
            "YahooFinanceService.safe_download blocked in tests "
            "(use the fake_yahoo fixture or mark the test @pytest.mark.network)"
        )

    def guarded_safe_ticker_info(cls, ticker, *args, **kwargs):
        fn = _yf_patched("Ticker")
        if fn is not None:
            return fn(ticker).info
        raise NetworkBlockedError(
            f"YahooFinanceService.safe_ticker_info({ticker!r}) blocked in tests "
            "(use the fake_yahoo fixture or mark the test @pytest.mark.network)"
        )

    monkeypatch.setattr(YahooFinanceService, "safe_download", classmethod(guarded_safe_download))
    monkeypatch.setattr(YahooFinanceService, "safe_ticker_info", classmethod(guarded_safe_ticker_info))
    yield


class DialogRecorder:
    """Controls/records the non-blocking dialog patches (see ``nonblocking_dialogs``).

    Attributes:
        calls: list of ``(kind, detail)`` tuples, e.g. ``("exec", "CustomMessageBox")``,
            ``("QMessageBox.warning", "<title>")``, ``("QFileDialog.getOpenFileName", "")``.
        exec_result: value returned by ``QDialog.exec`` (default 0 = Rejected).
        on_exec: optional ``callable(dialog) -> int`` run instead of returning
            ``exec_result`` (interact with the dialog, then return a code).
        question_result: returned by ``QMessageBox.question`` (default No).
        file_result: path string returned by QFileDialog getters (default "").
    """

    def __init__(self):
        self.calls = []
        self.exec_result = 0
        self.on_exec = None
        self.question_result = None
        self.file_result = ""


def _install_dialog_patches(monkeypatch, rec: DialogRecorder) -> None:
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import (
        QColorDialog,
        QDialog,
        QFileDialog,
        QInputDialog,
        QMenu,
        QMessageBox,
    )

    def fake_exec(self, *args, **kwargs):
        rec.calls.append(("exec", type(self).__name__))
        if rec.on_exec is not None:
            return rec.on_exec(self)
        return rec.exec_result

    for cls in (QDialog, QMessageBox):
        monkeypatch.setattr(cls, "exec", fake_exec)
        if hasattr(cls, "exec_"):
            monkeypatch.setattr(cls, "exec_", fake_exec, raising=False)

    def fake_menu_exec(self, *args, **kwargs):
        rec.calls.append(("QMenu.exec", self.title()))
        return None

    monkeypatch.setattr(QMenu, "exec", fake_menu_exec)
    if hasattr(QMenu, "exec_"):
        monkeypatch.setattr(QMenu, "exec_", fake_menu_exec, raising=False)

    def _msg(kind, default):
        def fn(*args, **kwargs):
            title = args[1] if len(args) > 1 else kwargs.get("title", "")
            rec.calls.append((f"QMessageBox.{kind}", title))
            if kind == "question" and rec.question_result is not None:
                return rec.question_result
            return default

        return staticmethod(fn)

    SB = QMessageBox.StandardButton
    for kind, default in (
        ("information", SB.Ok),
        ("warning", SB.Ok),
        ("critical", SB.Ok),
        ("about", None),
        ("question", SB.No),
    ):
        monkeypatch.setattr(QMessageBox, kind, _msg(kind, default))

    def _file(kind, tuple_result=True):
        def fn(*args, **kwargs):
            rec.calls.append((f"QFileDialog.{kind}", rec.file_result))
            if kind == "getOpenFileNames":
                return ([rec.file_result] if rec.file_result else [], "")
            return (rec.file_result, "") if tuple_result else rec.file_result

        return staticmethod(fn)

    monkeypatch.setattr(QFileDialog, "getOpenFileName", _file("getOpenFileName"))
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", _file("getOpenFileNames"))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", _file("getSaveFileName"))
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", _file("getExistingDirectory", False))

    def fake_get_color(*args, **kwargs):
        rec.calls.append(("QColorDialog.getColor", ""))
        return QColor()  # invalid colour == user cancelled

    monkeypatch.setattr(QColorDialog, "getColor", staticmethod(fake_get_color))

    def _input(kind, cancel_value):
        def fn(*args, **kwargs):
            rec.calls.append((f"QInputDialog.{kind}", args[1] if len(args) > 1 else ""))
            return (cancel_value, False)

        return staticmethod(fn)

    for kind, cancel in (("getText", ""), ("getInt", 0), ("getDouble", 0.0), ("getItem", ""),
                         ("getMultiLineText", "")):
        monkeypatch.setattr(QInputDialog, kind, _input(kind, cancel))


@pytest.fixture
def nonblocking_dialogs(monkeypatch) -> DialogRecorder:
    """Explicitly request the dialog patches; returns the :class:`DialogRecorder`."""
    rec = DialogRecorder()
    _install_dialog_patches(monkeypatch, rec)
    return rec


@pytest.fixture(autouse=True)
def _nonblocking_dialogs(request, monkeypatch):
    """Make modal dialogs non-blocking for ui tests (and once QtWidgets is loaded)."""
    if "nonblocking_dialogs" in request.fixturenames:
        yield  # the explicit fixture installs its own recorder
        return
    is_ui = request.node.get_closest_marker("ui") is not None
    if is_ui or "PySide6.QtWidgets" in sys.modules:
        _install_dialog_patches(monkeypatch, DialogRecorder())
    yield


# ─────────────────────────────────────────────────────────────────────────────
# Shared Qt fixtures (hoisted from tests/ui and tests/modules)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def qapp():
    """Session-scoped QApplication (offscreen). Overrides pytest-qt's ``qapp``.

    The default font is pinned (Segoe UI 9pt plus family substitutions, see
    :mod:`fixtures.qt_fonts`) so text metrics in goldens do not depend on
    which other fonts the machine has.
    """
    from PySide6.QtWidgets import QApplication

    from fixtures.qt_fonts import pin_app_font

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    pin_app_font()
    yield app


@pytest.fixture
def theme_manager(qapp):
    """Real ThemeManager instance (default theme 'bloomberg')."""
    from app.core.theme_manager import ThemeManager

    return ThemeManager()


@pytest.fixture
def mock_theme_manager():
    """MagicMock ThemeManager with .current_theme and .theme_changed signal."""
    from unittest.mock import MagicMock

    tm = MagicMock()
    tm.current_theme = "bloomberg"
    tm.theme_changed = MagicMock()
    tm.theme_changed.connect = MagicMock()
    return tm


# ─────────────────────────────────────────────────────────────────────────────
# Data / path fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_cache_dir(tmp_path):
    """Isolated temp directory for cache tests."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return cache_dir


@pytest.fixture
def tmp_settings_dir(tmp_path):
    """Isolated temp directory for settings tests."""
    settings_dir = tmp_path / "settings"
    settings_dir.mkdir()
    return settings_dir


@pytest.fixture
def test_home() -> Path:
    """The session-wide redirected home directory (shared by all tests)."""
    return TEST_HOME


def _rebase(value: PurePath, old_root: Path, new_root: Path):
    try:
        rel = Path(value).relative_to(old_root)
    except ValueError:
        return None
    return new_root / rel


@pytest.fixture
def fresh_home(monkeypatch):
    """Give this test its OWN empty home directory (yields its Path).

    Sets HOME/USERPROFILE to a new short ``%TEMP%/_QT_TEST_fresh_*`` directory
    (short on purpose: deep app cache paths under the long pytest basetemp can
    exceed Windows MAX_PATH; it is deleted afterwards) and re-roots every
    ``pathlib.Path`` attribute found on loaded ``app.*`` modules and on the
    classes they define that points inside the session home (e.g.
    ``base_fred_service.CACHE_DIR``, ``TickerMetadataService._CACHE_FILE``).
    Modules first imported during the test naturally resolve to the fresh
    home; at teardown their Path attributes are pointed back at the session
    home.  In-memory caches/flags (``_version_checked``, class ``_cache``
    dicts, cooldown timestamps) are NOT reset - reset those explicitly.
    """
    new_home = Path(tempfile.mkdtemp(prefix="_QT_TEST_fresh_")).resolve()
    monkeypatch.setenv("HOME", str(new_home))
    monkeypatch.setenv("USERPROFILE", str(new_home))
    if os.name == "nt":
        drive, tail = os.path.splitdrive(str(new_home))
        monkeypatch.setenv("HOMEDRIVE", drive)
        monkeypatch.setenv("HOMEPATH", tail)

    old_roots = [TEST_HOME]
    raw = Path(os.path.abspath(tempfile.gettempdir()))
    # also catch un-resolved (8.3 short name) spellings of the session home
    alt = raw / TEST_HOME.name
    if alt != TEST_HOME:
        old_roots.append(alt)

    for owner, attr, value in _app_path_attributes():
        for old in old_roots:
            new_value = _rebase(value, old, new_home)
            if new_value is not None:
                monkeypatch.setattr(owner, attr, new_value)
                break
    yield new_home
    # Modules first imported DURING the test computed their paths from the
    # fresh home; point them back at the session home (monkeypatch restores
    # everything it patched above right after this).
    for owner, attr, value in _app_path_attributes():
        restored = _rebase(value, new_home, TEST_HOME)
        if restored is not None:
            setattr(owner, attr, restored)
    shutil.rmtree(new_home, ignore_errors=True)


def _app_path_attributes():
    """Yield (owner, attr, PurePath) for app modules and the classes they define."""
    seen = set()
    for mod_name, mod in list(sys.modules.items()):
        if mod is None or not (mod_name == "app" or mod_name.startswith("app.")):
            continue
        try:
            mod_vars = vars(mod)
        except TypeError:
            continue
        owners = [mod] + [
            v for v in list(mod_vars.values())
            if isinstance(v, type) and getattr(v, "__module__", None) == mod_name
        ]
        for owner in owners:
            if id(owner) in seen:
                continue
            seen.add(id(owner))
            for attr, value in list(vars(owner).items()):
                if isinstance(value, PurePath):
                    yield owner, attr, value


# FakeFred / FakeYahoo fixtures (see tests/fixtures/*.py for the full API)


@pytest.fixture
def fake_fred(monkeypatch):
    """Patch ``fredapi.Fred`` (all app code paths) with FakeFred; returns the controller."""
    from fixtures.fake_fred import patch_fred

    return patch_fred(monkeypatch)


@pytest.fixture
def fake_yahoo(monkeypatch):
    """Patch YahooFinanceService.safe_download/safe_ticker_info (+ yfinance) with FakeYahoo."""
    from fixtures.fake_yahoo import patch_yahoo

    return patch_yahoo(monkeypatch)
