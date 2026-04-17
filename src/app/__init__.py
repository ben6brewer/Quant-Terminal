"""Quant Terminal application package.

Importing this package unconditionally installs runtime compatibility
shims (Py3.12+ distutils, pandas 3.x deprecate_kwarg) so that any entry
point — including PyInstaller bundles, tests, and script invocations of
sub-modules — gets them. The shims are idempotent.
"""

from . import _compat  # noqa: F401  (imported for side effects)
