"""Tests for app.services.favorites_service.FavoritesService."""

import pytest

from app.services.favorites_service import FavoritesService


class TestFavoritesService:
    @pytest.fixture(autouse=True)
    def reset(self, tmp_path, monkeypatch):
        FavoritesService._favorites = set()
        monkeypatch.setattr(FavoritesService, "_SAVE_PATH", tmp_path / "favorites.json")
        yield
        FavoritesService._favorites = set()

    def test_toggle_favorite(self):
        result = FavoritesService.toggle_favorite("charts")
        assert result is True
        assert FavoritesService.is_favorite("charts") is True

    def test_toggle_off(self):
        FavoritesService.toggle_favorite("charts")
        result = FavoritesService.toggle_favorite("charts")
        assert result is False
        assert FavoritesService.is_favorite("charts") is False

    def test_get_favorites(self):
        FavoritesService.toggle_favorite("charts")
        FavoritesService.toggle_favorite("monte_carlo")
        favs = FavoritesService.get_favorites()
        assert "charts" in favs
        assert "monte_carlo" in favs

    def test_is_favorite_false(self):
        assert FavoritesService.is_favorite("nonexistent") is False

    def test_persistence(self, tmp_path, monkeypatch):
        monkeypatch.setattr(FavoritesService, "_SAVE_PATH", tmp_path / "favorites.json")
        FavoritesService.toggle_favorite("charts")
        FavoritesService.save_favorites()

        # Reload
        FavoritesService._favorites = set()
        FavoritesService.load_favorites()
        assert FavoritesService.is_favorite("charts") is True
