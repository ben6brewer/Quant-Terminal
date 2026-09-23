"""Offline test doubles and data fixtures.

* :mod:`fixtures.fake_fred`  - ``FakeFred`` / ``patch_fred`` (fredapi stand-in)
* :mod:`fixtures.fake_yahoo` - ``FakeYahooController`` / ``patch_yahoo`` (yfinance stand-in)
* ``fred_frequencies.json``  - native frequency (D/W/M/Q/A) of every FRED id used in ``src``
* :class:`NetworkBlockedError` - raised by the root-conftest network guard
"""


class NetworkBlockedError(RuntimeError):
    """Raised when a test (not marked ``network``) tries to reach the network."""
