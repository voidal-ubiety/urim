"""Urim: a contract language for decision models (pre-alpha).

Public API, the same surface as lib.rs and index.ts.

Implements: C-070, C-071, C-072
"""

from urim.check import SUPPORTED_HOSHEN, CheckResult, check_file, check_text
from urim.limits import MAX_BYTES, MAX_DEPTH

__version__ = "0.0.1"
__all__ = [
    "MAX_BYTES",
    "MAX_DEPTH",
    "SUPPORTED_HOSHEN",
    "CheckResult",
    "__version__",
    "check_file",
    "check_text",
]
