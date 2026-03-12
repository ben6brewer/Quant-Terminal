"""Tests for app.services.fred_api_key_service.FredApiKeyService."""

import pytest

from app.services.fred_api_key_service import FredApiKeyService


class TestFredApiKeyService:
    @pytest.fixture(autouse=True)
    def reset_cache(self):
        """Reset class-level cache between tests."""
        FredApiKeyService._api_key = None
        yield
        FredApiKeyService._api_key = None

    def test_set_and_get(self):
        """Setting cache directly should be returned by get_api_key."""
        FredApiKeyService._api_key = "test_key_123"
        assert FredApiKeyService.get_api_key() == "test_key_123"

    def test_has_api_key_false(self, monkeypatch):
        """No key set - should return False."""
        monkeypatch.setattr(
            "app.services.fred_api_key_service.FredApiKeyService._load_api_key",
            classmethod(lambda cls: None),
        )
        assert FredApiKeyService.has_api_key() is False

    def test_has_api_key_true(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.fred_api_key_service.FredApiKeyService._load_api_key",
            classmethod(lambda cls: "some_key"),
        )
        assert FredApiKeyService.has_api_key() is True

    def test_cached_key_returned(self):
        """If _api_key is set, _load_api_key returns it without file I/O."""
        FredApiKeyService._api_key = "cached_key"
        assert FredApiKeyService.get_api_key() == "cached_key"

    def test_set_api_key_writes_env(self, tmp_path, monkeypatch):
        """set_api_key should write to .env file (redirected to tmp_path)."""
        import app.services.fred_api_key_service as mod

        fake_file = tmp_path / "src" / "app" / "services" / "fred_api_key_service.py"
        fake_file.parent.mkdir(parents=True, exist_ok=True)
        fake_file.touch()
        monkeypatch.setattr(mod, "__file__", str(fake_file))

        FredApiKeyService.set_api_key("new_key")
        assert FredApiKeyService._api_key == "new_key"
        env_path = tmp_path / ".env"
        assert env_path.exists()
        assert "FRED_API_KEY=new_key" in env_path.read_text()
