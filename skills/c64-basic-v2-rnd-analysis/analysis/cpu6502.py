"""Compatibility import for the repository's shared 6502 support.

Keep the repository layout intact.  Implementation and attribution live in
shared/6502; this adapter is an ordinary file for portable directory copies.
"""
import importlib.util
from pathlib import Path
import sys

_source = Path(__file__).resolve().parents[3] / "shared" / "6502" / "cpu6502.py"
_spec = importlib.util.spec_from_file_location(__name__, _source)
_module = importlib.util.module_from_spec(_spec)
sys.modules[__name__] = _module
_spec.loader.exec_module(_module)
