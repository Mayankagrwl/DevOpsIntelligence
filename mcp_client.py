import os
import requests
import json
from sseclient import SSEClient
from dotenv import load_dotenv

load_dotenv()

class MCPClient:
    def __init__(self, server_url):
        self.server_url = server_url
        self.session = requests.Session()

    def get_tools(self):
        """Fetches available tools from the MCP server."""
        try:
            # MCP usually has a standard way to list tools via HTTP or SSE initialization
            # For this implementation, we assume a standard SSE/HTTP structure
            response = self.session.get(f"{self.server_url}/tools", timeout=5)
            if response.status_code == 200:
                return response.json()
            return []
        except:
            return []

    def call_tool(self, tool_name, arguments):
        """Executes a tool call on the MCP server."""
        try:
            payload = {
                "name": tool_name,
                "arguments": arguments
            }
            response = self.session.post(f"{self.server_url}/call", json=payload, timeout=10)
            if response.status_code == 200:
                return response.json()
            return {"error": f"Tool call failed with status {response.status_code}"}
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
        """Actively searching the vector database."""
        return self.call_tool("query_collection", {"query": query_text, "n_results": n_results})

    def add_memory(self, document):
        """Storing new information into the vector database."""
        return self.call_tool("add_document", {"document": document})

class DatabaseMCPClient(MCPClient):
    def __init__(self):
        url = os.getenv("DATABASE_MCP_URL")
        super().__init__(url)

    def list_tables(self):
        return self.call_tool("list_tables", {})

    def query_db(self, query):
        return self.call_tool("query", {"sql_query": query})

    def audit_schema(self):
        return self.call_tool("audit_schema", {})

class GrafanaMCPClient(MCPClient):
    def __init__(self):
        url = os.getenv("GRAFANA_MCP_URL")
        super().__init__(url)

    def get_dashboards(self):
        return self.call_tool("get_dashboards", {})

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
    """Helper for UI status lights."""
    if not url: return False
    try:
        # Simple health check if the server supports it, else check reachability
        response = requests.get(url.replace("/sse", "/health") if "/sse" in url else url, timeout=2)
        return response.status_code < 500
    except:
        return False
