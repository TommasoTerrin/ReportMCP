"""
Dashboard component renderer.

This module provides the render_layout() function that transforms
a DashboardBlueprint JSON structure into actual Dash components.
It recursively processes the component tree and creates the
appropriate Dash HTML and DCC elements.
"""

import logging
from typing import Any, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import dash_table, dcc, html
import dash_bootstrap_components as dbc

from src.models.blueprint import ComponentConfig, ComponentType, DashboardBlueprint
from src.models.exceptions import RenderingError

logger = logging.getLogger(__name__)


def render_layout(
    blueprint: DashboardBlueprint,
    query_executor: Optional[callable] = None,
) -> html.Div:
    """
    Transform a DashboardBlueprint into Dash components.
    """
    logger.info(f"Rendering blueprint: {blueprint.title} ({blueprint.count_components()} components)")
    
    try:
        # Create context for rendering
        context = RenderContext(
            session_id=blueprint.session_id,
            query_executor=query_executor,
        )
        
        # Render all root components
        rendered_components = []
        for component in blueprint.components:
            rendered = render_component(component, context)
            if rendered is not None:
                rendered_components.append(rendered)
        
        # Wrap in a fluid container
        return html.Div(
            children=[
                dbc.Container(
                    children=rendered_components,
                    fluid=True,
                    className="py-4",
                )
            ],
            id=f"dashboard-{blueprint.session_id}",
            className="dashboard-wrapper",
        )
        
    except Exception as e:
        logger.error(f"Layout rendering failed: {e}", exc_info=True)
        raise RenderingError(
            message=f"Failed to render dashboard layout: {str(e)}",
            details={"blueprint_title": blueprint.title},
        )


class RenderContext:
    """
    Context object passed through the render tree.
    """
    
    def __init__(
        self,
        session_id: str,
        query_executor: Optional[callable] = None,
    ) -> None:
        self.session_id = session_id
        self.query_executor = query_executor
        self._query_cache: dict[str, pd.DataFrame] = {}
    
    def execute_query(self, query: str) -> Optional[pd.DataFrame]:
        if self.query_executor is None:
            logger.warning("No query executor provided, returning None")
            return None
        
        # Check cache
        if query in self._query_cache:
            return self._query_cache[query]
        
        try:
            df = self.query_executor(self.session_id, query)
            self._query_cache[query] = df
            return df
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            return None


