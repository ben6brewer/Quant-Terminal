"""FakeFred - deterministic, offline stand-in for ``fredapi.Fred``.

* Every FRED series id used in ``src`` is listed in ``fred_frequencies.json``
  with its real native frequency (D/W/M/Q/A).  Unknown ids raise
  ``ValueError`` exactly like fredapi ("Bad Request ... does not exist") -
  add new ids to the JSON.
* Values are generated from ``np.random.default_rng(zlib.crc32(id))`` (never
  ``hash()``), with a per-id magnitude profile (rates mean-revert around a
  realistic level, index/level series grow geometrically to a realistic end
  level, ``USREC`` is 0/1 with the real NBER recession spans).
* Every series ends on or before ``END_DATE`` (2026-06-30); daily series are
  business days with NaN on Jan 1 / Jul 4 / Dec 25 like FRED (DFEDTARU/L are
  "Daily, 7-Day": every calendar day); weekly series use the real weekday
  anchor (claims W-SAT, H.4.1/H.8 W-WED, mortgage W-THU, NFCI/STLFSI W-FRI).
* ``observation_start`` / ``observation_end`` only slice the full history, so
  incremental fetches see exactly the same values as full fetches.

Patch every app code path (all app code does ``from fredapi import Fred`` at
call time) with :func:`patch_fred` or the root-conftest ``fake_fred`` fixture::

    def test_x(fake_fred):                       # FakeFredController
        fake_fred.end_dates["PAYEMS"] = "2026-03-01"   # simulate a lagging series
        fake_fred.fail.add("UNRATE")                   # make one id raise
        fake_fred.overrides["USREC"] = my_series       # serve custom data
        data = LaborMarketFredService.fetch_all_data()
        assert ("PAYEMS", None, None) in fake_fred.calls
"""

from __future__ import annotations

import json
import sys
import threading
import zlib
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

FREQUENCIES_FILE = Path(__file__).with_name("fred_frequencies.json")
END_DATE = pd.Timestamp("2026-06-30")

FREQ_NAMES = {"D": "Daily", "W": "Weekly", "M": "Monthly", "Q": "Quarterly", "A": "Annual"}
_PANDAS_FREQ = {"D": "B", "M": "MS", "Q": "QS-JAN", "A": "YS-JAN"}
_STEPS_PER_YEAR = {"D": 261, "W": 52, "M": 12, "Q": 4, "A": 1}
_BASE_START = {"D": "2000-01-03", "W": "1990-01-01", "M": "1970-01-01", "Q": "1970-01-01", "A": "1970-01-01"}

WEEKLY_ANCHORS: Dict[str, str] = {
    **{k: "W-SAT" for k in ("ICSA", "CCSA", "IC4WSA")},
    **{k: "W-WED" for k in ("WALCL", "WSHOTSL", "WSHOMCB", "WSHOFADSL", "WLCFLL", "WRBWFRBL", "TOTLL")},
    **{k: "W-THU" for k in ("MORTGAGE30US", "MORTGAGE15US")},
    **{k: "W-FRI" for k in ("NFCI", "ANFCI", "NFCICREDIT", "NFCILEVERAGE", "NFCINONFINLEVERAGE", "STLFSI4")},
}

# NBER recessions (USREC = 1 for these months, inclusive)
NBER_RECESSIONS: List[Tuple[str, str]] = [
    ("1969-12-01", "1970-11-01"),
    ("1973-11-01", "1975-03-01"),
    ("1980-01-01", "1980-07-01"),
    ("1981-07-01", "1982-11-01"),
    ("1990-07-01", "1991-03-01"),
    ("2001-03-01", "2001-11-01"),
    ("2007-12-01", "2009-06-01"),
    ("2020-02-01", "2020-04-01"),
]

# ── Magnitude profiles ────────────────────────────────────────────────────────
# ("rate", mean, sd, floor, cap)   mean-reverting AR(1), 2-year half-life
# ("level", end_level, annual_drift, annual_vol)   geometric path ending at end_level


