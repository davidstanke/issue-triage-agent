# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import asyncio
import logging
import os

from fastmcp import FastMCP 

logger = logging.getLogger(__name__)
logging.basicConfig(format="[%(levelname)s]: %(message)s", level=logging.INFO)

mcp = FastMCP("MCP Server on Cloud Run", stateless_http=True)

import datetime
import random

SEVERITY_LEVELS = {"INFO": 1, "WARNING": 2, "ERROR": 3}

@mcp.tool()
def fetch_storage_logs(limit: int = 50, min_severity: str = "INFO") -> list[dict]:
    """Retrieve structured mock log data from the storage monitoring service.

    Args:
        limit: The maximum number of logs to return. Default is 50.
        min_severity: The minimum severity level filter. Options are INFO, WARNING, ERROR. Default is INFO.

    Returns:
        A list of dictionaries representing individual log entries.
    """
    logger.info(f">>> 🛠️ Tool: 'fetch_storage_logs' called with limit='{limit}', min_severity='{min_severity}'")
    
    # Map input severity to hierarchy level
    min_sev_str = min_severity.upper()
    if min_sev_str == "WARN":
        min_sev_str = "WARNING"
    min_level = SEVERITY_LEVELS.get(min_sev_str, 1)

    buckets = [
        "user-photos-prod",
        "finance-reports-secure",
        "backup-db-vault",
        "static-assets-cdn",
        "temp-exports-tmp"
    ]
    components = ["API Gateway", "Metadata Server", "Storage Node", "Load Balancer"]
    operations = ["GET", "PUT", "DELETE", "LIST"]

    logs = []
    current_time = datetime.datetime.now(datetime.timezone.utc)

    # Generate candidate log entries starting from recent and going backwards in time
    for i in range(limit * 5): # Generate more candidate entries so we can filter by severity
        if len(logs) >= limit:
            break

        # Decrement time by a few seconds/minutes per log entry
        log_time = current_time - datetime.timedelta(
            seconds=random.randint(5, 120) * (i + 1)
        )
        
        # Determine scenario
        roll = random.random()
        if roll < 0.80:
            # 80% Success
            severity = "INFO"
            component = random.choice(components)
            operation = random.choice(operations)
            bucket = random.choice(buckets)
            latency_ms = random.randint(5, 150)
            status_code = 201 if operation == "PUT" else 200
            message = f"Successfully completed {operation} operation on bucket '{bucket}'."
        elif roll < 0.85:
            # 5% Permission Error
            severity = "WARNING"
            component = "API Gateway"
            operation = random.choice(["GET", "PUT", "DELETE"])
            bucket = random.choice(["finance-reports-secure", "backup-db-vault"])
            latency_ms = random.randint(10, 50)
            status_code = 403
            message = f"Permission denied: principal is missing 'storage.objects.get' permission on bucket '{bucket}'."
        elif roll < 0.90:
            # 5% Not Found
            severity = "WARNING"
            component = "Metadata Server"
            operation = "GET"
            bucket = random.choice(buckets)
            latency_ms = random.randint(8, 40)
            status_code = 404
            message = f"Object metadata entry not found for path in bucket '{bucket}'."
        elif roll < 0.95:
            # 5% High Latency/Timeout
            severity = "ERROR"
            component = "Metadata Server"
            operation = "LIST"
            bucket = random.choice(["backup-db-vault", "user-photos-prod"])
            latency_ms = random.randint(2000, 5000)
            status_code = 500
            message = f"Metadata DB query timed out (threshold 2000ms) for bucket '{bucket}'."
        else:
            # 5% Storage Node Full/Exhaustion
            severity = "ERROR"
            component = "Storage Node"
            operation = "PUT"
            bucket = "static-assets-cdn"
            latency_ms = random.randint(500, 1500)
            status_code = 500
            message = f"Storage node disk write failed or connection pool exhausted for bucket '{bucket}'."

        # Check severity level filter
        entry_level = SEVERITY_LEVELS.get(severity, 1)
        if entry_level >= min_level:
            logs.append({
                "timestamp": log_time.isoformat(),
                "severity": severity,
                "component": component,
                "operation": operation,
                "bucket": bucket,
                "latency_ms": latency_ms,
                "status_code": status_code,
                "message": message
            })

    # Sort logs chronologically (oldest first or newest first? Let's do newest first, or chronologically ascending. Standard log outputs are typically sorted chronologically, but latest is often preferred. Let's return sorted by timestamp descending for easiest top-level consumption, or ascending. Let's do descending so user sees most recent first).
    logs.sort(key=lambda x: x["timestamp"], reverse=True)
    return logs[:limit]

if __name__ == "__main__":
    logger.info(f"🚀 MCP server started on port {os.getenv('PORT', 8080)}")
    # Could also use 'sse' transport, host="0.0.0.0" required for Cloud Run.
    asyncio.run(
        mcp.run_async(
            transport="streamable-http",
            host="0.0.0.0",
            port=os.getenv("PORT", 8080),
        )
    )
