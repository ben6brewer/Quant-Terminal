"""Tests for the root-conftest isolation harness (home, FRED key, network, dialogs)."""

import os
import socket
import threading
from pathlib import Path

import pandas as pd
import pytest

from fixtures import NetworkBlockedError


class TestHomeIsolation:
    def test_home_redirected(self, test_home):
        assert test_home.name.startswith("_QT_TEST_")
        assert Path.home() == test_home
        assert os.path.realpath(os.path.expanduser("~")) == os.path.realpath(str(test_home))

    def test_import_time_paths_under_test_home(self, test_home):
        from app.core import config, paths
        from app.services import base_fred_service

        for p in (paths.user_data_dir(), base_fred_service.CACHE_DIR, config.TILE_SCREENSHOT_DIR):
            assert Path(p).is_relative_to(test_home), p

    def test_qt_offscreen(self):
        assert os.environ["QT_QPA_PLATFORM"] == os.environ.get("QT_TEST_QPA_PLATFORM", "offscreen")

    def test_api_key_env_vars_removed(self):
        assert not [k for k in os.environ if k.upper().endswith("_API_KEY")]

    def test_fresh_home_reroots_paths(self, fresh_home, test_home):
        from app.services import base_fred_service
        from app.services.ticker_metadata_service import TickerMetadataService

        assert Path.home() == fresh_home
        assert fresh_home != test_home
        assert base_fred_service.CACHE_DIR.is_relative_to(fresh_home)
        assert base_fred_service._FRED_VERSION_FILE.is_relative_to(fresh_home)
        cache_file = getattr(TickerMetadataService, "_CACHE_FILE", None)
        if isinstance(cache_file, Path):
            assert cache_file.is_relative_to(fresh_home)


class TestFredKeyIsolation:
    def test_fake_key(self):
        from app.services.fred_api_key_service import FredApiKeyService

        assert FredApiKeyService.get_api_key() == "test_api_key"
        assert FredApiKeyService.has_api_key()

    def test_env_file_redirected(self, tmp_path):
        from app.core import paths
        from app.services import fred_api_key_service as fks

        assert paths.env_file_path() == tmp_path / ".env"
        fks.FredApiKeyService.set_api_key("_QT_TEST_key")
        assert (tmp_path / ".env").read_text() == "FRED_API_KEY=_QT_TEST_key\n"


class TestNetworkGuard:
    def test_dns_blocked(self):
        with pytest.raises(NetworkBlockedError):
            socket.create_connection(("example.com", 80), timeout=1)

    def test_ip_connect_blocked(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            with pytest.raises(NetworkBlockedError):
                s.connect(("93.184.216.34", 80))
            with pytest.raises(NetworkBlockedError):
                s.connect_ex(("8.8.8.8", 53))
        finally:
            s.close()

    def test_localhost_allowed(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]
        t = threading.Thread(target=lambda: server.accept()[0].close(), daemon=True)
        t.start()
        client = socket.create_connection(("localhost", port), timeout=5)
        client.close()
        t.join(5)
        server.close()

    def test_urllib_blocked(self):
        import urllib.request

        with pytest.raises(Exception) as exc:
            urllib.request.urlopen("http://example.com", timeout=1)
        assert "network access blocked" in str(exc.value)

    def test_yahoo_safe_calls_blocked(self):
        from app.services.yahoo_finance_service import YahooFinanceService

        with pytest.raises(NetworkBlockedError):
            YahooFinanceService.safe_download(tickers="AAPL", period="5d")
        with pytest.raises(NetworkBlockedError):
            YahooFinanceService.safe_ticker_info("AAPL")
        # app code degrades gracefully
        assert YahooFinanceService.fetch_historical("AAPL", "2024-01-01", "2024-02-01").empty

    def test_patched_yfinance_download_served_in_process(self, monkeypatch):
        from app.services.yahoo_finance_service import YahooFinanceService

        df = pd.DataFrame({"Close": [1.0]}, index=pd.DatetimeIndex(["2024-01-02"]))
        monkeypatch.setattr("yfinance.download", lambda *a, **k: df)
        assert YahooFinanceService.safe_download(tickers="AAPL") is df

    def test_real_fredapi_blocked(self):
        """Unpatched fredapi hits urlopen -> blocked; the base service logs and returns None."""
        from app.services.base_fred_service import BaseFredService

        assert BaseFredService._fetch_full({"_QT_TEST": "GDP"}, Path(os.devnull)) is None

    @pytest.mark.network
    def test_network_marker_lifts_guard(self):
        assert socket.getaddrinfo.__module__ == "socket"


@pytest.mark.ui
class TestNonBlockingDialogs:
    def test_qdialog_exec_returns_immediately(self, qapp):
        from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox

        assert QDialog().exec() == 0
        assert QMessageBox.question(None, "t", "q") == QMessageBox.StandardButton.No
        assert QMessageBox.warning(None, "t", "w") == QMessageBox.StandardButton.Ok
        assert QFileDialog.getOpenFileName(None, "open") == ("", "")
        assert QFileDialog.getExistingDirectory(None, "dir") == ""

    def test_custom_message_box_nonblocking(self, qapp, theme_manager):
        from app.ui.widgets.common.custom_message_box import CustomMessageBox

        CustomMessageBox.warning(theme_manager, None, "_QT_TEST", "warning")
        assert CustomMessageBox.question(theme_manager, None, "_QT_TEST", "?") == CustomMessageBox.Cancel

    def test_recorder_controls_results(self, qapp, nonblocking_dialogs):
        from PySide6.QtWidgets import QDialog, QMessageBox

        nonblocking_dialogs.exec_result = QDialog.DialogCode.Accepted
        assert QDialog().exec() == QDialog.DialogCode.Accepted
        nonblocking_dialogs.on_exec = lambda dlg: 7
        assert QDialog().exec() == 7
        nonblocking_dialogs.question_result = QMessageBox.StandardButton.Yes
        assert QMessageBox.question(None, "_QT_TEST", "?") == QMessageBox.StandardButton.Yes
        kinds = [c[0] for c in nonblocking_dialogs.calls]
        assert kinds == ["exec", "exec", "QMessageBox.question"]

    def test_fred_module_show_without_key_does_not_block(self, qapp, theme_manager, monkeypatch):
        """FredDataModule._initialize_data opens APIKeyDialog.exec() when no key exists."""
        from app.services.fred_api_key_service import FredApiKeyService
        from app.ui.modules.fred_base_module import FredDataModule

        monkeypatch.setattr(FredApiKeyService, "_api_key", None)
        monkeypatch.setattr(FredApiKeyService, "_load_api_key", classmethod(lambda cls: None))
        shown = []
        monkeypatch.setattr(FredDataModule, "_fetch_data", lambda self: shown.append("fetch"), raising=False)

        from app.core.config import ALL_MODULES
        import importlib

        entry = next(e for e in ALL_MODULES if e["id"] == "pce")
        mod_path, cls_name = entry["class"].split(":")
        cls = getattr(importlib.import_module(mod_path), cls_name)
        widget = cls(theme_manager)
        widget._initialize_data()  # would block forever without the dialog patch
        assert shown == []
        widget.deleteLater()
