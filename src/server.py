"""
MCP Server for ReportMCP.

This module implements the Model Context Protocol server that exposes
tools for data ingestion, dashboard blueprint generation, and URL retrieval.
The server can be run in stdio mode for AI agent integration.

Usage:
    # Run with FastMCP
    fastmcp dev src/server.py
    
    # Or run directly
    python -m src.server
"""

import logging
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from fastmcp import FastMCP
from pydantic import BaseModel, Field

from src.models.blueprint import DashboardBlueprint, ComponentConfig, ComponentType
from src.models.data import (
    ColumnSchema,
    ColumnType,
    DataIngestionRequest,
    DataIngestionResponse,
)
from src.models.exceptions import (
    BlueprintGenerationError,
    DataIngestionError,
    SessionNotFoundError,
)
from src.storage.duckdb_manager import DuckDBManager
from src.templates.base import get_template, list_templates

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize MCP server
mcp = FastMCP(
    "ReportMCP",
    instructions=(
        "MCP Server for Business Intelligence Dashboard. "
        "Ingest data, generate dashboard blueprints, and view interactive reports."
    ),
)

import os

# Global storage instances
# Note: In production, consider dependency injection or context management
DUCKDB_PATH = os.getenv("DUCKDB_PATH", ":memory:")
db_manager = DuckDBManager(db_path=DUCKDB_PATH)
blueprint_store: dict[str, DashboardBlueprint] = {}

def load_saved_blueprints() -> None:
    """Load all saved blueprints from DuckDB into memory."""
    try:
        saved = db_manager.list_blueprints()
        for session_id, blueprint_json in saved:
            try:
                blueprint = DashboardBlueprint.model_validate_json(blueprint_json)
                blueprint_store[session_id] = blueprint
                logger.info(f"Restored blueprint for session: {session_id}")
            except Exception as e:
                logger.error(f"Failed to validate restored blueprint {session_id}: {e}")
    except Exception as e:
        logger.error(f"Error loading saved blueprints: {e}")

# Load persistence on module import
load_saved_blueprints()

# Configuration
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8050


# ============================================================================
# Input/Output Models for Tools
# ============================================================================


class IngestDataInput(BaseModel):
    """Input model for ingest_data tool."""
    
    session_id: str = Field(
        ...,
        description="Unique identifier for the data session",
        examples=["sales_q4_2024", "marketing_campaign_01"],
    )
    table_name: str = Field(
        ...,
        description="Name for the table to create",
        examples=["sales", "customers", "transactions"],
    )
    data: list[dict[str, Any]] = Field(
        ...,
        description="List of data records as dictionaries",
        examples=[[{"month": "Jan", "revenue": 50000}, {"month": "Feb", "revenue": 62000}]],
    )
    schema: list[dict[str, Any]] = Field(
        ...,
        description=(
            "Column schema definitions. Each column should have: "
            "name (str), type (string|integer|float|date|datetime|boolean), "
            "is_metric (bool, optional), is_dimension (bool, optional)"
        ),
        examples=[[
            {"name": "month", "type": "string", "is_dimension": True},
            {"name": "revenue", "type": "float", "is_metric": True},
        ]],
    )
    source_description: Optional[str] = Field(
        default=None,
        description="Optional description of the data source",
    )


class GenerateBlueprintInput(BaseModel):
    """Input model for generate_dashboard_blueprint tool."""
    
    session_id: str = Field(
        ...,
        description="Session ID containing the ingested data",
    )
    title: str = Field(
        default="Business Dashboard",
        description="Title for the dashboard",
    )
    objective: Optional[str] = Field(
        default=None,
        description=(
            "Business objective for the dashboard "
            "(e.g., 'Show sales trends and top performing products')"
        ),
    )
    template: Literal["executive_summary", "deep_dive"] = Field(
        default="executive_summary",
        description="Dashboard template to use",
    )


