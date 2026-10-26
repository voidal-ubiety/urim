"""Urim: a contract language for decision models (pre-alpha)."""

from urim.check import SUPPORTED_HOSHEN, CheckResult, check_file, check_text

__version__ = "0.0.1"
__all__ = ["SUPPORTED_HOSHEN", "CheckResult", "__version__", "check_file", "check_text"]
