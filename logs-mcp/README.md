# Mock Storage Monitoring MCP Server

This repository contains a high-fidelity **Model Context Protocol (MCP)** server simulating an enterprise multi-tier storage performance monitoring cluster. It dynamically generates performance metrics (IOPS, latency, throughput, queue depth, and capacities) and real-time event logs on-the-fly, injected with realistic SRE anomalies like NVMe write storms and replication delays.

Designed for AI agent consumption, the server supports:
- **STDIO Transport**: Ideal for local desktops, IDEs, and CLI tools (e.g. Claude Desktop).
- **SSE Transport (FastAPI)**: Over HTTP, container-ready, and optimized for serverless hosting on **Google Cloud Run**.

---

## 🏗️ Storage Cluster Topology

We simulate a realistic enterprise infrastructure with three tiers:
1. **NVMe Hot Tier (`nvme-01`, `nvme-02`)**: Low latency, high performance database nodes.
2. **SSD Main Tier (`ssd-01` to `ssd-04`)**: Standard virtual machine storage.
3. **HDD Archival Tier (`hdd-01` to `hdd-06`)**: High capacity, slow cold backups.

---

## 🛠️ MCP Interfaces Offered

### 1. Tool: `query_storage_logs`
Enables the AI agent to query specific subsets of real-time performance and event logs with parameter filtering.
* **Arguments:**
  - `system_id` (string, optional): Filter by node ID (e.g., `nvme-01`) or tier (`nvme`, `ssd`, `hdd`).
  - `severity` (string, optional): Filter by log importance (`INFO`, `WARN`, `ERROR`).
  - `limit` (int, optional): Max logs to fetch (default: `20`).
* **Returns**: JSON list of timestamped log records.

### 2. Resource: `storage://logs/stream`
Exposes the complete cluster real-time state.
* **Returns**: A premium Markdown report complete with **status tables**, **active system-wide alerts**, and the last 15 system-wide syslog logs.

---

## 🚀 Local Quickstart

### Prerequisites
Make sure you have [uv](https://github.com/astral-sh/uv) installed (the extremely fast Python package manager):
```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Install Dependencies
Set up the virtual environment and install dependencies:
```bash
uv pip install -e .
```
*(Or manually install: `uv pip install mcp fastapi uvicorn click`)*

### 1. Run in STDIO Mode (Default)
Recommended for standard MCP integrations (e.g., pointing Claude Desktop directly to a local script).
```bash
uv run python main.py --transport stdio
```

### 2. Run in SSE/HTTP Mode Locally
Spawns a local FastAPI server hosting Server-Sent Events (SSE).
```bash
uv run python main.py --transport sse --port 8080
```
- Custom Health Probe: `http://localhost:8080/health`
- MCP SSE Stream URL: `http://localhost:8080/mcp/sse`

---

## 🚀 Deploying to Google Cloud Run

To make this MCP server accessible remotely to any web-based AI Agent, deploy it to **Google Cloud Run** with a single command.

### 1. Log in to Google Cloud & Set Project
```bash
gcloud auth login
gcloud config set project <YOUR-PROJECT-ID>
```

### 2. Run Deployment Script
We've included an automated deployment script that compiles the Docker image via Google Cloud Build and provisions the Cloud Run service.
```bash
chmod +x deploy.sh
./deploy.sh
```

---

## 💻 Connecting to Clients

### Claude Desktop Configuration
To integrate this server locally with your Claude Desktop client, add the following to your `claude_desktop_config.json`:

#### For Local STDIO execution:
```json
{
  "mcpServers": {
    "storage-monitoring": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/logs-mcp",
        "python",
        "main.py",
        "--transport",
        "stdio"
      ]
    }
  }
}
```

#### For Deployed SSE (Cloud Run):
```json
{
  "mcpServers": {
    "storage-monitoring-remote": {
      "url": "https://<YOUR-CLOUD-RUN-URL>/mcp/sse"
    }
  }
}
```
