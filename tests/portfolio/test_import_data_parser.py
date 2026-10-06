"""Characterization: the import_data file parser (``parse_returns_file``) on small
CSV/XLSX fixtures written at test time, plus the module's parse-and-save worker
function end to end into ``custom_data_service``.
"""

from __future__ import annotations

import io

import numpy as np
import pandas as pd
import pytest

from app.services import custom_data_service as cds
from app.ui.modules.import_data.import_data_module import _parse_and_save
from app.ui.modules.import_data.parser import SUPPORTED_EXTENSIONS, parse_returns_file

from ._helpers import CUSTOM_NAME, PREFIX, assert_golden

# pandas >= 3 reads text columns as StringDtype instead of object.  The parser only
# runs its per-cell "%"-stripping / row-numbered error path for ``dtype == object``,
# so on those pandas versions any text value falls through to ``astype(float64)``.
TEXT_IS_STRING_DTYPE = pd.read_csv(io.StringIO("v\nx\n"))["v"].dtype != object
string_dtype_bug = pytest.mark.xfail(
    TEXT_IS_STRING_DTYPE, strict=True, raises=(ValueError, AssertionError),
    reason="KNOWN-BUG:import-parser-string-dtype - parser.py checks `dtype == object`, so with "
           "pandas StringDtype text columns '%' values are rejected with 'Could not convert column "
           "... to numeric' instead of being divided by 100, and the row-numbered "
           "'Non-numeric value ... at row N' message is never produced",
)


