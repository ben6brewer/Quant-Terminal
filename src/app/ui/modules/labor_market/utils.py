"""Shared utilities for labor market chart modules.

Re-exports add_recession_bands from shared utils for backward compatibility.
"""

from app.utils.recession_bands import add_recession_bands

__all__ = ["add_recession_bands"]
