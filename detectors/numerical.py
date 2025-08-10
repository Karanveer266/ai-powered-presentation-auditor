"""
LLM-powered numerical conflict detector with optimized batch processing.
"""

import logging
import re
import json
from collections import defaultdict
from typing import List, Dict, Tuple, Any, Optional

from extraction import SlideDoc
from models import Issue
from gemini_wrapper import GeminiClient


logger = logging.getLogger(__name__)


class NumericalConflictDetector:
    """Detects conflicting numerical data using AI-powered semantic analysis with batch optimization."""
    
    def __init__(self, config: Dict[str, Any], gemini_client: GeminiClient):
        self.config = config
        self.gemini_client = gemini_client
        self.tolerance_pct = config.get('tolerance_pct', 1)
        
        # Enhanced regex for comprehensive number detection
        self.number_pattern = re.compile(
            r'(?:(?:USD?|EUR?|GBP|\$|€|£|Rs\.?)\s*)?'  # Optional currency prefix
            r'(-?\d{1,3}(?:,\d{3})*(?:\.\d+)?)'       # Number with commas and decimals
            r'\s*([KMBTkmbt])?'                        # Optional suffix (K, M, B, T)
            r'(?:\s*(?:USD?|EUR?|GBP|\$|€|£|Rs\.?|hours?|mins?|minutes?|%|x|times?))?',  # Unit suffix
            re.IGNORECASE
        )
    
    async def detect(self, slides: List[SlideDoc]) -> List[Issue]:
        """Detect numerical conflicts using optimized batch LLM analysis."""
        logger.debug("Starting optimized numerical conflict detection")
        
        # Extract all metrics using batch processing per slide
        metric_registry = await self._extract_metrics_batch_optimized(slides)
        
        # Find genuine conflicts between semantically equivalent metrics
        issues = self._find_genuine_conflicts(metric_registry)
        
        logger.debug(f"Found {len(issues)} genuine numerical conflicts")
        return issues
    
    async def _extract_metrics_batch_optimized(self, slides: List[SlideDoc]) -> Dict[str, List[Tuple[float, int, str, str]]]:
        """Extract metrics using optimized batch LLM calls per slide."""
        registry = defaultdict(list)
        
        for slide in slides:
            text = slide.get_all_text()
            
            # Find all potential numbers on this slide
            slide_numbers = []
            for match in self.number_pattern.finditer(text):
                sentence = self._extract_sentence_context(text, match.start(), match.end())
                slide_numbers.append({
                    'number': match.group(),
                    'sentence': sentence,
                    'value_part': match.group(1),
                    'suffix_part': match.group(2)
                })
            
            if not slide_numbers:
                continue
            
            # Batch analyze all numbers on this slide with single LLM call
            slide_metrics = await self._batch_analyze_slide_metrics(slide.slide_num, text, slide_numbers)
            
            # Add valid metrics to registry
            for metric_info in slide_metrics:
                if self._is_valid_business_metric(metric_info):
                    value = self._normalize_value(metric_info['value_part'], metric_info.get('suffix_part'))
                    semantic_key = metric_info['metric_name'].lower().replace(' ', '_')
                    registry[semantic_key].append((
                        value, 
                        slide.slide_num, 
                        metric_info['sentence'], 
                        metric_info['unit']
                    ))
        
        return registry
    
    async def _batch_analyze_slide_metrics(self, slide_num: int, slide_text: str, numbers: List[Dict]) -> List[Dict[str, Any]]:
        """Analyze all numbers on a slide with a single batch LLM call."""
        if not numbers:
            return []
        
        try:
            # Prepare batch prompt with all numbers
            numbers_info = []
            for i, num_info in enumerate(numbers):
                numbers_info.append({
                    'id': i,
                    'number': num_info['number'],
                    'sentence': num_info['sentence']
                })
            
            prompt = f"""
            Analyze the following slide content and identify all business metrics. For each numbered item below, determine what business concept the number represents.

            Slide Content: "{slide_text}"

            Numbers to analyze: {json.dumps(numbers_info, indent=2)}

            For each number, return a JSON object with:
            - "id": The ID from the input (0, 1, 2, etc.)
            - "metric_name": What specific business concept this number represents (e.g., "annual_revenue", "time_saved_per_slide", "market_share_percentage")
            - "unit": The unit of measurement (e.g., "USD_millions", "minutes", "percentage", "multiplier", "hours")
            - "is_business_metric": true if this is a measurable business/performance metric that could conflict with similar metrics, false for identifiers, years, versions, technical specs
            - "context_type": "financial", "time_performance", "business_performance", "technical_specification", or "identifier"
            - "sentence": The sentence context for this number
            - "value_part": The numeric part (e.g., "2" from "$2M")
            - "suffix_part": The suffix part if any (e.g., "M" from "$2M")

            Guidelines:
            - Only mark as business_metric=true if it's a quantifiable business performance indicator
            - Graduation years, version numbers, team sizes, technical specs should be is_business_metric=false
            - Different types of time savings (e.g., "time per slide" vs "time per month") are different metrics
            - Revenue, costs, savings, market metrics are business metrics if they measure performance

            Respond with a JSON array of objects, one for each input number:
            [
                {{
                    "id": 0,
                    "metric_name": "annual_savings",
                    "unit": "USD_millions",
                    "is_business_metric": true,
                    "context_type": "financial",
                    "sentence": "...",
                    "value_part": "2",
                    "suffix_part": "M"
                }},
                ...
            ]
            """
            
            response = await self.gemini_client.generate_text(prompt)
            
            # Parse batch response
            try:
                results = json.loads(response.strip())
                if not isinstance(results, list):
                    logger.debug(f"Expected array response, got: {type(results)}")
                    return []
                
                # Merge with original number data
                metrics = []
                for result in results:
                    try:
                        num_id = result.get('id')
                        if num_id is not None and 0 <= num_id < len(numbers):
                            original_data = numbers[num_id]
                            merged_metric = {
                                **result,
                                'value_part': original_data['value_part'],
                                'suffix_part': original_data.get('suffix_part'),
                                'sentence': original_data['sentence']
                            }
                            metrics.append(merged_metric)
                    except (KeyError, TypeError, IndexError) as e:
                        logger.debug(f"Error processing metric result: {e}")
                        continue
                
                logger.debug(f"Batch analyzed {len(metrics)} metrics for slide {slide_num}")
                return metrics
            
            except json.JSONDecodeError as e:
                logger.debug(f"Failed to parse batch LLM response: {e}")
                return []
        
        except Exception as e:
            logger.debug(f"Batch metric analysis failed for slide {slide_num}: {e}")
            return []
    
    def _extract_sentence_context(self, text: str, start: int, end: int) -> str:
        """Extract the sentence containing the number for context analysis."""
        # Find sentence boundaries using multiple delimiters
        sentences = re.split(r'[.!?]+\s+', text)
        
        # Find which sentence contains our number
        current_pos = 0
        for sentence in sentences:
            sentence_end = current_pos + len(sentence) + 2  # Account for delimiter
            if current_pos <= start < sentence_end:
                return sentence.strip()
            current_pos = sentence_end
        
        # Fallback to surrounding context window
        context_start = max(0, start - 100)
        context_end = min(len(text), end + 100)
        return text[context_start:context_end].strip()
    
    def _is_valid_business_metric(self, metric_info: Dict[str, Any]) -> bool:
        """Determine if this is a valid business metric worth comparing for conflicts."""
        is_business = metric_info.get('is_business_metric', False)
        context_type = metric_info.get('context_type', '')
        
        # Only consider genuine business performance metrics
        valid_contexts = {'financial', 'time_performance', 'business_performance'}
        
        return is_business and context_type in valid_contexts
    
    def _normalize_value(self, number_str: str, suffix: Optional[str]) -> float:
        """Normalize numerical value handling suffixes and formatting."""
        try:
            # Remove commas and convert to float
            value = float(number_str.replace(',', ''))
            
            # Apply suffix multipliers
            if suffix:
                multipliers = {
                    'k': 1000, 'K': 1000,
                    'm': 1000000, 'M': 1000000,
                    'b': 1000000000, 'B': 1000000000,
                    't': 1000000000000, 'T': 1000000000000
                }
                value *= multipliers.get(suffix, 1)
            
            return value
        except (ValueError, TypeError):
            logger.debug(f"Failed to normalize value: {number_str}")
            return 0.0
    
    def _find_genuine_conflicts(self, registry: Dict[str, List[Tuple[float, int, str, str]]]) -> List[Issue]:
        """Find genuine conflicts between semantically equivalent metrics."""
        issues = []
        
        for metric_key, occurrences in registry.items():
            if len(occurrences) < 2:
                continue  # Need at least 2 occurrences for conflict
            
            # Group by unit to ensure we're comparing compatible values
            unit_groups = defaultdict(list)
            for value, slide_num, sentence, unit in occurrences:
                # Normalize unit names for better grouping
                normalized_unit = self._normalize_unit(unit)
                unit_groups[normalized_unit].append((value, slide_num, sentence))
            
            # Check for conflicts within each unit group
            for unit, unit_occurrences in unit_groups.items():
                if len(unit_occurrences) < 2:
                    continue
                
                # Group by tolerance to identify genuine conflicts
                value_groups = self._group_by_tolerance(unit_occurrences)
                
                if len(value_groups) > 1:  # Found conflicting values
                    issue = self._create_conflict_issue(metric_key, unit, value_groups)
                    if issue:
                        issues.append(issue)
        
        return issues
    
    def _normalize_unit(self, unit: str) -> str:
        """Normalize unit names for better comparison."""
        unit_lower = unit.lower()
        
        # Normalize common variations
        normalizations = {
            'usd_millions': 'usd_m',
            'usd_million': 'usd_m',
            'dollars_millions': 'usd_m',
            'minutes': 'min',
            'minute': 'min',
            'hours': 'hr',
            'hour': 'hr'
        }
        
        return normalizations.get(unit_lower, unit_lower)
    
    def _group_by_tolerance(self, occurrences: List[Tuple[float, int, str]]) -> List[List[Tuple[float, int, str]]]:
        """Group occurrences by value within acceptable tolerance."""
        groups = []
        
        for value, slide_num, sentence in occurrences:
            found_group = False
            for group in groups:
                group_value = group[0][0]  # Representative value
                if self._values_within_tolerance(value, group_value):
                    group.append((value, slide_num, sentence))
                    found_group = True
                    break
            
            if not found_group:
                groups.append([(value, slide_num, sentence)])
        
        return groups
    
    def _values_within_tolerance(self, val1: float, val2: float) -> bool:
        """Check if two values are within acceptable tolerance."""
        if val1 == 0 and val2 == 0:
            return True
        if val1 == 0 or val2 == 0:
            return False
        
        # Calculate percentage difference
        diff_pct = abs(val1 - val2) / max(abs(val1), abs(val2)) * 100
        return diff_pct <= self.tolerance_pct
    
    def _create_conflict_issue(self, metric_key: str, unit: str, value_groups: List[List[Tuple[float, int, str]]]) -> Optional[Issue]:
        """Create an Issue object for a genuine numerical conflict."""
        try:
            all_slides = []
            value_summaries = []
            
            for group in value_groups:
                group_slides = [slide_num for _, slide_num, _ in group]
                all_slides.extend(group_slides)
                
                # Use representative value from group
                rep_value = group[0][0]
                formatted_value = self._format_value(rep_value, unit)
                slides_str = ', '.join(map(str, group_slides))
                value_summaries.append(f"{formatted_value} (slide {slides_str})")
            
            # Create human-readable description
            metric_display = metric_key.replace('_', ' ').title()
            description = f"Conflicting {metric_display} values detected"
            details = f"Found different values: {' vs '.join(value_summaries)}"
            
            return Issue(
                slides=list(set(all_slides)),
                issue_type="numerical_conflict",
                description=description,
                details=details,
                confidence=0.9  # High confidence for LLM-verified semantic conflicts
            )
        
        except Exception as e:
            logger.error(f"Failed to create conflict issue for {metric_key}: {e}")
            return None
    
    def _format_value(self, value: float, unit: str) -> str:
        """Format a numerical value with appropriate unit for display."""
        unit_lower = unit.lower()
        
        if 'usd' in unit_lower or '$' in unit:
            return self._format_currency(value)
        elif unit_lower in ['hours', 'hr', 'hour']:
            return f"{value:,.0f} hours" if value != 1 else "1 hour"
        elif unit_lower in ['minutes', 'min', 'minute']:
            return f"{value:,.0f} minutes" if value != 1 else "1 minute"
        elif unit_lower == 'percentage':
            return f"{value}%"
        elif unit_lower == 'multiplier':
            return f"{value}x"
        else:
            return f"{value:,.0f}"
    
    def _format_currency(self, value: float) -> str:
        """Format currency values with appropriate scale."""
        if value >= 1e12:
            return f"${value/1e12:.1f}T"
        elif value >= 1e9:
            return f"${value/1e9:.1f}B"
        elif value >= 1e6:
            return f"${value/1e6:.1f}M"
        elif value >= 1e3:
            return f"${value/1e3:.1f}K"
        else:
            return f"${value:,.0f}"
