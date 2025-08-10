"""
Output formatters for inconsistency detection results.
"""

import json
import logging
from typing import List

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from models import Issue


logger = logging.getLogger(__name__)


class BaseFormatter:
    """Base formatter interface."""
    
    def format(self, issues: List[Issue]) -> str:
        """Format issues and return as string."""
        raise NotImplementedError


class RichTableFormatter(BaseFormatter):
    """Rich table formatter for beautiful console output."""
    
    def __init__(self):
        self.console = Console()
    
    def format(self, issues: List[Issue]) -> str:
        """Format issues as a beautiful Rich table and return empty string (prints directly)."""
        if not issues:
            self._display_no_issues()
            return ""
        
        # Create the main table
        table = Table(
            title="🔍 PowerPoint Inconsistency Detection Results",
            show_header=True,
            header_style="bold cyan",
            border_style="bright_blue",
            title_style="bold magenta"
        )
        
        # Add columns
        table.add_column("Issue Type", style="yellow", no_wrap=True)
        table.add_column("Slides", style="green", justify="center")
        table.add_column("Description", style="white")
        table.add_column("Details", style="dim white")
        table.add_column("Confidence", style="red", justify="center")
        
        # Add rows
        for issue in issues:
            slides_str = ", ".join(map(str, issue.slides))
            confidence_str = f"{issue.confidence:.1%}"
            
            # Color code confidence
            if issue.confidence >= 0.8:
                confidence_style = "bold red"
            elif issue.confidence >= 0.6:
                confidence_style = "yellow"
            else:
                confidence_style = "dim white"
            
            table.add_row(
                issue.issue_type.replace('_', ' ').title(),
                slides_str,
                issue.description,
                issue.details[:100] + "..." if len(issue.details) > 100 else issue.details,
                Text(confidence_str, style=confidence_style)
            )
        
        # Display the table
        self.console.print("\n")
        self.console.print(table)
        self.console.print(f"\n[bold green]Total Issues Found: {len(issues)}[/bold green]")
        return ""  # Rich prints directly, so return empty string
    
    def _display_no_issues(self) -> None:
        """Display a message when no issues are found."""
        panel = Panel(
            "[bold green]No Inconsistencies Detected![/bold green]\n\n"
            "The presentation appears to be internally consistent.\n"
            "All numerical data, claims, and timelines align properly.",
            title="Analysis Complete",
            border_style="green",
            padding=(1, 2)
        )
        
        self.console.print("\n")
        self.console.print(panel)


class SimpleFormatter(BaseFormatter):
    """Simple text formatter for basic output."""
    
    def format(self, issues: List[Issue]) -> str:
        """Format issues as simple text and return as string."""
        if not issues:
            return "No inconsistencies detected"
        
        output = []
        output.append(f"\n🔍 PowerPoint Inconsistency Detection Results")
        output.append("=" * 60)
        
        for i, issue in enumerate(issues, 1):
            output.append(f"\n{i}. {issue.description}")
            output.append(f"   Type: {issue.issue_type}")
            output.append(f"   Slides: {', '.join(map(str, issue.slides))}")
            output.append(f"   Confidence: {issue.confidence:.1%}")
            output.append(f"   Details: {issue.details}")
        
        output.append(f"\nTotal Issues Found: {len(issues)}")
        return "\n".join(output)


class JSONFormatter(BaseFormatter):
    """JSON formatter for structured output."""
    
    def format(self, issues: List[Issue]) -> str:
        """Format issues as JSON and return as string."""
        issues_data = []
        
        for issue in issues:
            issues_data.append({
                "issue_type": issue.issue_type,
                "slides": issue.slides,
                "description": issue.description,
                "details": issue.details,
                "confidence": issue.confidence
            })
        
        result = {
            "total_issues": len(issues),
            "issues": issues_data
        }
        
        return json.dumps(result, indent=2)


class FormatterFactory:
    """Factory to create appropriate formatters."""
    
    @staticmethod
    def create(format_type: str) -> BaseFormatter:
        """Create formatter based on format type."""
        if format_type == "json":
            return JSONFormatter()
        elif format_type == "simple":
            return SimpleFormatter()
        else:  # default to rich
            return RichTableFormatter()