def _rates(ids, mean, sd, floor=None, cap=None):
    return {i: ("rate", mean, sd, floor, cap) for i in ids.split()}


def _levels(pairs, drift=0.03, vol=0.02):
    return {i: ("level", float(v), drift, vol) for i, v in (p.split("=") for p in pairs.split())}


PROFILES: Dict[str, tuple] = {
    **_rates("DGS1MO DGS3MO DGS6MO DGS1", 2.5, 1.8, 0.01),
    **_rates("DGS2 DGS3 DGS5", 3.0, 1.6, 0.05),
    **_rates("DGS7 DGS10 DGS20 DGS30", 3.8, 1.3, 0.3),
    **_rates("DFII5 DFII10 DFII20 DFII30", 0.9, 1.0),
    **_rates("FEDFUNDS", 2.5, 2.0, 0.05),
    **_rates("MORTGAGE30US", 6.0, 1.5, 2.6),
    **_rates("MORTGAGE15US", 5.3, 1.4, 2.1),
    **_rates("UNRATE UNRATENSA LNS14000003 LNS14000009 LNS14000024 LNS14000025 LNU04000036 "
             "LNU04000048 LNU04000086 LNU04000088 LNU04000089 LNU04000091 LNU04000093 "
             "LNU04000095 LNU04000097", 5.2, 1.5, 2.5),
    **_rates("LNS14000006", 9.0, 2.5, 4.5),
    **_rates("LNU04000012", 13.0, 3.0, 7.0),
    **_rates("U6RATE", 9.5, 2.5, 6.0),
    **_rates("CIVPART", 63.0, 1.5), **_rates("LNS11300060", 82.5, 1.0), **_rates("EMRATIO", 59.5, 2.0),
    **_rates("PSAVERT", 6.5, 2.5, 1.0),
    **_rates("TCU", 77.0, 3.0),
    **_rates("AAA10Y", 1.0, 0.4, 0.2), **_rates("BAA10Y", 2.0, 0.6, 0.8),
    **_rates("BAMLH0A0HYM2", 4.5, 1.8, 2.3), **_rates("T10Y2Y", 0.8, 1.0),
    **_rates("T10YIEM", 2.2, 0.3), **_rates("T5YIEM", 2.0, 0.4), **_rates("MICH", 3.0, 0.8, 0.5),
    **_rates("VIXCLS VXDCLS", 19.0, 7.0, 9.0), **_rates("VXNCLS VXEEMCLS VXVCLS", 22.0, 7.0, 11.0),
    **_rates("RVXCLS", 24.0, 7.0, 13.0), **_rates("OVXCLS", 35.0, 12.0, 15.0),
    **_rates("NFCI ANFCI NFCICREDIT NFCILEVERAGE NFCINONFINLEVERAGE", -0.3, 0.4),
    **_rates("STLFSI4 KCFSI", 0.0, 1.0), **_rates("CFNAI CFNAIMA3", 0.0, 0.6),
    **_rates("SAHMCURRENT", 0.3, 0.4, 0.0), **_rates("RECPROUSM156N", 8.0, 15.0, 0.0, 100.0),
    **_rates("UMCSENT", 80.0, 12.0, 50.0),
    **_rates("DRCCLACBS", 3.2, 1.0, 1.5), **_rates("DRCLACBS", 2.8, 1.0, 1.2), **_rates("DRALACBS", 2.3, 1.4, 1.0),
    **_rates("DRTSCILM DRTSCIS DRTSCLCC STDSAUTO SUBLPDHMSENQ", 5.0, 20.0, -40.0, 90.0),
    **_rates("ISRATIO", 1.35, 0.05, 1.2), **_rates("MNFCTRIRSA", 1.5, 0.1, 1.2),
    **_rates("RETAILIRSA", 1.3, 0.1, 1.0), **_rates("WHLSLRIRSA", 1.3, 0.08, 1.1),
    **_rates("MSACSR", 6.5, 2.0, 3.0), **_rates("MNMFS", 3.5, 1.0, 1.0),
    **_rates("M2V", 1.5, 0.2, 1.1), **_rates("A191RL1Q225SBEA", 2.5, 2.5),
    **_rates("GFDEGDQ188S", 85.0, 20.0, 30.0), **_rates("TDSP", 10.5, 1.0, 8.0),
    **_rates("COMREPUSQ159N", 4.0, 6.0), **_rates("HDTGPDUSQ163N", 75.0, 10.0),
    **_rates("RHORUSQ156N", 5.5, 1.5, 2.0),
    **_rates("DEXUSEU", 1.15, 0.12, 0.8), **_rates("DEXUSUK", 1.45, 0.2, 1.05),
    **_rates("DEXJPUS", 115.0, 15.0, 75.0), **_rates("DEXCHUS", 6.9, 0.4, 6.0),
    **_rates("DTWEXBGS", 115.0, 8.0, 90.0), **_rates("DTWEXAFEGS", 108.0, 8.0, 85.0),
    **_rates("DHHNGSP", 3.5, 1.5, 1.5), **_rates("DCOILWTICO", 65.0, 20.0, 15.0),
    **_rates("DCOILBRENTEU", 70.0, 20.0, 15.0),
    **_rates("WFRBST01134", 30.0, 2.0, 20.0), **_rates("WFRBSN09161", 30.0, 2.0, 20.0),
    **_rates("WFRBSN40188", 37.0, 1.5, 30.0), **_rates("WFRBSB50215", 2.5, 0.5, 1.0),
    **_rates("EXHOSLUSM495S", 5.0e6, 0.8e6, 2.5e6), **_rates("HSN1F", 650.0, 120.0, 280.0),
    **_rates("HOUST PERMIT", 1400.0, 250.0, 450.0), **_rates("HOUST1F PERMIT1", 950.0, 200.0, 350.0),
    **_rates("HOUST5F", 400.0, 90.0, 80.0),
    **_rates("ICSA IC4WSA", 230000.0, 40000.0, 180000.0), **_rates("CCSA", 1.8e6, 0.3e6, 1.1e6),
    **_rates("JTSJOL", 8000.0, 1800.0, 3000.0), **_rates("JTSHIL", 6000.0, 600.0, 4000.0),
    **_rates("JTSQUL", 3500.0, 700.0, 1800.0), **_rates("JTSLDR", 1700.0, 200.0, 1100.0),
    **_rates("TOTALSA", 16.0, 1.5, 9.0), **_rates("LAUTOSA", 3.5, 0.8, 1.5),
    **_rates("HTRUCKSSA", 0.45, 0.05, 0.25),
    **_rates("GACDFSA066MSFRBPHI GAFDISA066MSFRBNY BACTSAMFRBDAL", 2.0, 15.0, -60.0, 60.0),
    **_rates("NAPM NAPMEI NAPMNOI NMFBAI", 52.0, 4.0, 30.0, 70.0),
    **_rates("BOPGSTB", -70000.0, 20000.0),
    **_levels("CPIAUCSL=325 CPILFESL=330 CPIAPPSL=131 CPIEDUSL=146 CPIENGSL=285 CPIFABSL=340 "
              "CPIHOSSL=335 CPIMEDSL=585 CPIRECSL=136 CPITRNSL=282", 0.035, 0.012),
    **_levels("PCEPI=128 PCEPILFE=126 PPIFID=150 PPIFDS=152 PPICOR=147 PPIDES=146", 0.03, 0.015),
    **_levels("GDP=30500 GDPC1=23700 PCECC96=16500 PCEC=20500 GPDIC1=4500 GCEC1=4100 "
              "EXPGSC1=2600 IMPGSC1=3700 GPDI=5400 GCE=5200 EXPGS=3200 IMPGS=4100 GNPCA=22000",
              0.05, 0.02),
    **_levels("PAYEMS=159500 USCONS=8300 USEHS=27000 USFIRE=9200 USGOVT=23500 USINFO=3000 "
              "USLAH=17000 USPBS=23000 MANEMP=12700", 0.012, 0.008),
    **_levels("CES0500000003=37.5 ECIWAG=172 COMPRNFB=118 OPHNFB=116 ULCNFB=126", 0.03, 0.01),
    **_levels("M1SL=18800 M2SL=22000 WALCL=6600000 WSHOTSL=4200000 WSHOMCB=2100000 "
              "WSHOFADSL=2300 WLCFLL=5000 WRBWFRBL=3300000", 0.06, 0.04),
    **_levels("TOTLL=12900 BUSLOANS=2800 REALLN=5600 CONSUMER=1950 TOTALSL=5100 REVOLSL=1350 "
              "NONREVSL=3750 SLOAS=1750 CMDEBT=20500", 0.05, 0.03),
    **_levels("INDPRO=103 IPMAN=100 IPMINE=115", 0.015, 0.03),
    **_levels("DGORDER=310000 NEWORDER=74000 AMDMUO=1400000 RSAFS=740000 RRSFS=230000 "
              "BOPTEXP=265000 BOPTIMP=335000", 0.045, 0.04),
    **_levels("DSPI=22000 DSPIC96=17500 PI=25500 RPI=16800 PCE=20800 PCEC96=16600", 0.05, 0.015),
    **_levels("MEHOINUSA672N=80000 MEPAINUSA672N=43000", 0.035, 0.02),
    **_levels("CSUSHPINSA=330 SPCS20RSA=340 ASPUS=510000 MSPUS=420000", 0.045, 0.04),
    **_levels("GFDEBTN=37000000 FGCCSAQ027S=1300000 BOGZ1FL192090005Q=170000000", 0.07, 0.03),
    **_levels("POPTHM=342000 CNP16OV=275000 LFWA64TTUSM647S=210000000", 0.008, 0.001),
}
DEFAULT_PROFILE = ("level", 100.0, 0.02, 0.05)
DFEDTAR_START = pd.Timestamp("2008-12-16")
# "Daily, 7-Day" series: every calendar day, no holiday gaps
CALENDAR_DAILY = frozenset({"DFEDTARU", "DFEDTARL"})


