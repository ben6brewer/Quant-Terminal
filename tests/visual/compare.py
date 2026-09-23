"""Pixel-diff two visual capture directories (made by tests/visual/test_visual_capture.py).

Usage::

    python tests/visual/compare.py BEFORE AFTER [--tolerance N] [--diff-out DIR]
                                                [--json FILE] [--all]

``BEFORE`` / ``AFTER`` are directories, or capture labels resolved under the
visual root (``$QT_VISUAL_ROOT``, default: the refactor scratchpad
``visual`` directory, else ``%TEMP%/quant_terminal_visual``).  A capture
directory holds ``<theme>/<module_id>.png``.

Prints one row per module with the changed-pixel count per theme (a pixel
"changed" when any RGBA channel differs by more than ``--tolerance``, default
0), then the files present on one side only.  ``--diff-out`` writes, for every
changed image, a PNG with the BEFORE image dimmed and changed pixels in red.

Exit status: 0 = identical, 1 = differences (changed pixels, size changes or
missing files), 2 = bad arguments.

Needs only PySide6 (QtGui, for PNG decoding) and numpy; no QApplication.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

# Session scratchpad of the consolidation refactor (outside the repo).
SCRATCHPAD_VISUAL_ROOT = Path(
    r"C:\Users\BENBRE~1\AppData\Local\Temp\claude"
    r"\C--Users-BenBrewer-Desktop-Coding-Projects-Quant-Terminal"
    r"\4ce6be3d-d473-4994-99c8-92ac6780a8f0\scratchpad\visual"
)
DEFAULT_LABEL = "latest"


def visual_root() -> Path:
    """Directory that holds one sub-directory per capture label."""
    env = os.environ.get("QT_VISUAL_ROOT")
    if env:
        return Path(env)
    if SCRATCHPAD_VISUAL_ROOT.parent.is_dir():
        return SCRATCHPAD_VISUAL_ROOT
    return Path(tempfile.gettempdir()) / "quant_terminal_visual"


def capture_dir(label: Optional[str] = None) -> Path:
    """Where a capture is written: ``$QT_VISUAL_OUT``, else ``<root>/<label>``.

    ``label`` defaults to ``$QT_VISUAL_LABEL`` or ``"latest"``.
    """
    env = os.environ.get("QT_VISUAL_OUT")
    if env:
        return Path(env)
    label = label or os.environ.get("QT_VISUAL_LABEL") or DEFAULT_LABEL
    return visual_root() / label


def resolve(arg: str) -> Path:
    """A directory path, or a capture label under :func:`visual_root`."""
    p = Path(arg)
    if p.is_dir():
        return p
    q = visual_root() / arg
    if q.is_dir():
        return q
    raise FileNotFoundError(f"not a directory or a known capture label: {arg!r} (root: {visual_root()})")


# ─────────────────────────────────────────────────────────────────────────────
# Image loading / diffing
# ─────────────────────────────────────────────────────────────────────────────


def load_rgba(path: Path):
    """PNG -> numpy uint8 array (h, w, 4) in RGBA order."""
    import numpy as np
    from PySide6.QtGui import QImage

    img = QImage(str(path))
    if img.isNull():
        raise ValueError(f"cannot read image: {path}")
    img = img.convertToFormat(QImage.Format.Format_RGBA8888)
    w, h, bpl = img.width(), img.height(), img.bytesPerLine()
    buf = np.frombuffer(img.constBits(), dtype=np.uint8, count=h * bpl)
    return buf.reshape(h, bpl)[:, : w * 4].reshape(h, w, 4).copy()


def save_rgba(arr, path: Path) -> None:
    import numpy as np
    from PySide6.QtGui import QImage

    arr = np.ascontiguousarray(arr, dtype=np.uint8)
    h, w = arr.shape[:2]
    img = QImage(arr.data, w, h, w * 4, QImage.Format.Format_RGBA8888).copy()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not img.save(str(path)):
        raise OSError(f"cannot write image: {path}")


@dataclass
class ImageDiff:
    rel: str  # "<theme>/<module>.png"
    module: str
    theme: str
    changed: int  # changed pixels (all pixels of the larger image on a size change)
    total: int
    size_a: tuple
    size_b: tuple

    @property
    def size_changed(self) -> bool:
        return self.size_a != self.size_b


@dataclass
class CompareReport:
    dir_a: str
    dir_b: str
    tolerance: int
    diffs: List[ImageDiff] = field(default_factory=list)
    only_a: List[str] = field(default_factory=list)
    only_b: List[str] = field(default_factory=list)

    @property
    def changed(self) -> List[ImageDiff]:
        return [d for d in self.diffs if d.changed or d.size_changed]

    @property
    def identical(self) -> bool:
        return not self.changed and not self.only_a and not self.only_b

    def per_module(self) -> Dict[str, Dict[str, int]]:
        """{module: {theme: changed pixels}} for every compared image."""
        out: Dict[str, Dict[str, int]] = {}
        for d in self.diffs:
            out.setdefault(d.module, {})[d.theme] = d.changed
        return out

    def to_json(self) -> dict:
        return {
            "dir_a": self.dir_a,
            "dir_b": self.dir_b,
            "tolerance": self.tolerance,
            "identical": self.identical,
            "images_compared": len(self.diffs),
            "images_changed": len(self.changed),
            "pixels_changed": sum(d.changed for d in self.diffs),
            "per_module": self.per_module(),
            "size_changes": {d.rel: [list(d.size_a), list(d.size_b)] for d in self.diffs if d.size_changed},
            "only_a": self.only_a,
            "only_b": self.only_b,
        }


def _pngs(root: Path) -> Dict[str, Path]:
    return {p.relative_to(root).as_posix(): p for p in sorted(root.rglob("*.png"))}


def compare_dirs(dir_a: Path, dir_b: Path, *, tolerance: int = 0,
                 diff_out: Optional[Path] = None) -> CompareReport:
    import numpy as np

    dir_a, dir_b = Path(dir_a), Path(dir_b)
    a_files, b_files = _pngs(dir_a), _pngs(dir_b)
    report = CompareReport(str(dir_a), str(dir_b), tolerance)
    report.only_a = sorted(set(a_files) - set(b_files))
    report.only_b = sorted(set(b_files) - set(a_files))
    for rel in sorted(set(a_files) & set(b_files)):
        a, b = load_rgba(a_files[rel]), load_rgba(b_files[rel])
        parts = rel.split("/")
        module = Path(parts[-1]).stem
        theme = parts[-2] if len(parts) > 1 else ""
        size_a, size_b = (a.shape[1], a.shape[0]), (b.shape[1], b.shape[0])
        if size_a != size_b:
            total = max(a.shape[0] * a.shape[1], b.shape[0] * b.shape[1])
            report.diffs.append(ImageDiff(rel, module, theme, total, total, size_a, size_b))
            continue
        delta = np.abs(a.astype(np.int16) - b.astype(np.int16))
        mask = (delta > tolerance).any(axis=2)
        changed = int(mask.sum())
        report.diffs.append(ImageDiff(rel, module, theme, changed, int(mask.size), size_a, size_b))
        if changed and diff_out is not None:
            vis = (a.astype(np.float32) * 0.35).astype(np.uint8)
            vis[..., 3] = 255
            vis[mask] = (255, 0, 0, 255)
            save_rgba(vis, Path(diff_out) / rel)
    return report


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def format_report(report: CompareReport, *, show_all: bool = False) -> str:
    themes = sorted({d.theme for d in report.diffs})
    per_module = report.per_module()
    size_changed = {(d.module, d.theme) for d in report.diffs if d.size_changed}
    rows = sorted(per_module.items(), key=lambda kv: (-sum(kv[1].values()), kv[0]))
    if not show_all:
        rows = [r for r in rows if sum(r[1].values())]
    name_w = max([len("module")] + [len(m) for m, _ in rows])
    col_w = max([12] + [len(t) for t in themes])
    lines = [f"A: {report.dir_a}", f"B: {report.dir_b}", f"tolerance: {report.tolerance}", ""]
    header = "module".ljust(name_w) + "".join(t.rjust(col_w + 2) for t in themes) + "total".rjust(col_w + 2)
    lines += [header, "-" * len(header)]
    for module, by_theme in rows:
        cells = []
        for t in themes:
            if t not in by_theme:
                cells.append("-".rjust(col_w + 2))
            else:
                mark = "*" if (module, t) in size_changed else ""
                cells.append(f"{by_theme[t]}{mark}".rjust(col_w + 2))
        lines.append(module.ljust(name_w) + "".join(cells) + str(sum(by_theme.values())).rjust(col_w + 2))
    if not rows:
        lines.append("(no changed pixels)")
    if size_changed:
        lines.append("* = image size changed (all pixels counted)")
    for title, items in (("only in A", report.only_a), ("only in B", report.only_b)):
        if items:
            lines.append(f"\n{title} ({len(items)}):")
            lines += [f"  {rel}" for rel in items]
    lines.append("")
    lines.append(
        f"{len(report.diffs)} images compared, {len(report.changed)} changed, "
        f"{sum(d.changed for d in report.diffs)} pixels changed, "
        f"{len(report.only_a)} only in A, {len(report.only_b)} only in B -> "
        + ("IDENTICAL" if report.identical else "DIFFERENT")
    )
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("before", help="capture directory or label")
    parser.add_argument("after", help="capture directory or label")
    parser.add_argument("--tolerance", type=int, default=0,
                        help="per-channel difference ignored (0-255, default 0)")
    parser.add_argument("--diff-out", type=Path, default=None, help="write diff images here")
    parser.add_argument("--json", type=Path, default=None, help="write the report as JSON here")
    parser.add_argument("--all", action="store_true", help="list unchanged modules too")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    try:
        dir_a, dir_b = resolve(args.before), resolve(args.after)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    report = compare_dirs(dir_a, dir_b, tolerance=args.tolerance, diff_out=args.diff_out)
    print(format_report(report, show_all=args.all))
    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report.to_json(), indent=2), encoding="utf-8")
    return 0 if report.identical else 1


if __name__ == "__main__":
    raise SystemExit(main())
