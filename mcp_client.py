import os
import asyncio
import json
import requests
from dotenv import load_dotenv

load_dotenv()

# --- Native Kubernetes Client ---
try:
    from kubernetes import client, config
    K8S_SDK_AVAILABLE = True
except ImportError:
    K8S_SDK_AVAILABLE = False

# --- MCP SDK for SSE-based servers ---
try:
    from mcp import ClientSession
    from mcp.client.sse import sse_client
    MCP_SDK_AVAILABLE = True
except ImportError:
    MCP_SDK_AVAILABLE = False


class MCPClient:
    """Base client for other MCP-based specialists (DB, Grafana, etc.)"""
    def __init__(self, server_url):
        self.server_url = server_url

    async def call_tool_async(self, tool_name, arguments):
        if not self.server_url:
            return {"error": "Server URL not configured"}
        try:
            async with sse_client(self.server_url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments)
                    extracted = "\n".join([c.text for c in result.content if hasattr(c, 'text')])
                    try:
                        return json.loads(extracted)
                    except (json.JSONDecodeError, ValueError):
                        return extracted if extracted else {"result": "Success"}
        except Exception as e:
            return {"error": str(e)}

    def call_tool(self, tool_name, arguments):
        try:
            return asyncio.run(self.call_tool_async(tool_name, arguments))
        except Exception as e:
            return {"error": str(e)}


class K8sNativeClient:
    """
    Direct Kubernetes integration using the official Python client.
    Replaces the external MCP server for better performance and complete access.
    """
    def __init__(self):
        self.kubeconfig = os.getenv("KUBECONFIG_PATH")
        self.initialized = False
        try:
            if self.kubeconfig and os.path.exists(self.kubeconfig):
                config.load_kube_config(config_file=self.kubeconfig)
            else:
                config.load_incluster_config()
            self.v1 = client.CoreV1Api()
            self.apps_v1 = client.AppsV1Api()
            self.initialized = True
        except Exception as e:
            print(f"K8s Init Error: {e}")

    def list_pods(self, namespace="default"):
        if not self.initialized: return {"error": "K8s client not initialized"}
        try:
            if namespace == "all":
                pods = self.v1.list_pod_for_all_namespaces()
            else:
                pods = self.v1.list_namespaced_pod(namespace)
            return [
                {
                    "name": p.metadata.name,
                    "namespace": p.metadata.namespace,
                    "status": p.status.phase,
                    "ip": p.status.pod_ip
                } for p in pods.items
            ]
        except Exception as e:
            return {"error": str(e)}

    def get_pod_logs(self, name, namespace="default", tail=100):
        if not self.initialized: return {"error": "K8s client not initialized"}
        try:
            return self.v1.read_namespaced_pod_log(name, namespace, tail_lines=tail)
        except Exception as e:
            return {"error": str(e)}

    def list_deployments(self, namespace="default"):
        if not self.initialized: return {"error": "K8s client not initialized"}
        try:
            deps = self.apps_v1.list_namespaced_deployment(namespace)
            return [
                {
                    "name": d.metadata.name,
                    "replicas": f"{d.status.available_replicas or 0}/{d.spec.replicas}",
                    "strategy": d.spec.strategy.type
                } for d in deps.items
            ]
        except Exception as e:
            return {"error": str(e)}

    def list_namespaces(self):
        if not self.initialized: return {"error": "K8s client not initialized"}
        try:
            ns = self.v1.list_namespace()
            return [n.metadata.name for n in ns.items]
        except Exception as e:
            return {"error": str(e)}

    def get_events(self, namespace="default"):
        if not self.initialized: return {"error": "K8s client not initialized"}
        try:
            events = self.v1.list_namespaced_event(namespace)
            return [
                {
                    "type": e.type,
                    "reason": e.reason,
                    "message": e.message,
                    "object": e.involved_object.name
                } for e in events.items
            ][-20:] # Last 20 events
        except Exception as e:
            return {"error": str(e)}


class ChromaMCPClient(MCPClient):
    def __init__(self):
        url = os.getenv("CHROMADB_MCP_URL")
        super().__init__(url)

class DatabaseMCPClient(MCPClient):
    def __init__(self):
        url = os.getenv("DATABASE_MCP_URL")
        super().__init__(url)

class GrafanaMCPClient(MCPClient):
    def __init__(self):
        url = os.getenv("GRAFANA_MCP_URL")
        super().__init__(url)

class K8sGPTMCPClient(MCPClient):
    def __init__(self):
        url = os.getenv("K8SGPT_MCP_URL")
        super().__init__(url)


def check_k8s_status():
    """Health check for native Kubernetes connectivity with strict timeout."""
    try:
        # Use a background task with timeout for the API call
        async def _check_quick():
            c = K8sNativeClient()
            if not c.initialized: return False
            # set a very low limit and timeout for the health check
            c.v1.list_namespace(limit=1, _request_timeout=2)
            return True
        
        # Since this is called from a thread, we use a new event loop or run_coro
        return asyncio.run(asyncio.wait_for(_check_quick(), timeout=3))
    except (asyncio.TimeoutError, Exception):
        return False

def check_mcp_status(url):
    """Health check for other MCP servers with strict timeout."""
    if not url or not MCP_SDK_AVAILABLE:
        return False
    try:
        async def _check():
            async with sse_client(url) as (read, write):
                async with ClientSession(read, write) as session:
                    # Initialize with a timeout
                    await asyncio.wait_for(session.initialize(), timeout=2)
                    return True
        return asyncio.run(asyncio.wait_for(_check(), timeout=3))
    except (asyncio.TimeoutError, Exception):
        return False