def render_component(
    config: ComponentConfig,
    context: RenderContext,
) -> Any:
    """
    Render a single component from its configuration.
    """
    try:
        base_id = config.id or f"comp-{id(config)}"
        class_name = config.class_name or ""
        session_id = context.session_id
        
        # Determine ID for Dash callbacks
        if config.type in (ComponentType.LINE_CHART, ComponentType.BAR_CHART, ComponentType.PIE_CHART, ComponentType.TABLE, ComponentType.KPI_CARD):
            dash_id = {"type": "data-comp", "sid": session_id, "index": base_id}
        elif config.type in (ComponentType.DROPDOWN, ComponentType.DATE_PICKER):
            # For filters, we use the 'column' prop as the identifier
            filter_name = config.props.get("column", base_id)
            dash_id = {"type": "filter", "sid": session_id, "name": filter_name}
        else:
            dash_id = base_id
        
        match config.type:
            # Layout components
            case ComponentType.ROW:
                return render_row(config, context, dash_id)
            case ComponentType.COLUMN:
                return render_column(config, context, dash_id)
            case ComponentType.CONTAINER:
                return render_container(config, context, dash_id)
            case ComponentType.CARD:
                return render_card(config, context, dash_id)
            
            # Text components
            case ComponentType.H1:
                return html.H1(
                    config.props.get("text", ""),
                    id=dash_id,
                    className=class_name or "display-5 fw-bold mb-3",
                )
            case ComponentType.H2:
                return html.H2(
                    config.props.get("text", ""),
                    id=dash_id,
                    className=class_name or "h3 mb-3",
                )
            case ComponentType.H3:
                return html.H3(
                    config.props.get("text", ""),
                    id=dash_id,
                    className=class_name or "h4 mb-2",
                )
            case ComponentType.P:
                return html.P(
                    config.props.get("text", ""),
                    id=dash_id,
                    className=class_name or "mb-2",
                )
            case ComponentType.ALERT:
                return render_alert(config, context, dash_id)
            
            # Data components
            case ComponentType.KPI_CARD | ComponentType.LINE_CHART | ComponentType.BAR_CHART | ComponentType.PIE_CHART | ComponentType.TABLE | ComponentType.STAT_CARD:
                # Wrap data components with a store for their original query configuration
                rendered = None
                if config.type == ComponentType.KPI_CARD:
                    rendered = render_kpi_card(config, context, dash_id)
                elif config.type == ComponentType.LINE_CHART:
                    rendered = render_line_chart(config, context, dash_id)
                elif config.type == ComponentType.BAR_CHART:
                    rendered = render_bar_chart(config, context, dash_id)
                elif config.type == ComponentType.PIE_CHART:
                    rendered = render_pie_chart(config, context, dash_id)
                elif config.type == ComponentType.TABLE:
                    rendered = render_table(config, context, dash_id)
                elif config.type == ComponentType.STAT_CARD:
                    rendered = render_stat_card(config, context, dash_id)
                
                return html.Div([
                    rendered,
                    dcc.Store(
                        id={"type": "query-metadata", "sid": session_id, "index": base_id},
                        data={
                            "query": config.data_query,
                            "type": config.type,
                            "props": config.props,
                            "sid": session_id
                        }
                    )
                ], id={"type": "data-comp-wrapper", "sid": session_id, "index": base_id}, style={"height": "100%"})
            
            # Interactive components
            case ComponentType.DATE_PICKER:
                return render_date_picker(config, context, dash_id)
            case ComponentType.DROPDOWN:
                return render_dropdown(config, context, dash_id)
            
            case _:
                logger.warning(f"Unknown component type: {config.type}")
                return html.Div(
                    f"Unknown component: {config.type}",
                    className="alert alert-warning",
                )
                
    except Exception as e:
        logger.error(f"Component rendering failed: {e}", exc_info=True)
        return html.Div(
            f"Error rendering component: {str(e)}",
            className="alert alert-danger",
        )


def render_row(config: ComponentConfig, context: RenderContext, component_id: str) -> dbc.Row:
    children = [render_component(c, context) for c in config.children]
    return dbc.Row(
        children=children,
        id=component_id,
        className=config.class_name or "mb-3",
    )


def render_column(config: ComponentConfig, context: RenderContext, component_id: str) -> dbc.Col:
    children = [render_component(c, context) for c in config.children]
    width = config.props.get("width", 12)
    return dbc.Col(
        children=children,
        id=component_id,
        md=width,
        className=config.class_name,
    )


def render_container(config: ComponentConfig, context: RenderContext, component_id: str) -> dbc.Container:
    children = [render_component(c, context) for c in config.children]
    return dbc.Container(
        children=children,
        id=component_id,
        fluid=config.props.get("fluid", True),
        className=config.class_name or "py-3",
    )


def render_card(config: ComponentConfig, context: RenderContext, component_id: str) -> dbc.Card:
    children = [render_component(c, context) for c in config.children]
    return dbc.Card(
        children=dbc.CardBody(children),
        id=component_id,
        className=config.class_name or "shadow-sm",
    )


def render_alert(config: ComponentConfig, context: RenderContext, component_id: str) -> dbc.Alert:
    return dbc.Alert(
        config.props.get("text", ""),
        id=component_id,
        color=config.props.get("color", "info"),
        className=config.class_name,
    )


