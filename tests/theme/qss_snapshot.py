"""QSS normalization, widget-tree stylesheet capture and golden files for T9.

A stylesheet string is normalized to an ordered list of rules::

    [[selector, [[property, value], ...]], ...]

Normalization only removes formatting noise that cannot change what Qt
renders:

* ``/* comments */`` are dropped;
* whitespace inside selectors and values is collapsed to single spaces,
  selector lists are re-joined with ``", "``;
* spaces around commas and parentheses in values are canonicalized
  (``rgba( 0,0,0 )`` -> ``rgba(0, 0, 0)``);
* hex colors are lower-cased (``#FF8000`` -> ``#ff8000``);
* empty declarations (``;;``) are skipped.

Rule order and declaration order are kept (they decide the cascade), and so
are duplicate declarations.  Declarations that are not inside a ``{}`` block
(``setStyleSheet("color: red;")``) are reported under the pseudo-selector
:data:`INLINE`.

Goldens live in ``tests/theme/goldens/<name>.json``.  They are written with
``--update-goldens`` (the root conftest flag; read at call time from
``golden_utils.UPDATE``) and compared structurally otherwise, so a CRLF
checkout does not matter.  The writer is deterministic (sorted keys, one
declaration per line, LF endings) so regenerating is byte-stable.
"""

from __future__ import annotations

import difflib
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pytest

import golden_utils

GOLDEN_DIR: Path = Path(__file__).resolve().parent / "goldens"
INLINE = "<inline>"
THEMES: Tuple[str, ...] = ("bloomberg", "dark", "light")

_NAME_RE = re.compile(r"^[A-Za-z0-9_.\-]+$")
_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_HEX_RE = re.compile(r"#[0-9A-Fa-f]{3,8}\b")


class QssParseError(ValueError):
    """Raised for stylesheets whose braces do not balance."""


# ─────────────────────────────────────────────────────────────────────────────
# Normalization
# ─────────────────────────────────────────────────────────────────────────────


def _collapse(text: str) -> str:
    return " ".join(text.split())


def normalize_selector(selector: str) -> str:
    parts = [_collapse(p) for p in selector.split(",")]
    return ", ".join(p for p in parts if p)


def normalize_value(value: str) -> str:
    v = _collapse(value)
    v = re.sub(r"\s*,\s*", ", ", v)
    v = re.sub(r"\(\s+", "(", v)
    v = re.sub(r"\s+\)", ")", v)
    return _HEX_RE.sub(lambda m: m.group(0).lower(), v)


def _split_outside_quotes(text: str, sep: str) -> List[str]:
    parts, buf, quote = [], [], None
    for ch in text:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            buf.append(ch)
        elif ch == sep:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf))
    return parts


def parse_declarations(body: str) -> List[List[Optional[str]]]:
    """``"a: 1; b : 2 ;"`` -> ``[["a", "1"], ["b", "2"]]`` (order kept)."""
    decls: List[List[Optional[str]]] = []
    for piece in _split_outside_quotes(body, ";"):
        if not piece.strip():
            continue
        if ":" in piece:
            prop, value = piece.split(":", 1)
            decls.append([_collapse(prop), normalize_value(value)])
        else:  # not valid QSS, but keep it visible instead of dropping it
            decls.append([_collapse(piece), None])
    return decls


def parse_qss(text: str) -> List[list]:
    """Normalize a stylesheet string into ``[[selector, [[prop, value], ...]], ...]``."""
    text = _COMMENT_RE.sub(" ", text or "")
    rules: List[list] = []
    buf: List[str] = []
    i, n = 0, len(text)
    quote = None
    while i < n:
        ch = text[i]
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            buf.append(ch)
        elif ch == "{":
            head = "".join(buf)
            buf = []
            if ";" in head:  # bare declarations directly before a rule
                inline, head = head.rsplit(";", 1)
                decls = parse_declarations(inline)
                if decls:
                    rules.append([INLINE, decls])
            selector = normalize_selector(head)
            if not selector:
                raise QssParseError(f"rule without selector near offset {i}: {text[max(0, i - 40):i + 40]!r}")
            j = i + 1
            inner_quote = None
            while j < n:
                c = text[j]
                if inner_quote:
                    if c == inner_quote:
                        inner_quote = None
                elif c in "\"'":
                    inner_quote = c
                elif c == "}":
                    break
                elif c == "{":
                    raise QssParseError(f"nested '{{' in rule {selector!r}")
                j += 1
            if j >= n:
                raise QssParseError(f"unterminated rule {selector!r}")
            rules.append([selector, parse_declarations(text[i + 1:j])])
            i = j
        elif ch == "}":
            raise QssParseError(f"unbalanced '}}' near offset {i}: {text[max(0, i - 40):i + 40]!r}")
        else:
            buf.append(ch)
        i += 1
    tail = "".join(buf)
    if tail.strip():
        decls = parse_declarations(tail)
        if decls:
            rules.append([INLINE, decls])
    return rules


