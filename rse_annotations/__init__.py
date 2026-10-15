"""Concern decorators for generated research code, plus a static analysis and a review runner.

    from rse_annotations import calculations, data_input

    @calculations
    def normalize(x, lo, hi):
        return (x - lo) / (hi - lo)
"""
from .decorators import *  # noqa: F401,F403
from .decorators import CONCERNS, Concern, __all__
