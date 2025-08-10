# detectors/numerical.py

import logging
import re
import json
from typing import List, Dict, Any

from extraction import SlideDoc
from models import Issue
from gemini_wrapper import GeminiClient

logger = logging.getLogger(__name__)

class NumericalConflictDetector:
    def __init__(self, config: Dict[str, Any], gemini_client: GeminiClient):
        self.config = config.get('numerical', {})
        self.gemini_client = gemini_client
        self.number_pattern = re.compile(r'([$€£]?\s*\d[\d,]*\.?\d*\s*(?:[KMBT]|times|x|mins|hours)?)\b', re.IGNORECASE)

    async def detect(self, slides: List[SlideDoc]) -> List[Issue]:
        logger.debug("Batch processing slides for numerical metrics...")

        all_numbers = []
        for slide in slides:
            text = slide.get_all_text()
            found_on_slide = set(self.number_pattern.findall(text))
            for num_text in found_on_slide:
                all_numbers.append({"slide_num": slide.slide_num, "number_text": num_text})

        if not all_numbers:
            logger.debug("No numerical data found to analyze.")
            return []

        logger.info(f"Found {len(all_numbers)} numerical data points. Analyzing for conflicts in a single batch...")

        prompt = f"""
        Analyze the following list of numerical data points from a presentation.
        Your task is to identify groups of numbers that refer to the SAME underlying metric but have DIFFERENT values.

        Data Points: {json.dumps(all_numbers, indent=2)}

        Return a JSON array of conflict objects. Each object must have "metric_name" (a snake_case string) and "conflicting_values" (an array of objects with "value" and "slide_num").
        If there are no conflicts, return an empty array [].
        """
        
        response_text = await self.gemini_client.generate_text(prompt)

        # --- GRACEFUL HANDLING OF EMPTY RESPONSE ---
        if not response_text:
            logger.warning("Numerical detector received an empty response from the API. Cannot analyze.")
            return []

        try:
            conflicts = json.loads(response_text)
        except json.JSONDecodeError:
            logger.error("Failed to parse numerical conflict analysis from API. The response was not valid JSON.")
            return []

        issues = []
        for conflict in conflicts:
            values = conflict.get("conflicting_values", [])
            if len(values) < 2: continue

            slides_involved = sorted(list(set(item['slide_num'] for item in values)))
            details_parts = [f"'{item['value']}' on slide {item['slide_num']}" for item in values]
            
            issue = Issue(
                slides=slides_involved,
                issue_type="numerical_conflict",
                description=f"Conflicting values for metric: {conflict.get('metric_name', 'Unnamed Metric')}",
                details=" vs ".join(details_parts),
                confidence=0.95
            )
            issues.append(issue)

        if issues:
            logger.debug(f"Detected {len(issues)} numerical conflicts from batch analysis.")
        return issues