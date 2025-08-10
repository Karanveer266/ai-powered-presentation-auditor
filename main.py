# main.py

"""
AI-Powered PowerPoint Inconsistency Detector
Optimized with a strategic batching architecture for minimal API calls.
"""

import asyncio
import argparse
import logging
import sys

from extraction import validate_inputs, extract_presentation_content
from detectors import (
    NumericalConflictDetector,
    TextContradictionDetector,
    PercentageSanityDetector,
    TimelineMismatchDetector
)
from gemini_wrapper import GeminiClient
from formatter import FormatterFactory
from config_loader import load_config

def setup_logging(verbose: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)

async def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description="AI-Powered PowerPoint Inconsistency Detector")
    parser.add_argument('pptx_path', help='Path to PowerPoint (.pptx) file')
    parser.add_argument('--format', choices=['rich', 'simple', 'json'], default='rich', help='Output format')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--config', default='config.yaml', help='Configuration file path')
    args = parser.parse_args()
    
    setup_logging(verbose=args.verbose or args.debug)
    logger = logging.getLogger(__name__)
    
    try:
        config = load_config(args.config)
        logger.info("📋 Configuration loaded successfully")
        
        gemini_client = GeminiClient(config['gemini'])
        logger.info("🤖 Gemini client initialized")
        
        # Note: Pass None for img_dir as it's not implemented in this version
        slides = await extract_presentation_content(args.pptx_path, None, gemini_client)
        logger.info(f"✅ Extracted content from {len(slides)} slides")
        
        if not slides:
            return

        logger.info("🔍 Starting comprehensive inconsistency detection with batch processing...")

        # Detectors are now self-contained and don't need a semaphore
        detectors = [
            NumericalConflictDetector(config.get('detectors', {}), gemini_client),
            TextContradictionDetector(config.get('detectors', {}), gemini_client),
            PercentageSanityDetector(config.get('detectors', {}), gemini_client),
            TimelineMismatchDetector(config.get('detectors', {}), gemini_client)
        ]

        tasks = [detector.detect(slides) for detector in detectors]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_issues = []
        for result in results:
            if isinstance(result, list):
                all_issues.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"A detector failed: {result}", exc_info=args.debug)
        
        issues = list(set(all_issues))
        
        formatter = FormatterFactory.create(args.format)
        output = formatter.format(issues)
        if output:
            print(output)
        
        total_issues = len(issues)
        if total_issues > 0:
             logger.info(f"✅ Analysis complete. Found {total_issues} unique inconsistencies.")
        else:
             logger.info("✅ Analysis complete. No inconsistencies were detected.")
    
    except Exception as e:
        logger.error(f"❌ Analysis failed: {e}", exc_info=args.debug)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())