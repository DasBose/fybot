"""Shared pytest fixtures for fybot tests."""

import sys
from pathlib import Path

# Ensure project root is importable when pytest collects tests.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