# ─────────────────────────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def load_frequencies() -> Dict[str, str]:
    """``{series_id: "D"|"W"|"M"|"Q"|"A"}`` for every FRED id used in src."""
    with open(FREQUENCIES_FILE, encoding="utf-8") as fh:
        return dict(json.load(fh))


def _seed(series_id: str) -> int:
    return zlib.crc32(series_id.encode("utf-8"))


def native_index(series_id: str, freq: str, end: pd.Timestamp = END_DATE) -> pd.DatetimeIndex:
    """Observation dates for ``series_id`` at its native frequency, ending <= ``end``."""
    if series_id in ("DFEDTARU", "DFEDTARL"):
        start = DFEDTAR_START
    elif series_id == "USREC":
        start = pd.Timestamp("1970-01-01")
    else:
        start = pd.Timestamp(_BASE_START[freq]) + pd.DateOffset(years=_seed(series_id) % 6)
    if series_id in CALENDAR_DAILY:
        return pd.date_range(start, end, freq="D")
    pfreq = WEEKLY_ANCHORS.get(series_id, "W-FRI") if freq == "W" else _PANDAS_FREQ[freq]
    return pd.date_range(start, end, freq=pfreq)


def _ar1(rng, n, spy, mean, sd):
    phi = 0.5 ** (1.0 / (2.0 * spy))
    eps = rng.standard_normal(n)
    out = np.empty(n)
    x = mean + sd * eps[0]
    scale = sd * np.sqrt(1.0 - phi * phi)
    for i in range(n):
        if i:
            x = mean + phi * (x - mean) + scale * eps[i]
        out[i] = x
    return out


