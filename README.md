# ReportMCP - MCP Server for Business Intelligence Dashboard

A production-ready Model Context Protocol (MCP) server that transforms raw data into interactive business dashboards using FastAPI and Plotly Dash.

## Features

- **MCP Tools**: Powerful tools for data ingestion, blueprint generation, and dashboard access.
- **Dynamic Dashboards**: Generate interactive dashboards from JSON blueprints or via AI-driven templates.
- **Unified Architecture**: Combines an MCP server, a REST API, and a Plotly Dash web interface in a single service.
- **DuckDB Backend**: Fast in-memory (or persistent) analytics on ingested data.
- **Premium Design**: Responsive, mobile-friendly layouts with modern aesthetics (Glassmorphism, Google Fonts).

---

## 🚀 Getting Started with Docker (Recommended)

The easiest way to run the project is using Docker. This will start the unified application (FastAPI + Dash + MCP) on port `8050`.

```bash
# Clone the repository
git clone https://github.com/yourusername/ReportMCP.git
cd ReportMCP

# Start the service
docker-compose up --build
```

The application will be available at:
- **Dashboard UI**: [http://localhost:8050/dashboard/](http://localhost:8050/dashboard/)
- **MCP HTTP/SSE Endpoint**: `http://localhost:8050/mcp/http`
- **API Documentation**: [http://localhost:8050/docs](http://localhost:8050/docs)

---

## 🛠 Local Installation (Development)

If you prefer to run it locally:

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the unified server
python -m src.app
```

---

## 🧪 How to Test and Use

### 1. Ingest Data
Use an AI agent or the API to ingest data.
**API Example:**
```bash
curl -X POST http://localhost:8050/api/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sales_q4",
    "table_name": "sales",
    "data": [{"month": "Oct", "revenue": 50000}, {"month": "Nov", "revenue": 65000}],
    "schema": [
      {"name": "month", "type": "string", "is_dimension": true},
      {"name": "revenue", "type": "float", "is_metric": true}
    ]
  }'
```

### 2. Generate Dashboard
Ask the MCP tool `generate_dashboard_blueprint` or use the API:
```bash
curl -X POST http://localhost:8050/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sales_q4",
    "template": "executive_summary"
  }'
```

### 3. View the Result
Open your browser at [http://localhost:8050/dashboard/sales_q4](http://localhost:8050/dashboard/sales_q4).

---

## 🛠 MCP Tools

### `ingest_data`
Ingest CSV/JSON data with schema metadata into DuckDB.

### `generate_dashboard_blueprint`
Generate a dashboard configuration based on business objectives.

### `create_dashboard`
Agent-specific tool to create custom layouts with granular control.

### `get_dashboard_url`
Get the URL to view the generated dashboard.

---

## 📂 Project Structure

```
ReportMCP/
├── src/
│   ├── server.py              # MCP Server implementation
│   ├── app.py                 # FastAPI + Dash integration (Unified Entry Point)
│   ├── models/                # Pydantic models & validation
│   ├── components/            # Dash component renderers
│   ├── templates/             # Dashboard templates (Executive Summary, Deep Dive)
│   └── storage/               # DuckDB manager & SQL executor
├── data/                      # Persistent DuckDB storage (volume mapped in Docker)
├── tests/                     # Test suite
├── Dockerfile                 # Multi-stage container definition
├── docker-compose.yml         # Container orchestration
├── requirements.txt
└── README.md
```

## ⚙️ Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Server host |
| `PORT` | `8050` | Server port |
| `LOG_LEVEL` | `INFO` | Logging level |
| `DUCKDB_PATH` | `:memory:` | Path to DuckDB file (use `/app/data/report.db` for persistence in Docker) |

## 📄 License

MIT License - See [LICENSE](LICENSE) for details.

