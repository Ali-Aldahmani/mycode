"""Access to the shared Python engine (/pyengine), used for validation."""
import sys

from .config import REPO_DIR

if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

from pyengine import checker, runner, valuespec  # noqa: E402

__all__ = ["checker", "runner", "valuespec"]
