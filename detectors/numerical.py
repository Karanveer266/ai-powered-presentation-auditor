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
        logger.debug("Batch processing slides for numerical metrics with few-shot prompting...")

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

        # --- ENHANCED FEW-SHOT PROMPT ---
        prompt = f"""
        Analyze the following list of numerical data points from a presentation.
        Your task is to group numbers that refer to the SAME underlying metric and identify if they have DIFFERENT values.

        Data Points:
        {json.dumps(all_numbers, indent=2)}

        Instructions:
        1.  Group data points by their semantic meaning. For example, "$2M in savings" and "a $3M productivity gain" should be grouped under a metric like "total_productivity_savings_usd". Similarly, "15 mins" and "20 minutes" referring to slide creation time should be grouped.
        2.  For each group, check if there are conflicting (different) values.
        3.  Return a JSON array of all the conflicts you find. Each object in the array represents one conflict.

        Here is an example of a perfect response based on hypothetical data:
        [
          {{
            "metric_name": "total_productivity_savings_usd",
            "conflicting_values": [
              {{ "value": "$2M", "slide_num": 1 }},
              {{ "value": "$3M", "slide_num": 2 }}
            ]
          }},
          {{
            "metric_name": "time_saved_per_slide_minutes",
            "conflicting_values": [
              {{ "value": "15 mins", "slide_num": 1 }},
              {{ "value": "20 mins", "slide_num": 2 }}
            ]
          }}
        ]

        Now, analyze the provided data points and return ONLY a valid JSON array of conflict objects.
        If there are no conflicts, return an empty array [].
        """

        response_text = await self.gemini_client.generate_text(prompt)

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