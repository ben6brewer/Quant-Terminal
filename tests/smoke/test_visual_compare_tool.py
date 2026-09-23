"""Unit tests for the visual pixel-diff CLI (tests/visual/compare.py).

tests/visual itself is only collected with ``--visual``; the diff tool is
plain code, so it is tested here in the default suite.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from visual import compare


def _img(w=20, h=10, value=(10, 20, 30, 255)):
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[...] = value
    return arr


@pytest.fixture
def two_captures(tmp_path):
    """A and B capture dirs: same / 5 px changed / resized / only-A / only-B / subtle change."""
    a, b = tmp_path / "A", tmp_path / "B"
    base = _img()
    changed = base.copy()
    changed[2, 3:8] = (255, 0, 0, 255)  # 5 pixels
    subtle = base.copy()
    subtle[0, 0] = (13, 20, 30, 255)  # +3 on one channel of one pixel
    compare.save_rgba(base, a / "dark" / "_qt_test_same.png")
    compare.save_rgba(base, b / "dark" / "_qt_test_same.png")
    compare.save_rgba(base, a / "dark" / "_qt_test_changed.png")
    compare.save_rgba(changed, b / "dark" / "_qt_test_changed.png")
    compare.save_rgba(base, a / "light" / "_qt_test_changed.png")
    compare.save_rgba(base, b / "light" / "_qt_test_changed.png")
    compare.save_rgba(base, a / "light" / "_qt_test_resized.png")
    compare.save_rgba(_img(w=30), b / "light" / "_qt_test_resized.png")
    compare.save_rgba(base, a / "light" / "_qt_test_subtle.png")
    compare.save_rgba(subtle, b / "light" / "_qt_test_subtle.png")
    compare.save_rgba(base, a / "dark" / "_qt_test_gone.png")
    compare.save_rgba(base, b / "dark" / "_qt_test_new.png")
    return a, b


def test_png_round_trip_is_lossless(tmp_path):
    arr = np.arange(20 * 10 * 4, dtype=np.uint32).reshape(10, 20, 4) % 256
    arr[..., 3] = 255
    compare.save_rgba(arr.astype(np.uint8), tmp_path / "x.png")
    assert np.array_equal(compare.load_rgba(tmp_path / "x.png"), arr.astype(np.uint8))


def test_compare_dirs_counts_changed_pixels_per_module_and_theme(two_captures, tmp_path):
    a, b = two_captures
    report = compare.compare_dirs(a, b, diff_out=tmp_path / "diff")
    per_module = report.per_module()
    assert per_module["_qt_test_same"] == {"dark": 0}
    assert per_module["_qt_test_changed"] == {"dark": 5, "light": 0}
    assert per_module["_qt_test_resized"] == {"light": 300}  # size change: all pixels of the larger image
    assert per_module["_qt_test_subtle"] == {"light": 1}
    assert report.only_a == ["dark/_qt_test_gone.png"]
    assert report.only_b == ["dark/_qt_test_new.png"]
    assert not report.identical
    assert sorted(d.rel for d in report.changed) == [
        "dark/_qt_test_changed.png", "light/_qt_test_resized.png", "light/_qt_test_subtle.png"]
    # diff image: changed pixels red, the rest dimmed
    diff = compare.load_rgba(tmp_path / "diff" / "dark" / "_qt_test_changed.png")
    assert (diff[2, 3:8] == (255, 0, 0, 255)).all()
    assert tuple(diff[0, 0]) == (3, 7, 10, 255)
    assert not (tmp_path / "diff" / "dark" / "_qt_test_same.png").exists()


def test_tolerance_ignores_small_channel_differences(two_captures):
    a, b = two_captures
    report = compare.compare_dirs(a, b, tolerance=3)
    assert report.per_module()["_qt_test_subtle"] == {"light": 0}
    assert report.per_module()["_qt_test_changed"]["dark"] == 5


def test_cli_exit_codes_table_and_json(two_captures, tmp_path, capsys):
    a, b = two_captures
    json_path = tmp_path / "report.json"
    assert compare.main([str(a), str(b), "--json", str(json_path)]) == 1
    out = capsys.readouterr().out
    rows = {line.split()[0]: line.split()[1:] for line in out.splitlines()
            if line.startswith("_qt_test_")}
    assert rows["_qt_test_resized"] == ["-", "300*", "300"]
    assert rows["_qt_test_changed"] == ["5", "0", "5"]
    assert "_qt_test_same" not in rows  # unchanged modules hidden without --all
    assert "only in A (1):" in out and "only in B (1):" in out
    assert out.rstrip().endswith("DIFFERENT")
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["identical"] is False
    assert data["pixels_changed"] == 306
    assert data["per_module"]["_qt_test_changed"] == {"dark": 5, "light": 0}

    assert compare.main([str(a), str(a), "--all"]) == 0
    out = capsys.readouterr().out
    assert "_qt_test_same" in out and out.rstrip().endswith("IDENTICAL")

    assert compare.main([str(a), str(tmp_path / "_qt_test_missing_label")]) == 2


def test_capture_dir_resolution(monkeypatch, tmp_path):
    monkeypatch.delenv("QT_VISUAL_OUT", raising=False)
    monkeypatch.setenv("QT_VISUAL_ROOT", str(tmp_path))
    monkeypatch.delenv("QT_VISUAL_LABEL", raising=False)
    assert compare.capture_dir() == tmp_path / compare.DEFAULT_LABEL
    monkeypatch.setenv("QT_VISUAL_LABEL", "_qt_test_label")
    assert compare.capture_dir() == tmp_path / "_qt_test_label"
    (tmp_path / "_qt_test_label").mkdir()
    assert compare.resolve("_qt_test_label") == tmp_path / "_qt_test_label"
    monkeypatch.setenv("QT_VISUAL_OUT", str(tmp_path / "_qt_test_out"))
    assert compare.capture_dir() == tmp_path / "_qt_test_out"
    with pytest.raises(FileNotFoundError):
        compare.resolve("_qt_test_no_such_label")
