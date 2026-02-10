import os
import requests
import json
import asyncio
from dotenv import load_dotenv

load_dotenv()

# --- Lightweight SDK import for health checks only ---
try:
    from mcp import ClientSession
    from mcp.client.sse import sse_client
    MCP_SDK_AVAILABLE = True
except ImportError:
    MCP_SDK_AVAILABLE = False


class MCPClient:
    """
    Hybrid MCP Client:
    - Tool execution: Simple HTTP POST (reliable, synchronous)
    - Health checks: MCP SDK via SSE (accurate handshake verification)
    """
    def __init__(self, server_url):
        self.server_url = server_url
        # Derive the base URL (without /sse) for HTTP tool calls
        if server_url and server_url.endswith("/sse"):
            self.base_url = server_url[:-4]  # strip "/sse"
        else:
            self.base_url = server_url

    def call_tool(self, tool_name, arguments):
        """Execute a tool via simple HTTP POST to the MCP server."""
        if not self.base_url:
            return {"error": "Server URL not configured"}
        try:
            response = requests.post(
                f"{self.base_url}/tool",
                json={"name": tool_name, "arguments": arguments},
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError:
            return {"error": f"Cannot connect to MCP server at {self.base_url}"}
        except requests.exceptions.Timeout:
            return {"error": f"Timeout connecting to MCP server at {self.base_url}"}
        except Exception as e:
            return {"error": str(e)}


class K8sMCPClient(MCPClient):
    def __init__(self):
        url = os.getenv("K8S_MCP_URL")
        super().__init__(url)

    def list_pods(self, namespace="default"):
        return self.call_tool("list_pods", {"namespace": namespace})

    def get_pod_logs(self, pod_name, namespace="default"):
        return self.call_tool("get_pod_logs", {"pod_name": pod_name, "namespace": namespace})


class ChromaMCPClient(MCPClient):
    def __init__(self):
        url = os.getenv("CHROMADB_MCP_URL")
        super().__init__(url)

    def query_memory(self, query_text, n_results=3):
        return self.call_tool("query_collection", {"query": query_text, "n_results": n_results})


class DatabaseMCPClient(MCPClient):
    def __init__(self):
        url = os.getenv("DATABASE_MCP_URL")
        super().__init__(url)

    def query_db(self, query):
        return self.call_tool("query", {"sql_query": query})


class GrafanaMCPClient(MCPClient):
    def __init__(self):
        url = os.getenv("GRAFANA_MCP_URL")
        super().__init__(url)

    def query_metrics(self, query):
        return self.call_tool("query_metrics", {"query": query})

    def get_alerts(self):
        return self.call_tool("get_alerts", {})


class K8sGPTMCPClient(MCPClient):
    def __init__(self):
        url = os.getenv("K8SGPT_MCP_URL")
        super().__init__(url)

    def analyze_cluster(self):
        return self.call_tool("analyze", {})

    def triage_namespace(self, namespace):
        return self.call_tool("triage", {"namespace": namespace})


def check_mcp_status(url):
    """
    Health check using the MCP SDK for accurate handshake verification.
    Falls back to a simple HTTP GET if the SDK is not available.
    """
    if not url:
        return False

    # Method 1: MCP SDK (preferred - true protocol handshake)
    if MCP_SDK_AVAILABLE:
        try:
            async def _check():
                async with sse_client(url) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.list_tools()
                        return result is not None
            return asyncio.run(_check())
        except Exception:
            return False

    # Method 2: Simple HTTP fallback
    try:
        base_url = url[:-4] if url.endswith("/sse") else url
        r = requests.get(f"{base_url}/health", timeout=5)
        return r.status_code == 200
    except Exception:
        return False
