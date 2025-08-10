# detectors/percentage.py

"""
Enhanced percentage sanity detector with better validation logic.
"""

import logging
import re
import json
from typing import List, Dict, Any, Tuple

from extraction import SlideDoc
from models import Issue
from gemini_wrapper import GeminiClient


logger = logging.getLogger(__name__)


class PercentageSanityDetector:
    """Detects percentage-related inconsistencies with enhanced validation."""
    
    def __init__(self, config: Dict[str, Any], gemini_client: GeminiClient):
        self.config = config
        self.gemini_client = gemini_client
        self.total_tolerance_pp = config.get('total_tolerance_pp', 2)
        
        self.percentage_pattern = re.compile(r'(\d+(?:\.\d+)?)\s*%')
    
    async def detect(self, slides: List[SlideDoc]) -> List[Issue]:
        """Detect percentage-related issues by checking each slide's full content."""
        logger.debug("Starting enhanced percentage sanity detection")
        issues = []
        
        for slide in slides:
            # Get all text from the slide, including title, content, tables, and notes
            full_slide_text = slide.get_all_text()
            
            if not full_slide_text:
                continue

            # Find all percentages in the text
            percentages = []
            for match in self.percentage_pattern.finditer(full_slide_text):
                try:
                    value = float(match.group(1))
                    percentages.append(value)
                except ValueError:
                    continue
            
            if not percentages:
                continue

            # --- Individual Percentage Checks ---
            for value in percentages:
                if value > 100:
                    issues.append(Issue(
                        slides=[slide.slide_num],
                        issue_type="potential_percentage_error",
                        description="Percentage exceeds 100%",
                        details=f"Found a value of {value}% on slide {slide.slide_num}, which may be invalid if it represents part of a whole.",
                        confidence=0.7
                    ))

            # --- Group Summation Checks (if more than one percentage) ---
            if len(percentages) > 1:
                # A simple rule: if percentages on a slide seem to add up close to 100, flag if they don't.
                # This is a heuristic and might have false positives, but is good for finding errors in charts.
                total = sum(percentages)
                # Check if the total is in a range that suggests it *should* be 100 (e.g., 80-120)
                # but is not within the acceptable tolerance of 100.
                if (80 < total < 120) and abs(total - 100) > self.total_tolerance_pp:
                    issues.append(Issue(
                        slides=[slide.slide_num],
                        issue_type="percentage_sum_error",
                        description="Related percentages may not sum to 100%",
                        details=f"On slide {slide.slide_num}, a group of percentages sum to {total:.1f}%. This might be an error if they represent parts of a whole.",
                        confidence=0.75
                    ))

        logger.debug(f"Found {len(issues)} potential percentage issues")
        return issues