# ─────────────────────────────────────────────────────────────────────────────
# Widget trees
# ─────────────────────────────────────────────────────────────────────────────


def describe(widget) -> str:
    """``ClassName#objectName`` (or just ``ClassName``)."""
    name = widget.objectName()
    cls = type(widget).__name__
    return f"{cls}#{name}" if name else cls


def widget_stylesheets(root, prune: Iterable[type] = ()) -> Dict[str, List[list]]:
    """Every non-empty ``styleSheet()`` in ``root``'s widget tree.

    Returns ``{descriptor: [normalized_rules, ...]}`` where descriptor is
    :func:`describe` of the widget.  Distinct rule lists for the same
    descriptor are kept in depth-first (child-insertion) order; identical
    repeats are collapsed, so the snapshot does not depend on how many
    identical widgets exist (e.g. one entry for all module tiles).
    Descendants that are instances of ``prune`` are skipped with their
    subtree (they have their own snapshot).
    """
    from PySide6.QtWidgets import QWidget

    prune = tuple(prune)
    out: Dict[str, List[list]] = {}

    def visit(widget, is_root: bool) -> None:
        if not is_root and prune and isinstance(widget, prune):
            return
        rules = parse_qss(widget.styleSheet())
        if rules:
            variants = out.setdefault(describe(widget), [])
            if rules not in variants:
                variants.append(rules)
        for child in widget.children():
            if isinstance(child, QWidget):
                visit(child, False)

    visit(root, True)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Golden files
# ─────────────────────────────────────────────────────────────────────────────


def _is_leaf_list(obj: Any) -> bool:
    return isinstance(obj, list) and all(
        v is None or isinstance(v, (str, int, float, bool)) for v in obj
    )


def dumps(obj: Any, indent: int = 0) -> str:
    """Deterministic JSON: sorted keys, 2-space indent, scalar-only lists on one line."""
    pad = "  " * indent
    if isinstance(obj, dict):
        if not obj:
            return "{}"
        items = [
            f"{pad}  {json.dumps(str(k), ensure_ascii=True)}: {dumps(obj[k], indent + 1)}"
            for k in sorted(obj, key=str)
        ]
        return "{\n" + ",\n".join(items) + "\n" + pad + "}"
    if isinstance(obj, (list, tuple)):
        obj = list(obj)
        if _is_leaf_list(obj):
            return json.dumps(obj, ensure_ascii=True)
        items = [f"{pad}  {dumps(v, indent + 1)}" for v in obj]
        return "[\n" + ",\n".join(items) + "\n" + pad + "]"
    return json.dumps(obj, ensure_ascii=True, allow_nan=False)


def golden_file(name: str) -> Path:
    if not _NAME_RE.match(name):
        raise ValueError(f"golden name must match [A-Za-z0-9_.-]+, got {name!r}")
    return GOLDEN_DIR / f"{name}.json"


def assert_stylesheet_golden(name: str, data: Any) -> None:
    """Compare ``data`` with ``tests/theme/goldens/<name>.json`` (or rewrite it)."""
    path = golden_file(name)
    text = dumps(data) + "\n"
    actual = json.loads(text)

    if golden_utils.UPDATE:
        old = path.read_text(encoding="utf-8").replace("\r\n", "\n") if path.exists() else None
        if old != text:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
            golden_utils.WRITTEN.append(path)
        return

    if not path.exists():
        pytest.fail(
            f"stylesheet golden missing: {path}\nrun pytest with --update-goldens to create it",
            pytrace=False,
        )
    golden_text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    expected = json.loads(golden_text)
    if actual != expected:
        problems = golden_utils.compare_canonical(actual, expected)
        udiff = "".join(
            list(
                difflib.unified_diff(
                    golden_text.splitlines(True),
                    text.splitlines(True),
                    fromfile=f"tests/theme/goldens/{name}.json",
                    tofile="actual",
                    n=2,
                )
            )[:150]
        )
        pytest.fail(
            f"stylesheet snapshot mismatch for {name} ({len(problems)}+ differences):\n  "
            + "\n  ".join(problems[:40])
            + f"\n--- unified diff (truncated) ---\n{udiff}"
            + "\n(re-run with --update-goldens ONLY in a Behavior-Change: yes commit)",
            pytrace=False,
        )
