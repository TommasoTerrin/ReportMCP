# Components package for ReportMCP
"""
Dash component generators and renderers.

This package provides:
- renderer: Main render_layout() function for blueprint conversion
- kpi: KPI card components
- charts: Chart components (line, bar, pie)
- tables: Data table components
"""

from src.components.renderer import render_layout, render_component

__all__ = ["render_layout", "render_component"]
