# 🤖 AI-Powered PowerPoint Inconsistency Detector

An advanced, AI-powered tool that analyzes PowerPoint presentations to identify factual and logical inconsistencies across slides using **Gemini 2.5 Flash** for semantic understanding and intelligent context analysis.

## 🎯 Features

### **Core AI-Powered Detection Capabilities**
- **🔢 Numerical Conflicts**: LLM-powered semantic analysis of conflicting numerical data with context understanding
- **📊 Percentage Validation**: AI-enhanced validation of percentages, sums, and mathematical consistency  
- **💬 Textual Contradictions**: Advanced semantic contradiction detection using natural language understanding
- **📅 Timeline Mismatches**: Intelligent chronological analysis and temporal consistency checking

### **Advanced AI Capabilities**
- **🧠 Semantic Understanding**: Distinguishes between different types of metrics (revenue vs. time vs. technical specs)
- **🎯 Context-Aware Analysis**: Understands business vs. technical presentations automatically
- **🚫 False Positive Elimination**: Filters out graduation years, version numbers, and technical specifications
- **📈 Confidence Scoring**: AI-powered confidence assessment for each detected issue

### **Technical Features**
- **🖼️ OCR Support**: Gemini Vision API extracts text from slide images with high accuracy
- **⚡ Batch Processing**: Efficiently handles large presentations with parallel processing
- **🎨 Rich Output**: Beautiful terminal formatting, JSON export, and detailed analysis reports
- **🔧 Configurable**: Customizable detection thresholds and AI model parameters

## 🚀 Quick Start

### **Prerequisites**
- Python 3.8+
- Google Gemini API key ([Get free key here](https://aistudio.google.com/app/apikey))

### **Installation**

1. Clone the repository:
```bash
git clone https://github.com/yourusername/powerpoint-inconsistency-detector.git
cd powerpoint-inconsistency-detector
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
# Create a .env file with your Gemini API key
echo "GEMINI_API_KEY=your_api_key_here" > .env
```

### **Usage**

```bash
# Basic usage
python main.py path/to/presentation.pptx

# With verbose output
python main.py path/to/presentation.pptx --verbose

# With custom output format
python main.py path/to/presentation.pptx --format json
```

