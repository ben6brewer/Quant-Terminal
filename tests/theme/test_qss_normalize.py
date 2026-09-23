"""Unit tests for the T9 QSS normalizer, widget-tree capture and golden writer."""

from __future__ import annotations

import json

import pytest

import golden_utils
import qss_snapshot
from qss_snapshot import (
    INLINE,
    QssParseError,
    assert_stylesheet_golden,
    dumps,
    normalize_selector,
    normalize_value,
    parse_qss,
    widget_stylesheets,
)


class TestParseQss:
    def test_rules_and_declarations_keep_their_order(self):
        qss = """
            QPushButton { color: #FFFFFF; background-color: #000814; }
            QPushButton:hover { border: 1px solid #FF8000; }
        """
        assert parse_qss(qss) == [
            ["QPushButton", [["color", "#ffffff"], ["background-color", "#000814"]]],
            ["QPushButton:hover", [["border", "1px solid #ff8000"]]],
        ]

    def test_formatting_noise_is_removed(self):
        messy = "QLabel#a ,\n   QLabel#b{color :  rgba( 0,212 ,255,0.15 ) ;;\n font-size:13px}"
        tidy = "QLabel#a, QLabel#b { color: rgba(0, 212, 255, 0.15); font-size: 13px; }"
        assert parse_qss(messy) == parse_qss(tidy) == [
            ["QLabel#a, QLabel#b", [["color", "rgba(0, 212, 255, 0.15)"], ["font-size", "13px"]]]
        ]

    def test_comments_are_dropped(self):
        assert parse_qss("/* header */ QWidget { /* c */ color: red; }") == [
            ["QWidget", [["color", "red"]]]
        ]

    def test_duplicate_declarations_and_rules_are_kept(self):
        qss = "QLabel { color: red; color: blue; } QLabel { color: green; }"
        assert parse_qss(qss) == [
            ["QLabel", [["color", "red"], ["color", "blue"]]],
            ["QLabel", [["color", "green"]]],
        ]

    def test_selectorless_declarations_are_inline(self):
        assert parse_qss("font-size: 24px; color: rgb(76, 153, 0);") == [
            [INLINE, [["font-size", "24px"], ["color", "rgb(76, 153, 0)"]]]
        ]

    def test_quoted_values_may_contain_separators(self):
        qss = 'QLineEdit { font-family: "Menlo", "A;B", "C{D}"; padding: 0px; }'
        assert parse_qss(qss) == [
            ["QLineEdit", [["font-family", '"Menlo", "A;B", "C{D}"'], ["padding", "0px"]]]
        ]

    def test_empty_and_blank_stylesheets(self):
        assert parse_qss("") == []
        assert parse_qss("   \n  ") == []
        assert parse_qss(None) == []

    def test_empty_rule_is_kept(self):
        assert parse_qss("QWidget { }") == [["QWidget", []]]

    def test_declaration_without_colon_is_visible(self):
        assert parse_qss("QWidget { bogus; color: red; }") == [
            ["QWidget", [["bogus", None], ["color", "red"]]]
        ]

    @pytest.mark.parametrize(
        "bad", ["QWidget { color: red;", "QWidget { a { b } }", "color: red; }", "{ color: red; }"]
    )
    def test_unbalanced_or_selectorless_blocks_raise(self, bad):
        with pytest.raises(QssParseError):
            parse_qss(bad)

    def test_hex_case_is_normalized_but_not_other_text(self):
        assert normalize_value("1px solid #FFa040") == "1px solid #ffa040"
        assert normalize_value('"Segoe UI", "Arial"') == '"Segoe UI", "Arial"'
        assert normalize_selector("#navButton:HOVER") == "#navButton:HOVER"