def _csv(tmp_path, text, name="_QT_TEST_returns.csv"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


def _xlsx(tmp_path, frame, name="_QT_TEST_returns.xlsx", **kwargs):
    path = tmp_path / name
    frame.to_excel(path, index=False, **kwargs)
    return str(path)


def _as_pairs(series):
    return [(d.strftime("%Y-%m-%d"), round(float(v), 12)) for d, v in series.items()]


class TestCsv:
    def test_basic_decimal_csv(self, tmp_path):
        s = parse_returns_file(_csv(tmp_path, "Date,Value\n2024-01-02,0.01\n2024-01-03,-0.005\n2024-01-04,0\n"))
        assert s.name == "returns"
        assert s.dtype == np.float64
        assert isinstance(s.index, pd.DatetimeIndex) and s.index.tz is None
        assert _as_pairs(s) == [("2024-01-02", 0.01), ("2024-01-03", -0.005), ("2024-01-04", 0.0)]

    def test_unsorted_rows_are_sorted(self, tmp_path):
        s = parse_returns_file(_csv(tmp_path, "date,value\n2024-03-01,0.03\n2024-01-01,0.01\n2024-02-01,0.02\n"))
        assert _as_pairs(s) == [("2024-01-01", 0.01), ("2024-02-01", 0.02), ("2024-03-01", 0.03)]
        assert s.index.is_monotonic_increasing

    @string_dtype_bug
    def test_percent_strings(self, tmp_path):
        s = parse_returns_file(_csv(tmp_path, "Date,Value\n2024-01-02,1.5%\n2024-01-03, -2 % \n2024-01-04,0.25\n"))
        assert _as_pairs(s) == [("2024-01-02", 0.015), ("2024-01-03", -0.02), ("2024-01-04", 0.25)]

    def test_column_detection(self, tmp_path):
        # Date column found by name ("time"), even when it is the second column.
        s = parse_returns_file(_csv(tmp_path, "Ret,Timestamp\n0.01,2024-01-02\n0.02,2024-01-03\n"))
        assert _as_pairs(s) == [("2024-01-02", 0.01), ("2024-01-03", 0.02)]
        # No date-like header -> first column is the date column.
        s = parse_returns_file(_csv(tmp_path, "A,B\n2024-01-02,0.01\n2024-01-03,0.02\n", name="_QT_TEST_ab.csv"))
        assert _as_pairs(s) == [("2024-01-02", 0.01), ("2024-01-03", 0.02)]

    def test_times_and_timezones_are_normalized(self, tmp_path):
        s = parse_returns_file(_csv(tmp_path, "Date,Value\n2024-01-02 16:00:00,0.01\n2024-01-03 09:30:00,0.02\n"))
        assert list(s.index.strftime("%Y-%m-%d %H:%M")) == ["2024-01-02 00:00", "2024-01-03 00:00"]
        # tz-aware stamps keep their wall-clock date (tz dropped, not converted to UTC).
        s = parse_returns_file(_csv(tmp_path, "Date,Value\n2024-01-02T23:00:00-05:00,0.01\n"
                                              "2024-01-03T23:00:00-05:00,0.02\n", name="_QT_TEST_tz.csv"))
        assert s.index.tz is None
        assert _as_pairs(s) == [("2024-01-02", 0.01), ("2024-01-03", 0.02)]

    def test_trailing_blank_rows_are_dropped(self, tmp_path):
        s = parse_returns_file(_csv(tmp_path, "Date,Value\n2024-01-02,0.01\n2024-01-03,0.02\n,\n,\n"))
        assert len(s) == 2

    def test_integer_values_become_float(self, tmp_path):
        s = parse_returns_file(_csv(tmp_path, "Date,Value\n2024-01-02,1\n2024-01-03,0\n"))
        assert s.dtype == np.float64 and s.tolist() == [1.0, 0.0]


class TestErrors:
    @pytest.mark.parametrize("text, pattern", [
        ("Date,Value,Extra\n2024-01-02,0.1,1\n2024-01-03,0.2,2\n",
         r"File must have exactly two columns \(Date and Value\)\. Found 3 columns: \['Date', 'Value', 'Extra'\]"),
        ("Value\n0.1\n0.2\n", r"exactly two columns .* Found 1 columns"),
        ("Date,Value\n2024-01-02,0.1\n", r"Need at least two rows of data; found 1 after removing blank rows\."),
        ("Date,Value\n2024-01-02,0.1\n,\n,\n", r"found 1 after removing blank rows"),
        ("Date,Value\n2024-01-02,0.1\nnot-a-date,0.2\n", r"Could not parse dates in column 'Date'"),
        ("Date,Value\n2024-01-02,0.1\n2024-01-03,\n2024-01-04,\n",
         r"Found 2 blank/NaN value\(s\); first at 2024-01-03\. Remove or fill before importing\."),
        ("Date,Value\n2024-01-02,0.1\n2024-01-02,0.2\n2024-01-03,0.3\n",
         r"Duplicate dates found: 2024-01-02$"),
        ("Date,Value\n" + "".join(f"2024-01-0{d} 00:00,0.1\n2024-01-0{d} 12:00,0.2\n" for d in range(1, 8)),
         r"Duplicate dates found: 2024-01-01, 2024-01-02, 2024-01-03, 2024-01-04, 2024-01-05\.\.\.$"),
        ("Date,Value\n", r"Need at least two rows of data; found 0"),
    ])
    def test_csv_validation_messages(self, tmp_path, text, pattern):
        with pytest.raises(ValueError, match=pattern):
            parse_returns_file(_csv(tmp_path, text))

    @string_dtype_bug
    def test_non_numeric_value_reports_row(self, tmp_path):
        with pytest.raises(ValueError, match=r"Non-numeric value found in column 'Value' at row 3: 'abc'"):
            parse_returns_file(_csv(tmp_path, "Date,Value\n2024-01-02,0.1\n2024-01-03,abc\n2024-01-04,xyz\n"))

    def test_non_numeric_value_is_rejected(self, tmp_path):
        """Whatever the pandas version, a non-numeric value is a ValueError naming the column."""
        with pytest.raises(ValueError, match=r"column 'Value'"):
            parse_returns_file(_csv(tmp_path, "Date,Value\n2024-01-02,0.1\n2024-01-03,abc\n"))

    def test_mixed_date_formats_are_rejected(self, tmp_path):
        # The date format is inferred from the first row, so a later row with a time fails.
        with pytest.raises(ValueError, match="Could not parse dates in column 'Date'"):
            parse_returns_file(_csv(tmp_path, "Date,Value\n2024-01-02,0.1\n2024-01-03 12:00,0.2\n"))

    def test_missing_and_unsupported_files(self, tmp_path):
        missing = tmp_path / "_QT_TEST_missing.csv"
        with pytest.raises(ValueError, match="File not found"):
            parse_returns_file(str(missing))
        txt = tmp_path / "_QT_TEST_returns.txt"
        txt.write_text("Date,Value\n2024-01-02,0.1\n2024-01-03,0.2\n", encoding="utf-8")
        with pytest.raises(ValueError, match=r"Unsupported file type '\.txt'\. Use one of: \['\.csv', '\.xls', '\.xlsx'\]"):
            parse_returns_file(str(txt))
        assert SUPPORTED_EXTENSIONS == {".csv", ".xlsx", ".xls"}

    def test_unreadable_spreadsheets(self, tmp_path):
        for name in ("_QT_TEST_bad.xlsx", "_QT_TEST_bad.xls"):
            path = tmp_path / name
            path.write_bytes(b"this is not a spreadsheet")
            with pytest.raises(ValueError, match="^Could not read file: "):
                parse_returns_file(str(path))

    def test_extension_is_case_insensitive(self, tmp_path):
        s = parse_returns_file(_csv(tmp_path, "Date,Value\n2024-01-02,0.01\n2024-01-03,0.02\n",
                                    name="_QT_TEST_UPPER.CSV"))
        assert len(s) == 2


class TestXlsx:
    def test_xlsx_with_datetimes_and_floats(self, tmp_path):
        frame = pd.DataFrame({
            "Date": pd.to_datetime(["2024-03-28", "2024-01-31", "2024-02-29"]),
            "Monthly Return": [0.031, -0.012, 0.0205],
        })
        s = parse_returns_file(_xlsx(tmp_path, frame))
        assert _as_pairs(s) == [("2024-01-31", -0.012), ("2024-02-29", 0.0205), ("2024-03-28", 0.031)]

    @string_dtype_bug
    def test_xlsx_with_text_dates_and_percent_strings(self, tmp_path):
        frame = pd.DataFrame({"Date": ["2024-01-02", "2024-01-03"], "Value": ["1%", "-0.5%"]})
        s = parse_returns_file(_xlsx(tmp_path, frame, name="_QT_TEST_text.xlsx"))
        assert s.name == "returns" and s.index.name is None
        assert _as_pairs(s) == [("2024-01-02", 0.01), ("2024-01-03", -0.005)]

    def test_date_column_is_detected_by_header_substring(self, tmp_path):
        # "when" is not date-like but "Date Value" is, so the VALUE column is taken
        # as the date column and parsing fails.
        frame = pd.DataFrame({"when": ["2024-01-02", "2024-01-03"], "Date Value": ["1%", "-0.5%"]})
        with pytest.raises(ValueError, match="Could not parse dates in column 'Date Value'"):
            parse_returns_file(_xlsx(tmp_path, frame, name="_QT_TEST_hdr.xlsx"))

    def test_xlsx_blank_cells(self, tmp_path):
        frame = pd.DataFrame({"Date": pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]),
                              "Value": [0.01, None, 0.02]})
        with pytest.raises(ValueError, match=r"Found 1 blank/NaN value\(s\); first at 2024-01-03"):
            parse_returns_file(_xlsx(tmp_path, frame))