# ============================================================================
# MCP Tools
# ============================================================================


@mcp.tool()
async def ingest_data(
    session_id: str,
    table_name: str,
    data: list[dict[str, Any]],
    schema: list[dict[str, Any]],
    source_description: Optional[str] = None,
) -> dict[str, Any]:
    """
    Ingest data into the ReportMCP system for analysis and visualization.
    
    This tool accepts a dataset with its schema definition and stores it
    in an in-memory DuckDB database for fast querying. Each session is
    isolated, allowing multiple datasets to coexist.
    
    Args:
        session_id: Unique identifier for the data session. Use descriptive
            names like "sales_q4_2024" or "marketing_analysis".
        table_name: Name for the table to create. Must be a valid SQL
            identifier (letters, numbers, underscores).
        data: List of data records. Each record is a dictionary with
            column names as keys.
        schema: Column schema definitions. Each column needs:
            - name: Column name (required)
            - type: Data type - one of: string, integer, float, date, datetime, boolean
            - is_metric: True for numeric columns used in calculations (optional)
            - is_dimension: True for categorical/grouping columns (optional)
        source_description: Optional description of where the data came from.
    
    Returns:
        Dictionary containing:
        - success: True if ingestion succeeded
        - session_id: The session where data was stored
        - table_name: The created table name
        - row_count: Number of rows ingested
        - column_count: Number of columns
        - message: Human-readable status message
    
    Example:
        ```python
        result = await ingest_data(
            session_id="sales_2024",
            table_name="monthly_sales",
            data=[
                {"month": "January", "revenue": 50000, "units": 120},
                {"month": "February", "revenue": 62000, "units": 145},
            ],
            schema=[
                {"name": "month", "type": "string", "is_dimension": True},
                {"name": "revenue", "type": "float", "is_metric": True},
                {"name": "units", "type": "integer", "is_metric": True},
            ]
        )
        ```
    
    Raises:
        DataIngestionError: If data validation or insertion fails.
    """
    logger.info(f"Ingesting data: session={session_id}, table={table_name}, rows={len(data)}")
    
    try:
        # Convert schema dictionaries to ColumnSchema objects
        column_schemas = []
        for col_def in schema:
            col_type = ColumnType(col_def.get("type", "string"))
            column_schemas.append(
                ColumnSchema(
                    name=col_def["name"],
                    type=col_type,
                    description=col_def.get("description"),
                    is_metric=col_def.get("is_metric", False),
                    is_dimension=col_def.get("is_dimension", False),
                    format=col_def.get("format"),
                )
            )
        
        # Create ingestion request
        request = DataIngestionRequest(
            session_id=session_id,
            table_name=table_name,
            data=data,
            schema=column_schemas,
            source_description=source_description,
        )
        
        # Perform ingestion
        response = db_manager.ingest_data(request)
        
        logger.info(f"Data ingestion successful: {response.row_count} rows")
        
        return response.model_dump()
        
    except DataIngestionError:
        raise
    except Exception as e:
        logger.error(f"Data ingestion failed: {e}", exc_info=True)
        raise DataIngestionError(
            message=f"Failed to ingest data: {str(e)}",
            session_id=session_id,
            details={"table_name": table_name, "error": str(e)},
        )


