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

from fastmcp import Client

async def test_server():
    # Test the MCP server using streamable-http transport.
    # Use "/sse" endpoint if using sse transport.
    async with Client("http://localhost:8080/mcp") as client:
        # List available tools
        tools = await client.list_tools()
        for tool in tools:
            print(f">>> 🛠️  Tool found: {tool.name}")
        # Call fetch_storage_logs tool
        print(">>> 🪛  Calling fetch_storage_logs tool with limit=5, min_severity=WARNING")
        result = await client.call_tool("fetch_storage_logs", {"limit": 5, "min_severity": "WARNING"})
        print(f"<<< ✅ Result: {result.content[0].text}")

if __name__ == "__main__":
    asyncio.run(test_server())
