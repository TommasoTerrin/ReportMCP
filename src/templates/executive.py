"""
Executive Summary template.

This template generates a high-level dashboard with:
- Header with title
- Row of 4 KPI cards
- Main trend chart
- Summary table
"""

from typing import Any, Optional

from src.models.blueprint import ComponentConfig, ComponentType, DashboardBlueprint
from src.templates.base import BaseTemplate, register_template


@register_template
class ExecutiveSummaryTemplate(BaseTemplate):
    """
    Executive Summary template for quick business overview.
    
    Layout structure:
    ┌─────────────────────────────────────────┐
    │  Title                                    │
    │  Subtitle (date)                        │
    ├─────────┬─────────┬─────────┬──────────┤
    │  KPI 1  │  KPI 2  │  KPI 3  │  KPI 4   │
    ├─────────┴─────────┴─────────┴──────────┤
    │           Main Trend Chart             │
    ├─────────────────────────────────────────┤
    │           Summary Table                │
    └─────────────────────────────────────────┘
    """
    
    @classmethod
    def get_name(cls) -> str:
        """Return template identifier."""
        return "executive_summary"
    
    @classmethod
    def get_description(cls) -> str:
        """Return template description."""
        return "High-level business overview with KPIs, trend chart, and summary table"
    
    def generate(
        self,
        session_id: str,
        title: str,
        data_summary: dict[str, Any],
        objective: Optional[str] = None,
    ) -> DashboardBlueprint:
        """
        Generate executive summary dashboard.
        
        Args:
            session_id: Data session identifier.
            title: Dashboard title.
            data_summary: Summary of available data.
            objective: Optional business objective.
            
        Returns:
            Complete dashboard blueprint.
        """
        components: list[ComponentConfig] = []
        
        # 1. Header section
        components.extend(self._create_header(title))
        
        # 1b. Filters section
        filters = self._generate_filters(data_summary)
        if filters:
            components.append(
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
                                    class_name="shadow-sm bg-light",
                                    children=[
                                        ComponentConfig(
                                            type=ComponentType.ROW,
                                            children=filters,
                                        )
                                    ],
                                ),
                            ],
                        ),
                    ],
                )
            )
        
        # 2. KPI row
        kpis = self._generate_kpis(data_summary, objective)
        if kpis:
            components.append(self._create_kpi_row(kpis))
        
        # 3. Main chart section
        chart_config = self._generate_main_chart(data_summary, objective)
        if chart_config:
            components.append(
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
        
        # 4. Summary table
        table_config = self._generate_summary_table(data_summary)
        if table_config:
            components.append(
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
                                            props={"text": "📋 Data Summary"},
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
        
        return DashboardBlueprint(
            session_id=session_id,
            title=title,
            template="executive_summary",
            components=components,
            metadata={
                "objective": objective,
                "total_tables": data_summary.get("table_count", 0),
                "total_rows": data_summary.get("total_rows", 0),
            },
        )
    
    def _generate_filters(self, data_summary: dict[str, Any]) -> list[ComponentConfig]:
        """Generate filter components based on dimensions."""
        filters = []
        tables = data_summary.get("tables", [])
        if not tables:
            return filters
            
        primary_table = tables[0]
        table_name = primary_table["table_name"]
        columns = primary_table.get("columns", [])
        
        # Add Date Picker if date column exists
        date_cols = [c["name"] for c in columns if c.get("type", "").upper() in ("DATE", "TIMESTAMP")]
        if date_cols:
            filters.append(
                ComponentConfig(
                    type=ComponentType.COLUMN,
                    props={"width": 4},
                    children=[
                        ComponentConfig(type=ComponentType.P, props={"text": "Date Range:"}, class_name="small fw-bold mb-1"),
                        ComponentConfig(
                            type=ComponentType.DATE_PICKER,
                            props={"column": date_cols[0], "table": table_name},
                            id="filter-date",
                        )
                    ]
                )
            )
            
        # Add Dropdown for categorical dimensions (limit to top 2)
        string_cols = [c for c in columns if c.get("type", "").upper() in ("VARCHAR", "STRING", "TEXT")]
        for col in string_cols[:2]:
            col_name = col["name"]
            filters.append(
                ComponentConfig(
                    type=ComponentType.COLUMN,
                    props={"width": 4},
                    children=[
                        ComponentConfig(type=ComponentType.P, props={"text": f"Filter by {col_name.title()}:"}, class_name="small fw-bold mb-1"),
                        ComponentConfig(
                            type=ComponentType.DROPDOWN,
                            props={
                                "column": col_name,
                                "table": table_name,
                                "placeholder": f"All {col_name.title()}...",
                                "options": [], # Options will be populated or handled by a callback
                            },
                        )
                    ]
                )
            )
            
        return filters

    def _generate_kpis(
        self,
        data_summary: dict[str, Any],
        objective: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        Generate KPI configurations based on data.
        
        Analyzes the data structure to identify key metrics.
        """
        kpis = []
        
        tables = data_summary.get("tables", [])
        if not tables:
            return kpis
        
        # Primary table (first one)
        primary_table = tables[0]
        table_name = primary_table["table_name"]
        
        # Add total records KPI
        kpis.append({
            "title": "Total Records",
            "value": f"{primary_table['row_count']:,}",
            "icon": "fa-database",
            "color": "primary",
            "description": f"Records in {table_name}",
        })
        
        # Analyze columns for numeric metrics
        numeric_columns = [
            col for col in primary_table.get("columns", [])
            if col.get("type", "").upper() in ("DOUBLE", "BIGINT", "INTEGER", "FLOAT", "DECIMAL")
        ]
        
        # Add KPIs for first 3 numeric columns
        for i, col in enumerate(numeric_columns[:3]):
            col_name = col["name"]
            display_name = col_name.replace("_", " ").title()
            
            # Determine icon based on column name patterns
            icon = "fa-chart-bar"
            color = ["success", "info", "warning"][i % 3]
            
            if any(term in col_name.lower() for term in ["revenue", "sales", "amount", "price"]):
                icon = "fa-euro-sign"
            elif any(term in col_name.lower() for term in ["count", "quantity", "num"]):
                icon = "fa-hashtag"
            elif any(term in col_name.lower() for term in ["percent", "rate", "ratio"]):
                icon = "fa-percent"
            
            kpis.append({
                "title": display_name,
                "value": "—",  # Placeholder, filled at render time
                "icon": icon,
                "color": color,
                "description": f"Sum of {display_name}",
                "metric": col_name,
                "aggregation": "sum",
                "data_query": f"SELECT * FROM {table_name}",
            })
        
        return kpis
    
    def _generate_main_chart(
        self,
        data_summary: dict[str, Any],
        objective: Optional[str] = None,
    ) -> Optional[ComponentConfig]:
        """
        Generate main chart configuration.
        
        Attempts to identify a time-series or categorical trend.
        """
        tables = data_summary.get("tables", [])
        if not tables:
            return None
        
        primary_table = tables[0]
        table_name = primary_table["table_name"]
        columns = primary_table.get("columns", [])
        
        # Find date/time column for X axis
        date_columns = [
            col["name"] for col in columns
            if col.get("type", "").upper() in ("DATE", "TIMESTAMP", "DATETIME")
        ]
        
        # Find numeric column for Y axis
        numeric_columns = [
            col["name"] for col in columns
            if col.get("type", "").upper() in ("DOUBLE", "BIGINT", "INTEGER", "FLOAT", "DECIMAL")
        ]
        
        if date_columns and numeric_columns:
            # Time series chart
            x_col = date_columns[0]
            y_col = numeric_columns[0]
            
            return ComponentConfig(
                type=ComponentType.LINE_CHART,
                props={
                    "title": f"📈 {y_col.replace('_', ' ').title()} Over Time",
                    "x_axis": x_col,
                    "y_axis": y_col,
                    "height": 400,
                    "show_legend": True,
                },
                data_query=f"SELECT * FROM {table_name}",
                id="main-chart",
            )
        elif len(numeric_columns) >= 2:
            # Bar chart with first column as category
            string_columns = [
                col["name"] for col in columns
                if col.get("type", "").upper() in ("VARCHAR", "STRING", "TEXT")
            ]
            
            if string_columns:
                x_col = string_columns[0]
                y_col = numeric_columns[0]
                
                return ComponentConfig(
                    type=ComponentType.BAR_CHART,
                    props={
                        "title": f"📊 {y_col.replace('_', ' ').title()} by {x_col.replace('_', ' ').title()}",
                        "x_axis": x_col,
                        "y_axis": y_col,
                        "height": 400,
                    },
                    data_query=f"SELECT * FROM {table_name}",
                    id="main-chart",
                )
        
        return None
    
    def _generate_summary_table(
        self,
        data_summary: dict[str, Any],
    ) -> Optional[ComponentConfig]:
        """
        Generate summary table configuration.
        """
        tables = data_summary.get("tables", [])
        if not tables:
            return None
        
        primary_table = tables[0]
        table_name = primary_table["table_name"]
        
        return ComponentConfig(
            type=ComponentType.TABLE,
            props={
                "page_size": 10,
                "sortable": True,
                "filterable": True,
            },
            data_query=f"SELECT * FROM {table_name} LIMIT 100",
            id="summary-table",
        )


def generate_executive_layout(
    session_id: str,
    title: str,
    data_summary: dict[str, Any],
    objective: Optional[str] = None,
) -> DashboardBlueprint:
    """
    Convenience function to generate executive summary layout.
    
    Args:
        session_id: Data session identifier.
        title: Dashboard title.
        data_summary: Summary of available data.
        objective: Optional business objective.
        
    Returns:
        Complete dashboard blueprint.
    """
    template = ExecutiveSummaryTemplate()
    return template.generate(session_id, title, data_summary, objective)
