"""
Unified detector hub that performs comprehensive analysis with minimal API calls.
"""

import asyncio
import logging
import json
from typing import List, Dict, Any, Union

from extraction import SlideDoc
from models import Issue
from gemini_wrapper import GeminiClient


logger = logging.getLogger(__name__)


class UnifiedDetectorHub:
    """Unified detector that performs comprehensive analysis with minimal API calls."""
    
    def __init__(self, config: Dict[str, Any], gemini_client: GeminiClient):
        self.config = config
        self.gemini_client = gemini_client
        self.slide_analyses = {}  # Cache slide analysis results
        
    ## NEW: Centralized, robust JSON parsing function
    def _clean_and_parse_json(self, response_text: str) -> Union[Dict, List]:
        """
        Cleans markdown fences from a string and parses it into JSON (object or array).
        """
        if not response_text or not response_text.strip():
            raise json.JSONDecodeError("Response is empty.", response_text, 0)

        # Remove markdown fences like ```json ... ``` or ``` ... ```
        cleaned_text = response_text.strip()
        if cleaned_text.startswith("```") and cleaned_text.endswith("```"):
            # Find the first newline to remove the language specifier (e.g., "json")
            first_newline = cleaned_text.find('\n')
            if first_newline != -1:
                cleaned_text = cleaned_text[first_newline+1:-3].strip()
            else: # Should not happen, but as a fallback
                cleaned_text = cleaned_text[3:-3].strip()

        # Find the start of the JSON (either { or [)
        first_bracket = cleaned_text.find('{')
        first_square = cleaned_text.find('[')
        
        start_pos = -1
        
        if first_bracket == -1 and first_square == -1:
             raise json.JSONDecodeError("No JSON object or array found.", cleaned_text, 0)
        
        if first_bracket != -1 and (first_bracket < first_square or first_square == -1):
            start_pos = first_bracket
            end_char = '}'
        else:
            start_pos = first_square
            end_char = ']'

        # Find the corresponding closing character
        end_pos = cleaned_text.rfind(end_char)

        if start_pos != -1 and end_pos != -1 and end_pos > start_pos:
            json_str = cleaned_text[start_pos:end_pos+1]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.debug(f"Final JSON parse attempt failed for: {json_str[:200]}...")
                raise e
        else:
            raise json.JSONDecodeError("Could not find a valid JSON structure.", cleaned_text, 0)

    async def detect_all_inconsistencies(self, slides: List[SlideDoc]) -> List[Issue]:
        """Perform comprehensive inconsistency detection with minimal API calls."""
        logger.info("Starting unified inconsistency detection (optimized for free tier)")
        
        # Step 1: Analyze each slide comprehensively (1 API call per slide)
        slide_data = await self._analyze_all_slides(slides)
        
        # Step 2: Cross-slide analysis for conflicts (1-2 API calls total)
        issues = await self._find_cross_slide_conflicts(slide_data)
        
        api_calls_made = len([sd for sd in slide_data.values() if sd.get("business_metrics") or sd.get("business_claims")])
        if any(self._combine_metrics(slide_data)): api_calls_made +=1
        if any(self._combine_claims(slide_data)): api_calls_made +=1
        
        logger.info(f"Analysis complete. Found {len(issues)} issues using ~{api_calls_made} API calls")
        return issues
    
    async def _analyze_all_slides(self, slides: List[SlideDoc]) -> Dict[int, Dict[str, Any]]:
        """Analyze each slide comprehensively with a single API call per slide."""
        slide_data = {}
        
        logger.info(f"Analyzing {len(slides)} slides (1 API call per slide)")
        
        for i, slide in enumerate(slides):
            logger.info(f"Analyzing slide {slide.slide_num} ({i+1}/{len(slides)})")
            
            # Get comprehensive analysis for this slide
            analysis = await self._comprehensive_slide_analysis(slide)
            slide_data[slide.slide_num] = analysis
            
            # Rate limiting delay for free tier
            if i < len(slides) - 1:  # Don't delay after last slide
                await asyncio.sleep(self.config.get('gemini', {}).get('request_delay', 8))
        
        return slide_data
    
    async def _comprehensive_slide_analysis(self, slide: SlideDoc) -> Dict[str, Any]:
        """Perform comprehensive analysis of a single slide with one API call."""
        text = slide.get_all_text()
        
        # Prepare a default empty structure
        empty_analysis = {
            "slide_number": slide.slide_num, "business_metrics": [], "percentages": [],
            "business_claims": [], "dates_and_timelines": [], "financial_data": []
        }
        
        if not text.strip():
            logger.debug(f"Slide {slide.slide_num} is empty, skipping AI analysis.")
            return empty_analysis
        
        prompt = f"""
        Analyze this PowerPoint slide content and extract data for inconsistency detection. 
        Your entire response must be ONLY a single, valid JSON object. Do not include any explanations or markdown formatting.

        Slide Content: "{text}"

        Return ONLY this JSON structure:
        {{
            "slide_number": {slide.slide_num},
            "business_metrics": [
                {{
                    "metric_name": "annual_revenue", "value": 2000000, "unit": "USD",
                    "formatted_text": "$2M", "context": "Our annual revenue reached $2M last year"
                }}
            ],
            "percentages": [
                {{"value": 45, "context": "Market share: 45%", "category": "market_share"}}
            ],
            "business_claims": [
                {{"claim": "We are the market leader", "category": "market_position", "confidence": "high"}}
            ],
            "dates_and_timelines": [
                {{"date": "2024-03-15", "event": "Product launch", "type": "past_event"}}
            ],
            "financial_data": [
                {{"type": "revenue", "amount": 2000000, "period": "annual", "year": 2023}}
            ]
        }}

        Guidelines:
        - Extract ALL numbers, percentages, business claims, and dates.
        - If no data of a certain type exists, use an empty array [].
        - Your response must begin with {{ and end with }}.
        """
        
        try:
            response = await self.gemini_client.generate_text(prompt)
            logger.debug(f"Raw API Response for slide {slide.slide_num}: {response[:300]}...")
            analysis = self._clean_and_parse_json(response)
            logger.debug(f"Slide {slide.slide_num} analysis complete")
            return analysis
        
        except Exception as e:
            logger.error(f"Failed to analyze slide {slide.slide_num}: {e}")
            return empty_analysis
    
    async def _find_cross_slide_conflicts(self, slide_data: Dict[int, Dict[str, Any]]) -> List[Issue]:
        """Find conflicts across slides using batch analysis."""
        issues = []
        
        all_metrics = self._combine_metrics(slide_data)
        all_claims = self._combine_claims(slide_data)
        all_percentages = self._combine_percentages(slide_data)
        
        if not any([all_metrics, all_claims, all_percentages]):
            logger.warning("No data extracted from slides to perform cross-slide analysis.")
            return issues
        
        if len(all_metrics) >= 2:
            metric_issues = await self._detect_metric_conflicts(all_metrics)
            issues.extend(metric_issues)
            await asyncio.sleep(self.config.get('gemini', {}).get('request_delay', 8))
        
        if len(all_claims) >= 2:
            claim_issues = await self._detect_claim_conflicts(all_claims)
            issues.extend(claim_issues)
            
        percentage_issues = self._check_percentage_conflicts(all_percentages)
        issues.extend(percentage_issues)
        
        return issues
    
    def _combine_metrics(self, slide_data: Dict[int, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Combine all business metrics from all slides."""
        all_metrics = []
        for slide_num, data in slide_data.items():
            if isinstance(data, dict):
                for metric in data.get('business_metrics', []):
                    metric['slide_number'] = slide_num
                    all_metrics.append(metric)
        return all_metrics
    
    def _combine_claims(self, slide_data: Dict[int, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Combine all business claims from all slides."""
        all_claims = []
        for slide_num, data in slide_data.items():
            if isinstance(data, dict):
                for claim in data.get('business_claims', []):
                    claim['slide_number'] = slide_num
                    all_claims.append(claim)
        return all_claims
    
    def _combine_percentages(self, slide_data: Dict[int, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Combine all percentages from all slides."""
        all_percentages = []
        for slide_num, data in slide_data.items():
             if isinstance(data, dict):
                for pct in data.get('percentages', []):
                    pct['slide_number'] = slide_num
                    all_percentages.append(pct)
        return all_percentages
    
    async def _detect_metric_conflicts(self, metrics: List[Dict[str, Any]]) -> List[Issue]:
        """Detect conflicts in business metrics with single API call."""
        prompt = f"""
        Analyze these business metrics for conflicts. Your response must be ONLY a valid JSON array.

        Metrics: {json.dumps(metrics, indent=2)}

        Find conflicts where the same metric has different values or related metrics are illogical.

        Return ONLY a JSON array using this format. Do not add explanations.
        [
            {{
                "conflict_type": "numerical_inconsistency",
                "description": "Conflicting revenue figures",
                "slides": [1, 3],
                "details": "Slide 1 shows $2M revenue while Slide 3 shows $3M revenue.",
                "confidence": 0.9
            }}
        ]
        
        If no conflicts are found, return an empty array [].
        """
        
        try:
            response = await self.gemini_client.generate_text(prompt)
            conflicts = self._clean_and_parse_json(response)
            
            issues = []
            if isinstance(conflicts, list):
                for conflict in conflicts:
                    issues.append(Issue(
                        slides=conflict.get('slides', []),
                        issue_type=conflict.get('conflict_type', 'numerical_conflict'),
                        description=conflict.get('description', 'Metric conflict detected'),
                        details=conflict.get('details', ''),
                        confidence=float(conflict.get('confidence', 0.8))
                    ))
            logger.debug(f"Found {len(issues)} metric conflicts.")
            return issues
        
        except Exception as e:
            logger.error(f"Failed to detect metric conflicts: {e}")
            return []
    
    async def _detect_claim_conflicts(self, claims: List[Dict[str, Any]]) -> List[Issue]:
        """Detect conflicts in business claims with single API call."""
        prompt = f"""
        Analyze these business claims for logical contradictions. Your response must be ONLY a valid JSON array.

        Claims: {json.dumps(claims, indent=2)}

        Find contradictions where claims are mutually exclusive.

        Return ONLY a JSON array using this format. Do not add explanations.
        [
            {{
                "conflict_type": "textual_contradiction",
                "description": "Contradictory market position claims",
                "slides": [2, 5],
                "details": "Slide 2 claims 'market leader' while Slide 5 says 'startup'.",
                "confidence": 0.85
            }}
        ]

        If no contradictions are found, return an empty array [].
        """
        
        try:
            response = await self.gemini_client.generate_text(prompt)
            conflicts = self._clean_and_parse_json(response)
            
            issues = []
            if isinstance(conflicts, list):
                for conflict in conflicts:
                    issues.append(Issue(
                        slides=conflict.get('slides', []),
                        issue_type=conflict.get('conflict_type', 'textual_contradiction'),
                        description=conflict.get('description', 'Claim contradiction detected'),
                        details=conflict.get('details', ''),
                        confidence=float(conflict.get('confidence', 0.8))
                    ))
            
            logger.debug(f"Found {len(issues)} claim conflicts.")
            return issues
        
        except Exception as e:
            logger.error(f"Failed to detect claim conflicts: {e}")
            return []
    
    def _check_percentage_conflicts(self, percentages: List[Dict[str, Any]]) -> List[Issue]:
        """Check percentage conflicts using rule-based logic (no API calls)."""
        issues = []
        by_category = {}
        
        for pct in percentages:
            category = pct.get('category', 'unknown_category')
            slide = pct.get('slide_number')
            value = pct.get('value')

            if not all([category, slide, isinstance(value, (int, float))]):
                continue

            if category not in by_category:
                by_category[category] = {}
            if slide not in by_category[category]:
                by_category[category][slide] = []
            
            by_category[category][slide].append(pct)
        
        for category, slides in by_category.items():
            for slide, pcts in slides.items():
                if len(pcts) > 1:
                    total = sum(p.get('value', 0) for p in pcts)
                    # Check if the parts of a whole do not sum to 100
                    if 98 < total < 102: # Allow for small rounding errors
                        continue
                    
                    # This logic assumes any group of same-category percentages on a slide should sum to 100.
                    # This might be too aggressive, but we'll flag it.
                    issue = Issue(
                        slides=[slide],
                        issue_type="percentage_validation",
                        description=f"Percentages may not sum correctly for '{category}'",
                        details=f"On slide {slide}, percentages for '{category}' sum to {total:.1f}%. This might be an error if they represent parts of a whole.",
                        confidence=0.75
                    )
                    issues.append(issue)
        
        return issues