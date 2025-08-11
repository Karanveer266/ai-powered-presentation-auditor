# 🔍 AI-Powered PowerPoint Inconsistency Detector

An advanced, AI-powered tool that analyzes PowerPoint presentations to identify factual and logical inconsistencies across slides using **Google Gemini 1.5 Flash** for semantic understanding and intelligent context analysis.

## 🎯 Project Overview

This tool helps users identify inconsistencies in their PowerPoint presentations by analyzing numerical data, percentages, textual claims, and timelines. It uses advanced AI techniques to understand the semantic meaning of content and detect contradictions that might be missed by human reviewers.

## ✨ Key Features

### **Core AI-Powered Detection Capabilities**

- **🔢 Numerical Conflicts**: Identifies conflicting numerical values across slides with semantic understanding of what the numbers represent (e.g., revenue, user count, time savings)
- **📊 Percentage Validation**: Validates percentage values for mathematical consistency and checks if related percentages sum to 100%
- **💬 Textual Contradictions**: Detects semantic contradictions in business claims and statements across slides
- **📅 Timeline Mismatches**: Analyzes dates and events for chronological inconsistencies and conflicting timelines

### **Advanced AI Capabilities**

- **🧠 Semantic Understanding**: Distinguishes between different types of metrics and understands their business context
- **🎯 Context-Aware Analysis**: Understands the presentation's domain and adapts analysis accordingly
- **🚫 False Positive Reduction**: Intelligently filters out non-contradictory information
- **📈 Confidence Scoring**: Provides confidence levels for each detected issue

### **Technical Features**

- **🖼️ OCR Support**: Extracts text from slide images for comprehensive analysis
- **⚡ Batch Processing**: Efficiently processes large presentations with parallel detection
- **🎨 Rich Output Formatting**: Multiple output formats including rich console display and JSON
- **🔧 Configurable**: Customizable detection thresholds and parameters

## 🚀 Installation

### Prerequisites

- Python 3.8+
- Google Gemini API key ([Get free key here](https://aistudio.google.com/app/apikey))

### Setup

1. Clone the repository:
```bash
git clone https://github.com/Karanveer266/ai-powered-presentation-auditor.git
cd ai-powered-presentation-auditor
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up your API key:
```bash
# Create a .env file with your Gemini API key
echo "GEMINI_API_KEY=your_api_key_here" > .env
```

## 📊 Usage

```bash
# Basic usage
python main.py path/to/presentation.pptx

# With verbose output
python main.py path/to/presentation.pptx --verbose

# With custom output format
python main.py path/to/presentation.pptx --format json

# With debug information
python main.py path/to/presentation.pptx --debug
```

## 🔍 How It Works

### Detection Process

1. **Content Extraction**: Extracts text, tables, and image content from PowerPoint slides
2. **Parallel Analysis**: Runs specialized detectors concurrently for efficient processing
3. **AI-Powered Detection**: Uses Gemini AI to understand context and identify inconsistencies
4. **Result Aggregation**: Combines and deduplicates results from all detectors
5. **Formatted Output**: Presents findings in a clear, actionable format

### Detector Types

1. **Numerical Conflict Detector**: Groups numerical data by semantic meaning and identifies conflicts
2. **Percentage Sanity Detector**: Validates individual percentages and checks if related percentages sum correctly
3. **Text Contradiction Detector**: Identifies logical contradictions in business claims
4. **Timeline Mismatch Detector**: Detects chronological inconsistencies and conflicting event dates

## WHAT IT DOES

### Accuracy and Completeness of Inconsistency Detection

- **Comprehensive Detection**: Analyzes multiple types of inconsistencies (numerical, textual, percentage, timeline)
- **Semantic Understanding**: Uses AI to understand the meaning behind numbers and statements
- **Context-Aware Analysis**: Considers the business context when identifying inconsistencies
- **Confidence Scoring**: Provides confidence levels for each detected issue

### Clarity and Usability of the Output

- **Rich Formatting**: Beautiful console output with color-coding and clear organization
- **Multiple Output Formats**: Supports rich, simple, and JSON output formats
- **Actionable Information**: Provides slide numbers, descriptions, and detailed explanations
- **Confidence Indicators**: Helps users prioritize which issues to address first

### Scalability, Generalizability and Robustness to Large Decks

- **Parallel Processing**: Concurrent execution of detectors for efficient processing
- **Batch Analysis**: Processes multiple slides in batches to minimize API calls
- **Error Handling**: Robust error handling and retry mechanisms for API calls
- **Configurable Parameters**: Adjustable thresholds for different presentation types

## 🛠️ Configuration

The tool is highly configurable through the `config.yaml` file:

```yaml
# Gemini API Configuration
gemini:
  api_key_env: "GEMINI_API_KEY"
  model: "gemini-1.5-flash-latest" 
  max_retries: 3

# Detector-specific configurations
detectors:
  numerical:
    tolerance_pct: 1 # Allow 1% difference for floating point comparisons
  textual:
    similarity_threshold: 0.70
  percentage:
    total_tolerance_pp: 2 # Allow a 2 percentage point deviation from 100%
  timeline:
    overlap_tolerance_days: 0
```

## 🔄 Limitations and Future Improvements

### Current Limitations

- **Language Support**: Currently optimized for English content
- **Complex Tables**: May have difficulty with highly complex or nested tables
- **Domain Knowledge**: General business understanding but limited specialized domain knowledge
- **API Dependency**: Requires internet connection and valid API key

### Planned Improvements

- **Multi-language Support**: Extend to additional languages
- **Enhanced OCR**: Improve image text extraction capabilities
- **Domain-Specific Models**: Add specialized models for different industries
- **Local Processing Option**: Add option for local processing without API calls
- **Interactive Fixing**: Suggest corrections for identified inconsistencies