class TestDumps:
    def test_sorted_keys_and_one_declaration_per_line(self):
        data = {"b": [["QLabel", [["color", "red"], ["padding", "0px"]]]], "a": [1, 2, 3]}
        assert dumps(data) == (
            "{\n"
            '  "a": [1, 2, 3],\n'
            '  "b": [\n'
            "    [\n"
            '      "QLabel",\n'
            "      [\n"
            '        ["color", "red"],\n'
            '        ["padding", "0px"]\n'
            "      ]\n"
            "    ]\n"
            "  ]\n"
            "}"
        )

    def test_round_trips_through_json(self):
        data = {"themes": {"dark": parse_qss("QLabel { color: #FFFFFF; } x: 1;"), "light": []}}
        assert json.loads(dumps(data)) == json.loads(json.dumps(data))

    def test_non_ascii_is_escaped(self):
        assert dumps({"k": ["\u2715"]}) == '{\n  "k": ["\\u2715"]\n}'


class TestGoldenFile:
    def test_update_then_compare(self, tmp_path, monkeypatch):
        monkeypatch.setattr(qss_snapshot, "GOLDEN_DIR", tmp_path)
        data = {"themes": {"dark": parse_qss("QLabel { color: red; }")}}

        monkeypatch.setattr(golden_utils, "UPDATE", True)
        written_before = len(golden_utils.WRITTEN)
        assert_stylesheet_golden("_QT_TEST_golden", data)
        path = tmp_path / "_QT_TEST_golden.json"
        first = path.read_bytes()
        assert first.endswith(b"}\n") and b"\r\n" not in first
        assert_stylesheet_golden("_QT_TEST_golden", data)  # unchanged: not rewritten
        assert path.read_bytes() == first
        assert len(golden_utils.WRITTEN) == written_before + 1
        del golden_utils.WRITTEN[written_before:]

        monkeypatch.setattr(golden_utils, "UPDATE", False)
        assert_stylesheet_golden("_QT_TEST_golden", data)
        # A CRLF checkout of the same golden still matches.
        path.write_bytes(first.replace(b"\n", b"\r\n"))
        assert_stylesheet_golden("_QT_TEST_golden", data)

        changed = {"themes": {"dark": parse_qss("QLabel { color: blue; }")}}
        with pytest.raises(pytest.fail.Exception, match="stylesheet snapshot mismatch"):
            assert_stylesheet_golden("_QT_TEST_golden", changed)

    def test_missing_golden_fails(self, tmp_path, monkeypatch):
        monkeypatch.setattr(qss_snapshot, "GOLDEN_DIR", tmp_path)
        monkeypatch.setattr(golden_utils, "UPDATE", False)
        with pytest.raises(pytest.fail.Exception, match="golden missing"):
            assert_stylesheet_golden("_QT_TEST_absent", {"themes": {}})

    def test_names_are_restricted(self):
        with pytest.raises(ValueError):
            qss_snapshot.golden_file("../escape")


@pytest.mark.ui
class TestWidgetStylesheets:
    def test_collects_tree_dedupes_repeats_and_prunes(self, qapp, qtbot):
        from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget

        class _QtTestPruned(QFrame):
            pass

        root = QWidget()
        qtbot.addWidget(root)
        root.setObjectName("_qt_test_root")
        root.setStyleSheet("QWidget#_qt_test_root { background: #FFFFFF; }")
        layout = QVBoxLayout(root)
        for _ in range(3):  # identical repeats collapse into one entry
            button = QPushButton("x")
            button.setStyleSheet("color: red;")
            layout.addWidget(button)
        other = QPushButton("y")
        other.setStyleSheet("color: blue;")
        layout.addWidget(other)
        layout.addWidget(QLabel("no stylesheet"))
        pruned = _QtTestPruned()
        pruned.setStyleSheet("QFrame { color: green; }")
        QVBoxLayout(pruned).addWidget(QLabel("inside"))
        layout.addWidget(pruned)

        assert widget_stylesheets(root, prune=(_QtTestPruned,)) == {
            "QWidget#_qt_test_root": [[["QWidget#_qt_test_root", [["background", "#ffffff"]]]]],
            "QPushButton": [
                [[INLINE, [["color", "red"]]]],
                [[INLINE, [["color", "blue"]]]],
            ],
        }
        assert "_QtTestPruned" in widget_stylesheets(root)
