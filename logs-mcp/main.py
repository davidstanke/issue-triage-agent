import time
import math
import random
import json
from datetime import datetime, timezone
from mcp.server.fastmcp import FastMCP
import click

# Define the node specifications for our fictitious multi-tier storage cluster
NODES = {
    # NVMe Hot Tier
    "nvme-01": {"tier": "NVMe Hot Tier", "capacity_tb": 10.0, "base_iops": 100000, "base_latency_ms": 0.4, "base_throughput_mbs": 4500},
    "nvme-02": {"tier": "NVMe Hot Tier", "capacity_tb": 10.0, "base_iops": 95000, "base_latency_ms": 0.5, "base_throughput_mbs": 4200},
    
    # SSD Main Tier
    "ssd-01": {"tier": "SSD Main Tier", "capacity_tb": 50.0, "base_iops": 22000, "base_latency_ms": 2.2, "base_throughput_mbs": 1200},
    "ssd-02": {"tier": "SSD Main Tier", "capacity_tb": 50.0, "base_iops": 20000, "base_latency_ms": 2.5, "base_throughput_mbs": 1100},
    "ssd-03": {"tier": "SSD Main Tier", "capacity_tb": 50.0, "base_iops": 21000, "base_latency_ms": 2.4, "base_throughput_mbs": 1150},
    "ssd-04": {"tier": "SSD Main Tier", "capacity_tb": 50.0, "base_iops": 19000, "base_latency_ms": 2.8, "base_throughput_mbs": 1050},
    
    # HDD Archival Tier
    "hdd-01": {"tier": "HDD Archival Tier", "capacity_tb": 200.0, "base_iops": 350, "base_latency_ms": 15.0, "base_throughput_mbs": 150},
    "hdd-02": {"tier": "HDD Archival Tier", "capacity_tb": 200.0, "base_iops": 320, "base_latency_ms": 16.5, "base_throughput_mbs": 140},
    "hdd-03": {"tier": "HDD Archival Tier", "capacity_tb": 200.0, "base_iops": 340, "base_latency_ms": 15.8, "base_throughput_mbs": 145},
    "hdd-04": {"tier": "HDD Archival Tier", "capacity_tb": 200.0, "base_iops": 310, "base_latency_ms": 17.2, "base_throughput_mbs": 135},
    "hdd-05": {"tier": "HDD Archival Tier", "capacity_tb": 200.0, "base_iops": 330, "base_latency_ms": 16.0, "base_throughput_mbs": 142},
    "hdd-06": {"tier": "HDD Archival Tier", "capacity_tb": 200.0, "base_iops": 300, "base_latency_ms": 18.0, "base_throughput_mbs": 130},
}