def _fed_target_lower(index: pd.DatetimeIndex) -> np.ndarray:
    """Step path for the fed-funds target lower bound (0.25 steps, 0..5.25)."""
    rng = np.random.default_rng(_seed("DFEDTAR"))
    months = pd.date_range(DFEDTAR_START.normalize().replace(day=1), END_DATE, freq="MS")
    steps = rng.choice([-0.25, 0.0, 0.0, 0.0, 0.25], size=len(months))
    level, path = 0.0, []
    for s in steps:
        level = min(max(level + s, 0.0), 5.25)
        path.append(level)
    monthly = pd.Series(path, index=months)
    return monthly.reindex(index, method="ffill").fillna(0.0).to_numpy()


@lru_cache(maxsize=512)
def _full_series_cached(series_id: str, freq: str, end: pd.Timestamp) -> pd.Series:
    idx = native_index(series_id, freq, end)
    n = len(idx)
    rng = np.random.default_rng(_seed(series_id))
    spy = _STEPS_PER_YEAR[freq]

    if series_id == "USREC":
        vals = np.zeros(n)
        for a, b in NBER_RECESSIONS:
            vals[(idx >= pd.Timestamp(a)) & (idx <= pd.Timestamp(b))] = 1.0
    elif series_id in ("DFEDTARL", "DFEDTARU"):
        vals = _fed_target_lower(idx) + (0.25 if series_id == "DFEDTARU" else 0.0)
    else:
        prof = PROFILES.get(series_id, DEFAULT_PROFILE)
        if prof[0] == "rate":
            _, mean, sd, floor, cap = prof
            vals = _ar1(rng, n, spy, mean, sd)
            if floor is not None:
                vals = np.maximum(vals, floor)
            if cap is not None:
                vals = np.minimum(vals, cap)
        else:
            _, end_level, drift, vol = prof
            steps = drift / spy + (vol / np.sqrt(spy)) * rng.standard_normal(n)
            logp = np.cumsum(steps)
            vals = end_level * np.exp(logp - logp[-1])
        vals = np.round(vals, 3)

    if freq == "D" and series_id not in CALENDAR_DAILY:
        md = idx.strftime("%m-%d")
        vals = np.where(np.isin(md, ["01-01", "07-04", "12-25"]), np.nan, vals)

    s = pd.Series(vals.astype("float64"), index=pd.DatetimeIndex(idx, freq=None))
    return s


