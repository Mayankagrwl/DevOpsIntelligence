import os
import asyncio
import json
from mcp import ClientSession
from mcp.client.sse import sse_client
from dotenv import load_dotenv

load_dotenv()

class MCPClient:
    def __init__(self, server_url):
        self.server_url = server_url

    async def get_tools_async(self):
        """Fetches available tools using official MCP SDK."""
        if not self.server_url: return []
        try:
            async with sse_client(self.server_url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    # SDK returns a ListToolsResult object, convert tools to dict for legacy compatibility
                    return [{"name": t.name, "description": t.description} for t in result.tools]
        except Exception as e:
            print(f"Error fetching tools from {self.server_url}: {e}")
            return None

    async def call_tool_async(self, tool_name, arguments):
        """Executes a tool call using official MCP SDK."""
        if not self.server_url: return {"error": "Server URL not configured"}
        try:
            async with sse_client(self.server_url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments)
                    # Extract text content for easier processing by the orchestrator
                    extracted_text = "\n".join([c.text for c in result.content if hasattr(c, 'text')])
                    try:
                        # Attempt to parse as JSON if it looks like JSON
                        return json.loads(extracted_text)
                    except:
                        return extracted_text
        except Exception as e:
            return {"error": str(e)}

    def get_tools(self):
        """Sync wrapper for Streamlit/Legacy code."""
        try:
            return asyncio.run(self.get_tools_async())
        except Exception as e:
            print(f"Sync Handshake Failed: {e}")
            return None

    def call_tool(self, tool_name, arguments):
        """Sync wrapper for Streamlit/Legacy code."""
        try:
            return asyncio.run(self.call_tool_async(tool_name, arguments))
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
        """Perform a full cluster analysis with K8sGPT."""
        return self.call_tool("analyze", {})

    def triage_namespace(self, namespace):
        """Triage a specific namespace."""
        return self.call_tool("triage", {"namespace": namespace})

def check_mcp_status(url):
    """Helper for UI status lights using new SDK logic."""
    if not url: return False
    try:
        client = MCPClient(url)
        tools = client.get_tools()
        return tools is not None # Only green if we got a real response (even if empty list)
    except:
        return False