@mcp.tool()
async def generate_dashboard_blueprint(
    session_id: str,
    title: str = "Business Dashboard",
    objective: Optional[str] = None,
    template: Literal["executive_summary", "deep_dive"] = "executive_summary",
) -> dict[str, Any]:
    """
    Generate a dashboard blueprint based on ingested data.
    
    This tool analyzes the data in the specified session and generates
    a configuration that describes the dashboard layout, components,
    and visualizations. The blueprint can then be rendered as an
    interactive dashboard.
    
    Args:
        session_id: Session ID containing the data to visualize.
        title: Title to display on the dashboard.
        objective: Business objective or question to answer
            (e.g., "Show monthly revenue trends and identify top customers").
            This helps the template select appropriate visualizations.
        template: Dashboard template to use:
            - "executive_summary": High-level overview with KPIs and main chart
            - "deep_dive": Detailed analysis with multiple charts and tables
    
    Returns:
        Dictionary containing the complete dashboard blueprint:
        - session_id: Reference to the data session
        - title: Dashboard title
        - template: Template used
        - components: List of component configurations
        - metadata: Additional dashboard metadata
        - created_at: Timestamp of creation
    
    Example:
        ```python
        blueprint = await generate_dashboard_blueprint(
            session_id="sales_2024",
            title="Q4 Sales Analysis",
            objective="Show sales trends and identify top performing regions",
            template="executive_summary"
        )
        ```
    
    Raises:
        SessionNotFoundError: If the session does not exist.
        BlueprintGenerationError: If blueprint generation fails.
    """
    logger.info(
        f"Generating blueprint: session={session_id}, template={template}"
    )
    
    try:
        # Verify session exists and get data summary
        if not db_manager.session_exists(session_id):
            raise SessionNotFoundError(session_id)
        
        data_summary = db_manager.get_data_summary(session_id)
        
        # Get the template
        template_instance = get_template(template)
        if template_instance is None:
            available = [t["name"] for t in list_templates()]
            raise BlueprintGenerationError(
                message=f"Unknown template: {template}",
                session_id=session_id,
                template=template,
                details={"available_templates": available},
            )
        
        # Generate the blueprint
        blueprint = template_instance.generate(
            session_id=session_id,
            title=title,
            data_summary=data_summary,
            objective=objective,
        )
        
        # Store the blueprint in memory
        blueprint_store[session_id] = blueprint
        
        # PERSIST TO DUCKDB
        try:
            db_manager.save_blueprint(session_id, blueprint.model_dump_json())
        except Exception as e:
            logger.error(f"Failed to persist blueprint to DuckDB: {e}")
        
        logger.info(
            f"Blueprint generated: {blueprint.count_components()} components"
        )
        
        return blueprint.model_dump()
        
    except (SessionNotFoundError, BlueprintGenerationError):
        raise
    except Exception as e:
        logger.error(f"Blueprint generation failed: {e}", exc_info=True)
        raise BlueprintGenerationError(
            message=f"Failed to generate blueprint: {str(e)}",
            session_id=session_id,
            template=template,
            details={"error": str(e)},
        )