def generate_series(series_id: str, freq: Optional[str] = None, end=END_DATE) -> pd.Series:
    """Full deterministic history for ``series_id`` (a fresh copy)."""
    if freq is None:
        freq = load_frequencies()[series_id]
    return _full_series_cached(series_id, freq, pd.Timestamp(end)).copy()


class FakeFredController:
    """Shared state/recorder for every FakeFred instance created by one patch.

    Attributes:
        frequencies: ``{id: "D"|"W"|"M"|"Q"|"A"}`` (copy; add ids to extend).
        calls: ``[(series_id, observation_start, observation_end), ...]`` in call order.
        overrides: ``{id: pd.Series}`` served instead of generated data (still sliced).
        fail: ids whose ``get_series`` raises ``ValueError``.
        end_dates: ``{id: date}`` truncate a series (simulate a lagging release).
        end: global last date (default 2026-06-30).
        instances: number of ``Fred(...)`` objects constructed.
    """

    def __init__(self):
        self.frequencies: Dict[str, str] = dict(load_frequencies())
        self.calls: List[Tuple[str, Optional[str], Optional[str]]] = []
        self.overrides: Dict[str, pd.Series] = {}
        self.fail: Set[str] = set()
        self.end_dates: Dict[str, object] = {}
        self.end = END_DATE
        self.instances = 0
        self._lock = threading.Lock()

    # public helpers -------------------------------------------------------
    def series(self, series_id: str, observation_start=None, observation_end=None) -> pd.Series:
        """What ``get_series`` returns for these args (without recording a call)."""
        if series_id in self.overrides:
            s = self.overrides[series_id].copy()
            s.index = pd.DatetimeIndex(s.index)
        else:
            if series_id not in self.frequencies:
                raise ValueError(
                    "Bad Request.  The series does not exist. "
                    f"(FakeFred: add {series_id!r} to tests/fixtures/fred_frequencies.json)"
                )
            s = generate_series(series_id, self.frequencies[series_id], self.end)
        cutoff = self.end_dates.get(series_id)
        if cutoff is not None:
            s = s[s.index <= pd.Timestamp(cutoff)]
        if observation_start is not None:
            s = s[s.index >= pd.Timestamp(observation_start)]
        if observation_end is not None:
            s = s[s.index <= pd.Timestamp(observation_end)]
        return s

    def call_ids(self) -> List[str]:
        return [c[0] for c in self.calls]

    def reset_calls(self) -> None:
        with self._lock:
            self.calls.clear()


