"""
Enhanced percentage sanity detector with better validation logic.
"""

import logging
import re
from typing import List, Dict, Any, Tuple, Optional

from extraction import SlideDoc
from models import Issue
from gemini_wrapper import GeminiClient


logger = logging.getLogger(__name__)


class PercentageSanityDetector:
    """Detects percentage-related inconsistencies with enhanced validation."""
    
    def __init__(self, config: Dict[str, Any], gemini_client: GeminiClient):
        self.config = config
        self.gemini_client = gemini_client
        self.total_tolerance_pp = config.get('total_tolerance_pp', 1)  # 1 percentage point tolerance
        
        # Enhanced pattern to match percentages in various contexts
        self.percentage_pattern = re.compile(
            r'(\d+(?:\.\d+)?)\s*%',
            re.IGNORECASE
        )
    
    async def detect(self, slides: List[SlideDoc]) -> List[Issue]:
        """Detect percentage-related issues with enhanced logic."""
        logger.debug("Starting enhanced percentage sanity detection")
        
        issues = []
        
        for slide in slides:
            # Check each slide for percentage issues
            slide_issues = await self._check_slide_percentages(slide)
            issues.extend(slide_issues)
        
        logger.debug(f"Found {len(issues)} percentage issues")
        return issues
    
    async def _check_slide_percentages(self, slide: SlideDoc) -> List[Issue]:
        """Check percentage issues within a single slide with enhanced validation."""
        issues = []
        
        # Check slide text
        text_issues = await self._check_text_percentages(slide.slide_num, slide.text)
        issues.extend(text_issues)
        
        # Check speaker notes
        if slide.notes:
            notes_issues = await self._check_text_percentages(slide.slide_num, slide.notes, context="notes")
            issues.extend(notes_issues)
        
        # Check tables with enhanced logic
        for table_idx, table in enumerate(slide.tables):
            table_issues = await self._check_table_percentages(slide.slide_num, table, table_idx)
            issues.extend(table_issues)
        
        return issues
    
    async def _check_text_percentages(self, slide_num: int, text: str, context: str = "text") -> List[Issue]:
        """Check percentages in text content with better validation."""
        issues = []
        
        if not text:
            return issues
        
        # Find all percentages in the text
        percentages = []
        for match in self.percentage_pattern.finditer(text):
            try:
                value = float(match.group(1))
                percentages.append((value, match.start(), match.end(), match.group()))
            except ValueError:
                continue
        
        if not percentages:
            return issues
        
        # Check for invalid individual percentages
        for value, start, end, match_text in percentages:
            if value < 0:
                issues.append(Issue(
                    slides=[slide_num],
                    issue_type="invalid_percentage",
                    description="Negative percentage detected",
                    details=f"Found {value}% in slide {context}",
                    confidence=1.0
                ))
            elif value > 100:
                # Check if this might be basis points or other valid > 100% context
                if not await self._is_valid_over_100_percent(text, start, end):
                    issues.append(Issue(
                        slides=[slide_num],
                        issue_type="invalid_percentage",
                        description="Percentage exceeds 100%",
                        details=f"Found {value}% in slide {context} - may need validation",
                        confidence=0.8  # Lower confidence as some >100% values are valid
                    ))
        
        # Check for percentage groups that should sum to 100%
        percentage_groups = await self._find_percentage_groups_with_llm(text, percentages)
        for group in percentage_groups:
            group_issues = self._check_percentage_group_sum(slide_num, group, context)
            issues.extend(group_issues)
        
        return issues
    
    async def _is_valid_over_100_percent(self, text: str, start: int, end: int) -> bool:
        """Check if a >100% value is valid in context using LLM."""
        try:
            # Extract context around the percentage
            context_start = max(0, start - 100)
            context_end = min(len(text), end + 100)
            context = text[context_start:context_end]
            
            prompt = f"""
            Analyze this text context and determine if a percentage over 100% is valid:
            
            Context: "{context}"
            
            A percentage over 100% is valid if it represents:
            - Growth rates (e.g., "300% growth")
            - Returns on investment
            - Improvements or increases (e.g., "150% improvement")
            - Comparisons to baseline (e.g., "200% of target")
            - Basis points in financial contexts
            
            A percentage over 100% is invalid if it represents:
            - Parts of a whole (market share, composition, distribution)
            - Probability or likelihood
            - Completion rates
            - Accuracy or success rates
            
            Respond with only: "VALID" or "INVALID"
            """
            
            response = await self.gemini_client.generate_text(prompt)
            return response.strip().upper() == "VALID"
        
        except Exception as e:
            logger.debug(f"Failed to validate >100% percentage: {e}")
            return False  # Conservative approach - flag as potentially invalid
    
    async def _find_percentage_groups_with_llm(self, text: str, percentages: List[Tuple[float, int, int, str]]) -> List[List[float]]:
        """Use LLM to identify which percentages should logically sum to 100%."""
        if len(percentages) < 2:
            return []
        
        try:
            percentage_values = [p[0] for p in percentages]
            
            prompt = f"""
            Analyze this text and the percentages found within it. Determine which percentages should logically sum to 100% as parts of a whole.

            Text: "{text}"
            Percentages found: {percentage_values}

            Group percentages that represent:
            - Market share breakdown
            - Budget allocation
            - Time distribution
            - Resource allocation  
            - Composition percentages
            - Parts of a whole

            Do NOT group percentages that represent:
            - Growth rates
            - Individual success rates
            - Separate metrics or KPIs
            - Unrelated measurements

            Respond with JSON array of arrays, where each inner array contains percentages that should sum to 100%:
            Example: [[25.0, 35.0, 40.0], [60.0, 40.0]]
            If no percentages should be grouped, respond with: []
            """
            
            response = await self.gemini_client.generate_text(prompt)
            
            # Parse response
            import json
            try:
                groups = json.loads(response.strip())
                return groups if isinstance(groups, list) else []
            except json.JSONDecodeError:
                return []
        
        except Exception as e:
            logger.debug(f"Failed to group percentages with LLM: {e}")
            return []
    
    async def _check_table_percentages(self, slide_num: int, table, table_idx: int) -> List[Issue]:
        """Check percentages in table data with enhanced validation."""
        issues = []
        
        try:
            # Convert table to string and extract percentages
            table_str = table.to_string()
            percentages = []
            
            for match in self.percentage_pattern.finditer(table_str):
                try:
                    value = float(match.group(1))
                    percentages.append(value)
                except ValueError:
                    continue
            
            if not percentages:
                return issues
            
            # Check individual percentages
            for value in percentages:
                if value < 0:
                    issues.append(Issue(
                        slides=[slide_num],
                        issue_type="invalid_percentage",
                        description="Negative percentage in table",
                        details=f"Found {value}% in table {table_idx + 1}",
                        confidence=1.0
                    ))
                elif value > 100:
                    # For tables, be more conservative about >100% values
                    issues.append(Issue(
                        slides=[slide_num],
                        issue_type="invalid_percentage",
                        description="Percentage exceeds 100% in table",
                        details=f"Found {value}% in table {table_idx + 1} - verify if this represents growth/improvement vs. composition",
                        confidence=0.7
                    ))
            
            # Check if table percentages should sum to 100%
            if await self._table_should_sum_to_100(table, percentages):
                total = sum(percentages)
                if abs(total - 100) > self.total_tolerance_pp:
                    issues.append(Issue(
                        slides=[slide_num],
                        issue_type="percentage_sum_error",
                        description="Table percentages don't sum to 100%",
                        details=f"Table {table_idx + 1} percentages sum to {total:.1f}% (expected: ~100%)",
                        confidence=0.8
                    ))
        
        except Exception as e:
            logger.debug(f"Error checking table percentages: {e}")
        
        return issues
    
    def _check_percentage_group_sum(self, slide_num: int, group: List[float], context: str) -> List[Issue]:
        """Check if a group of percentages sums correctly to 100%."""
        issues = []
        
        if len(group) < 2:
            return issues
        
        total = sum(group)
        
        if abs(total - 100) > self.total_tolerance_pp:
            issues.append(Issue(
                slides=[slide_num],
                issue_type="percentage_sum_error",
                description="Related percentages don't sum to 100%",
                details=f"Found {len(group)} related percentages in {context} summing to {total:.1f}% (expected: ~100%)",
                confidence=0.7
            ))
        
        return issues
    
    async def _table_should_sum_to_100(self, table, percentages: List[float]) -> bool:
        """Determine if table percentages should sum to 100% using enhanced logic."""
        if len(percentages) < 2:
            return False
        
        try:
            # Look at table structure and headers for clues
            table_str = table.to_string().lower()
            
            # Keywords that suggest percentages should sum to 100%
            breakdown_keywords = [
                'share', 'distribution', 'breakdown', 'composition',
                'allocation', 'split', 'portion', 'segment', 'division',
                'market share', 'budget', 'time spent', 'resource'
            ]
            
            has_breakdown_indicators = any(keyword in table_str for keyword in breakdown_keywords)
            
            # If we have clear indicators, percentages should sum to 100%
            if has_breakdown_indicators:
                return True
            
            # If percentages are reasonably close to 100% total, likely should sum
            total = sum(percentages)
            if 80 <= total <= 120 and len(percentages) >= 2:
                return True
            
            return False
        
        except Exception as e:
            logger.debug(f"Error determining if table should sum to 100%: {e}")
            return False
