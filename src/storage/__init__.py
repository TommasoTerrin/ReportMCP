# Storage package for ReportMCP
"""
Data storage and management utilities.

This package provides:
- DuckDB manager for in-memory analytics
- Session-based data isolation
"""

from src.storage.duckdb_manager import DuckDBManager

__all__ = ["DuckDBManager"]
