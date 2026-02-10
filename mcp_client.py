import os
import asyncio
import json
import requests
from dotenv import load_dotenv

load_dotenv()

# --- MCP SDK for SSE-based servers ---
try:
    from mcp import ClientSession
    from mcp.client.sse import sse_client
    MCP_SDK_AVAILABLE = True
except ImportError:
    MCP_SDK_AVAILABLE = False


class MCPClient:
    """
    MCP Client using the official SDK for SSE-based MCP servers.
    The kubernetes-mcp-server (containers/kubernetes-mcp-server) only speaks
    the MCP protocol over SSE — there are no REST/HTTP endpoints.
    """
    def __init__(self, server_url):
        self.server_url = server_url

    async def get_tools_async(self):
        """Fetches available tools using official MCP SDK."""
        if not self.server_url:
            return []
        try:
            async with sse_client(self.server_url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    return [{"name": t.name, "description": t.description} for t in result.tools]
        except Exception as e:
            print(f"Error fetching tools from {self.server_url}: {e}")
            return None

    async def call_tool_async(self, tool_name, arguments):
        """Executes a tool call using official MCP SDK over SSE."""
        if not self.server_url:
            return {"error": "Server URL not configured"}
        try:
            async with sse_client(self.server_url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments)
                    # Extract text content from the MCP result
                    extracted = "\n".join([c.text for c in result.content if hasattr(c, 'text')])
                    try:
                        return json.loads(extracted)
                    except (json.JSONDecodeError, ValueError):
                        return extracted if extracted else {"result": "Tool executed successfully (no output)"}
        except Exception as e:
            return {"error": f"Tool call failed: {str(e)}"}

    def get_tools(self):
        """Sync wrapper for Streamlit compatibility."""
        try:
            return asyncio.run(self.get_tools_async())
        except Exception as e:
            print(f"Sync get_tools failed: {e}")
            return None

    def call_tool(self, tool_name, arguments):
        """Sync wrapper for Streamlit compatibility."""
        try:
            return asyncio.run(self.call_tool_async(tool_name, arguments))
        except Exception as e:
            return {"error": f"Sync call_tool failed: {str(e)}"}


class K8sMCPClient(MCPClient):
    """
    Client for containers/kubernetes-mcp-server.
    Tool names match the actual server implementation:
    - pods_list / pods_list_in_namespace (NOT 'list_pods')
    - pods_log (NOT 'get_pod_logs')
    - pods_get, pods_delete, pods_exec, pods_run, pods_top
    - namespaces_list, events_list, resources_list, etc.
    """
    def __init__(self):
        url = os.getenv("K8S_MCP_URL")
        super().__init__(url)

    def list_pods(self, namespace=None):
        """List pods — uses pods_list_in_namespace if namespace is given."""
        if namespace:
            return self.call_tool("pods_list_in_namespace", {"namespace": namespace})
        return self.call_tool("pods_list", {})

    def get_pod_logs(self, pod_name, namespace=None):
        """Get pod logs — tool is 'pods_log', arg is 'name' not 'pod_name'."""
        args = {"name": pod_name}
        if namespace:
            args["namespace"] = namespace
        return self.call_tool("pods_log", args)

    def get_pod(self, pod_name, namespace=None):
        """Get details of a specific pod."""
        args = {"name": pod_name}
        if namespace:
            args["namespace"] = namespace
        return self.call_tool("pods_get", args)

    def list_namespaces(self):
        """List all namespaces."""
        return self.call_tool("namespaces_list", {})

    def list_events(self, namespace=None):
        """List cluster events."""
        args = {}
        if namespace:
            args["namespace"] = namespace
        return self.call_tool("events_list", args)


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
    """Health check using MCP SDK handshake."""
    if not url:
        return False
    if not MCP_SDK_AVAILABLE:
        return False
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