DEFAULT_CONTROLLER = FakeFredController()


class FakeFred:
    """Drop-in for ``fredapi.Fred`` (``get_series``, ``get_series_info``)."""

    _controller: FakeFredController = DEFAULT_CONTROLLER

    def __init__(self, api_key=None, api_key_file=None, proxies=None, **kwargs):
        if not api_key and not api_key_file:
            raise ValueError("You need to set a valid API key. (FakeFred)")
        self.api_key = api_key
        ctl = self._controller
        with ctl._lock:
            ctl.instances += 1

    def get_series(self, series_id, observation_start=None, observation_end=None, **kwargs):
        if kwargs.get("frequency") or kwargs.get("aggregation_method"):
            raise NotImplementedError("FakeFred does not implement FRED frequency aggregation")
        ctl = self._controller
        start = None if observation_start is None else str(pd.Timestamp(observation_start).date())
        end = None if observation_end is None else str(pd.Timestamp(observation_end).date())
        with ctl._lock:
            ctl.calls.append((series_id, start, end))
        if series_id in ctl.fail:
            raise ValueError(f"Internal Server Error (FakeFred: {series_id} set to fail)")
        return ctl.series(series_id, observation_start, observation_end)

    def get_series_info(self, series_id):
        ctl = self._controller
        if series_id in ctl.fail or series_id not in ctl.frequencies:
            raise ValueError("Bad Request.  The series does not exist.")
        f = ctl.frequencies[series_id]
        s = ctl.series(series_id)
        return pd.Series({
            "id": series_id,
            "title": f"FakeFred {series_id}",
            "frequency": FREQ_NAMES[f],
            "frequency_short": f,
            "units": "Fake units",
            "observation_start": str(s.index[0].date()) if len(s) else None,
            "observation_end": str(s.index[-1].date()) if len(s) else None,
            "seasonal_adjustment_short": "SA",
        })

    # fredapi aliases used by some code bases
    get_series_latest_release = get_series


def make_fake_fred_class(controller: Optional[FakeFredController] = None):
    """A FakeFred subclass bound to ``controller`` (new controller if None)."""
    ctl = controller or FakeFredController()
    return type("FakeFred", (FakeFred,), {"_controller": ctl}), ctl


def patch_fred(monkeypatch, controller: Optional[FakeFredController] = None) -> FakeFredController:
    """Replace ``fredapi.Fred`` (and any already-imported ``app.*`` module-level
    ``Fred`` binding) with a FakeFred bound to ``controller``; returns it."""
    import fredapi
    import fredapi.fred as fredapi_fred

    real = fredapi_fred.Fred
    cls, ctl = make_fake_fred_class(controller)
    monkeypatch.setattr(fredapi, "Fred", cls)
    monkeypatch.setattr(fredapi_fred, "Fred", cls)
    for name, mod in list(sys.modules.items()):
        if mod is None or not (name == "app" or name.startswith("app.")):
            continue
        try:
            bound = vars(mod).get("Fred")
        except TypeError:
            continue
        if bound is real:
            monkeypatch.setattr(mod, "Fred", cls)
    return ctl
