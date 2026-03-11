"""
FastAPI application with Dash integration.

This module sets up the main FastAPI application and mounts
the Plotly Dash application as a sub-application for rendering
dashboards.

Usage:
    uvicorn src.app:app --host 0.0.0.0 --port 8050 --reload
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.wsgi import WSGIMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel, Field
from fastmcp.server.http import create_streamable_http_app

from dash import Dash, dcc, html, Input, Output, State, callback, MATCH, ALL
import dash_bootstrap_components as dbc

from src.components.renderer import render_layout
from src.models.blueprint import DashboardBlueprint
from src.models.exceptions import SessionNotFoundError
from src.storage.duckdb_manager import DuckDBManager

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Configuration
HOST = os.getenv("HOST", "localhost")
PORT = int(os.getenv("PORT", "8050"))

from src.server import db_manager, blueprint_store, mcp

# Configuration
HOST = os.getenv("HOST", "localhost")
PORT = int(os.getenv("PORT", "8050"))


def get_db_manager() -> DuckDBManager:
    """Get the shared database manager from server module."""
    return db_manager


def get_blueprint_store() -> dict[str, DashboardBlueprint]:
    """Get the shared blueprint store from server module."""
    return blueprint_store


# Initialize FastAPI
app = FastAPI(title="ReportMCP Dashboard")

# Mount MCP Server (Streamable HTTP)
# This exposes the MCP server at /mcp/http
mcp_app = create_streamable_http_app(
    server=mcp,
    streamable_http_path="/http",
    debug=True
)
app.mount("/mcp", mcp_app)

# ============================================================================
# Dash Application
# ============================================================================

# Initialize Dash app with Bootstrap theme
dash_app = Dash(
    __name__,
    requests_pathname_prefix="/dashboard/",
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        dbc.icons.FONT_AWESOME,
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap",
    ],
    suppress_callback_exceptions=True,
    title="ReportMCP Dashboard",
)

# Custom CSS for premium styling
CUSTOM_CSS = """
    body {
        font-family: 'Inter', sans-serif;
        background: linear-gradient(135deg, #f5f7fa 0%, #e4e8ec 100%);
        min-height: 100vh;
    }
    .dashboard-wrapper {
        animation: fadeIn 0.5s ease-in-out;
    }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .card {
        border: none;
        border-radius: 12px;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(0,0,0,0.1) !important;
    }
    .display-5 {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    .shadow-sm {
        box-shadow: 0 4px 15px rgba(0,0,0,0.05) !important;
    }
"""

# Dash layout with dynamic content
dash_app.layout = html.Div([
    # Location component to track URL
    dcc.Location(id="url", refresh=False),
    
    # Custom styles
    html.Div([
        html.Style(CUSTOM_CSS)
    ]) if hasattr(html, 'Style') else html.Div(),
    
    # Main content container (populated by callback)
    html.Div(id="page-content"),
    
    # Hidden store for session data
    dcc.Store(id="session-store"),
    
    # Toast notifications
    dbc.Toast(
        id="notification-toast",
        header="Notification",
        is_open=False,
        dismissable=True,
        duration=4000,
        icon="info",
        style={"position": "fixed", "top": 66, "right": 10, "width": 350},
    ),
])


@callback(
    Output("page-content", "children"),
    Input("url", "pathname"),
)
def display_page(pathname: str):
    """
    Route handler for Dash pages.
    
    Extracts session ID from URL and renders the appropriate dashboard.
    """
    if pathname is None or pathname == "/dashboard/":
        return render_welcome_page()
    
    # Extract session ID from path: /dashboard/{session_id}
    parts = pathname.strip("/").split("/")
    if len(parts) >= 2:
        session_id = parts[1]
        return render_dashboard(session_id)
    
    return render_welcome_page()


def render_welcome_page() -> html.Div:
    """Render the welcome/landing page."""
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.I(className="fas fa-chart-line fa-4x text-primary mb-4"),
                    html.H1("ReportMCP Dashboard", className="display-4 fw-bold"),
                    html.P(
                        "Business Intelligence powered by AI",
                        className="lead text-muted mb-4"
                    ),
                    dbc.Alert([
                        html.I(className="fas fa-info-circle me-2"),
                        "To view a dashboard, navigate to ",
                        html.Code("/dashboard/{session_id}"),
                        " after ingesting data via the MCP tools.",
                    ], color="info"),
                ], className="text-center py-5"),
            ], md=8, className="mx-auto"),
        ]),
        
        # Features section
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.I(className="fas fa-database fa-2x text-primary mb-3"),
                        html.H5("Data Ingestion"),
                        html.P("Ingest CSV/JSON data with schema definitions", className="text-muted"),
                    ], className="text-center")
                ], className="shadow-sm h-100"),
            ], md=4),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.I(className="fas fa-magic fa-2x text-success mb-3"),
                        html.H5("Smart Blueprints"),
                        html.P("Auto-generate dashboard layouts from data", className="text-muted"),
                    ], className="text-center")
                ], className="shadow-sm h-100"),
            ], md=4),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.I(className="fas fa-chart-pie fa-2x text-info mb-3"),
                        html.H5("Interactive Charts"),
                        html.P("Explore data with dynamic visualizations", className="text-muted"),
                    ], className="text-center")
                ], className="shadow-sm h-100"),
            ], md=4),
        ], className="g-4 mt-4"),
    ], fluid=True, className="py-5")


def render_dashboard(session_id: str) -> html.Div:
    """
    Render a dashboard for the given session.
    
    Args:
        session_id: The session identifier.
        
    Returns:
        Rendered dashboard or error message.
    """
    store = get_blueprint_store()
    db = get_db_manager()
    
    # Check if blueprint exists
    if session_id not in store:
        # Check if data exists
        if db.session_exists(session_id):
            return dbc.Container([
                dbc.Alert([
                    html.H4("Blueprint Not Found", className="alert-heading"),
                    html.P(
                        f"Data exists for session '{session_id}', but no dashboard blueprint "
                        "has been generated yet."
                    ),
                    html.Hr(),
                    html.P([
                        "Use the ",
                        html.Code("generate_dashboard_blueprint"),
                        " MCP tool to create a dashboard configuration.",
                    ], className="mb-0"),
                ], color="warning"),
            ], fluid=True, className="py-5")
        
        return dbc.Container([
            dbc.Alert([
                html.H4("Session Not Found", className="alert-heading"),
                html.P(f"No data found for session '{session_id}'."),
                html.Hr(),
                html.P([
                    "Use the ",
                    html.Code("ingest_data"),
                    " MCP tool to add data first.",
                ], className="mb-0"),
            ], color="danger"),
        ], fluid=True, className="py-5")
    
    # Get blueprint and render
    blueprint = store[session_id]
    
    # Create query executor that uses the db manager
    def query_executor(sid: str, query: str):
        return db.execute_query(sid, query)
    
    try:
        return render_layout(blueprint, query_executor=query_executor)
    except Exception as e:
        logger.error(f"Dashboard rendering failed: {e}", exc_info=True)
        return dbc.Container([
            dbc.Alert([
                html.H4("Rendering Error", className="alert-heading"),
                html.P(f"Failed to render dashboard: {str(e)}"),
            ], color="danger"),
        ], fluid=True, className="py-5")


# ============================================================================
# Dynamic Filtering Callbacks
# ============================================================================

@callback(
    Output({"type": "data-comp-wrapper", "sid": MATCH, "index": MATCH}, "children"),
    Input({"type": "filter", "sid": MATCH, "name": ALL}, "value"),
    Input({"type": "filter", "sid": MATCH, "name": ALL}, "start_date"),
    Input({"type": "filter", "sid": MATCH, "name": ALL}, "end_date"),
    State({"type": "filter", "sid": MATCH, "name": ALL}, "id"),
    State({"type": "query-metadata", "sid": MATCH, "index": MATCH}, "data"),
    prevent_initial_call=True
)
def update_filtered_component(filter_values, start_dates, end_dates, filter_ids, metadata):
    """
    Update a single component based on all active filters in the session.
    """
    if not metadata:
        return dash.no_update
        
    session_id = metadata["sid"]
    original_query = metadata["query"]
    comp_type = metadata["type"]
    props = metadata["props"]
    
    if not original_query:
        return dash.no_update
        
    # Build WHERE clauses from filters
    clauses = []
    for i, f_id in enumerate(filter_ids):
        col_name = f_id["name"]
        val = filter_values[i]
        start = start_dates[i]
        end = end_dates[i]
        
        if val:
            if isinstance(val, list):
                if val:
                    vals_str = ", ".join([f"'{v}'" for v in val])
                    clauses.append(f"{col_name} IN ({vals_str})")
            else:
                clauses.append(f"{col_name} = '{val}'")
        
        if start and end:
            clauses.append(f"{col_name} BETWEEN '{start}' AND '{end}'")
            
    # Wrap original query with filters
    filtered_query = original_query
    if clauses:
        where_stmt = " AND ".join(clauses)
        filtered_query = f"SELECT * FROM ({original_query}) WHERE {where_stmt}"
    
    # Re-render the component
    from src.components.renderer import RenderContext, render_component
    from src.models.blueprint import ComponentConfig
    
    db = get_db_manager()
    context = RenderContext(
        session_id=session_id,
        query_executor=lambda sid, q: db.execute_query(sid, q)
    )
    
    config = ComponentConfig(
        type=comp_type,
        props=props,
        data_query=filtered_query,
        id=metadata["index"]
    )
    
    # We only want the internal component, not another wrapper/store
    # So we call the specific renderer based on type
    from src.components.renderer import (
        render_kpi_card, render_line_chart, render_bar_chart, 
        render_pie_chart, render_table, render_stat_card
    )
    
    # Map types to render functions
    # (Note: this is a bit redundant but avoids infinite recursion if we called render_component)
    from src.models.blueprint import ComponentType
    
    dash_id = {"type": "data-comp", "sid": session_id, "index": metadata["index"]}
    
    if comp_type == ComponentType.KPI_CARD:
        rendered = render_kpi_card(config, context, dash_id)
    elif comp_type == ComponentType.LINE_CHART:
        rendered = render_line_chart(config, context, dash_id)
    elif comp_type == ComponentType.BAR_CHART:
        rendered = render_bar_chart(config, context, dash_id)
    elif comp_type == ComponentType.PIE_CHART:
        rendered = render_pie_chart(config, context, dash_id)
    elif comp_type == ComponentType.TABLE:
        rendered = render_table(config, context, dash_id)
    elif comp_type == ComponentType.STAT_CARD:
        rendered = render_stat_card(config, context, dash_id)
    else:
        return dash.no_update

    return [
        rendered,
        dcc.Store(
            id={"type": "query-metadata", "sid": session_id, "index": metadata["index"]},
            data=metadata # Keep original metadata
        )
    ]


# ============================================================================
# FastAPI Application
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting ReportMCP Web Server")
    
    # Initialize shared state with MCP server
    try:
        from src.server import blueprint_store as mcp_blueprints, db_manager as mcp_db
        global blueprint_store, db_manager
        blueprint_store = mcp_blueprints
        db_manager = mcp_db
        logger.info("Linked with MCP server state")
    except ImportError:
        logger.warning("MCP server not available, using local state")
    
    yield
    
    # Shutdown
    logger.info("Shutting down ReportMCP Web Server")
    if db_manager:
        db_manager.close()


# Create FastAPI app
app = FastAPI(
    title="ReportMCP Dashboard API",
    description="API for Business Intelligence Dashboard",
    version="0.1.0",
    lifespan=lifespan,
)

# Mount Dash app
app.mount("/dashboard", WSGIMiddleware(dash_app.server))


# ============================================================================
# API Endpoints
# ============================================================================

from src.models.data import DataIngestionRequest

@app.post("/api/ingest")
async def ingest_data(request: DataIngestionRequest):
    """Ingest data via API."""
    db = get_db_manager()
    response = db.ingest_data(request)
    return response.model_dump()

class GenerateRequest(BaseModel):
    session_id: str
    title: str = "Dashboard"
    template: str = "executive_summary"
    objective: Optional[str] = None

@app.post("/api/generate")
async def generate_dashboard(request: GenerateRequest):
    """Generate dashboard blueprint via API."""
    db = get_db_manager()
    store = get_blueprint_store()
    
    if not db.session_exists(request.session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    
    summary = db.get_data_summary(request.session_id)
    from src.templates.base import get_template
    template_instance = get_template(request.template)
    
    if not template_instance:
        raise HTTPException(status_code=400, detail="Template not found")
        
    blueprint = template_instance.generate(
        session_id=request.session_id,
        title=request.title,
        data_summary=summary,
        objective=request.objective
    )
    store[request.session_id] = blueprint
    return {"status": "success", "session_id": request.session_id}


class CreateDashboardRequest(BaseModel):
    session_id: str
    title: str
    components: list[dict[str, Any]]

@app.post("/api/create")
async def create_custom_dashboard(request: CreateDashboardRequest):
    """Create a dashboard with custom components via API."""
    db = get_db_manager()
    store = get_blueprint_store()
    
    if not db.session_exists(request.session_id):
        raise HTTPException(status_code=404, detail="Session not found")
        
    # Importiamo la logica di creazione interna dal server
    from src.server import create_dashboard_internal
    
    # Chiamiamo direttamente la logica interna
    result = await create_dashboard_internal(
        session_id=request.session_id,
        title=request.title,
        components=request.components
    )
    
    return result


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "ReportMCP Dashboard API",
        "version": "0.1.0",
        "dashboard_url": f"http://{HOST}:{PORT}/dashboard/",
        "docs_url": f"http://{HOST}:{PORT}/docs",
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "components": {
            "database": db_manager is not None,
            "blueprints_loaded": len(blueprint_store),
        },
    }


@app.get("/api/sessions")
async def list_sessions():
    """List all available sessions."""
    db = get_db_manager()
    store = get_blueprint_store()
    
    sessions = []
    for session_id in db._sessions:
        try:
            summary = db.get_data_summary(session_id)
            sessions.append({
                "session_id": session_id,
                "has_blueprint": session_id in store,
                "table_count": summary.get("table_count", 0),
                "total_rows": summary.get("total_rows", 0),
                "dashboard_url": f"/dashboard/{session_id}",
            })
        except Exception:
            continue
    
    return {"sessions": sessions, "count": len(sessions)}

@app.post("/api/reset")
async def reset_application():
    """
    Completely reset the application state: 
    - Clears blueprint store (in-memory)
    - Resets DuckDB (deletes file and reconnects)
    """
    logger.warning("Application reset requested")
    
    # 1. Clear memory
    blueprint_store.clear()
    
    # 2. Reset database (file + connections)
    success = db_manager.reset_database()
    
    if success:
        return {"message": "Application state reset successfully (Memory cleared + Database deleted)"}
    else:
        raise HTTPException(status_code=500, detail="Failed to reset database file")


from fastapi.responses import RedirectResponse

@app.get("/dashboard")
async def dashboard_root():
    """Redirect to Dash app."""
    return RedirectResponse(url="/dashboard/")

@app.get("/api/sessions/{session_id}")
async def get_session_details(request: Request, session_id: str):
    """Get details for a specific session."""
    db = get_db_manager()
    store = get_blueprint_store()
    
    if not db.session_exists(session_id):
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    
    summary = db.get_data_summary(session_id)
    blueprint = store.get(session_id)
    
    return {
        "session_id": session_id,
        "data_summary": summary,
        "has_blueprint": blueprint is not None,
        "blueprint_title": blueprint.title if blueprint else None,
        "blueprint_template": blueprint.template if blueprint else None,
        "dashboard_url": f"/dashboard/{session_id}",
    }


# Exception handlers
@app.exception_handler(SessionNotFoundError)
async def session_not_found_handler(request: Request, exc: SessionNotFoundError):
    """Handle session not found errors."""
    return JSONResponse(
        status_code=404,
        content=exc.to_dict(),
    )


# ============================================================================
# Utility to link with MCP server
# ============================================================================

def link_with_mcp_server(mcp_blueprints: dict, mcp_db: DuckDBManager) -> None:
    """
    Link the web app with MCP server state.
    
    Call this when running both servers in the same process.
    
    Args:
        mcp_blueprints: Blueprint store from MCP server.
        mcp_db: Database manager from MCP server.
    """
    global blueprint_store, db_manager
    blueprint_store = mcp_blueprints
    db_manager = mcp_db
    logger.info("Web app linked with MCP server state")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
