"""
Pydantic models for dashboard blueprint configuration.

This module defines the component tree structure used to describe
dashboard layouts. The blueprint is a JSON-serializable representation
that gets converted to Dash components at render time.
"""

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class ComponentType(str, Enum):
    """
    Available dashboard component types.
    
    Layout components:
        - ROW: Horizontal container (Bootstrap row)
        - COLUMN: Vertical container with configurable width
        - CONTAINER: Top-level fluid container
        - CARD: Bordered card container
    
    Text components:
        - H1, H2, H3: Heading elements
        - P: Paragraph text
        - ALERT: Bootstrap alert component
    
    Data components:
        - KPI_CARD: Key Performance Indicator card
        - LINE_CHART: Time series line chart
        - BAR_CHART: Categorical bar chart
        - PIE_CHART: Pie/donut chart
        - TABLE: Data table with sorting
        - STAT_CARD: Statistics summary card
    
    Interactive components:
        - DATE_PICKER: Date range selector
        - DROPDOWN: Filter dropdown
    """
    # Layout
    ROW = "row"
    COLUMN = "column"
    CONTAINER = "container"
    CARD = "card"
    
    # Text
    H1 = "h1"
    H2 = "h2"
    H3 = "h3"
    P = "p"
    ALERT = "alert"
    
    # Data visualization
    KPI_CARD = "kpi_card"
    LINE_CHART = "line_chart"
    BAR_CHART = "bar_chart"
    PIE_CHART = "pie_chart"
    TABLE = "table"
    STAT_CARD = "stat_card"
    
    # Interactive
    DATE_PICKER = "date_picker"
    DROPDOWN = "dropdown"


class KPIConfig(BaseModel):
    """
    Configuration for KPI card component.
    
    Attributes:
        title: Display title for the KPI.
        value: Main value to display.
        delta: Optional change indicator (e.g., "+15%").
        delta_type: Whether delta is positive, negative, or neutral.
        icon: Optional Font Awesome icon class.
        color: Bootstrap color variant.
        description: Optional tooltip description.
    """
    title: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="KPI display title",
    )
    value: str = Field(
        ...,
        description="Main value to display (pre-formatted)",
    )
    delta: Optional[str] = Field(
        default=None,
        description="Change indicator (e.g., '+15%')",
    )
    delta_type: Literal["positive", "negative", "neutral"] = Field(
        default="neutral",
        description="Type of change for color coding",
    )
    icon: Optional[str] = Field(
        default=None,
        description="Font Awesome icon class (e.g., 'fa-euro-sign')",
    )
    color: Literal["primary", "secondary", "success", "warning", "danger", "info"] = Field(
        default="primary",
        description="Bootstrap color variant",
    )
    description: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Tooltip description",
    )


class ChartConfig(BaseModel):
    """
    Configuration for chart components.
    
    Applies to LINE_CHART, BAR_CHART, and PIE_CHART types.
    
    Attributes:
        title: Chart title.
        x_axis: Column name for X axis (or category for pie).
        y_axis: Column name for Y axis (or value for pie).
        color_by: Optional column for color grouping.
        height: Chart height in pixels.
        show_legend: Whether to show legend.
        stacked: For bar charts, whether to stack bars.
    """
    title: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Chart title",
    )
    x_axis: str = Field(
        ...,
        description="Column name for X axis",
    )
    y_axis: str = Field(
        ...,
        description="Column name for Y axis",
    )
    color_by: Optional[str] = Field(
        default=None,
        description="Column name for color grouping",
    )
    height: int = Field(
        default=400,
        ge=100,
        le=1000,
        description="Chart height in pixels",
    )
    show_legend: bool = Field(
        default=True,
        description="Whether to display legend",
    )
    stacked: bool = Field(
        default=False,
        description="Stack bars (bar chart only)",
    )
    aggregation: Literal["sum", "avg", "count", "min", "max"] = Field(
        default="sum",
        description="Aggregation function for y-axis values",
    )


