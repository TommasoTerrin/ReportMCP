"""
Pydantic models for data ingestion and schema definition.

This module defines the data structures for ingesting external data
into the ReportMCP system, including column schemas and type definitions.
"""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class ColumnType(str, Enum):
    """
    Supported column data types for schema definition.
    
    These types map to DuckDB native types for optimal performance.
    """
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    DATE = "date"
    DATETIME = "datetime"
    BOOLEAN = "boolean"
    
    def to_duckdb_type(self) -> str:
        """Convert to DuckDB SQL type."""
        mapping = {
            ColumnType.STRING: "VARCHAR",
            ColumnType.INTEGER: "BIGINT",
            ColumnType.FLOAT: "DOUBLE",
            ColumnType.DATE: "DATE",
            ColumnType.DATETIME: "TIMESTAMP",
            ColumnType.BOOLEAN: "BOOLEAN",
        }
        return mapping[self]


class ColumnSchema(BaseModel):
    """
    Schema definition for a single data column.
    
    Attributes:
        name: Column identifier (must be valid SQL identifier).
        type: Data type of the column.
        description: Optional human-readable description.
        is_metric: True if column contains measurable values (for aggregations).
        is_dimension: True if column is used for grouping/filtering.
        format: Optional display format (e.g., "currency", "percentage").
    """
    name: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Column name (valid SQL identifier)",
    )
    type: ColumnType = Field(
        default=ColumnType.STRING,
        description="Data type of the column",
    )
    description: str = Field(
        default=None,
        max_length=500,
        description="Human-readable column description",
    )
    is_metric: bool = Field(
        default=False,
        description="True if column contains measurable values",
    )
    is_dimension: bool = Field(
        default=False,
        description="True if column is used for grouping/filtering",
    )
    format: Optional[str] = Field(
        default=None,
        description="Display format hint (e.g., 'currency', 'percentage')",
    )
    
    @field_validator("name")
    @classmethod
    def validate_column_name(cls, v: str) -> str:
        """Ensure column name is a valid SQL identifier."""
        # Remove leading/trailing whitespace
        v = v.strip()
        
        # Check for reserved characters
        invalid_chars = set(' -/\\@#$%^&*()+=[]{}|;:\'",.<>?!')
        if any(char in v for char in invalid_chars):
            raise ValueError(
                f"Column name '{v}' contains invalid characters. "
                "Use only alphanumeric characters and underscores."
            )
        
        # Cannot start with a number
        if v[0].isdigit():
            raise ValueError(f"Column name '{v}' cannot start with a number.")
        
        return v


class DataIngestionRequest(BaseModel):
    """
    Request payload for data ingestion.
    
    Contains the dataset to ingest along with its schema definition
    and session identifier for multi-tenant isolation.
    
    Attributes:
        session_id: Unique identifier for the data session.
        table_name: Name of the table to create in DuckDB.
        data: List of records as dictionaries.
        schema: List of column schema definitions.
        source_description: Optional description of data source.
        replace_if_exists: If True, replace existing table with same name.
    """
    session_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Unique session identifier",
    )
    table_name: str = Field(
        ...,
        min_length=1,
        max_length=64,
        pattern=r"^[a-zA-Z][a-zA-Z0-9_]*$",
        description="DuckDB table name",
    )
    data: list[dict[str, Any]] = Field(
        ...,
        min_length=1,
        description="List of data records",
    )
    schema: list[ColumnSchema] = Field(
        ...,
        min_length=1,
        description="Column schema definitions",
    )
    source_description: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Description of the data source",
    )
    replace_if_exists: bool = Field(
        default=True,
        description="Replace existing table if it exists",
    )
    
    @field_validator("data")
    @classmethod
    def validate_data_not_empty(cls, v: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Ensure data contains at least one record."""
        if not v:
            raise ValueError("Data must contain at least one record.")
        return v
    
    @field_validator("schema")
    @classmethod
    def validate_schema_not_empty(cls, v: list[ColumnSchema]) -> list[ColumnSchema]:
        """Ensure schema contains at least one column."""
        if not v:
            raise ValueError("Schema must define at least one column.")
        
        # Check for duplicate column names
        names = [col.name for col in v]
        if len(names) != len(set(names)):
            duplicates = [name for name in names if names.count(name) > 1]
            raise ValueError(f"Duplicate column names found: {set(duplicates)}")
        
        return v
    
    def get_column_names(self) -> list[str]:
        """Get list of column names from schema."""
        return [col.name for col in self.schema]
    
    def get_metrics(self) -> list[ColumnSchema]:
        """Get columns marked as metrics."""
        return [col for col in self.schema if col.is_metric]
    
    def get_dimensions(self) -> list[ColumnSchema]:
        """Get columns marked as dimensions."""
        return [col for col in self.schema if col.is_dimension]


class DataIngestionResponse(BaseModel):
    """
    Response after successful data ingestion.
    
    Attributes:
        success: True if ingestion was successful.
        session_id: The session ID where data was stored.
        table_name: The created table name.
        row_count: Number of rows ingested.
        column_count: Number of columns in the table.
        message: Human-readable status message.
    """
    success: bool = Field(
        default=True,
        description="Whether ingestion was successful",
    )
    session_id: str = Field(
        ...,
        description="Session ID where data was stored",
    )
    table_name: str = Field(
        ...,
        description="Created table name",
    )
    row_count: int = Field(
        ...,
        ge=0,
        description="Number of rows ingested",
    )
    column_count: int = Field(
        ...,
        ge=0,
        description="Number of columns in the table",
    )
    message: str = Field(
        default="Data ingested successfully",
        description="Human-readable status message",
    )
