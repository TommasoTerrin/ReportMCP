"""
Custom exception classes for ReportMCP.

This module defines a hierarchy of exceptions for proper error handling
across the application. All exceptions inherit from ReportMCPError.
"""

from typing import Any, Optional


class ReportMCPError(Exception):
    """
    Base exception for all ReportMCP errors.
    
    Attributes:
        message: Human-readable error description.
        details: Optional dictionary with additional context.
        error_code: Optional error code for programmatic handling.
    """
    
    def __init__(
        self,
        message: str,
        details: Optional[dict[str, Any]] = None,
        error_code: Optional[str] = None,
    ) -> None:
        self.message = message
        self.details = details or {}
        self.error_code = error_code or "REPORTMCP_ERROR"
        super().__init__(self.message)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error": True,
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
        }


class DataIngestionError(ReportMCPError):
    """
    Raised when data ingestion fails.
    
    Examples:
        - Invalid data format
        - Schema validation failure
        - DuckDB insertion error
    """
    
    def __init__(
        self,
        message: str,
        details: Optional[dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> None:
        error_details = details or {}
        if session_id:
            error_details["session_id"] = session_id
        super().__init__(
            message=message,
            details=error_details,
            error_code="DATA_INGESTION_ERROR",
        )


class BlueprintGenerationError(ReportMCPError):
    """
    Raised when dashboard blueprint generation fails.
    
    Examples:
        - No data available for session
        - Invalid template name
        - Query execution failure
    """
    
    def __init__(
        self,
        message: str,
        details: Optional[dict[str, Any]] = None,
        session_id: Optional[str] = None,
        template: Optional[str] = None,
    ) -> None:
        error_details = details or {}
        if session_id:
            error_details["session_id"] = session_id
        if template:
            error_details["template"] = template
        super().__init__(
            message=message,
            details=error_details,
            error_code="BLUEPRINT_GENERATION_ERROR",
        )


class RenderingError(ReportMCPError):
    """
    Raised when dashboard rendering fails.
    
    Examples:
        - Invalid component type
        - Missing required props
        - Data query failure
    """
    
    def __init__(
        self,
        message: str,
        details: Optional[dict[str, Any]] = None,
        component_type: Optional[str] = None,
    ) -> None:
        error_details = details or {}
        if component_type:
            error_details["component_type"] = component_type
        super().__init__(
            message=message,
            details=error_details,
            error_code="RENDERING_ERROR",
        )




class SessionNotFoundError(ReportMCPError):
    """
    Raised when a requested session does not exist.
    """
    
    def __init__(self, session_id: str) -> None:
        super().__init__(
            message=f"Session '{session_id}' not found",
            details={"session_id": session_id},
            error_code="SESSION_NOT_FOUND",
        )


class ValidationError(ReportMCPError):
    """
    Raised when input validation fails.
    """
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
    ) -> None:
        details = {}
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = str(value)
        super().__init__(
            message=message,
            details=details,
            error_code="VALIDATION_ERROR",
        )
