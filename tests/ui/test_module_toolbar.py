"""Tests for module toolbars - setup and theme."""

import pytest


@pytest.mark.ui
class TestModuleToolbar:
    def test_cpi_toolbar_imports(self):
        from app.ui.modules.cpi.widgets.cpi_toolbar import CpiToolbar
        assert CpiToolbar is not None

    def test_pce_toolbar_imports(self):
        from app.ui.modules.pce.widgets.pce_toolbar import PceToolbar
        assert PceToolbar is not None

    def test_ppi_toolbar_imports(self):
        from app.ui.modules.ppi.widgets.ppi_toolbar import PpiToolbar
        assert PpiToolbar is not None

    def test_fred_toolbar_imports(self):
        from app.ui.modules.fred_toolbar import FredToolbar
        assert FredToolbar is not None

    def test_module_toolbar_imports(self):
        from app.ui.modules.module_toolbar import ModuleToolbar
        assert ModuleToolbar is not None
