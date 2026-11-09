"""Frozen six-axis research scoring; production activation remains separate."""

from .contracts import OverlayContext, ScoreContext
from .engine import compute_score, study_signals
from .profiles import PROFILE_VERSION
from .service import ScoreService

__all__ = [
    "PROFILE_VERSION",
    "OverlayContext",
    "ScoreContext",
    "ScoreService",
    "compute_score",
    "study_signals",
]
