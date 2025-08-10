# gemini_wrapper.py

import asyncio
import logging
import os
from typing import List, Dict, Any

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self, config: Dict[str, Any]):
        self.api_key = os.getenv(config.get('api_key_env', 'GEMINI_API_KEY'))
        if not self.api_key:
            raise ValueError("Gemini API key not found in environment variables")
        
        genai.configure(api_key=self.api_key)
        
        # --- ROBUST API CONFIGURATION ---
        self.model = genai.GenerativeModel(
            model_name=config.get('model', 'gemini-1.5-flash-latest'),
            # 1. Disable all safety filters to prevent erroneous blocking of business text
            safety_settings={
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            },
            # 2. Enable JSON Mode to force the model to output valid JSON
            generation_config={"response_mime_type": "application/json"}
        )

        self.max_retries = config.get('max_retries', 3)
        self.base_retry_delay = config.get('base_retry_delay', 5)
        logger.info(f"🔧 Gemini client configured for model {self.model.model_name} with JSON mode enabled.")

    async def _make_api_call(self, call_func, *args, **kwargs):
        for attempt in range(self.max_retries):
            try:
                return await call_func(*args, **kwargs)
            except Exception as e:
                if "429" in str(e) and "quota" in str(e).lower():
                    if attempt < self.max_retries - 1:
                        delay = self.base_retry_delay * (2 ** attempt)
                        logger.warning(f"RATE LIMIT HIT. Waiting {delay}s before retry {attempt + 2}/{self.max_retries}...")
                        await asyncio.sleep(delay)
                    else:
                        logger.error("RATE LIMIT EXCEEDED. All retries failed.")
                        raise e
                else:
                    logger.error(f"API call failed with non-retriable error: {e}")
                    raise e
        raise Exception("All retry attempts failed")

    async def generate_text(self, prompt: str) -> str:
        logger.debug(f"🤖 Generating text for prompt (first 50 chars): {prompt[:50]}...")
        try:
            response = await self._make_api_call(self.model.generate_content_async, prompt)
            return response.text.strip() if response and response.text else ""
        except Exception as e:
            logger.error(f"Text generation failed after all retries: {e}")
            return "" # Return empty string on failure