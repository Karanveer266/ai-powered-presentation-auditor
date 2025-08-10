"""
Enhanced detectors package for PowerPoint inconsistency detection.
"""

from .numerical import NumericalConflictDetector
from .percentage import PercentageSanityDetector 
from .textual import TextContradictionDetector
from .timeline import TimelineMismatchDetector

__all__ = [
    'NumericalConflictDetector',
    'PercentageSanityDetector', 
    'TextContradictionDetector',
    'TimelineMismatchDetector'
]
