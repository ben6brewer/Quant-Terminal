"""Tests for module toolbars - setup and theme.

Note: the dedicated ``PceToolbar`` / ``PpiToolbar`` classes no longer exist;
the PCE and PPI modules build the shared ``FredToolbar`` directly, so those
import tests now assert that wiring instead.
"""

import pytest


@pytest.mark.ui
class TestModuleToolbar:
    def test_cpi_toolbar_imports(self):
        from app.ui.modules.cpi.widgets.cpi_toolbar import CpiToolbar
        from app.ui.modules.fred_toolbar import FredToolbar

        assert issubclass(CpiToolbar, FredToolbar)

    def test_pce_uses_shared_fred_toolbar(self):
        from app.ui.modules.fred_toolbar import FredToolbar
        from app.ui.modules.pce import pce_module

        assert pce_module.FredToolbar is FredToolbar

    def test_ppi_uses_shared_fred_toolbar(self):
        from app.ui.modules.fred_toolbar import FredToolbar
        from app.ui.modules.ppi import ppi_module

        assert ppi_module.FredToolbar is FredToolbar

    def test_fred_toolbar_imports(self):
        from app.ui.modules.fred_toolbar import FredToolbar
        assert FredToolbar is not None

    def test_module_toolbar_imports(self):
        from app.ui.modules.module_toolbar import ModuleToolbar
        assert ModuleToolbar is not None
