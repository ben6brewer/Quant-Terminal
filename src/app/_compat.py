"""Compatibility shims applied at app startup.

Must be imported before any module that touches ``pandas_datareader`` so the
shims are in place when pandas_datareader is first loaded.

Two shims are installed:

1. **distutils shim (Python 3.12+).**  Python 3.12 removed the stdlib
   ``distutils`` package. ``pandas_datareader 0.10.0`` still does
   ``from distutils.version import LooseVersion``. We alias
   ``setuptools._distutils`` (still vendored in modern setuptools) into
   ``sys.modules['distutils']`` so the import resolves.

2. **deprecate_kwarg shim (pandas 3.x).**  Pandas 3.x added a required
   first ``klass`` argument to ``pandas.util._decorators.deprecate_kwarg``.
   ``pandas_datareader`` uses the old 2-arg form. We wrap the new
   function so that a leading ``str`` arg is treated as the old-style
   ``old_arg_name`` and ``FutureWarning`` is supplied as ``klass``.

Either shim is a no-op if the underlying package is already
self-consistent, so this file is safe to import unconditionally.
"""

from __future__ import annotations

import sys


def _install_distutils_shim() -> None:
    if "distutils" in sys.modules:
        return
    try:
        import setuptools._distutils as _distutils  # type: ignore[import-not-found]
    except ImportError:
        return
    sys.modules["distutils"] = _distutils
    # Eagerly install the submodules pandas_datareader uses.
    try:
        from setuptools._distutils import version as _version  # type: ignore[import-not-found]
        sys.modules["distutils.version"] = _version
    except ImportError:
        pass


def _install_pandas_deprecate_kwarg_shim() -> None:
    try:
        import pandas.util._decorators as _decorators  # type: ignore[import-not-found]
    except ImportError:
        return

    original = _decorators.deprecate_kwarg
    if getattr(original, "_quant_terminal_shimmed", False):
        return

    def deprecate_kwarg_compat(*args, **kwargs):
        # Old signature: (old_arg_name, new_arg_name, mapping=None, stacklevel=2)
        # New signature: (klass, old_arg_name, new_arg_name, mapping=None, stacklevel=2)
        # If the first positional argument is a string, the caller is using
        # the old form — supply FutureWarning as the missing klass.
        if args and isinstance(args[0], str):
            return original(FutureWarning, *args, **kwargs)
        return original(*args, **kwargs)

    deprecate_kwarg_compat._quant_terminal_shimmed = True  # type: ignore[attr-defined]
    _decorators.deprecate_kwarg = deprecate_kwarg_compat


def install() -> None:
    """Install all compatibility shims. Idempotent."""
    _install_distutils_shim()
    _install_pandas_deprecate_kwarg_shim()


# Apply on import so a single ``import app._compat`` at the top of an entry
# point is sufficient.
install()