def render_kpi_card(config: ComponentConfig, context: RenderContext, component_id: str) -> dbc.Card:
    props = config.props
    title = props.get("title", "KPI")
    value = props.get("value", "—")
    
    # Fetch data if query available
    if config.data_query and context.query_executor:
        try:
            df = context.execute_query(config.data_query)
            if df is not None and not df.empty:
                metric = props.get("metric")
                aggregation = props.get("aggregation", "sum")
                
                if metric in df.columns:
                    if aggregation == "sum":
                        raw_value = df[metric].sum()
                    elif aggregation == "avg":
                        raw_value = df[metric].mean()
                    elif aggregation == "count":
                        raw_value = len(df)
                    else:
                        raw_value = df[metric].iloc[0]
                else:
                    raw_value = df.iloc[0, 0]
                
                if isinstance(raw_value, (int, float, complex)):
                    if abs(raw_value) >= 1000000:
                        value = f"{raw_value / 1000000:.1f}M"
                    elif abs(raw_value) >= 1000:
                        value = f"{raw_value / 1000:.1f}K"
                    else:
                        value = f"{raw_value:,.0f}" if raw_value % 1 == 0 else f"{raw_value:,.2f}"
                else:
                    value = str(raw_value)
        except Exception as e:
            logger.warning(f"KPI data fetch failed: {e}")
            
    delta = props.get("delta")
    delta_type = props.get("delta_type", "neutral")
    icon = props.get("icon", "fa-chart-bar")
    color = props.get("color", "primary")
    
    delta_color = {
        "positive": "text-success",
        "negative": "text-danger",
        "neutral": "text-muted",
    }.get(delta_type, "text-muted")
    
    delta_icon = {
        "positive": "fa-arrow-up",
        "negative": "fa-arrow-down",
        "neutral": "fa-minus",
    }.get(delta_type, "fa-minus")
    
    card_content = [
        html.Div(
            [
                html.I(className=f"fas {icon} fa-2x text-{color} mb-2"),
            ],
            className="text-end",
        ),
        html.H6(title, className="text-muted text-uppercase mb-1"),
        html.H3(value, className="mb-0 fw-bold"),
    ]
    
    if delta:
        card_content.append(
            html.Small(
                [
                    html.I(className=f"fas {delta_icon} me-1"),
                    delta,
                ],
                className=f"{delta_color} mt-2 d-block",
            )
        )
    
    return dbc.Card(
        dbc.CardBody(card_content),
        id=component_id,
        className=config.class_name or "shadow-sm h-100",
    )


def render_stat_card(config: ComponentConfig, context: RenderContext, component_id: str) -> dbc.Card:
    props = config.props
    title = props.get("title", "Statistics")
    stats = props.get("stats", [])
    
    stat_items = []
    for stat in stats:
        stat_items.append(
            html.Div(
                [
                    html.Span(stat.get("label", ""), className="text-muted"),
                    html.Span(stat.get("value", ""), className="fw-bold float-end"),
                ],
                className="border-bottom py-2",
            )
        )
    
    return dbc.Card(
        dbc.CardBody([
            html.H5(title, className="card-title mb-3"),
            html.Div(stat_items),
        ]),
        id=component_id,
        className=config.class_name or "shadow-sm h-100",
    )


