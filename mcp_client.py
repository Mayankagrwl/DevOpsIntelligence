import os
import asyncio
import json
import requests
from dotenv import load_dotenv

load_dotenv()

# --- Native Kubernetes Client ---
try:
    from kubernetes import client, config
    from kubernetes.stream import stream
    import yaml
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
            self.custom_api = client.CustomObjectsApi()
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
                    "ip": p.status.pod_ip,
                    "node": p.spec.node_name
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

    def get_pod_details(self, name, namespace="default"):
        """Get rich metadata for a specific pod (like kubectl describe)."""
        if not self.initialized: return {"error": "K8s client not initialized"}
        try:
            p = self.v1.read_namespaced_pod(name, namespace)
            return {
                "name": p.metadata.name,
                "namespace": p.metadata.namespace,
                "status": p.status.phase,
                "node": p.spec.node_name,
                "start_time": str(p.status.start_time),
                "images": [c.image for c in p.spec.containers],
                "container_statuses": [
                    {
                        "name": s.name,
                        "ready": s.ready,
                        "restart_count": s.restart_count,
                        "state": str(s.state)
                    } for s in (p.status.container_statuses or [])
                ],
                "conditions": [{"type": c.type, "status": c.status} for c in p.status.conditions]
            }
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

    def get_deployment_details(self, name, namespace="default"):
        """Get rich metadata for a specific deployment."""
        if not self.initialized: return {"error": "K8s client not initialized"}
        try:
            d = self.apps_v1.read_namespaced_deployment(name, namespace)
            return {
                "name": d.metadata.name,
                "namespace": d.metadata.namespace,
                "replicas": f"{d.status.ready_replicas or 0}/{d.spec.replicas}",
                "updated_replicas": d.status.updated_replicas,
                "strategy": d.spec.strategy.type,
                "selector": d.spec.selector.match_labels,
                "images": [c.image for c in d.spec.template.spec.containers],
                "conditions": [{"type": c.type, "status": c.status, "message": c.message} for c in d.status.conditions]
            }
        except Exception as e:
            return {"error": str(e)}

    def get_events(self, namespace="default"):
        if not self.initialized: return {"error": "K8s client not initialized"}
        try:
            if namespace == "all":
                events = self.v1.list_event_for_all_namespaces()
            else:
                events = self.v1.list_namespaced_event(namespace)
            
            return [
                {
                    "namespace": e.metadata.namespace if namespace == "all" else None,
                    "type": e.type,
                    "reason": e.reason,
                    "message": e.message,
                    "object": e.involved_object.name,
                    "time": str(e.last_timestamp)
                } for e in events.items
            ][-20:] # Last 20 events
        except Exception as e:
            return {"error": str(e)}

    def exec_command(self, pod_name, command, namespace="default", container=None):
        """Execute a non-interactive command inside a pod container."""
        if not self.initialized: return {"error": "K8s client not initialized"}
        try:
            # We wrap the command in /bin/sh -c to allow for complex strings/pipes
            exec_args = ['/bin/sh', '-c', command]
            
            resp = stream(self.v1.connect_get_namespaced_pod_exec,
                          pod_name,
                          namespace,
                          command=exec_args,
                          container=container,
                          stderr=True, stdin=False,
                          stdout=True, tty=False)
            return {"output": resp}
        except Exception as e:
            return {"error": f"Exec failed: {str(e)}"}

    def list_services(self, namespace="default"):
        if not self.initialized: return {"error": "K8s client not initialized"}
        try:
            if namespace == "all":
                objs = self.v1.list_service_for_all_namespaces()
            else:
                objs = self.v1.list_namespaced_service(namespace)
            return [{"name": i.metadata.name, "type": i.spec.type, "cluster_ip": i.spec.cluster_ip} for i in objs.items]
        except Exception as e:
            return {"error": str(e)}

    def get_service_details(self, name, namespace="default"):
        if not self.initialized: return {"error": "K8s client not initialized"}
        try:
            i = self.v1.read_namespaced_service(name, namespace)
            return {
                "name": i.metadata.name,
                "type": i.spec.type,
                "cluster_ip": i.spec.cluster_ip,
                "ports": [{"port": p.port, "protocol": p.protocol, "target_port": str(p.target_port)} for p in i.spec.ports],
                "selector": i.spec.selector
            }
        except Exception as e:
            return {"error": str(e)}

    def list_configmaps(self, namespace="default"):
        if not self.initialized: return {"error": "K8s client not initialized"}
        try:
            if namespace == "all":
                objs = self.v1.list_config_map_for_all_namespaces()
            else:
                objs = self.v1.list_namespaced_config_map(namespace)
            return [{"name": i.metadata.name, "namespace": i.metadata.namespace} for i in objs.items]
        except Exception as e:
            return {"error": str(e)}

    def get_configmap_details(self, name, namespace="default"):
        if not self.initialized: return {"error": "K8s client not initialized"}
        try:
            i = self.v1.read_namespaced_config_map(name, namespace)
            return {"name": i.metadata.name, "data_keys": list(i.data.keys()) if i.data else []}
        except Exception as e:
            return {"error": str(e)}

    def list_secrets(self, namespace="default"):
        if not self.initialized: return {"error": "K8s client not initialized"}
        try:
            if namespace == "all":
                objs = self.v1.list_secret_for_all_namespaces()
            else:
                objs = self.v1.list_namespaced_secret(namespace)
            return [{"name": i.metadata.name, "type": i.type} for i in objs.items]
        except Exception as e:
            return {"error": str(e)}

    def get_secret_details(self, name, namespace="default"):
        if not self.initialized: return {"error": "K8s client not initialized"}
        try:
            i = self.v1.read_namespaced_secret(name, namespace)
            return {"name": i.metadata.name, "type": i.type, "data_keys": list(i.data.keys()) if i.data else []}
        except Exception as e:
            return {"error": str(e)}

    def list_nodes(self):
        if not self.initialized: return {"error": "K8s client not initialized"}
        try:
            nodes = self.v1.list_node()
            return [
                {
                    "name": n.metadata.name,
                    "status": n.status.conditions[-1].type if n.status.conditions else "Unknown",
                    "version": n.status.node_info.kubelet_version
                } for n in nodes.items
            ]
        except Exception as e:
            return {"error": str(e)}

    def get_node_details(self, name):
        if not self.initialized: return {"error": "K8s client not initialized"}
        try:
            n = self.v1.read_node(name)
            return {
                "name": n.metadata.name,
                "labels": n.metadata.labels,
                "capacity": n.status.capacity,
                "info": str(n.status.node_info)
            }
        except Exception as e:
            return {"error": str(e)}

    def get_cluster_info(self):
        if not self.initialized: return {"error": "K8s client not initialized"}
        try:
            # Requires version API
            version = client.VersionApi().get_code()
            return {
                "git_version": version.git_version,
                "platform": version.platform,
                "build_date": version.build_date
            }
        except:
            return {"status": "Connected (Version API hidden/unavailable)"}

    def delete_resource(self, kind, name, namespace="default"):
        """Delete a Kubernetes resource by kind and name."""
        if not self.initialized: return {"error": "K8s client not initialized"}
        try:
            kind = kind.lower()
            if kind in ["pod", "pods"]:
                self.v1.delete_namespaced_pod(name, namespace)
            elif kind in ["deployment", "deployments", "deploy"]:
                self.apps_v1.delete_namespaced_deployment(name, namespace)
            elif kind in ["service", "services", "svc"]:
                self.v1.delete_namespaced_service(name, namespace)
            elif kind in ["configmap", "cm"]:
                self.v1.delete_namespaced_config_map(name, namespace)
            elif kind in ["secret", "secrets"]:
                self.v1.delete_namespaced_secret(name, namespace)
            else:
                return {"error": f"Unsupported resource kind: {kind}"}
            return {"status": "Deleted", "kind": kind, "name": name, "namespace": namespace}
        except Exception as e:
            return {"error": str(e)}

    def create_namespace(self, name):
        """Create a new namespace."""
        if not self.initialized: return {"error": "K8s client not initialized"}
        try:
            ns = client.V1Namespace(metadata=client.V1ObjectMeta(name=name))
            self.v1.create_namespace(ns)
            return {"status": "Created", "namespace": name}
        except Exception as e:
            return {"error": str(e)}

    def get_node_metrics(self):
        """Get resource usage metrics for nodes (requires metrics-server)."""
        if not self.initialized: return {"error": "K8s client not initialized"}
        try:
            metrics = self.custom_api.list_cluster_custom_object(
                "metrics.k8s.io", "v1beta1", "nodes"
            )
            return [
                {
                    "name": item["metadata"]["name"],
                    "cpu": item["usage"]["cpu"],
                    "memory": item["usage"]["memory"]
                } for item in metrics.get("items", [])
            ]
        except Exception as e:
            return {"error": f"Metrics API unavailable: {str(e)}"}

    def get_resource_manifest(self, kind, name, namespace="default"):
        """Get the full YAML manifest of a resource, stripped of cluster-specific metadata for cloning."""
        if not self.initialized: return {"error": "K8s client not initialized"}
        try:
            # Dynamically resolve the read method
            kind_lower = kind.lower()
            obj = None
            if kind_lower == "pod":
                obj = self.v1.read_namespaced_pod(name, namespace)
            elif kind_lower == "deployment":
                obj = self.apps_v1.read_namespaced_deployment(name, namespace)
            elif kind_lower == "service":
                obj = self.v1.read_namespaced_service(name, namespace)
            elif kind_lower == "configmap":
                obj = self.v1.read_namespaced_config_map(name, namespace)
            elif kind_lower == "secret":
                obj = self.v1.read_namespaced_secret(name, namespace)
            elif kind_lower == "ingress":
                net_v1 = client.NetworkingV1Api()
                obj = net_v1.read_namespaced_ingress(name, namespace)
            elif kind_lower == "daemonset":
                obj = self.apps_v1.read_namespaced_daemon_set(name, namespace)
            elif kind_lower == "statefulset":
                obj = self.apps_v1.read_namespaced_stateful_set(name, namespace)
            else:
                return {"error": f"Unsupported kind for manifest extraction: {kind}"}

            if not obj:
                return {"error": f"Resource {kind}/{name} not found"}

            # Convert to dict
            data = client.ApiClient().sanitize_for_serialization(obj)
            
            # CRITICAL: Strip cluster-specific fields for cloning
            if "metadata" in data:
                m = data["metadata"]
                keys_to_strip = ["uid", "resourceVersion", "creationTimestamp", "selfLink", "ownerReferences", "managedFields", "generateName"]
                for key in keys_to_strip:
                    m.pop(key, None)
                # Keep name and namespace for now, the agent can change them
            
            # Strip status entirely
            data.pop("status", None)

            return yaml.dump(data, default_flow_style=False)
        except Exception as e:
            return {"error": str(e)}

    def create_pod(self, name, image, namespace="default", command=None, args=None):
        """Create a single pod (like kubectl run)."""
        if not self.initialized: return {"error": "K8s client not initialized"}
        try:
            pod_manifest = {
                "apiVersion": "v1",
                "kind": "Pod",
                "metadata": {"name": name, "namespace": namespace},
                "spec": {
                    "containers": [{
                        "name": name,
                        "image": image,
                        "command": command.split() if command else None,
                        "args": args if args else None
                    }]
                }
            }
            # Filter None values
            if not command: pod_manifest["spec"]["containers"][0].pop("command", None)
            if not args: pod_manifest["spec"]["containers"][0].pop("args", None)

            self.v1.create_namespaced_pod(namespace, pod_manifest)
            return {"status": "Created", "pod": name, "namespace": namespace}
        except Exception as e:
            return {"error": f"Failed to create pod: {str(e)}"}

    def apply_manifest(self, manifest_yaml, namespace="default"):
        """Apply a raw YAML manifest using native Python Kubernetes client."""
        if not self.initialized: return {"error": "K8s client not initialized"}
        
        try:
            import yaml
            docs = list(yaml.safe_load_all(manifest_yaml))
            results = []
            
            for doc in docs:
                if not doc:
                    continue
                kind = doc.get("kind", "").lower()
                metadata = doc.get("metadata", {})
                name = metadata.get("name", "unknown")
                ns = metadata.get("namespace", namespace)
                
                try:
                    if kind == "pod":
                        self.v1.create_namespaced_pod(ns, doc)
                    elif kind == "deployment":
                        self.apps_v1.create_namespaced_deployment(ns, doc)
                    elif kind == "service":
                        self.v1.create_namespaced_service(ns, doc)
                    elif kind == "configmap":
                        self.v1.create_namespaced_config_map(ns, doc)
                    elif kind == "secret":
                        self.v1.create_namespaced_secret(ns, doc)
                    elif kind == "namespace":
                        self.v1.create_namespace(doc)
                    elif kind == "serviceaccount":
                        self.v1.create_namespaced_service_account(ns, doc)
                    elif kind == "ingress":
                        net_v1 = client.NetworkingV1Api()
                        net_v1.create_namespaced_ingress(ns, doc)
                    elif kind == "daemonset":
                        self.apps_v1.create_namespaced_daemon_set(ns, doc)
                    elif kind == "statefulset":
                        self.apps_v1.create_namespaced_stateful_set(ns, doc)
                    elif kind == "job":
                        batch_v1 = client.BatchV1Api()
                        batch_v1.create_namespaced_job(ns, doc)
                    elif kind == "cronjob":
                        batch_v1 = client.BatchV1Api()
                        batch_v1.create_namespaced_cron_job(ns, doc)
                    else:
                        results.append({"kind": kind, "name": name, "status": f"Unsupported kind: {kind}"})
                        continue
                    results.append({"kind": kind, "name": name, "namespace": ns, "status": "Created"})
                except client.exceptions.ApiException as e:
                    if e.status == 409:
                        # Already exists — try to update
                        try:
                            if kind == "deployment":
                                self.apps_v1.replace_namespaced_deployment(name, ns, doc)
                            elif kind == "service":
                                self.v1.replace_namespaced_service(name, ns, doc)
                            elif kind == "configmap":
                                self.v1.replace_namespaced_config_map(name, ns, doc)
                            elif kind == "secret":
                                self.v1.replace_namespaced_secret(name, ns, doc)
                            else:
                                results.append({"kind": kind, "name": name, "status": f"Already exists"})
                                continue
                            results.append({"kind": kind, "name": name, "namespace": ns, "status": "Updated"})
                        except Exception as ue:
                            results.append({"kind": kind, "name": name, "status": f"Update failed: {str(ue)}"})
                    else:
                        results.append({"kind": kind, "name": name, "status": f"Error: {e.reason}"})
            
            return {"resources": results}
        except Exception as e:
            return {"error": str(e)}

    def scale_deployment(self, name, replicas, namespace="default"):
        """Scale a deployment to the specified number of replicas."""
        if not self.initialized: return {"error": "K8s client not initialized"}
        try:
            body = {"spec": {"replicas": int(replicas)}}
            self.apps_v1.patch_namespaced_deployment_scale(name, namespace, body)
            return {"status": "Scaled", "deployment": name, "replicas": int(replicas), "namespace": namespace}
        except Exception as e:
            return {"error": str(e)}

    def restart_deployment(self, name, namespace="default"):
        """Restart a deployment by triggering a rollout restart."""
        if not self.initialized: return {"error": "K8s client not initialized"}
        try:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).isoformat()
            body = {
                "spec": {
                    "template": {
                        "metadata": {
                            "annotations": {
                                "kubectl.kubernetes.io/restartedAt": now
                            }
                        }
                    }
                }
            }
            self.apps_v1.patch_namespaced_deployment(name, namespace, body)
            return {"status": "Restarted", "deployment": name, "namespace": namespace}
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
