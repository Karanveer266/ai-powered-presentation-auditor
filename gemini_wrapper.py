"""
Gemini API wrapper optimized for free tier usage with minimal API calls.
"""

import asyncio
import logging
import os
from typing import List, Optional, Dict, Any

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold


logger = logging.getLogger(__name__)


class GeminiClient:
    """Gemini API client optimized for free tier constraints."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.api_key = os.getenv(config.get('api_key_env', 'GEMINI_API_KEY'))
        
        if not self.api_key:
            raise ValueError("Gemini API key not found in environment variables")
        
        # Configure Gemini
        genai.configure(api_key=self.api_key)
        
        # Initialize model with safety settings
        self.model = genai.GenerativeModel(
            model_name=config.get('model', 'gemini-2.0-flash-exp'),
            safety_settings={
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
        )
        
        # Rate limiting for free tier
        self.request_delay = config.get('request_delay', 8)  # 8 seconds between requests
        self.max_retries = config.get('max_retries', 2)
        
        logger.info("🔧 Gemini client configured for free tier usage")
    
    async def generate_text(self, prompt: str) -> str:
        """Generate text with free tier optimized retry logic."""
        for attempt in range(self.max_retries):
            try:
                if attempt > 0:
                    wait_time = 60  # Wait 1 minute on retry for quota reset
                    logger.info(f"⏳ Waiting {wait_time}s for quota reset (attempt {attempt + 1})")
                    await asyncio.sleep(wait_time)
                
                logger.debug("🤖 Making API request...")
                response = self.model.generate_content(prompt)
                
                if response and hasattr(response, 'text') and response.text:
                    logger.debug("✅ API request successful")
                    return response.text.strip()
                else:
                    raise ValueError("Empty response from Gemini")
            
            except Exception as e:
                error_str = str(e).lower()
                
                # Handle quota errors specifically
                if 'quota' in error_str or '429' in error_str or 'rate limit' in error_str:
                    logger.warning(f"🚫 Rate limit hit: {e}")
                    if attempt < self.max_retries - 1:
                        logger.info("💡 Will retry after quota reset...")
                        continue
                    else:
                        logger.error("❌ Rate limit exceeded. Please wait 1 minute and try again.")
                        raise Exception("Rate limit exceeded. Free tier quota exhausted.")
                
                # Handle other errors
                elif any(term in error_str for term in ['billing', 'permission', 'authentication']):
                    logger.error(f"❌ API configuration error: {e}")
                    raise
                
                else:
                    logger.warning(f"⚠️ API error (attempt {attempt + 1}): {e}")
                    if attempt >= self.max_retries - 1:
                        raise
        
        raise Exception("All retry attempts failed")
    
    async def extract_text_from_image(self, image_path: str) -> str:
        """Extract text from image with free tier optimization."""
        try:
            logger.debug(f"🖼️ Extracting text from: {image_path}")
            
            # Load image
            image_data = self._load_image(image_path)
            
            # Simple, efficient OCR prompt
            prompt = """Extract all visible text from this slide image. Include:
- All text content, headings, bullet points
- Numbers, percentages, financial figures
- Chart labels and data points
- Any other readable text

Return clean, structured text preserving hierarchy."""
            
            response = await self.generate_text_with_image(prompt, image_data)
            logger.debug(f"✅ Extracted {len(response)} characters from image")
            return response
        
        except Exception as e:
            logger.error(f"❌ OCR failed for {image_path}: {e}")
            return ""
    
    async def generate_text_with_image(self, prompt: str, image_data: Dict[str, Any]) -> str:
        """Generate text response with image input."""
        try:
            content = [prompt, image_data]
            response = self.model.generate_content(content)
            
            if response and hasattr(response, 'text') and response.text:
                return response.text.strip()
            else:
                raise ValueError("Empty response from Gemini Vision")
        
        except Exception as e:
            logger.error(f"Vision API error: {e}")
            raise
    
    def _load_image(self, image_path: str) -> Dict[str, Any]:
        """Load image file for Gemini Vision API."""
        import mimetypes
        
        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type or not mime_type.startswith('image/'):
            mime_type = 'image/jpeg'
        
        with open(image_path, 'rb') as f:
            image_data = f.read()
        
        return {
            'mime_type': mime_type,
            'data': image_data
        }