class TableConfig(BaseModel):
    """
    Configuration for data table component.
    
    Attributes:
        columns: List of column names to display.
        page_size: Number of rows per page.
        sortable: Whether columns are sortable.
        filterable: Whether to show column filters.
    """
    columns: list[str] = Field(
        default_factory=list,
        description="Columns to display (empty = all)",
    )
    page_size: int = Field(
        default=10,
        ge=5,
        le=100,
        description="Rows per page",
    )
    sortable: bool = Field(
        default=True,
        description="Enable column sorting",
    )
    filterable: bool = Field(
        default=False,
        description="Enable column filtering",
    )


class ComponentConfig(BaseModel):
    """
    Configuration for a single dashboard component.
    
    This is a recursive structure that can contain child components
    for layout elements like ROW and COLUMN.
    
    Attributes:
        type: The component type to render.
        props: Component-specific properties.
        children: Nested child components (for layout types).
        data_query: Optional SQL query to fetch data from DuckDB.
        id: Optional unique identifier for callbacks.
        class_name: Optional CSS classes to apply.
    """
    type: ComponentType = Field(
        ...,
        description="Component type to render",
    )
    props: dict[str, Any] = Field(
        default_factory=dict,
        description="Component-specific properties",
    )
    children: list["ComponentConfig"] = Field(
        default_factory=list,
        description="Nested child components",
    )
    data_query: Optional[str] = Field(
        default=None,
        description="SQL query for data-driven components",
    )
    id: Optional[str] = Field(
        default=None,
        pattern=r"^[a-zA-Z][a-zA-Z0-9_-]*$",
        description="Unique component identifier",
    )
    class_name: Optional[str] = Field(
        default=None,
        description="CSS classes to apply",
    )
    
    @model_validator(mode="after")
    def validate_children_for_layout(self) -> "ComponentConfig":
        """Validate that only layout components have children."""
        layout_types = {ComponentType.ROW, ComponentType.COLUMN, ComponentType.CONTAINER, ComponentType.CARD}
        
        if self.children and self.type not in layout_types:
            raise ValueError(
                f"Component type '{self.type}' cannot have children. "
                f"Only layout components ({', '.join(t.value for t in layout_types)}) support children."
            )
        
        return self
    
    @model_validator(mode="after")
    def validate_data_query_for_data_components(self) -> "ComponentConfig":
        """Validate that data components have required queries."""
        data_types = {
            ComponentType.LINE_CHART,
            ComponentType.BAR_CHART,
            ComponentType.PIE_CHART,
            ComponentType.TABLE,
        }
        
        # Note: We don't require data_query because data might come through props
        return self


class DashboardBlueprint(BaseModel):
    """
    Complete dashboard blueprint configuration.
    
    This is the top-level model that describes an entire dashboard,
    including its title, template, and component tree.
    
    Attributes:
        session_id: Reference to the data session.
        title: Dashboard display title.
        template: Template used to generate the blueprint.
        components: List of root-level components.
        metadata: Additional metadata for the dashboard.
        created_at: ISO timestamp of blueprint creation.
    """
    session_id: str = Field(
        ...,
        description="Reference to the data session",
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Dashboard display title",
    )
    template: Literal["executive_summary", "deep_dive", "dynamic"] = Field(
        default="executive_summary",
        description="Template used for generation",
    )
    components: list[ComponentConfig] = Field(
        default_factory=list,
        description="Root-level components",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional dashboard metadata",
    )
    created_at: Optional[str] = Field(
        default=None,
        description="ISO timestamp of creation",
    )
    
    @model_validator(mode="after")
    def add_created_at(self) -> "DashboardBlueprint":
        """Add creation timestamp if not provided."""
        if self.created_at is None:
            from datetime import datetime, timezone
            self.created_at = datetime.now(timezone.utc).isoformat()
        return self
    
    def get_component_by_id(self, component_id: str) -> Optional[ComponentConfig]:
        """
        Find a component by its ID in the component tree.
        """
        def search(components: list[ComponentConfig]) -> Optional[ComponentConfig]:
            for comp in components:
                if comp.id == component_id:
                    return comp
                if comp.children:
                    result = search(comp.children)
                    if result:
                        return result
            return None
        
        return search(self.components)
    
    def count_components(self) -> int:
        """Count total number of components in the blueprint."""
        def count(components: list[ComponentConfig]) -> int:
            total = len(components)
            for comp in components:
                total += count(comp.children)
            return total
        
        return count(self.components)