@mcp.tool()
async def get_dashboard_url(
    session_id: str,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> dict[str, Any]:
    """
    Get the URL to view an interactive dashboard.
    
    After generating a blueprint, use this tool to get the URL where
    the dashboard can be viewed in a web browser. The dashboard is
    rendered as an interactive Plotly Dash application.
    
    Args:
        session_id: Session ID for which to get the dashboard URL.
        host: Server host (default: localhost).
        port: Server port (default: 8050).
    
    Returns:
        Dictionary containing:
        - url: Full URL to the dashboard
        - session_id: The session ID
        - has_blueprint: Whether a blueprint exists for this session
        - message: Instructions for viewing
    
    Example:
        ```python
        result = await get_dashboard_url(session_id="sales_2024")
        # Returns: {"url": "http://localhost:8050/dashboard/sales_2024", ...}
        ```
    
    Note:
        The web server must be running separately for the dashboard
        to be accessible. Start it with:
        `uvicorn src.app:app --host 0.0.0.0 --port 8050`
    """
    logger.info(f"Getting dashboard URL: session={session_id}")
    
    url = f"http://{host}:{port}/dashboard/{session_id}"
    has_blueprint = session_id in blueprint_store
    
    if not has_blueprint:
        # Check if data exists for this session
        if not db_manager.session_exists(session_id):
            return {
                "url": url,
                "session_id": session_id,
                "has_blueprint": False,
                "has_data": False,
                "message": (
                    f"No data found for session '{session_id}'. "
                    "Use ingest_data to add data first."
                ),
            }
        
        return {
            "url": url,
            "session_id": session_id,
            "has_blueprint": False,
            "has_data": True,
            "message": (
                f"Data exists but no blueprint generated for session '{session_id}'. "
                "Use generate_dashboard_blueprint to create a dashboard configuration."
            ),
        }
    
    return {
        "url": url,
        "session_id": session_id,
        "has_blueprint": True,
        "has_data": True,
        "message": (
            f"Dashboard ready at {url}. "
            "Make sure the web server is running with: "
            "uvicorn src.app:app --host 0.0.0.0 --port 8050"
        ),
    }


@mcp.tool()
async def list_sessions() -> dict[str, Any]:
    """
    List all available data sessions.
    
    Returns information about all sessions that have data ingested,
    including table counts and row statistics.
    
    Returns:
        Dictionary containing:
        - sessions: List of session information
        - total_sessions: Number of active sessions
    
    Example:
        ```python
        result = await list_sessions()
        # Returns: {"sessions": [{"session_id": "sales_2024", ...}], ...}
        ```
    """
    logger.info("Listing all sessions")
    
    sessions = []
    
    # Get sessions from DuckDB
    for session_id in db_manager._sessions:
        try:
            summary = db_manager.get_data_summary(session_id)
            has_blueprint = session_id in blueprint_store
            
            sessions.append({
                "session_id": session_id,
                "table_count": summary.get("table_count", 0),
                "total_rows": summary.get("total_rows", 0),
                "has_blueprint": has_blueprint,
                "tables": [t["table_name"] for t in summary.get("tables", [])],
            })
        except Exception as e:
            logger.warning(f"Error getting summary for session {session_id}: {e}")
    
    return {
        "sessions": sessions,
        "total_sessions": len(sessions),
    }


@mcp.tool()
async def list_available_templates() -> dict[str, Any]:
    """
    List all available dashboard templates.
    
    Returns information about the templates that can be used
    with generate_dashboard_blueprint.
    
    Returns:
        Dictionary containing:
        - templates: List of template information with name and description
        - count: Number of available templates
    
    Example:
        ```python
        result = await list_available_templates()
        # Returns: {"templates": [{"name": "executive_summary", ...}], ...}
        ```
    """
    logger.info("Listing available templates")
    
    templates = list_templates()
    
    return {
        "templates": templates,
        "count": len(templates),
    }


# ============================================================================
# MCP Prompt — Dashboard Creation Instructions
# ============================================================================


@mcp.prompt()
async def dashboard_creation_instructions(session_id: str) -> str:
    """
    Get structured instructions for creating a dynamic dashboard.

    This prompt returns detailed instructions that tell the AI agent
    exactly how to compose a dashboard configuration based on the
    ingested data. The agent should use these instructions to build
    a components list and then call the create_dashboard tool.

    Args:
        session_id: Session ID containing the ingested data to analyze.
    """
    # Verify session exists and get data summary
    if not db_manager.session_exists(session_id):
        raise SessionNotFoundError(session_id)

    data_summary = db_manager.get_data_summary(session_id)

    # Build a human-readable description of available data
    data_description_parts = []
    for table_info in data_summary.get("tables", []):
        table_name = table_info["table_name"]
        row_count = table_info.get("row_count", 0)
        columns = table_info.get("columns", [])

        col_descriptions = []
        for col in columns:
            col_type = col.get("type", "UNKNOWN")
            col_descriptions.append(f"  - `{col['name']}` (type: {col_type})")

        data_description_parts.append(
            f"### Table: `{table_name}` ({row_count} rows)\n"
            + "\n".join(col_descriptions)
        )

    data_description = "\n\n".join(data_description_parts)

    return f"""You are creating a dashboard using the ReportMCP system.
The user has ingested data into session `{session_id}`. Below is the schema of the available data.

## Available Data

{data_description}

## Your Task

Based on the user's request and the data above, compose a **complete dashboard configuration**.
You must call the `create_dashboard` tool with the following arguments:
- `session_id`: "{session_id}"
- `title`: A descriptive dashboard title (in Italian)
- `components`: A JSON array of component objects (described below)

## Component Types

Each component in the `components` array is a JSON object with a `type` field and additional fields depending on the type.

### Text Components

#### `h1` / `h2` / `h3` — Headings
```json
{{"type": "h1", "text": "Main Title"}}
{{"type": "h2", "text": "Section Title"}}
```

#### `p` — Paragraph text
```json
{{"type": "p", "text": "Some descriptive text or analysis summary."}}
```

#### `alert` — Highlighted alert box
```json
{{"type": "alert", "text": "Important insight or note.", "color": "info"}}
```
Colors: `"primary"`, `"secondary"`, `"success"`, `"warning"`, `"danger"`, `"info"`

### KPI Cards

#### `kpi_card` — Key Performance Indicator
```json
{{
  "type": "kpi_card",
  "title": "Total Revenue",
  "metric": "revenue",
  "aggregation": "sum",
  "table": "{data_summary.get('tables', [{}])[0].get('table_name', 'table')}",
  "icon": "fa-euro-sign",
  "color": "success",
  "description": "Total revenue across all records"
}}
```
- `metric` (required): column name from the data to aggregate
- `aggregation`: one of `"sum"`, `"avg"`, `"count"`, `"min"`, `"max"` (default: `"sum"`)
- `table`: table name to query (required)
- `icon`: Font Awesome icon class (e.g., `"fa-euro-sign"`, `"fa-chart-bar"`, `"fa-users"`, `"fa-hashtag"`, `"fa-percent"`, `"fa-arrow-trend-up"`)
- `color`: Bootstrap color (`"primary"`, `"success"`, `"info"`, `"warning"`, `"danger"`, `"secondary"`)

### Charts

#### `line_chart` — Line/Trend chart
```json
{{
  "type": "line_chart",
  "title": "Revenue Over Time",
  "x_axis": "date_column",
  "y_axis": "revenue",
  "table": "table_name",
  "aggregation": "sum",
  "height": 400
}}
```

#### `bar_chart` — Bar chart
```json
{{
  "type": "bar_chart",
  "title": "Revenue by Region",
  "x_axis": "region",
  "y_axis": "revenue",
  "table": "table_name",
  "aggregation": "sum",
  "height": 400
}}
```

#### `pie_chart` — Pie/Donut chart
```json
{{
  "type": "pie_chart",
  "title": "Distribution by Category",
  "x_axis": "category_column",
  "y_axis": "count",
  "table": "table_name",
  "aggregation": "count",
  "height": 350
}}
```

For all charts:
- `x_axis` (required): column for X axis / categories
- `y_axis` (required): column for Y axis / values (use `"count"` for counting)
- `table` (required): table name to query
- `aggregation`: `"sum"`, `"avg"`, `"count"`, `"min"`, `"max"` (default: `"sum"`)

### Tables

#### `table` — Data table with pagination
```json
{{
  "type": "table",
  "table": "table_name",
  "page_size": 10,
  "columns": ["col1", "col2", "col3"]
}}
```
- `table` (required): table name to query
- `page_size`: rows per page (default: 10)
- `columns`: list of columns to show (empty = all columns)

## Layout Rules

- Components are rendered **top to bottom** in the order you list them.
- The system automatically wraps components in responsive rows and columns.
- Group related KPI cards together — they will be placed side by side automatically (up to 4 per row).
- Charts are placed in cards with shadows automatically.

## Instructions

1. Start with an `h1` heading as the dashboard title.
2. Optionally add a `p` paragraph with a brief description or date.
3. Add 3-4 `kpi_card` components for the most important metrics.
4. Add 1-2 charts that best represent the data trends or distributions.
5. Optionally add a `table` component at the bottom for detailed data exploration.
6. Write ALL user-facing text (titles, descriptions, labels) in **Italian**.
7. Choose chart types that make sense for the data: use `line_chart` for time series, `bar_chart` for categorical comparisons, `pie_chart` for distributions.
8. Use meaningful titles and descriptions that explain what each component shows.

## Example

```json
[
  {{"type": "h1", "text": "Dashboard Vendite Q4 2024"}},
  {{"type": "p", "text": "Panoramica delle performance commerciali del quarto trimestre."}},
  {{"type": "kpi_card", "title": "Fatturato Totale", "metric": "revenue", "aggregation": "sum", "table": "sales", "icon": "fa-euro-sign", "color": "success"}},
  {{"type": "kpi_card", "title": "Unità Vendute", "metric": "units", "aggregation": "sum", "table": "sales", "icon": "fa-hashtag", "color": "info"}},
  {{"type": "kpi_card", "title": "Fatturato Medio", "metric": "revenue", "aggregation": "avg", "table": "sales", "icon": "fa-chart-bar", "color": "warning"}},
  {{"type": "bar_chart", "title": "Fatturato per Regione", "x_axis": "region", "y_axis": "revenue", "table": "sales", "aggregation": "sum", "height": 400}},
  {{"type": "table", "table": "sales", "page_size": 10}}
]
```

Now compose the components list based on the user's request and call `create_dashboard`."""


# ============================================================================
# MCP Tool — Create Dashboard from Agent-Structured Components
# ============================================================================


@mcp.tool()
async def create_dashboard(
    session_id: str,
    title: str,
    components: list[dict[str, Any]],
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> dict[str, Any]:
    """
    Create a dashboard from a structured list of components.
    """
    return await create_dashboard_internal(session_id, title, components, host, port)


async def create_dashboard_internal(
    session_id: str,
    title: str,
    components: list[dict[str, Any]],
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> dict[str, Any]:
    """
    Internal logic to create a dashboard from a structured list of components.
    This can be called directly by the FastAPI app.
    """
    logger.info(
        f"Creating dashboard: session={session_id}, title={title}, "
        f"components={len(components)}"
    )

    try:
        # Verify session exists
        if not db_manager.session_exists(session_id):
            raise SessionNotFoundError(session_id)

        # Build ComponentConfig tree from the flat component list
        blueprint_components: list[ComponentConfig] = []
        kpi_buffer: list[ComponentConfig] = []

        def _flush_kpi_buffer() -> None:
            """Wrap buffered KPI cards into a row."""
            nonlocal kpi_buffer
            if not kpi_buffer:
                return
            col_width = 12 // len(kpi_buffer) if kpi_buffer else 12
            children = [
                ComponentConfig(
                    type=ComponentType.COLUMN,
                    props={"width": col_width},
                    children=[kpi],
                )
                for kpi in kpi_buffer
            ]
            blueprint_components.append(
                ComponentConfig(
                    type=ComponentType.ROW,
                    class_name="mb-4 g-3",
                    children=children,
                )
            )
            kpi_buffer = []

        for i, comp in enumerate(components):
            comp_type_str = comp.get("type", "")
            comp_id = f"dynamic-{comp_type_str}-{i}"

            # --- Text components ---
            if comp_type_str in ("h1", "h2", "h3", "p"):
                _flush_kpi_buffer()
                type_map = {
                    "h1": ComponentType.H1,
                    "h2": ComponentType.H2,
                    "h3": ComponentType.H3,
                    "p": ComponentType.P,
                }
                blueprint_components.append(
                    ComponentConfig(
                        type=ComponentType.ROW,
                        class_name="mb-3" if comp_type_str == "p" else "mb-4",
                        children=[
                            ComponentConfig(
                                type=ComponentType.COLUMN,
                                props={"width": 12},
                                children=[
                                    ComponentConfig(
                                        type=type_map[comp_type_str],
                                        props={"text": comp.get("text", "")},
                                        class_name=comp.get("class_name", (
                                            "display-5 fw-bold text-primary"
                                            if comp_type_str == "h1" else None
                                        )),
                                    ),
                                ],
                            ),
                        ],
                    )
                )

            # --- Alert ---
            elif comp_type_str == "alert":
                _flush_kpi_buffer()
                blueprint_components.append(
                    ComponentConfig(
                        type=ComponentType.ROW,
                        class_name="mb-4",
                        children=[
                            ComponentConfig(
                                type=ComponentType.COLUMN,
                                props={"width": 12},
                                children=[
                                    ComponentConfig(
                                        type=ComponentType.ALERT,
                                        props={
                                            "text": comp.get("text", ""),
                                            "color": comp.get("color", "info"),
                                        },
                                    ),
                                ],
                            ),
                        ],
                    )
                )

            # --- KPI Card ---
            elif comp_type_str == "kpi_card":
                table_name = comp.get("table", "")
                metric = comp.get("metric", "")
                aggregation = comp.get("aggregation", "sum")

                kpi_config = ComponentConfig(
                    type=ComponentType.KPI_CARD,
                    props={
                        "title": comp.get("title", "KPI"),
                        "value": "—",
                        "icon": comp.get("icon", "fa-chart-bar"),
                        "color": comp.get("color", "primary"),
                        "description": comp.get("description", ""),
                        "metric": metric,
                        "aggregation": aggregation,
                    },
                    data_query=f"SELECT * FROM {table_name}" if table_name else None,
                    id=comp_id,
                )
                kpi_buffer.append(kpi_config)

                # Auto-flush when we hit 4 KPIs in a row
                if len(kpi_buffer) >= 4:
                    _flush_kpi_buffer()

            # --- Charts ---
            elif comp_type_str in ("line_chart", "bar_chart", "pie_chart"):
                _flush_kpi_buffer()
                type_map = {
                    "line_chart": ComponentType.LINE_CHART,
                    "bar_chart": ComponentType.BAR_CHART,
                    "pie_chart": ComponentType.PIE_CHART,
                }
                table_name = comp.get("table", "")
                x_axis = comp.get("x_axis", "")
                y_axis = comp.get("y_axis", "")
                aggregation = comp.get("aggregation", "sum")

                # Build SQL query
                if y_axis == "count" or aggregation == "count":
                    data_query = (
                        f"SELECT {x_axis}, COUNT(*) as count "
                        f"FROM {table_name} GROUP BY {x_axis} "
                        f"ORDER BY count DESC LIMIT 20"
                    )
                    y_axis_resolved = "count"
                else:
                    agg_func = aggregation.upper()
                    data_query = (
                        f"SELECT {x_axis}, {agg_func}({y_axis}) as {y_axis} "
                        f"FROM {table_name} GROUP BY {x_axis} "
                        f"ORDER BY {x_axis}"
                    )
                    y_axis_resolved = y_axis

                chart_config = ComponentConfig(
                    type=type_map[comp_type_str],
                    props={
                        "title": comp.get("title", ""),
                        "x_axis": x_axis,
                        "y_axis": y_axis_resolved,
                        "height": comp.get("height", 400),
                        "show_legend": comp.get("show_legend", True),
                    },
                    data_query=data_query,
                    id=comp_id,
                )

                blueprint_components.append(
                    ComponentConfig(
                        type=ComponentType.ROW,
                        class_name="mb-4",
                        children=[
                            ComponentConfig(
                                type=ComponentType.COLUMN,
                                props={"width": 12},
                                children=[
                                    ComponentConfig(
                                        type=ComponentType.CARD,
                                        class_name="shadow-sm",
                                        children=[chart_config],
                                    ),
                                ],
                            ),
                        ],
                    )
                )

            # --- Table ---
            elif comp_type_str == "table":
                _flush_kpi_buffer()
                table_name = comp.get("table", "")
                columns_filter = comp.get("columns", [])

                if columns_filter:
                    cols_sql = ", ".join(columns_filter)
                    data_query = f"SELECT {cols_sql} FROM {table_name}"
                else:
                    data_query = f"SELECT * FROM {table_name}"

                table_config = ComponentConfig(
                    type=ComponentType.TABLE,
                    props={
                        "page_size": comp.get("page_size", 10),
                        "sortable": True,
                        "filterable": True,
                    },
                    data_query=data_query,
                    id=comp_id,
                )

                blueprint_components.append(
                    ComponentConfig(
                        type=ComponentType.ROW,
                        class_name="mb-4",
                        children=[
                            ComponentConfig(
                                type=ComponentType.COLUMN,
                                props={"width": 12},
                                children=[
                                    ComponentConfig(
                                        type=ComponentType.CARD,
                                        class_name="shadow-sm",
                                        children=[
                                            ComponentConfig(
                                                type=ComponentType.H3,
                                                props={"text": "📋 Dati di Dettaglio"},
                                                class_name="card-title mb-3",
                                            ),
                                            table_config,
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    )
                )

            else:
                logger.warning(f"Unknown component type: {comp_type_str}")

        # Flush any remaining KPIs
        _flush_kpi_buffer()

        # Create the blueprint
        blueprint = DashboardBlueprint(
            session_id=session_id,
            title=title,
            template="dynamic",
            components=blueprint_components,
            metadata={
                "source": "create_dashboard",
                "input_component_count": len(components),
            },
        )

        # Store it
        blueprint_store[session_id] = blueprint

        url = f"http://{host}:{port}/dashboard/{session_id}"

        logger.info(
            f"Dashboard created: {blueprint.count_components()} components, url={url}"
        )

        return {
            "success": True,
            "url": url,
            "session_id": session_id,
            "component_count": blueprint.count_components(),
            "message": (
                f"Dashboard '{title}' created successfully with "
                f"{blueprint.count_components()} components. "
                f"View it at {url}. "
                "Make sure the web server is running with: "
                "uvicorn src.app:app --host 0.0.0.0 --port 8050"
            ),
        }

    except SessionNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Dashboard creation failed: {e}", exc_info=True)
        raise BlueprintGenerationError(
            message=f"Failed to create dashboard: {str(e)}",
            session_id=session_id,
            template="dynamic",
            details={"error": str(e)},
        )


# ============================================================================
# Server Entry Point
# ============================================================================


def get_mcp_server() -> FastMCP:
    """
    Get the MCP server instance.
    
    This function is useful for integration with other frameworks
    or when running the server programmatically.
    
    Returns:
        The configured FastMCP server instance.
    """
    return mcp


def get_db_manager() -> DuckDBManager:
    """
    Get the database manager instance.
    
    Returns:
        The DuckDB manager instance.
    """
    return db_manager


def get_blueprint_store() -> dict[str, DashboardBlueprint]:
    """
    Get the blueprint store.
    
    Returns:
        Dictionary mapping session IDs to blueprints.
    """
    return blueprint_store


def main() -> None:
    """Run the MCP server."""
    import sys
    import os
    
    # Check for SSE mode via args or environment
    use_sse = "--sse" in sys.argv or os.environ.get("MCP_MODE") == "sse"
    port = int(os.environ.get("MCP_PORT", 8051))
    host = os.environ.get("MCP_HOST", "0.0.0.0")

    if use_sse:
        logger.info(f"Starting ReportMCP server in SSE mode on {host}:{port}...")
        # FastMCP.run() with transport="sse" handles the server setup
        mcp.run(transport="sse", host=host, port=port)
    else:
        logger.info("Starting ReportMCP server in STDIO mode...")
        mcp.run()


if __name__ == "__main__":
    main()
