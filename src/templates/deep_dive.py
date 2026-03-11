"""
Deep Dive template.

This template generates a detailed analytics dashboard with:
- Header with title
- Row of 6 KPI cards (2 rows of 3)
- Multiple chart sections (line, bar, pie)
- Detailed data table with filtering
"""

from typing import Any, Optional

from src.models.blueprint import ComponentConfig, ComponentType, DashboardBlueprint
from src.templates.base import BaseTemplate, register_template


@register_template
class DeepDiveTemplate(BaseTemplate):
    """
    Deep Dive template for detailed data analysis.
    
    Layout structure:
    ┌─────────────────────────────────────────┐
    │  Title                                    │
    │  Subtitle (date)                        │
    ├─────────────┬─────────────┬─────────────┤
    │   KPI 1     │   KPI 2     │   KPI 3     │
    ├─────────────┼─────────────┼─────────────┤
    │   KPI 4     │   KPI 5     │   KPI 6     │
    ├─────────────────────┬───────────────────┤
    │   Line Chart        │   Bar Chart       │
    ├─────────────────────┼───────────────────┤
    │   Pie Chart         │   Stats Card      │
    ├─────────────────────┴───────────────────┤
    │        Detailed Data Table              │
    └─────────────────────────────────────────┘
    """
    
    @classmethod
    def get_name(cls) -> str:
        """Return template identifier."""
        return "deep_dive"
    
    @classmethod
    def get_description(cls) -> str:
        """Return template description."""
        return "Detailed analytics dashboard with multiple charts and comprehensive data exploration"
    
    def generate(
        self,
        session_id: str,
        title: str,
        data_summary: dict[str, Any],
        objective: Optional[str] = None,
    ) -> DashboardBlueprint:
        """
        Generate deep dive dashboard.
        
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
        components.extend(self._create_header(f"🔍 {title}"))
        
        # 2. Objective alert (if provided)
        if objective:
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
                                    type=ComponentType.ALERT,
                                    props={
                                        "text": f"📌 Analysis Objective: {objective}",
                                        "color": "info",
                                    },
                                ),
                            ],
                        ),
                    ],
                )
            )
        
        # 3. Extended KPI section (2 rows of 3)
        kpis = self._generate_extended_kpis(data_summary)
        if kpis:
            # First row of KPIs
            components.append(self._create_kpi_row(kpis[:3], max_kpis=3))
            # Second row of KPIs if available
            if len(kpis) > 3:
                components.append(self._create_kpi_row(kpis[3:6], max_kpis=3))
        
        # 4. Chart section (2x2 grid)
        chart_configs = self._generate_chart_grid(data_summary)
        if chart_configs:
            # First row: Line and Bar charts
            if len(chart_configs) >= 2:
                components.append(
                    ComponentConfig(
                        type=ComponentType.ROW,
                        class_name="mb-4 g-3",
                        children=[
                            ComponentConfig(
                                type=ComponentType.COLUMN,
                                props={"width": 6},
                                children=[
                                    ComponentConfig(
                                        type=ComponentType.CARD,
                                        class_name="shadow-sm h-100",
                                        children=[chart_configs[0]],
                                    ),
                                ],
                            ),
                            ComponentConfig(
                                type=ComponentType.COLUMN,
                                props={"width": 6},
                                children=[
                                    ComponentConfig(
                                        type=ComponentType.CARD,
                                        class_name="shadow-sm h-100",
                                        children=[chart_configs[1]],
                                    ),
                                ],
                            ),
                        ],
                    )
                )
            
            # Second row: Pie chart and Stats
            if len(chart_configs) >= 3:
                components.append(
                    ComponentConfig(
                        type=ComponentType.ROW,
                        class_name="mb-4 g-3",
                        children=[
                            ComponentConfig(
                                type=ComponentType.COLUMN,
                                props={"width": 6},
                                children=[
                                    ComponentConfig(
                                        type=ComponentType.CARD,
                                        class_name="shadow-sm h-100",
                                        children=[chart_configs[2]],
                                    ),
                                ],
                            ),
                            ComponentConfig(
                                type=ComponentType.COLUMN,
                                props={"width": 6},
                                children=[
                                    ComponentConfig(
                                        type=ComponentType.CARD,
                                        class_name="shadow-sm h-100",
                                        children=[
                                            self._generate_stats_card(data_summary),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    )
                )
        
        # 5. Detailed data table
        table_config = self._generate_detailed_table(data_summary)
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
                                            props={"text": "📋 Detailed Data Explorer"},
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
            template="deep_dive",
            components=components,
            metadata={
                "objective": objective,
                "total_tables": data_summary.get("table_count", 0),
                "total_rows": data_summary.get("total_rows", 0),
                "chart_count": len(chart_configs) if chart_configs else 0,
            },
        )
    
    def _generate_extended_kpis(
        self,
        data_summary: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Generate extended KPI configurations (up to 6).
        """
        kpis = []
        
        tables = data_summary.get("tables", [])
        if not tables:
            return kpis
        
        primary_table = tables[0]
        table_name = primary_table["table_name"]
        columns = primary_table.get("columns", [])
        
        # Total records
        kpis.append({
            "title": "Total Records",
            "value": f"{primary_table['row_count']:,}",
            "icon": "fa-database",
            "color": "primary",
        })
        
        # Number of columns
        kpis.append({
            "title": "Data Fields",
            "value": str(len(columns)),
            "icon": "fa-columns",
            "color": "secondary",
        })
        
        # Add KPIs for numeric columns
        numeric_columns = [
            col for col in columns
            if col.get("type", "").upper() in ("DOUBLE", "BIGINT", "INTEGER", "FLOAT", "DECIMAL")
        ]
        
        icons = ["fa-euro-sign", "fa-chart-line", "fa-arrow-trend-up", "fa-calculator"]
        colors = ["success", "info", "warning", "danger"]
        
        for i, col in enumerate(numeric_columns[:4]):
            col_name = col["name"]
            display_name = col_name.replace("_", " ").title()
            
            kpis.append({
                "title": display_name,
                "value": "—",
                "icon": icons[i % len(icons)],
                "color": colors[i % len(colors)],
                "_data_query": f"SELECT SUM({col_name}) as value FROM {table_name}",
            })
        
        return kpis[:6]
    
    def _generate_chart_grid(
        self,
        data_summary: dict[str, Any],
    ) -> list[ComponentConfig]:
        """
        Generate grid of charts for deep dive analysis.
        """
        charts = []
        
        tables = data_summary.get("tables", [])
        if not tables:
            return charts
        
        primary_table = tables[0]
        table_name = primary_table["table_name"]
        columns = primary_table.get("columns", [])
        
        # Categorize columns
        date_cols = [c["name"] for c in columns if c.get("type", "").upper() in ("DATE", "TIMESTAMP")]
        numeric_cols = [c["name"] for c in columns if c.get("type", "").upper() in ("DOUBLE", "BIGINT", "INTEGER", "FLOAT")]
        string_cols = [c["name"] for c in columns if c.get("type", "").upper() in ("VARCHAR", "STRING", "TEXT")]
        
        # 1. Line chart (time series if available)
        if date_cols and numeric_cols:
            x_col = date_cols[0]
            y_col = numeric_cols[0]
            charts.append(
                ComponentConfig(
                    type=ComponentType.LINE_CHART,
                    props={
                        "title": f"📈 {y_col.replace('_', ' ').title()} Trend",
                        "x_axis": x_col,
                        "y_axis": y_col,
                        "height": 350,
                    },
                    data_query=f"SELECT {x_col}, SUM({y_col}) as {y_col} FROM {table_name} GROUP BY {x_col} ORDER BY {x_col}",
                    id="trend-chart",
                )
            )
        
        # 2. Bar chart (categorical breakdown)
        if string_cols and numeric_cols:
            x_col = string_cols[0]
            y_col = numeric_cols[0] if not charts else (numeric_cols[1] if len(numeric_cols) > 1 else numeric_cols[0])
            charts.append(
                ComponentConfig(
                    type=ComponentType.BAR_CHART,
                    props={
                        "title": f"📊 {y_col.replace('_', ' ').title()} by {x_col.replace('_', ' ').title()}",
                        "x_axis": x_col,
                        "y_axis": y_col,
                        "height": 350,
                    },
                    data_query=f"SELECT {x_col}, SUM({y_col}) as {y_col} FROM {table_name} GROUP BY {x_col} ORDER BY {y_col} DESC LIMIT 10",
                    id="bar-chart",
                )
            )
        
        # 3. Pie chart (distribution)
        if string_cols:
            category_col = string_cols[0] if len(string_cols) == 1 else string_cols[1] if len(string_cols) > 1 else string_cols[0]
            charts.append(
                ComponentConfig(
                    type=ComponentType.PIE_CHART,
                    props={
                        "title": f"🥧 Distribution by {category_col.replace('_', ' ').title()}",
                        "x_axis": category_col,
                        "y_axis": "count",
                        "height": 350,
                    },
                    data_query=f"SELECT {category_col}, COUNT(*) as count FROM {table_name} GROUP BY {category_col} ORDER BY count DESC LIMIT 8",
                    id="pie-chart",
                )
            )
        
        return charts
    
    def _generate_stats_card(
        self,
        data_summary: dict[str, Any],
    ) -> ComponentConfig:
        """
        Generate statistics summary card.
        """
        return ComponentConfig(
            type=ComponentType.STAT_CARD,
            props={
                "title": "📊 Data Statistics",
                "stats": [
                    {"label": "Tables", "value": str(data_summary.get("table_count", 0))},
                    {"label": "Total Rows", "value": f"{data_summary.get('total_rows', 0):,}"},
                    {"label": "Template", "value": "Deep Dive"},
                ],
            },
            id="stats-card",
        )
    
    def _generate_detailed_table(
        self,
        data_summary: dict[str, Any],
    ) -> Optional[ComponentConfig]:
        """
        Generate detailed data table with all columns.
        """
        tables = data_summary.get("tables", [])
        if not tables:
            return None
        
        primary_table = tables[0]
        table_name = primary_table["table_name"]
        
        return ComponentConfig(
            type=ComponentType.TABLE,
            props={
                "page_size": 15,
                "sortable": True,
                "filterable": True,
            },
            data_query=f"SELECT * FROM {table_name}",
            id="detailed-table",
        )


def generate_deep_dive_layout(
    session_id: str,
    title: str,
    data_summary: dict[str, Any],
    objective: Optional[str] = None,
) -> DashboardBlueprint:
    """
    Convenience function to generate deep dive layout.
    
    Args:
        session_id: Data session identifier.
        title: Dashboard title.
        data_summary: Summary of available data.
        objective: Optional business objective.
        
    Returns:
        Complete dashboard blueprint.
    """
    template = DeepDiveTemplate()
    return template.generate(session_id, title, data_summary, objective)
