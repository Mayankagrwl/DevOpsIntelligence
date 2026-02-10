import os
import re
from brain import OllamaBrain
from memory import DevOpsMemory
from mcp_client import K8sNativeClient, ChromaMCPClient, DatabaseMCPClient, GrafanaMCPClient, K8sGPTMCPClient
import json

class DevOpsOrchestrator:
    def __init__(self):
        self.brain = OllamaBrain()
        self.memory = DevOpsMemory()
        self.k8s_client = K8sNativeClient()
        self.chroma_mcp = ChromaMCPClient()
        self.db_mcp = DatabaseMCPClient()
        self.grafana_mcp = GrafanaMCPClient()
        self.k8sgpt_mcp = K8sGPTMCPClient()
        
    def get_tool_definitions(self):
        """
        Tool definitions for Ollama — leveraging native K8s administration capabilities.
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": "list_pods",
                    "description": "List pods in a specific Kubernetes namespace. Use 'all' for all namespaces.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "namespace": {"type": "string", "description": "Namespace name (default: default, use 'all' for cluster-wide)"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_deployments",
                    "description": "List deployments in a specific Kubernetes namespace.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "namespace": {"type": "string", "description": "Namespace name"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_namespaces",
                    "description": "List all available namespaces in the Kubernetes cluster.",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_pod_logs",
                    "description": "Retrieve logs for a specific pod. Useful for troubleshooting and debugging.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Pod name"},
                            "namespace": {"type": "string", "description": "Pod namespace"},
                            "tail": {"type": "integer", "description": "Number of lines to retrieve (default: 100)"}
                        },
                        "required": ["name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_pod_details",
                    "description": "Get complete metadata for a specific pod (equivalent to 'kubectl describe'). Includes images, container states, and conditions.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Pod name"},
                            "namespace": {"type": "string", "description": "Pod namespace (default: default)"}
                        },
                        "required": ["name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_deployment_details",
                    "description": "Get detailed metadata for a specific deployment. Includes replicas, update strategy, and selection markers.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Deployment name"},
                            "namespace": {"type": "string", "description": "Namespace (default: default)"}
                        },
                        "required": ["name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_events",
                    "description": "Get recent Kubernetes events in a namespace for troubleshooting.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "namespace": {"type": "string", "description": "Namespace to check events for"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_services",
                    "description": "List services in a specific Kubernetes namespace. Use 'all' for all namespaces.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "namespace": {"type": "string", "description": "Namespace name (default: default)"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_service_details",
                    "description": "Get detailed metadata for a specific service (ports, selector, type).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Service name"},
                            "namespace": {"type": "string", "description": "Namespace (default: default)"}
                        },
                        "required": ["name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_configmaps",
                    "description": "List configmaps in a specific namespace.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "namespace": {"type": "string", "description": "Namespace (default: default)"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_configmap_details",
                    "description": "Get keys and metadata for a specific configmap.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "ConfigMap name"},
                            "namespace": {"type": "string", "description": "Namespace (default: default)"}
                        },
                        "required": ["name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_secrets",
                    "description": "List secrets in a specific namespace.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "namespace": {"type": "string", "description": "Namespace (default: default)"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_secret_details",
                    "description": "Get keys and metadata for a specific secret (does not reveal values by default).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Secret name"},
                            "namespace": {"type": "string", "description": "Namespace (default: default)"}
                        },
                        "required": ["name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_nodes",
                    "description": "List all physical/virtual nodes in the cluster with status and version.",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_node_details",
                    "description": "Get exhaustive metadata for a specific cluster node.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Node name"}
                        },
                        "required": ["name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_cluster_info",
                    "description": "Get overall cluster information and Kubernetes version.",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "delete_resource",
                    "description": "Delete a Kubernetes resource (Pod, Deployment, Service, etc.). CAUTION: This is destructive.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "kind": {"type": "string", "description": "Resource kind (pod, deployment, service, secret, configmap)"},
                            "name": {"type": "string", "description": "Resource name"},
                            "namespace": {"type": "string", "description": "Namespace (default: default)"}
                        },
                        "required": ["kind", "name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "create_namespace",
                    "description": "Create a new Kubernetes namespace.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Name of the new namespace"}
                        },
                        "required": ["name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "apply_manifest",
                    "description": "Apply a Kubernetes manifest (YAML) to the cluster. Equivalent to 'kubectl apply -f'.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "manifest_yaml": {"type": "string", "description": "The complete YAML content of the manifest"},
                            "namespace": {"type": "string", "description": "Target namespace (optional)"}
                        },
                        "required": ["manifest_yaml"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_node_metrics",
                    "description": "Get resource usage metrics (CPU/Memory) for all nodes.",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "exec_command",
                    "description": "Execute a shell command inside a pod's container. Use this to fetch config files, check processes, or run internal diagnostics.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pod_name": {"type": "string", "description": "Name of the pod"},
                            "command": {"type": "string", "description": "Shell command to run (e.g., 'ls -la', 'cat /etc/hosts')"},
                            "namespace": {"type": "string", "description": "Pod namespace (default: default)"},
                            "container": {"type": "string", "description": "Specific container name (optional)"}
                        },
                        "required": ["pod_name", "command"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "delete_resource",
                    "description": "Delete a Kubernetes resource (Pod, Deployment, Service, etc.). CAUTION: This is destructive.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "kind": {"type": "string", "description": "Resource kind (pod, deployment, service, secret, configmap)"},
                            "name": {"type": "string", "description": "Resource name"},
                            "namespace": {"type": "string", "description": "Namespace (default: default)"}
                        },
                        "required": ["kind", "name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "create_namespace",
                    "description": "Create a new Kubernetes namespace.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Name of the new namespace"}
                        },
                        "required": ["name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "apply_manifest",
                    "description": "Apply a Kubernetes manifest (YAML) to the cluster. Equivalent to 'kubectl apply -f'.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "manifest_yaml": {"type": "string", "description": "The complete YAML content of the manifest"},
                            "namespace": {"type": "string", "description": "Target namespace (optional)"}
                        },
                        "required": ["manifest_yaml"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_node_metrics",
                    "description": "Get resource usage metrics (CPU/Memory) for all nodes.",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "query_metrics",
                    "description": "Query Grafana/Prometheus metrics using PromQL.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "PromQL query string"}
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "query_db",
                    "description": "Execute a SQL query against the database.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "SQL query string"}
                        },
                        "required": ["query"]
                    }
                }
            }
        ]

    def execute_tool(self, name, args):
        """Routes tool calls to the native K8s client or MCP clients."""
        try:
            # --- Native K8s Tools ---
            if name in ["list_pods", "pods_list", "pods_list_in_namespace"]:
                return self.k8s_client.list_pods(namespace=args.get("namespace", "default"))
            elif name == "list_deployments":
                return self.k8s_client.list_deployments(namespace=args.get("namespace", "default"))
            elif name == "list_namespaces":
                return self.k8s_client.list_namespaces()
            elif name in ["get_pod_logs", "pods_log"]:
                return self.k8s_client.get_pod_logs(
                    args.get("name") or args.get("pod_name"), 
                    namespace=args.get("namespace", "default"),
                    tail=args.get("tail", 100)
                )
            elif name in ["get_pod_details", "pods_get", "describe_pod"]:
                return self.k8s_client.get_pod_details(
                    args.get("name"), 
                    namespace=args.get("namespace", "default")
                )
            elif name in ["get_deployment_details", "describe_deployment"]:
                return self.k8s_client.get_deployment_details(
                    args.get("name"), 
                    namespace=args.get("namespace", "default")
                )
            elif name == "get_events":
                return self.k8s_client.get_events(namespace=args.get("namespace", "default"))
            elif name == "exec_command":
                return self.k8s_client.exec_command(
                    args.get("pod_name") or args.get("name"),
                    args.get("command"),
                    namespace=args.get("namespace", "default"),
                    container=args.get("container")
                )
            elif name == "delete_resource":
                return self.k8s_client.delete_resource(
                    args.get("kind"),
                    args.get("name"),
                    namespace=args.get("namespace", "default")
                )
            elif name == "create_namespace":
                return self.k8s_client.create_namespace(args.get("name"))
            elif name == "apply_manifest":
                return self.k8s_client.apply_manifest(
                    args.get("manifest_yaml"),
                    namespace=args.get("namespace", "default")
                )
            elif name == "get_node_metrics":
                return self.k8s_client.get_node_metrics()
            
            elif name == "list_services":
                return self.k8s_client.list_services(namespace=args.get("namespace", "default"))
            elif name == "get_service_details":
                return self.k8s_client.get_service_details(args.get("name"), namespace=args.get("namespace", "default"))
            elif name == "list_configmaps":
                return self.k8s_client.list_configmaps(namespace=args.get("namespace", "default"))
            elif name == "get_configmap_details":
                return self.k8s_client.get_configmap_details(args.get("name"), namespace=args.get("namespace", "default"))
            elif name == "list_secrets":
                return self.k8s_client.list_secrets(namespace=args.get("namespace", "default"))
            elif name == "get_secret_details":
                return self.k8s_client.get_secret_details(args.get("name"), namespace=args.get("namespace", "default"))
            elif name == "list_nodes":
                return self.k8s_client.list_nodes()
            elif name == "get_node_details":
                return self.k8s_client.get_node_details(args.get("name"))
            elif name == "get_cluster_info":
                return self.k8s_client.get_cluster_info()
            
            # --- Legacy MCP fallbacks ---
            elif name == "analyze_cluster":
                return self.k8sgpt_mcp.analyze_cluster()
            elif name == "query_metrics":
                return self.grafana_mcp.query_metrics(args.get("query"))
            elif name == "query_db":
                return self.db_mcp.query_db(args.get("query"))
            
            return {"error": f"Tool '{name}' not found"}
        except Exception as e:
            return {"error": f"Tool execution failed: {str(e)}"}

    def run_step(self, skill, user_query, session_messages):
        """
        Executes a ReAct loop with selective tool injection.
        
        Logic:
        1. Check if the query needs live environment tools
        2. If YES: pass tool definitions to the LLM and enter ReAct loop
        3. If NO: just call the LLM for a direct answer (fast path)
        4. Always yield chunks for streaming UI
        """
        # 1. Universal RAG context
        context = self.memory.retrieve_context(user_query)
        prompt_prefix = f"Relevant Context from Documentation/History:\n{context}\n\n" if context else ""
        current_messages = session_messages + [
            {"role": "user", "content": f"{prompt_prefix}User Query: {user_query}"}
        ]
        
        # 2. Intent detection: does this query need live tools?
        env_keywords = [
            "pod", "pods", "cluster", "node", "nodes", "deploy", "namespace",
            "service", "services", "secret", "secrets", "configmap", "configmaps",
            "log", "logs", "metric", "metrics", "alert",
            "database", "sql", "table", "schema",
            "repo", "repository", "pr", "pull request", "issue",
            "artifact", "image", "scan",
            "health", "status", "running", "crashed", "error",
            "analyze", "triage", "diagnose", "describe", "inspect", "info", "version",
            "exec", "run", "cmd", "command", "events", "event",
            "delete", "remove", "create", "apply", "update", "top", "usage", "resource"
        ]
        query_lower = user_query.lower()
        needs_tools = any(keyword in query_lower for keyword in env_keywords)
        
        if not needs_tools:
            # === FAST PATH: General knowledge question ===
            # No tools, just stream the answer directly
            response_stream = self.brain.get_response(skill, current_messages, tools=None, stream=True)
            if isinstance(response_stream, str):
                yield {"message": {"content": response_stream}}
                return
            for chunk in response_stream:
                yield chunk
            return
        
        # === TOOL PATH: ReAct loop ===
        tools = self.get_tool_definitions()
        
        for i in range(5):  # Max 5 iterations to prevent infinite loops
            # Non-streaming call to check for tool calls
            response = self.brain.get_response(skill, current_messages, tools=tools, stream=False)
            
            # Handle error responses
            if isinstance(response, str):
                yield {"message": {"content": response}}
                return
            
            # A. Access message components safely (handles both dict and object/pydantic results)
            if hasattr(response, 'message'):
                message = response.message
                content = getattr(message, 'content', "")
                tool_calls = getattr(message, 'tool_calls', [])
            else:
                message = response.get("message", {})
                content = message.get("content", "")
                tool_calls = message.get("tool_calls", [])
            
            # 1. Check if model wants to call tools (structured tool_calls from Ollama)
            if tool_calls:
                current_messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})
                
                for tool_call in tool_calls:
                    # Handle both dict and object tool calls
                    if hasattr(tool_call, 'function'):
                        name = tool_call.function.name
                        args = tool_call.function.arguments
                    else:
                        name = tool_call["function"]["name"]
                        args = tool_call["function"]["arguments"]
                    
                    # Notify UI
                    yield {"status": f"🔧 Executing {name}..."}
                    
                    # Execute and add result to conversation
                    result = self.execute_tool(name, args)
                    current_messages.append({
                        "role": "tool",
                        "name": name,
                        "content": json.dumps(result) if isinstance(result, dict) else str(result)
                    })
                
                # Continue loop so LLM can see tool results and respond
                continue
            
            # 2. Fallback: Detection of tool calls embedded as JSON text in content
            # This handles models that output raw JSON instead of using structured calls.
            if content and (('"name"' in content or '"function"' in content) and '"arguments"' in content):
                try:
                    # Robust search: Find the first substring that looks like a JSON object
                    # We look for something that contains name/function and arguments
                    potential_json = None
                    
                    # Try to find the start of a JSON object
                    start_idx = content.find('{')
                    if start_idx != -1:
                        # Extract from the first '{' to the last '}'
                        end_idx = content.rfind('}')
                        if end_idx != -1 and end_idx > start_idx:
                            potential_json = content[start_idx:end_idx+1].strip()
                    
                    if potential_json:
                        try:
                            tool_json = json.loads(potential_json)
                            # Handle different possible JSON schemas for tool calls
                            name = tool_json.get("name") or tool_json.get("function", {}).get("name")
                            args = tool_json.get("arguments", {})
                            
                            if not name and "name" in tool_json: name = tool_json["name"]
                            
                            if name:
                                # Normalization map - bridge legacy names to native tools
                                name_map = {
                                    "pods_list_in_namespace": "list_pods",
                                    "pods_list": "list_pods",
                                    "pods_log": "get_pod_logs",
                                    "pods_get": "list_pods",
                                    "get_pods": "list_pods",
                                    "list_namespaces": "list_namespaces",
                                    "get_cluster_info": "get_cluster_info",
                                    "list_services": "list_services",
                                    "list_nodes": "list_nodes",
                                    "list_secrets": "list_secrets",
                                    "list_configmaps": "list_configmaps",
                                    "get_node_metrics": "get_node_metrics"
                                }
                                mapped_name = name_map.get(name, name)
                                
                                # Verify against active toolset
                                active_tools = [t["function"]["name"] for t in tools]
                                if mapped_name in active_tools:
                                    yield {"status": f"🔧 Executing {mapped_name}..."}
                                    
                                    # Execute
                                    result = self.execute_tool(mapped_name, args)
                                    
                                    # Formulate a dedicated summary prompt
                                    summary_prompt = [
                                        {"role": "user", "content": f"Task: {user_query}\n\nI ran the tool '{mapped_name}' with these arguments: {json.dumps(args)}.\n\nThe cluster returned: {json.dumps(result, indent=2)}\n\nPlease provide a helpful summary of this information for me. Keep it conversational."}
                                    ]
                                    
                                    # Call the brain again to get the final human-readable answer
                                    final_stream = self.brain.get_response(skill, summary_prompt, tools=None, stream=True)
                                    
                                    if isinstance(final_stream, str):
                                        yield {"message": {"content": final_stream}}
                                    else:
                                        for chunk in final_stream:
                                            yield chunk
                                    return
                        except Exception as json_err:
                            print(f"DEBUG: Failed to parse potential JSON: {json_err}")
                except Exception as outer_err:
                    print(f"DEBUG: Fallback tool interception failed: {outer_err}")
            
            # 3. Final answer path — handled if no tools were called or if fallback failed
            if content:
                # If content still looks like JSON but we haven't processed it, it's likely a malformed tool call
                if '"name"' in content and '"arguments"' in content:
                    yield {"message": {"content": "I intercepted a request to check your cluster, but the formatting was slightly off. I'm retrying with a standard request..."}}
                    # One last attempt without tools to give a generic answer
                    final_res = self.brain.get_response(skill, current_messages, tools=None, stream=True)
                    if isinstance(final_res, str):
                        yield {"message": {"content": final_res}}
                    else:
                        for chunk in final_res:
                            yield chunk
                    return
                else:
                    yield {"message": {"content": content}}
                return
            
            # Edge case: no content AND no tool calls after tool results
            # Call one more time with streaming for the final answer
            if i > 0:
                final_stream = self.brain.get_response(skill, current_messages, tools=None, stream=True)
                if isinstance(final_stream, str):
                    yield {"message": {"content": final_stream}}
                    return
                for chunk in final_stream:
                    yield chunk
                return
            
            # Fallback: empty response on first iteration
            yield {"message": {"content": "I wasn't able to generate a response. Please try rephrasing your question."}}
            return

    def extract_thinking(self, text):
        """Extracts text within <think> tags for reasoning models."""
        if not text:
            return None, ""
        match = re.search(r'<think>(.*?)</think>', text, re.DOTALL)
        if match:
            return match.group(1).strip(), text.replace(match.group(0), "").strip()
        return None, text

    def langgraph_statemachine_placeholder(self):
        """
        [TODO] Integration for 'LangGraph-lite' StateMachine.
        This will manage state transitions and Human-in-the-Loop (HITL) 
        approvals for destructive Kubernetes actions.
        """
        pass