def get_node_metrics(node_id: str, ts: float) -> dict:
    """Generates real-time storage performance metrics on-the-fly based on timestamp.
    
    This simulation engine uses deterministic mathematical functions (sine/cosine) combined
    with timestamp seeds to create realistic load variations, metrics, and anomalies,
    fully stateless and repeatable.
    """
    node = NODES[node_id]
    
    # Workload fluctuations: 5-minute cycle (300 seconds) for dynamic testing in playrounds
    cycle_period = 300.0
    phase = (ts % cycle_period) / cycle_period * 2 * math.pi
    load_factor = 0.75 + 0.25 * math.sin(phase)  # Load varies between 0.5 and 1.0
    
    # Add high-frequency noise for realism
    noise = 0.04 * math.sin(ts * 13.0) + 0.02 * math.cos(ts * 31.0)
    load_factor = max(0.1, min(1.5, load_factor + noise))
    
    # Base computations
    iops = int(node["base_iops"] * load_factor)
    throughput = int(node["base_throughput_mbs"] * load_factor)
    
    # Latency increases non-linearly with load factor (congestion emulation)
    latency = node["base_latency_ms"] * (1.0 + 0.9 * (load_factor ** 3))
    
    # Capacity used: starts at a deterministic hash value and creeps up very slowly
    growth_rate = 0.0001  # TB per hour
    elapsed_hours = (ts - 1770000000) / 3600.0
    hash_seed = abs(hash(node_id))
    used_base_ratio = (hash_seed % 60 + 20) / 100.0  # 20% to 80% full base
    capacity_used = node["capacity_tb"] * (used_base_ratio + (growth_rate * elapsed_hours) % 0.15)
    capacity_pct = (capacity_used / node["capacity_tb"]) * 100.0
    
    status = "HEALTHY"
    queue_depth = max(1, int(4 * load_factor))
    
    # --- Anomalies & Fault Injection ---
    minute_block = int(ts // 60)
    
    # Anomaly 1: NVMe Write Storm (Minute divisible by 5, first 45 seconds)
    if "nvme" in node_id and (minute_block % 5 == 0):
        second_in_minute = ts % 60
        if second_in_minute < 45:
            if node_id == "nvme-01":
                status = "DEGRADED"
                iops = int(node["base_iops"] * 2.8)
                throughput = int(node["base_throughput_mbs"] * 3.3)
                latency = node["base_latency_ms"] * 25.0  # Latency spikes to ~10-12ms
                queue_depth = 56
            else:
                # nvme-02 experiences slight congestion spillover
                latency = node["base_latency_ms"] * 3.2
                queue_depth = 12

    # Anomaly 2: SSD-03 Endurance Wear-out warning (persists under 5% remaining)
    if node_id == "ssd-03":
        status = "WARNING"
        
    # Anomaly 3: HDD Replication Delay (Minute divisible by 7, remainder 3, for 60 seconds)
    if "hdd" in node_id and (minute_block % 7 == 3):
        if node_id in ["hdd-01", "hdd-02"]:
            status = "WARNING"
            latency = node["base_latency_ms"] * 2.5
            queue_depth = max(queue_depth, 10)
            
    return {
        "node_id": node_id,
        "tier": node["tier"],
        "status": status,
        "iops": iops,
        "throughput_mbs": throughput,
        "latency_ms": round(latency, 2),
        "queue_depth": queue_depth,
        "capacity_tb": node["capacity_tb"],
        "capacity_used_tb": round(capacity_used, 2),
        "capacity_pct": round(capacity_pct, 1),
    }

def get_logs_history(ts: float, limit: int = 20, system_id: str = None, severity: str = None) -> list[dict]:
    """Generates a history of log events stepping backwards from the given timestamp.
    
    Uses deterministic PRNG seeding to maintain event log consistency per timestamp step.
    """
    logs = []
    
    # Align steps to 15s boundaries for consistency
    current_step = ts - (ts % 15)
    
    step = 0
    # Search limit to avoid infinite loops, scan up to 100 historical intervals to fulfill filtered requests
    while len(logs) < limit and step < 100:
        step_ts = current_step - (step * 15)
        step += 1
        
        # Seed random deterministically based on this step's unique timestamp
        rng = random.Random(int(step_ts))
        
        # Select which node generated a log at this second
        node_ids = list(NODES.keys())
        node_id = rng.choice(node_ids)
        node_metrics = get_node_metrics(node_id, step_ts)
        
        # Inject warning/error events matching active anomalies
        if node_metrics["status"] == "DEGRADED":
            log_level = "ERROR"
            message = f"High IOPS write storm causing queue depth overflow (queue_depth={node_metrics['queue_depth']}). Latency spiked to {node_metrics['latency_ms']}ms."
        elif node_metrics["status"] == "WARNING":
            if node_id == "ssd-03":
                log_level = "WARN"
                # Simulating a dynamic remaining percentage
                wear_pct = round(4.2 - (step_ts % 1000) / 1000.0, 2)
                message = f"SSD remaining endurance lifespan is critically low (remaining: {wear_pct}%). Replacement recommended."
            elif "hdd" in node_id:
                log_level = "WARN"
                lag_secs = int(40 + (step_ts % 30))
                message = f"Replication lag detected on cold storage archival peer (current lag: {lag_secs}s). Syncing blocks..."
            else:
                log_level = "WARN"
                message = f"Elevated latency alert: {node_metrics['latency_ms']}ms exceeds threshold."
        else:
            # Healthy standard logs
            log_level = "INFO"
            templates = [
                "Completed periodic storage block integrity scrub. 0 corrupt blocks found.",
                f"Metrics flush: IOPS={node_metrics['iops']:,}, Latency={node_metrics['latency_ms']}ms, Capacity={node_metrics['capacity_pct']}% full.",
                f"Cache eviction run completed. Cache hit ratio: {round(rng.uniform(92.0, 99.8), 2)}%.",
                "Connection poll healthy. Active cluster peer connections: 12/12.",
                f"Garbage collection completed. Reclaimed {round(rng.uniform(0.5, 8.2), 2)} GB of deleted blocks.",
                "Background disk scrubbing found no errors on filesystems.",
            ]
            message = rng.choice(templates)
            
        dt = datetime.fromtimestamp(step_ts, tz=timezone.utc)
        timestamp_str = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        
        log_entry = {
            "timestamp": timestamp_str,
            "node_id": node_id,
            "tier": node_metrics["tier"],
            "severity": log_level,
            "message": message,
        }
        
        # Apply optional filters
        match_system = True
        if system_id:
            sys_lower = system_id.lower()
            match_system = (sys_lower in node_id.lower() or sys_lower in node_metrics["tier"].lower())
            
        match_severity = True
        if severity:
            match_severity = (severity.upper() == log_level)
            
        if match_system and match_severity:
            logs.append(log_entry)
            
    return logs[:limit]

def get_logs_stream_report() -> str:
    """Builds a rich markdown formatted report containing active cluster stats and the latest log lines."""
    ts = time.time()
    metrics_list = [get_node_metrics(node_id, ts) for node_id in NODES]
    
    # 1. Title & Timestamp
    md = "# 📊 STORAGE CLUSTER REAL-TIME STATUS SUMMARY\n"
    md += f"Generated on: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
    
    # 2. Markdown Performance Metrics Table
    md += "| Node ID | Storage Tier | Status | IOPS | Throughput | Latency | Q-Depth | Capacity (Used/Total) | % Full |\n"
    md += "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
    
    for m in metrics_list:
        status_emoji = "🟢 HEALTHY"
        if m["status"] == "DEGRADED":
            status_emoji = "🔴 DEGRADED"
        elif m["status"] == "WARNING":
            status_emoji = "🟡 WARNING"
            
        md += f"| `{m['node_id']}` | {m['tier']} | {status_emoji} | {m['iops']:,} | {m['throughput_mbs']} MB/s | {m['latency_ms']}ms | {m['queue_depth']} | {m['capacity_used_tb']} TB / {m['capacity_tb']} TB | {m['capacity_pct']}% |\n"
        
    # 3. Dynamic Alert Bulletins
    anomalies = []
    for m in metrics_list:
        if m["status"] == "DEGRADED":
            anomalies.append(f"🚨 **[CRITICAL]** `{m['node_id']}` is **DEGRADED**: Active Write Storm! Latency is critical ({m['latency_ms']}ms), Queue Depth is {m['queue_depth']}.")
        elif m["status"] == "WARNING":
            if m["node_id"] == "ssd-03":
                anomalies.append(f"⚠️ **[WARNING]** `{m['node_id']}` remaining endurance is low (4.2%). Replacement SSD ordered.")
            else:
                anomalies.append(f"⚠️ **[WARNING]** `{m['node_id']}` experiences elevated replication delays syncing cold storage blocks.")
                
    if anomalies:
        md += "\n## 🚨 ACTIVE ALERTS & ANOMALIES\n"
        for alert in anomalies:
            md += f"- {alert}\n"
    else:
        md += "\n## ✅ NO ACTIVE SYSTEM ALERTS\nAll tiers operating within baseline parameters.\n"
        
    # 4. SySLog Feed
    recent_logs = get_logs_history(ts, limit=15)
    md += "\n## 📜 REAL-TIME SYSLOG STREAM (Last 15 Events)\n"
    md += "```syslog\n"
    for log in recent_logs:
        md += f"[{log['timestamp']}] [{log['severity']}] [{log['node_id']}] {log['message']}\n"
    md += "```\n"
    
    md += "\n---\n*💡 AI Agent Tip: You can query these logs programmatically with specific filters using the `query_storage_logs` tool.*"
    return md

# Initialize the FastMCP Server
mcp = FastMCP("Storage Monitoring Server")

@mcp.tool()
def query_storage_logs(system_id: str = None, severity: str = None, limit: int = 20) -> str:
    """Query logs and performance metrics from the virtual storage cluster with filters.
    
    Args:
        system_id: Filter by node ID (e.g. 'nvme-01', 'ssd-03') or storage tier ('nvme', 'ssd', 'hdd').
        severity: Filter by log severity level ('INFO', 'WARN', 'ERROR').
        limit: Maximum number of log entries to retrieve (default: 20).
    """
    logs = get_logs_history(time.time(), limit=limit, system_id=system_id, severity=severity)
    return json.dumps(logs, indent=2)

@mcp.resource("storage://logs/stream")
def get_logs_stream() -> str:
    """Provides a real-time status summary of all cluster nodes and a streaming slice of recent logs."""
    return get_logs_stream_report()


@click.command()
@click.option("--transport", default="stdio", type=click.Choice(["stdio", "sse"]), help="Transport protocol to use (stdio or sse)")
@click.option("--host", default="0.0.0.0", help="Host address to bind the SSE server to")
@click.option("--port", default=8080, type=int, help="Port to bind the SSE server to")
def cli(transport, host, port):
    """MCP Storage Monitoring Server"""
    if transport == "stdio":
        click.echo("Starting MCP Server in STDIO mode...", err=True)
        mcp.run(transport="stdio")
    elif transport == "sse":
        click.echo(f"Starting MCP Server in SSE mode on {host}:{port}...", err=True)
        
        from fastapi import FastAPI
        import uvicorn
        
        # Initialize FastAPI and mount FastMCP sse app
        app = FastAPI(title="Storage Monitoring MCP Server")
        
        # Custom health endpoints for Cloud Run standard health checks
        @app.get("/")
        @app.get("/health")
        def health():
            return {
                "status": "healthy", 
                "service": "storage-monitoring-mcp", 
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        app.mount("/mcp", mcp.sse_app())
        
        uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    cli()
