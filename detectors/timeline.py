"""
Enhanced timeline mismatch detector with better date parsing and conflict detection.
"""

import logging
import re
from datetime import datetime, date
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

import dateparser

from extraction import SlideDoc
from models import Issue
from gemini_wrapper import GeminiClient


logger = logging.getLogger(__name__)


@dataclass
class TimelineEvent:
    """Represents a timeline event with enhanced metadata."""
    slide_num: int
    date: date
    description: str
    context: str
    event_type: str  # 'past', 'future', 'ongoing', 'completion', 'deadline'
    confidence: float


class TimelineMismatchDetector:
    """Detects timeline and chronological inconsistencies with enhanced logic."""
    
    def __init__(self, config: Dict[str, Any], gemini_client: GeminiClient):
        self.config = config
        self.gemini_client = gemini_client
        self.overlap_tolerance_days = config.get('overlap_tolerance_days', 0)
        
        # Enhanced patterns for different types of temporal expressions
        self.date_patterns = [
            r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b',  # MM/DD/YYYY or DD/MM/YYYY
            r'\b(\d{4}[/-]\d{1,2}[/-]\d{1,2})\b',    # YYYY/MM/DD
            r'\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4})\b',
            r'\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4})\b',
            r'\b(Q[1-4]\s+\d{4})\b',  # Q1 2024
            r'\b(\d{4})\b(?=\s+(?:quarter|year|fiscal|budget|by\s+end))',  # Year with context
        ]
        
        # Enhanced event type indicators
        self.past_indicators = [
            'completed', 'achieved', 'launched', 'established', 'founded',
            'acquired', 'merged', 'closed', 'sold', 'delivered', 'finished',
            'ended', 'concluded', 'was', 'were', 'had', 'did', 'have completed',
            'successfully', 'implemented', 'deployed', 'released'
        ]
        
        self.future_indicators = [
            'will', 'plan', 'planning', 'expect', 'expecting', 'forecast',
            'projected', 'scheduled', 'upcoming', 'future', 'next',
            'target', 'goal', 'aim', 'intend', 'going to', 'shall',
            'anticipated', 'proposed', 'intended'
        ]
        
        self.completion_indicators = [
            'by', 'before', 'until', 'deadline', 'due', 'complete by',
            'finish by', 'deliver by', 'launch by', 'ready by',
            'completion date', 'target date', 'expected completion'
        ]
        
        self.deadline_indicators = [
            'deadline', 'due date', 'must be completed', 'final date',
            'cutoff', 'expiry', 'expires', 'ends by'
        ]
    
    async def detect(self, slides: List[SlideDoc]) -> List[Issue]:
        """Detect timeline inconsistencies with enhanced analysis."""
        logger.debug("Starting enhanced timeline mismatch detection")
        
        # Extract timeline events from all slides
        events = self._extract_timeline_events(slides)
        
        if len(events) < 2:
            logger.debug("Not enough timeline events for mismatch detection")
            return []
        
        # Sort events by date for analysis
        events.sort(key=lambda x: x.date)
        
        # Find various types of timeline mismatches
        issues = await self._find_timeline_mismatches(events)
        
        logger.debug(f"Found {len(issues)} timeline mismatches")
        return issues
    
    def _extract_timeline_events(self, slides: List[SlideDoc]) -> List[TimelineEvent]:
        """Extract timeline events from all slides with enhanced parsing."""
        events = []
        
        for slide in slides:
            text = slide.get_all_text()
            slide_events = self._extract_events_from_text(slide.slide_num, text)
            events.extend(slide_events)
        
        logger.debug(f"Extracted {len(events)} timeline events")
        return events
    
    def _extract_events_from_text(self, slide_num: int, text: str) -> List[TimelineEvent]:
        """Extract timeline events from slide text with enhanced parsing."""
        events = []
        
        # Split text into sentences for better context
        sentences = re.split(r'[.!?]+\s+', text)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence or len(sentence.split()) < 3:
                continue
            
            # Find dates in this sentence using multiple approaches
            sentence_events = self._find_dates_in_sentence(slide_num, sentence)
            events.extend(sentence_events)
        
        return events
    
    def _find_dates_in_sentence(self, slide_num: int, sentence: str) -> List[TimelineEvent]:
        """Find and parse dates within a sentence with enhanced detection."""
        events = []
        
        # Try regex patterns first
        for pattern in self.date_patterns:
            matches = re.finditer(pattern, sentence, re.IGNORECASE)
            
            for match in matches:
                date_str = match.group(1)
                parsed_date = self._parse_date(date_str)
                
                if parsed_date:
                    event_type = self._determine_event_type(sentence)
                    description = self._extract_event_description(sentence, match)
                    confidence = self._calculate_event_confidence(sentence, date_str)
                    
                    event = TimelineEvent(
                        slide_num=slide_num,
                        date=parsed_date,
                        description=description,
                        context=sentence,
                        event_type=event_type,
                        confidence=confidence
                    )
                    events.append(event)
        
        # Also try dateparser for more flexible parsing
        try:
            parsed_dates = dateparser.search.search_dates(sentence, languages=['en'])
            if parsed_dates:
                for date_str, parsed_datetime in parsed_dates:
                    if parsed_datetime and parsed_datetime.date() not in [e.date for e in events]:
                        # Skip obviously wrong dates (too far in past/future)
                        if not self._is_reasonable_date(parsed_datetime.date()):
                            continue
                            
                        event_type = self._determine_event_type(sentence)
                        description = self._extract_event_description_from_context(sentence, date_str)
                        confidence = self._calculate_event_confidence(sentence, date_str)
                        
                        event = TimelineEvent(
                            slide_num=slide_num,
                            date=parsed_datetime.date(),
                            description=description,
                            context=sentence,
                            event_type=event_type,
                            confidence=confidence
                        )
                        events.append(event)
        except Exception as e:
            logger.debug(f"Dateparser error for sentence: {e}")
        
        return events
    
    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse a date string into a date object with enhanced handling."""
        try:
            # Handle quarter notation
            if re.match(r'Q[1-4]\s+\d{4}', date_str, re.IGNORECASE):
                quarter_match = re.match(r'Q(\d)\s+(\d{4})', date_str, re.IGNORECASE)
                if quarter_match:
                    quarter = int(quarter_match.group(1))
                    year = int(quarter_match.group(2))
                    # Use middle month of quarter for better representation
                    month = (quarter - 1) * 3 + 2
                    return date(year, month, 15)
            
            # Try dateparser with specific settings
            parsed = dateparser.parse(
                date_str,
                languages=['en'],
                settings={'STRICT_PARSING': False, 'PREFER_DAY_OF_MONTH': 'first'}
            )
            if parsed:
                result_date = parsed.date()
                if self._is_reasonable_date(result_date):
                    return result_date
            
            return None
        
        except Exception as e:
            logger.debug(f"Failed to parse date '{date_str}': {e}")
            return None
    
    def _is_reasonable_date(self, check_date: date) -> bool:
        """Check if date is within reasonable business context (1980-2050)."""
        current_year = datetime.now().year
        return 1980 <= check_date.year <= current_year + 30
    
    def _determine_event_type(self, sentence: str) -> str:
        """Determine the type of event based on sentence content with enhanced logic."""
        sentence_lower = sentence.lower()
        
        # Check for deadline indicators first (most specific)
        if any(indicator in sentence_lower for indicator in self.deadline_indicators):
            return 'deadline'
        
        # Check for completion indicators
        if any(indicator in sentence_lower for indicator in self.completion_indicators):
            return 'completion'
        
        # Check for past indicators
        if any(indicator in sentence_lower for indicator in self.past_indicators):
            return 'past'
        
        # Check for future indicators
        if any(indicator in sentence_lower for indicator in self.future_indicators):
            return 'future'
        
        # Default classification based on tense and context
        if re.search(r'\b(will|shall|going to|plan to)\b', sentence_lower):
            return 'future'
        elif re.search(r'\b(was|were|had|did|completed|finished)\b', sentence_lower):
            return 'past'
        else:
            return 'ongoing'
    
    def _extract_event_description(self, sentence: str, date_match) -> str:
        """Extract a meaningful description of the event from the sentence."""
        # Take content around the date as description
        start = max(0, date_match.start() - 80)
        end = min(len(sentence), date_match.end() + 80)
        
        context = sentence[start:end]
        
        # Clean up the description
        description = re.sub(r'\s+', ' ', context).strip()
        
        # Remove the date itself from description to avoid redundancy
        description = re.sub(re.escape(date_match.group()), '[DATE]', description)
        
        # Limit length for readability
        if len(description) > 120:
            description = description[:117] + "..."
        
        return description
    
    def _extract_event_description_from_context(self, sentence: str, date_str: str) -> str:
        """Extract event description when we have the date string."""
        # Remove the date from the sentence to get the event description
        description = sentence.replace(date_str, '[DATE]').strip()
        
        # Clean up
        description = re.sub(r'\s+', ' ', description)
        description = re.sub(r'^[,\-\s]+|[,\-\s]+$', '', description)
        
        if len(description) > 120:
            description = description[:117] + "..."
        
        return description
    
    def _calculate_event_confidence(self, sentence: str, date_str: str) -> float:
        """Calculate confidence score for the extracted event with enhanced scoring."""
        confidence = 0.4  # Base confidence
        
        sentence_lower = sentence.lower()
        
        # Higher confidence for clear temporal indicators
        if any(indicator in sentence_lower for indicator in 
               self.past_indicators + self.future_indicators + self.completion_indicators):
            confidence += 0.3
        
        # Higher confidence for specific date formats
        if re.match(r'\d{1,2}[/-]\d{1,2}[/-]\d{4}', date_str):
            confidence += 0.2
        elif re.match(r'Q[1-4]\s+\d{4}', date_str):
            confidence += 0.15
        elif re.match(r'\d{4}', date_str):
            confidence += 0.1
        
        # Higher confidence for business context
        business_context = ['project', 'launch', 'deadline', 'completion', 'target', 'goal']
        if any(context in sentence_lower for context in business_context):
            confidence += 0.2
        
        # Lower confidence for very short sentences
        if len(sentence.split()) < 5:
            confidence -= 0.2
        
        # Lower confidence for vague dates
        if date_str.isdigit() and len(date_str) == 4:  # Just year
            confidence -= 0.1
        
        return max(0.1, min(1.0, confidence))
    
    async def _find_timeline_mismatches(self, events: List[TimelineEvent]) -> List[Issue]:
        """Find various types of timeline mismatches with enhanced logic."""
        issues = []
        
        # Check for chronological inconsistencies
        issues.extend(await self._check_chronological_order(events))
        
        # Check for completion/deadline conflicts
        issues.extend(await self._check_completion_conflicts(events))
        
        # Check for impossible timelines
        issues.extend(await self._check_impossible_timelines(events))
        
        # Check for deadline violations
        issues.extend(await self._check_deadline_violations(events))
        
        return issues
    
    async def _check_chronological_order(self, events: List[TimelineEvent]) -> List[Issue]:
        """Check for events that violate logical chronological order."""
        issues = []
        
        for i in range(len(events)):
            for j in range(i + 1, len(events)):
                event1, event2 = events[i], events[j]
                
                # Skip if same slide (focus on cross-slide inconsistencies)
                if event1.slide_num == event2.slide_num:
                    continue
                
                # Check if past event comes after future event (chronological violation)
                if (event1.event_type == 'future' and event2.event_type == 'past' and
                    event1.date < event2.date and
                    await self._events_seem_related(event1, event2)):
                    
                    issue = Issue(
                        slides=[event1.slide_num, event2.slide_num],
                        issue_type="chronological_mismatch",
                        description="Future event scheduled before related past event",
                        details=(f"Slide {event1.slide_num}: Future event on {event1.date} "
                                f"vs Slide {event2.slide_num}: Past event on {event2.date}"),
                        confidence=min(event1.confidence, event2.confidence) * 0.9
                    )
                    issues.append(issue)
        
        return issues
    
    async def _check_completion_conflicts(self, events: List[TimelineEvent]) -> List[Issue]:
        """Check for conflicts between completion dates and other events."""
        issues = []
        
        completion_events = [e for e in events if e.event_type in ['completion', 'deadline']]
        other_events = [e for e in events if e.event_type not in ['completion', 'deadline']]
        
        for completion_event in completion_events:
            for other_event in other_events:
                # Skip same slide
                if completion_event.slide_num == other_event.slide_num:
                    continue
                
                # Check if an event happens after its completion/deadline
                if (other_event.event_type in ['future', 'ongoing'] and
                    other_event.date > completion_event.date and
                    await self._events_seem_related(completion_event, other_event)):
                    
                    issue = Issue(
                        slides=[completion_event.slide_num, other_event.slide_num],
                        issue_type="completion_conflict",
                        description="Event scheduled after completion/deadline date",
                        details=(f"Completion/deadline by {completion_event.date} (slide {completion_event.slide_num}) "
                                f"but related event on {other_event.date} (slide {other_event.slide_num})"),
                        confidence=min(completion_event.confidence, other_event.confidence) * 0.8
                    )
                    issues.append(issue)
        
        return issues
    
    async def _check_impossible_timelines(self, events: List[TimelineEvent]) -> List[Issue]:
        """Check for impossible or highly unlikely timelines within slides."""
        issues = []
        
        # Group events by slide
        slides_events = {}
        for event in events:
            if event.slide_num not in slides_events:
                slides_events[event.slide_num] = []
            slides_events[event.slide_num].append(event)
        
        # Check within each slide for impossible sequences
        for slide_num, slide_events in slides_events.items():
            if len(slide_events) < 2:
                continue
            
            slide_events.sort(key=lambda x: x.date)
            
            for i in range(len(slide_events) - 1):
                event1, event2 = slide_events[i], slide_events[i + 1]
                
                # Check if past event comes after future event on same slide
                if (event1.event_type == 'future' and event2.event_type == 'past' and
                    event1.date < event2.date):
                    
                    issue = Issue(
                        slides=[slide_num],
                        issue_type="impossible_timeline",
                        description="Inconsistent timeline within slide",
                        details=(f"Slide {slide_num}: Future event ({event1.date}) occurs before "
                                f"past event ({event2.date})"),
                        confidence=min(event1.confidence, event2.confidence) * 0.9
                    )
                    issues.append(issue)
        
        return issues
    
    async def _check_deadline_violations(self, events: List[TimelineEvent]) -> List[Issue]:
        """Check for deadline violations and conflicts."""
        issues = []
        
        deadline_events = [e for e in events if e.event_type == 'deadline']
        future_events = [e for e in events if e.event_type == 'future']
        
        for deadline in deadline_events:
            for future_event in future_events:
                if (deadline.slide_num != future_event.slide_num and
                    future_event.date > deadline.date and
                    await self._events_seem_related(deadline, future_event)):
                    
                    issue = Issue(
                        slides=[deadline.slide_num, future_event.slide_num],
                        issue_type="deadline_violation",
                        description="Future event scheduled after deadline",
                        details=(f"Deadline: {deadline.date} (slide {deadline.slide_num}) "
                                f"but future event: {future_event.date} (slide {future_event.slide_num})"),
                        confidence=min(deadline.confidence, future_event.confidence) * 0.85
                    )
                    issues.append(issue)
        
        return issues
    
    async def _events_seem_related(self, event1: TimelineEvent, event2: TimelineEvent) -> bool:
        """Use enhanced logic to determine if two events are related."""
        # Simple keyword-based similarity (can be enhanced with LLM)
        desc1_words = set(event1.description.lower().split())
        desc2_words = set(event2.description.lower().split())
        
        # Remove common words
        common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', '[date]'}
        desc1_words -= common_words
        desc2_words -= common_words
        
        if len(desc1_words) == 0 or len(desc2_words) == 0:
            return False
        
        # Calculate word overlap
        overlap = len(desc1_words & desc2_words)
        similarity = overlap / min(len(desc1_words), len(desc2_words))
        
        # Also check for related business terms
        project_terms = {'project', 'launch', 'product', 'feature', 'system', 'platform', 'service'}
        event1_has_project = bool(desc1_words & project_terms)
        event2_has_project = bool(desc2_words & project_terms)
        
        if event1_has_project and event2_has_project:
            similarity += 0.2
        
        return similarity > 0.25  # 25% similarity threshold