class TestParseAndSave:
    def test_csv_to_custom_import_roundtrip(self, fresh_home, tmp_path):
        idx = pd.bdate_range("2024-01-01", periods=30)
        values = np.round(np.random.default_rng(3).normal(0.0005, 0.01, len(idx)), 6)
        lines = ["Date,Value"] + [f"{d:%Y-%m-%d},{v:.6f}" for d, v in zip(idx[::-1], values[::-1])]
        path = _csv(tmp_path, "\n".join(lines) + "\n", name="_QT_TEST_upload.csv")

        meta = _parse_and_save(path, CUSTOM_NAME, "daily", "Alternatives")
        assert (meta.name, meta.frequency, meta.asset_class, meta.source_filename, meta.row_count) == (
            CUSTOM_NAME, "daily", "Alternatives", "_QT_TEST_upload.csv", 30)
        assert (meta.start_date, meta.end_date) == ("2024-01-01", "2024-02-09")
        assert cds.list_custom_tickers() == [meta]

        served = cds.get_custom_returns(CUSTOM_NAME)
        np.testing.assert_allclose(served.to_numpy(), values, rtol=0, atol=1e-12)
        assert served.index.equals(idx)
        assert_golden("parse_and_save_roundtrip", {
            "meta": {k: v for k, v in meta.__dict__.items() if k != "imported_at"},
            "served": served,
            "weekly": cds.get_custom_returns(CUSTOM_NAME, "weekly"),
        }, area="import_parser")

    def test_parse_errors_do_not_write(self, fresh_home, tmp_path):
        path = _csv(tmp_path, "Date,Value\n2024-01-02,0.1\n")
        with pytest.raises(ValueError, match="Need at least two rows"):
            _parse_and_save(path, f"{PREFIX}bad", "daily", "Equity")
        assert cds.list_custom_tickers() == []
        assert not (fresh_home / ".quant_terminal" / "custom_data").exists()

    def test_bad_frequency_after_parse(self, fresh_home, tmp_path):
        path = _csv(tmp_path, "Date,Value\n2024-01-02,0.1\n2024-01-03,0.2\n")
        with pytest.raises(ValueError, match="frequency must be one of"):
            _parse_and_save(path, f"{PREFIX}bad", "Daily", "Equity")
        assert cds.list_custom_tickers() == []
