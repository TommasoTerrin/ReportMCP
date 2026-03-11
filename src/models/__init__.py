# Models package for ReportMCP
"""
Pydantic models for data validation and serialization.

This package contains:
- blueprint: Dashboard component and layout models
- data: Data ingestion and schema models
- exceptions: Custom exception classes
"""

from src.models.blueprint import (
    ComponentConfig,
    ComponentType,
    DashboardBlueprint,
    KPIConfig,
    ChartConfig,
)
from src.models.data import (
    ColumnSchema,
    ColumnType,
    DataIngestionRequest,
    DataIngestionResponse,
)
from src.models.exceptions import (
    ReportMCPError,
    DataIngestionError,
    BlueprintGenerationError,
    RenderingError,
    SessionNotFoundError,
    ValidationError,
)

__all__ = [
    # Blueprint models
    "ComponentConfig",
    "ComponentType",
    "DashboardBlueprint",
    "KPIConfig",
    "ChartConfig",
    # Data models
    "ColumnSchema",
    "ColumnType",
    "DataIngestionRequest",
    "DataIngestionResponse",
    # Exceptions
    "ReportMCPError",
    "DataIngestionError",
    "BlueprintGenerationError",
    "RenderingError",
    "SessionNotFoundError",
    "ValidationError",
]
