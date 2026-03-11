# Templates package for ReportMCP
"""
Dashboard template generators.

This package provides template functions that generate
standardized dashboard blueprints based on data analysis.

Available templates:
- executive_summary: High-level KPIs with trend charts
- deep_dive: Detailed analysis with multiple visualizations
"""

from src.templates.executive import generate_executive_layout
from src.templates.deep_dive import generate_deep_dive_layout
from src.templates.base import BaseTemplate, get_template

__all__ = [
    "generate_executive_layout",
    "generate_deep_dive_layout",
    "BaseTemplate",
    "get_template",
]
