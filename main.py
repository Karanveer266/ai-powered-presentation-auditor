"""
AI-Powered PowerPoint Inconsistency Detector (Free Tier Optimized)
Comprehensive inconsistency detection with minimal API calls.
"""

import asyncio
import argparse
import logging
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

from extraction import validate_inputs, extract_presentation_content
from detector_hub import UnifiedDetectorHub
from gemini_wrapper import GeminiClient
from formatter import FormatterFactory
from config_loader import load_config


def setup_logging(verbose: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Reduce noise from external libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)


async def main():
    """Main execution function optimized for free tier API usage."""
    # Load environment variables from .env file
    load_dotenv()
    
    parser = argparse.ArgumentParser(
        description="AI-Powered PowerPoint Inconsistency Detector (Free Tier Optimized)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py presentation.pptx --verbose
  python main.py deck.pptx --images slide_images/ --format simple
  python main.py presentation.pptx --debug

Note: This version is optimized for Gemini's free tier (10 requests/minute).
Analysis uses ~{N+2} API calls where N = number of slides.
        """
    )
    
    parser.add_argument('pptx_path', help='Path to PowerPoint (.pptx) file')
    parser.add_argument('--images', help='Directory containing slide images (optional)')
    parser.add_argument('--format', choices=['rich', 'simple', 'json'], 
                       default='rich', help='Output format (default: rich)')
    parser.add_argument('--verbose', '-v', action='store_true', 
                       help='Enable verbose logging')
    parser.add_argument('--debug', action='store_true', 
                       help='Enable debug logging and error details')
    parser.add_argument('--config', default='config.yaml', 
                       help='Configuration file path (default: config.yaml)')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(verbose=args.verbose or args.debug)
    logger = logging.getLogger(__name__)
    
    try:
        # Validate inputs
        validate_inputs(args.pptx_path, args.images)
        
        # Load configuration
        config = load_config(args.config)
        logger.info("Configuration loaded successfully")
        
        # Initialize Gemini client
        gemini_client = GeminiClient(config['gemini'])
        logger.info("Gemini client initialized")
        
        # Extract presentation content
        logger.info("Extracting presentation content...")
        slides = extract_presentation_content(args.pptx_path, args.images, gemini_client)
        logger.info(f"Extracted content from {len(slides)} slides")
        
        if not slides:
            logger.error("No slides found or extracted")
            return
        
        # Estimate API usage
        estimated_calls = len(slides) + 2
        estimated_time = (estimated_calls * 8) / 60  # 8 seconds between calls
        logger.info(f"Estimated API usage: {estimated_calls} calls (~{estimated_time:.1f} minutes)")
        
        # Run unified inconsistency detection
        logger.info("Starting comprehensive inconsistency detection...")
        detector_hub = UnifiedDetectorHub(config, gemini_client)
        issues = await detector_hub.detect_all_inconsistencies(slides)
        
        # Format and display results (FIXED SECTION)
        try:
            # Use the factory to create the correct formatter based on user args
            formatter = FormatterFactory.create(args.format)
            # Call the 'format' method and print the result
            output = formatter.format(issues)
            if output:  # Only print if formatter returns content (simple/json do, rich doesn't)
                print(output)
        except Exception as e:
            logger.error(f"Failed to format results: {e}")
            # As a fallback, just print the raw issues
            if issues:
                logger.info("Raw issues found:")
                for issue in issues:
                    logger.info(f"Issue: {issue.description} (Slides: {issue.slides})")
            else:
                logger.info("No issues found")
        
        # Summary
        if issues:
            logger.info(f"Analysis complete. Found {len(issues)} inconsistencies.")
        else:
            logger.info("Analysis complete. No inconsistencies detected!")
    
    except KeyboardInterrupt:
        logger.info("Analysis interrupted by user")
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        if args.debug:
            logger.exception("Full error details:")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
