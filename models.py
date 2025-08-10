"""
Data models for the inconsistency detector.
"""

from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class Issue:
    """Represents an inconsistency found in the presentation."""
    slides: List[int]           # Slide numbers where the issue occurs
    issue_type: str            # Type of inconsistency
    description: str           # Brief description of the issue
    details: str              # Detailed explanation
    confidence: float          # Confidence score (0.0 to 1.0)
    
    def __hash__(self):
        """Make Issue hashable for deduplication."""
        return hash((
            tuple(sorted(self.slides)),
            self.issue_type,
            self.description,
            self.details
        ))
    
    def __eq__(self, other):
        """Check equality for deduplication."""
        if not isinstance(other, Issue):
            return False
        return (
            sorted(self.slides) == sorted(other.slides) and
            self.issue_type == other.issue_type and
            self.description == other.description and
            self.details == other.details
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert Issue to dictionary for fallback display."""
        return {
            "slides": self.slides,
            "issue_type": self.issue_type,
            "description": self.description,
            "details": self.details,
            "confidence": self.confidence
        }