def render_line_chart(config: ComponentConfig, context: RenderContext, component_id: str) -> dcc.Graph:
    props = config.props
    title = props.get("title", "")
    x_axis = props.get("x_axis", "x")
    y_axis = props.get("y_axis", "y")
    color_by = props.get("color_by")
    height = props.get("height", 400)
    
    df = None
    if config.data_query and context.query_executor:
        df = context.execute_query(config.data_query)
    
    if df is None or df.empty:
        fig = go.Figure()
        fig.add_annotation(text="No data available", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
    else:
        # Aggregate if necessary
        if x_axis in df.columns and y_axis in df.columns:
            agg_df = df.groupby(x_axis)[y_axis].sum().reset_index()
            agg_df = agg_df.sort_values(by=x_axis)
            fig = px.line(agg_df, x=x_axis, y=y_axis, color=color_by, title=title, markers=True)
        else:
            fig = px.line(df, x=x_axis, y=y_axis, color=color_by, title=title, markers=True)
    
    fig.update_layout(height=height, margin=dict(l=40, r=40, t=60, b=40), template="plotly_white")
    
    return dcc.Graph(id=component_id, figure=fig)


def render_bar_chart(config: ComponentConfig, context: RenderContext, component_id: str) -> dcc.Graph:
    props = config.props
    title = props.get("title", "")
    x_axis = props.get("x_axis", "x")
    y_axis = props.get("y_axis", "y")
    color_by = props.get("color_by")
    height = props.get("height", 400)
    
    df = None
    if config.data_query and context.query_executor:
        df = context.execute_query(config.data_query)
    
    if df is None or df.empty:
        fig = go.Figure()
        fig.add_annotation(text="No data available", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
    else:
        # Aggregate if necessary
        if x_axis in df.columns and y_axis in df.columns:
            agg_df = df.groupby(x_axis)[y_axis].sum().reset_index()
            # If x_axis is string/category, we might want to sort by value
            if df[x_axis].dtype == 'object':
               agg_df = agg_df.sort_values(by=y_axis, ascending=False).head(10)
            else:
               agg_df = agg_df.sort_values(by=x_axis)
            fig = px.bar(agg_df, x=x_axis, y=y_axis, color=color_by, title=title)
        else:
            fig = px.bar(df, x=x_axis, y=y_axis, color=color_by, title=title)
    
    fig.update_layout(height=height, margin=dict(l=40, r=40, t=60, b=40), template="plotly_white")
    
    return dcc.Graph(id=component_id, figure=fig)


def render_pie_chart(config: ComponentConfig, context: RenderContext, component_id: str) -> dcc.Graph:
    props = config.props
    title = props.get("title", "")
    names_col = props.get("x_axis", "category")
    values_col = props.get("y_axis", "value")
    height = props.get("height", 400)
    
    df = None
    if config.data_query and context.query_executor:
        df = context.execute_query(config.data_query)
    
    if df is None or df.empty:
        fig = go.Figure()
        fig.add_annotation(text="No data available", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
    else:
        fig = px.pie(df, names=names_col, values=values_col, title=title, hole=0.4)
    
    fig.update_layout(height=height, margin=dict(l=40, r=40, t=60, b=40), template="plotly_white")
    
    return dcc.Graph(id=component_id, figure=fig)


def render_table(config: ComponentConfig, context: RenderContext, component_id: str) -> dash_table.DataTable:
    props = config.props
    page_size = props.get("page_size", 10)
    
    df = None
    if config.data_query and context.query_executor:
        df = context.execute_query(config.data_query)
    
    if df is None or df.empty:
        return html.Div("No data available", className="text-muted text-center py-4", id=component_id)
    
    columns = [{"name": col, "id": col} for col in df.columns]
    
    return dash_table.DataTable(
        id=component_id,
        data=df.to_dict("records"),
        columns=columns,
        page_size=page_size,
        style_table={"overflowX": "auto"},
        style_header={"backgroundColor": "rgb(230, 230, 230)", "fontWeight": "bold"},
        style_cell={"textAlign": "left", "padding": "10px"},
    )


def render_date_picker(config: ComponentConfig, context: RenderContext, component_id: str) -> dcc.DatePickerRange:
    from datetime import date, timedelta
    props = config.props
    column = props.get("column")
    table = props.get("table")
    
    start_date = None
    end_date = None
    
    if column and table and context.query_executor:
        try:
            df = context.execute_query(f"SELECT MIN({column}) as min_d, MAX({column}) as max_d FROM {table}")
            if df is not None and not df.empty:
                start_date = df['min_d'].iloc[0]
                end_date = df['max_d'].iloc[0]
        except Exception:
            pass
            
    return dcc.DatePickerRange(
        id=component_id,
        start_date=start_date or (date.today() - timedelta(days=30)),
        end_date=end_date or date.today(),
        className=config.class_name,
    )


def render_dropdown(config: ComponentConfig, context: RenderContext, component_id: str) -> dcc.Dropdown:
    props = config.props
    options = props.get("options", [])
    column = props.get("column")
    table = props.get("table")
    placeholder = props.get("placeholder", "Select...")
    
    if not options and column and table and context.query_executor:
        try:
            df = context.execute_query(f"SELECT DISTINCT {column} FROM {table} WHERE {column} IS NOT NULL ORDER BY {column}")
            if df is not None and not df.empty:
                options = [{"label": str(v), "value": v} for v in df[column].dropna().unique()]
        except Exception as e:
            logger.warning(f"Failed to fetch dropdown options: {e}")
            
    return dcc.Dropdown(
        id=component_id,
        options=options,
        placeholder=placeholder,
        className=config.class_name,
        clearable=True,
    )
