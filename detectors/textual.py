"""
Semantic textual contradiction detector using LLM-powered analysis with embedding optimization.
"""

import logging
import re
import json
import hashlib
import math
from typing import List, Dict, Any, Tuple

from extraction import SlideDoc
from models import Issue
from gemini_wrapper import GeminiClient


logger = logging.getLogger(__name__)


class TextContradictionDetector:
    """Detects textual contradictions using optimized semantic analysis with embedding filtering."""
    
    def __init__(self, config: Dict[str, Any], gemini_client: GeminiClient):
        self.config = config
        self.gemini_client = gemini_client
        self.similarity_threshold = config.get('similarity_threshold', 0.75)  # Threshold for embedding similarity
        self.confidence_threshold = config.get('confidence_threshold', 0.7)
        
        # Cache for contradiction analysis to avoid duplicate API calls
        self.contradiction_cache = {}
    
    async def detect(self, slides: List[SlideDoc]) -> List[Issue]:
        """Detect textual contradictions using optimized two-pass semantic analysis."""
        logger.debug("Starting optimized semantic contradiction detection")
        
        # Extract business claims from all slides
        business_claims = self._extract_business_claims(slides)
        
        if len(business_claims) < 2:
            logger.debug("Not enough business claims for contradiction detection")
            return []
        
        logger.debug(f"Extracted {len(business_claims)} business claims, using two-pass approach")
        
        # Pass 1: Generate embeddings for all claims (cheap)
        claim_texts = [claim[1] for claim in business_claims]
        embeddings = await self.gemini_client.get_embeddings(claim_texts)
        
        # Pass 2: Filter pairs by embedding similarity before expensive LLM calls
        similar_pairs = self._find_similar_pairs(business_claims, embeddings)
        logger.debug(f"Found {len(similar_pairs)} similar pairs out of {len(business_claims) * (len(business_claims) - 1) // 2} possible pairs")
        
        # Pass 3: LLM analysis only for similar pairs (expensive but targeted)
        issues = await self._analyze_similar_pairs(similar_pairs)
        
        logger.debug(f"Found {len(issues)} textual contradictions")
        return issues
    
    def _extract_business_claims(self, slides: List[SlideDoc]) -> List[Tuple[int, str]]:
        """Extract meaningful business claims and assertions from slides."""
        claims = []
        
        for slide in slides:
            text = slide.get_all_text()
            
            # Split into sentences with enhanced parsing
            sentences = self._split_into_sentences(text)
            
            for sentence in sentences:
                cleaned = self._clean_sentence(sentence)
                if self._is_meaningful_business_claim(cleaned):
                    claims.append((slide.slide_num, cleaned))
        
        logger.debug(f"Extracted {len(claims)} business claims")
        return claims
    
    def _find_similar_pairs(self, claims: List[Tuple[int, str]], embeddings: List[List[float]]) -> List[Tuple[int, int, float]]:
        """Find pairs of claims with high embedding similarity to reduce LLM calls."""
        similar_pairs = []
        
        for i in range(len(claims)):
            for j in range(i + 1, len(claims)):
                slide1, claim1 = claims[i]
                slide2, claim2 = claims[j]
                
                # Skip claims from the same slide (focus on cross-slide inconsistencies)
                if slide1 == slide2:
                    continue
                
                # Calculate cosine similarity between embeddings
                similarity = self._cosine_similarity(embeddings[i], embeddings[j])
                
                # Only consider pairs with high semantic similarity
                if similarity >= self.similarity_threshold:
                    similar_pairs.append((i, j, similarity))
        
        return similar_pairs
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two embedding vectors."""
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        
        # Calculate dot product
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        
        # Calculate magnitudes
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))
        
        # Avoid division by zero
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        return dot_product / (magnitude1 * magnitude2)
    
    async def _analyze_similar_pairs(self, similar_pairs: List[Tuple[int, int, float]]) -> List[Issue]:
        """Analyze only semantically similar pairs with LLM for contradictions."""
        issues = []
        
        logger.debug(f"Analyzing {len(similar_pairs)} similar pairs with LLM (cost-optimized)")
        
        for i, j, embedding_similarity in similar_pairs:
            # Note: We need access to the original claims - let's modify this approach
            # We'll need to pass claims to this method
            pass
        
        return issues
    
    async def _find_semantic_contradictions(self, claims: List[Tuple[int, str]]) -> List[Issue]:
        """Find contradictions using optimized LLM analysis with embedding pre-filtering."""
        issues = []
        
        # Generate embeddings for all claims first (Pass 1 - Cheap)
        claim_texts = [claim[1] for claim in claims]
        embeddings = await self.gemini_client.get_embeddings(claim_texts)
        
        # Find similar pairs based on embeddings (Pass 2 - Filtering)
        pairs_to_analyze = []
        total_possible_pairs = 0
        
        for i in range(len(claims)):
            for j in range(i + 1, len(claims)):
                slide1, claim1 = claims[i]
                slide2, claim2 = claims[j]
                total_possible_pairs += 1
                
                # Skip claims from the same slide
                if slide1 == slide2:
                    continue
                
                # Calculate embedding similarity
                similarity = self._cosine_similarity(embeddings[i], embeddings[j])
                
                # Only analyze pairs with high semantic similarity
                if similarity >= self.similarity_threshold:
                    pairs_to_analyze.append((i, j, slide1, slide2, claim1, claim2, similarity))
        
        logger.debug(f"Embedding filtering: {len(pairs_to_analyze)} pairs selected from {total_possible_pairs} total pairs")
        logger.debug(f"API call reduction: {((total_possible_pairs - len(pairs_to_analyze)) / max(total_possible_pairs, 1)) * 100:.1f}%")
        
        # Analyze only the filtered pairs with LLM (Pass 3 - Expensive but targeted)
        for i, j, slide1, slide2, claim1, claim2, embedding_similarity in pairs_to_analyze:
            is_contradiction, confidence, reasoning = await self._analyze_contradiction_with_llm(
                claim1, claim2, slide1, slide2
            )
            
            if is_contradiction and confidence >= self.confidence_threshold:
                # Boost confidence slightly for high embedding similarity
                adjusted_confidence = min(1.0, confidence + (embedding_similarity - self.similarity_threshold) * 0.1)
                
                issue = Issue(
                    slides=[slide1, slide2],
                    issue_type="textual_contradiction",
                    description="Contradictory business claims detected",
                    details=f"Slide {slide1}: \"{claim1[:150]}{'...' if len(claim1) > 150 else ''}\" contradicts Slide {slide2}: \"{claim2[:150]}{'...' if len(claim2) > 150 else ''}\" | Reasoning: {reasoning}",
                    confidence=adjusted_confidence
                )
                issues.append(issue)
        
        return issues
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into meaningful sentences for analysis."""
        # Enhanced sentence splitting with multiple delimiters
        sentences = re.split(r'[.!?]+\s+|[\n\r]+', text)
        
        # Filter and clean sentences
        meaningful_sentences = []
        for sentence in sentences:
            sentence = sentence.strip()
            # Must have at least 4 words and not be purely numeric
            if (sentence and 
                len(sentence.split()) >= 4 and 
                not re.match(r'^[\d\s\.,\$%\-]+$', sentence)):
                meaningful_sentences.append(sentence)
        
        return meaningful_sentences
    
    def _clean_sentence(self, sentence: str) -> str:
        """Clean sentence for analysis while preserving meaning."""
        # Remove bullet points and list markers
        sentence = re.sub(r'^[\u2022\u2023\u25E6\u2043\u2219\-\*\d+\.\s]+', '', sentence)
        
        # Normalize whitespace
        sentence = re.sub(r'\s+', ' ', sentence)
        
        # Remove excessive punctuation but keep sentence structure
        sentence = re.sub(r'[^\w\s\.,!?;:\-\'\"()]', ' ', sentence)
        sentence = re.sub(r'\s+', ' ', sentence)
        
        return sentence.strip()
    
    def _is_meaningful_business_claim(self, sentence: str) -> bool:
        """Determine if sentence contains a meaningful business claim for analysis."""
        # Skip very short sentences
        words = sentence.split()
        if len(words) < 4:
            return False
        
        # Skip purely numeric or technical content
        if re.match(r'^[\d\s\.,\$%\-x]+$', sentence):
            return False
        
        sentence_lower = sentence.lower()
        
        # Look for business claim indicators
        business_indicators = [
            # Market and competition
            'market', 'competition', 'competitive', 'competitor', 'leading', 'dominant',
            # Performance and metrics
            'growth', 'revenue', 'profit', 'cost', 'saving', 'efficiency', 'performance',
            # Customer and business
            'customer', 'client', 'user', 'successful', 'innovative', 'scalable',
            # Comparative claims
            'faster', 'better', 'improved', 'superior', 'advanced', 'optimized',
            'higher', 'lower', 'more', 'less', 'increased', 'decreased',
            # Time and productivity
            'time', 'productivity', 'automated', 'streamlined', 'efficient',
            # Quality and reliability
            'reliable', 'secure', 'quality', 'robust', 'stable', 'proven'
        ]
        
        # Must contain business indicators and have claim structure
        has_business_content = any(indicator in sentence_lower for indicator in business_indicators)
        
        # Look for claim structure (assertions, comparisons, statements of fact)
        claim_patterns = [
            r'\b(is|are|has|have|can|will|does|provides?|offers?|enables?|delivers?)\b',
            r'\b(more|less|better|worse|faster|slower|higher|lower|greater|smaller)\b',
            r'\b(leading|top|best|worst|first|primary|main|key|critical|important)\b'
        ]
        
        has_claim_structure = any(re.search(pattern, sentence_lower) for pattern in claim_patterns)
        
        return has_business_content and has_claim_structure
    
    async def detect(self, slides: List[SlideDoc]) -> List[Issue]:
        """Detect textual contradictions using optimized two-pass semantic analysis."""
        logger.debug("Starting optimized semantic contradiction detection")
        
        # Extract business claims from all slides
        business_claims = self._extract_business_claims(slides)
        
        if len(business_claims) < 2:
            logger.debug("Not enough business claims for contradiction detection")
            return []
        
        # Find contradictions using optimized approach
        issues = await self._find_semantic_contradictions(business_claims)
        
        logger.debug(f"Found {len(issues)} textual contradictions")
        return issues
    
    async def _analyze_contradiction_with_llm(self, claim1: str, claim2: str, 
                                           slide1: int, slide2: int) -> Tuple[bool, float, str]:
        """Use LLM for sophisticated contradiction analysis."""
        # Check cache first to avoid duplicate API calls
        cache_key = self._create_cache_key(claim1, claim2)
        if cache_key in self.contradiction_cache:
            return self.contradiction_cache[cache_key]
        
        try:
            prompt = f"""
            Analyze these two business claims from a presentation and determine if they contradict each other.

            Claim 1 (Slide {slide1}): "{claim1}"
            Claim 2 (Slide {slide2}): "{claim2}"

            Two claims contradict if they:
            1. Make opposing assertions about the same business aspect, market, or capability
            2. Present mutually exclusive facts, conditions, or outcomes
            3. Contain logically incompatible statements about performance, position, or characteristics

            They do NOT contradict if they:
            1. Discuss different aspects, metrics, or time periods of the business
            2. Present complementary information that can coexist
            3. Address different markets, products, or business units
            4. Show progression or change over time (past vs future states)

            Consider context and nuance:
            - "High competition" vs "market leadership" can coexist
            - "Growing costs" vs "increasing revenue" are not contradictory
            - "Few direct competitors" vs "competitive market" may contradict depending on context

            Respond with JSON:
            {{
                "contradiction": true/false,
                "confidence": 0.0-1.0 (confidence in the analysis),
                "reasoning": "Detailed explanation of why they do or don't contradict, including what specific aspects conflict or align"
            }}

            Examples:
            - "Market is highly competitive with many players" vs "We face few direct competitors" → {{"contradiction": true, "confidence": 0.85, "reasoning": "Direct contradiction about competitive landscape - cannot have both many competitors and few competitors"}}
            - "Revenue increased 20% this quarter" vs "Operating costs rose 15%" → {{"contradiction": false, "confidence": 0.9, "reasoning": "Different financial metrics that can coexist - revenue growth and cost increases are independent"}}
            - "We are the market leader" vs "As a startup entering this space" → {{"contradiction": true, "confidence": 0.8, "reasoning": "Market leaders cannot simultaneously be startups entering the space"}}

            Be precise and focus on genuine logical contradictions, not just different perspectives on the same topic.
            """
            
            response = await self.gemini_client.generate_text(prompt)
            
            # Parse LLM response
            try:
                result = json.loads(response.strip())
                
                contradiction = result.get('contradiction', False)
                confidence = float(result.get('confidence', 0.0))
                reasoning = result.get('reasoning', 'No reasoning provided')
                
                # Cache result for efficiency
                self.contradiction_cache[cache_key] = (contradiction, confidence, reasoning)
                
                logger.debug(f"LLM contradiction analysis: {contradiction} (confidence: {confidence:.2f})")
                return contradiction, confidence, reasoning
            
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.debug(f"Failed to parse LLM response: {e}")
                return False, 0.0, "Failed to parse analysis"
        
        except Exception as e:
            logger.debug(f"LLM contradiction analysis failed: {e}")
            return False, 0.0, "Analysis failed"
    
    def _create_cache_key(self, claim1: str, claim2: str) -> str:
        """Create cache key for claim pair to avoid duplicate analysis."""
        # Normalize order to ensure consistent caching
        claims = sorted([claim1.strip(), claim2.strip()])
        combined = "|".join(claims)
        return hashlib.md5(combined.encode('utf-8')).hexdigest()
