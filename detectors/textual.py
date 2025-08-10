# detectors/textual.py

import logging
import re
import json
from typing import List, Dict, Any

from extraction import SlideDoc
from models import Issue
from gemini_wrapper import GeminiClient

logger = logging.getLogger(__name__)

class TextContradictionDetector:
    def __init__(self, config: Dict[str, Any], gemini_client: GeminiClient):
        self.config = config.get('textual', {})
        self.gemini_client = gemini_client

    async def detect(self, slides: List[SlideDoc]) -> List[Issue]:
        logger.debug("Batch processing slides for textual claims...")

        all_claims = []
        for slide in slides:
            sentences = re.split(r'[.!?\n]+', slide.get_all_text())
            for sentence in sentences:
                cleaned = sentence.strip()
                if 5 < len(cleaned.split()) < 50: # Filter for reasonable claim length
                    all_claims.append({"slide_num": slide.slide_num, "claim_text": cleaned})

        if len(all_claims) < 2:
            logger.debug("Not enough textual claims found to analyze.")
            return []

        logger.info(f"Found {len(all_claims)} potential claims. Analyzing for contradictions in a single batch...")

        prompt = f"""
        Analyze the following list of claims from a business presentation to find logical contradictions.
        A contradiction occurs when two statements cannot both be true.

        List of Claims: {json.dumps(all_claims, indent=2)}

        Return a JSON array of contradiction objects. Each object must have "description", "conflicting_claims" (an array of two objects with "claim" and "slide_num"), and "reasoning".
        If there are no contradictions, return an empty array [].
        """
        response_text = await self.gemini_client.generate_text(prompt)

        # --- GRACEFUL HANDLING OF EMPTY RESPONSE ---
        if not response_text:
            logger.warning("Textual detector received an empty response from the API. Cannot analyze.")
            return []

        try:
            contradictions = json.loads(response_text)
        except json.JSONDecodeError:
            logger.error("Failed to parse textual contradiction analysis from API. The response was not valid JSON.")
            return []

        issues = []
        for contra in contradictions:
            claims_info = contra.get("conflicting_claims", [])
            if len(claims_info) != 2: continue

            claim1, claim2 = claims_info[0], claims_info[1]
            slides_involved = sorted([claim1['slide_num'], claim2['slide_num']])
            details = (f"On slide {claim1['slide_num']}, it says \"{claim1['claim']}\". "
                       f"But on slide {claim2['slide_num']}, it says \"{claim2['claim']}\". "
                       f"Reasoning: {contra.get('reasoning', 'N/A')}")

            issue = Issue(
                slides=slides_involved,
                issue_type="textual_contradiction",
                description=contra.get("description", "Contradictory claims found"),
                details=details,
                confidence=0.90
            )
            issues.append(issue)

        if issues:
            logger.debug(f"Detected {len(issues)} textual contradictions from batch analysis.")
        return issues