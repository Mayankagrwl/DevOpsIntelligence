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
        Compact tool definitions — minimized descriptions for faster LLM inference.
        Each description is kept under 10 words to reduce token overhead.
        """
        def _tool(name, desc, props=None, required=None):
            """Helper to build a tool definition concisely."""
            t = {"type": "function", "function": {"name": name, "description": desc, "parameters": {"type": "object", "properties": props or {}}}}
            if required:
                t["function"]["parameters"]["required"] = required
            return t

        ns = {"namespace": {"type": "string", "description": "K8s namespace"}}
        ns_name = {**ns, "name": {"type": "string", "description": "Resource name"}}

        return [
            _tool("list_pods", "List pods in namespace", ns),
            _tool("list_deployments", "List deployments in namespace", ns),
            _tool("list_namespaces", "List all cluster namespaces"),
            _tool("get_pod_logs", "Get pod logs", {**ns_name, "tail": {"type": "integer", "description": "Lines"}}, ["name"]),
            _tool("get_pod_details", "Describe a pod", ns_name, ["name"]),
            _tool("get_deployment_details", "Describe a deployment", ns_name, ["name"]),
            _tool("get_events", "Get namespace events", ns),
            _tool("list_services", "List services in namespace", ns),
            _tool("get_service_details", "Describe a service", ns_name, ["name"]),
            _tool("list_configmaps", "List configmaps", ns),
            _tool("get_configmap_details", "Describe a configmap", ns_name, ["name"]),
            _tool("list_secrets", "List secrets", ns),
            _tool("get_secret_details", "Describe a secret", ns_name, ["name"]),
            _tool("list_nodes", "List cluster nodes"),
            _tool("get_node_details", "Describe a node", {"name": {"type": "string", "description": "Node name"}}, ["name"]),
            _tool("get_cluster_info", "Get cluster version info"),
            _tool("delete_resource", "Delete a K8s resource", {"kind": {"type": "string", "description": "Resource kind"}, **ns_name}, ["kind", "name"]),
            _tool("create_namespace", "Create a namespace", {"name": {"type": "string", "description": "Namespace name"}}, ["name"]),
            _tool("apply_manifest", "Apply YAML manifest", {"manifest_yaml": {"type": "string", "description": "YAML content"}, **ns}, ["manifest_yaml"]),
            _tool("get_node_metrics", "Get node CPU/memory usage"),
            _tool("get_resource_manifest", "Get clean YAML for cloning", {"kind": {"type": "string"}, "name": {"type": "string"}, **ns}, ["kind", "name"]),
            _tool("exec_command", "Exec command in pod", {"pod_name": {"type": "string", "description": "Pod name"}, "command": {"type": "string", "description": "Shell command"}, **ns, "container": {"type": "string", "description": "Container name"}}, ["pod_name", "command"]),
            _tool("query_metrics", "Query Prometheus metrics", {"query": {"type": "string", "description": "PromQL query"}}, ["query"]),
            _tool("query_db", "Execute SQL query", {"query": {"type": "string", "description": "SQL query"}}, ["query"]),
            _tool("scale_deployment", "Scale deployment replicas", {**ns_name, "replicas": {"type": "integer", "description": "Replica count"}}, ["name", "replicas"]),
            _tool("restart_deployment", "Restart a deployment (rollout)", ns_name, ["name"]),
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
            elif name == "get_resource_manifest":
                return self.k8s_client.get_resource_manifest(
                    args.get("kind"),
                    args.get("name"),
                    namespace=args.get("namespace", "default")
                )
            elif name == "scale_deployment":
                return self.k8s_client.scale_deployment(
                    args.get("name"),
                    args.get("replicas", 1),
                    namespace=args.get("namespace", "default")
                )
            elif name == "restart_deployment":
                return self.k8s_client.restart_deployment(
                    args.get("name"),
                    namespace=args.get("namespace", "default")
                )
            
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
            "delete", "remove", "create", "apply", "update", "top", "usage", "resource",
            "scale", "restart", "rollout", "replicas", "deploy", "duplicate", "clone", "copy"
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
        
        # === FAST-PATH SHORT-CIRCUIT ===
        # For simple, unambiguous queries, skip the LLM and execute directly.
        fast_map = {
            "list pods": ("list_pods", {}),
            "get pods": ("list_pods", {}),
            "show pods": ("list_pods", {}),
            "list nodes": ("list_nodes", {}),
            "get nodes": ("list_nodes", {}),
            "show nodes": ("list_nodes", {}),
            "list namespaces": ("list_namespaces", {}),
            "get namespaces": ("list_namespaces", {}),
            "show namespaces": ("list_namespaces", {}),
            "list services": ("list_services", {}),
            "get services": ("list_services", {}),
            "show services": ("list_services", {}),
            "get events": ("get_events", {}),
            "show events": ("get_events", {}),
            "cluster info": ("get_cluster_info", {}),
            "node metrics": ("get_node_metrics", {}),
            "top nodes": ("get_node_metrics", {}),
        }
        
        # Check for namespace-specific patterns like "list pods in kube-system"
        ns_match = re.match(r'(?:list|get|show)\s+(pods|services|deployments|events|configmaps|secrets)\s+(?:in\s+)?(\S+)', query_lower)
        
        fast_tool = None
        fast_args = {}
        
        if ns_match:
            resource_map = {
                "pods": "list_pods", "services": "list_services",
                "deployments": "list_deployments", "events": "get_events",
                "configmaps": "list_configmaps", "secrets": "list_secrets",
            }
            fast_tool = resource_map.get(ns_match.group(1))
            fast_args = {"namespace": ns_match.group(2)}
        elif query_lower.strip() in fast_map:
            fast_tool, fast_args = fast_map[query_lower.strip()]
        
        if fast_tool:
            yield {"status": f"⚡ Fast-path: Executing {fast_tool}..."}
            result = self.execute_tool(fast_tool, fast_args)
            
            # Ask LLM to format the result nicely (streaming)
            summary_prompt = [
                {"role": "user", "content": f"Task: {user_query}\n\nTool '{fast_tool}' returned:\n{json.dumps(result, indent=2)}\n\nProvide a helpful summary. Use tables where appropriate."}
            ]
            final_stream = self.brain.get_response(skill, summary_prompt, tools=None, stream=True)
            if isinstance(final_stream, str):
                yield {"message": {"content": final_stream}}
            else:
                for chunk in final_stream:
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
            
            # 3. Final answer path — no tools were called
            if content:
                # If content still looks like JSON but we haven't processed it
                if '"name"' in content and '"arguments"' in content:
                    yield {"message": {"content": "I intercepted a request to check your cluster, but the formatting was slightly off. I'm retrying with a standard request..."}}
                    final_res = self.brain.get_response(skill, current_messages, tools=None, stream=True)
                    if isinstance(final_res, str):
                        yield {"message": {"content": final_res}}
                    else:
                        for chunk in final_res:
                            yield chunk
                    return
                
                # AUTO-APPLY SAFETY NET: If LLM outputs YAML manifest as text instead of calling apply_manifest
                if 'apiVersion:' in content and 'kind:' in content:
                    import re as yaml_re
                    # Extract YAML from fenced code blocks or inline
                    yaml_match = yaml_re.search(r'```(?:ya?ml)?\s*\n(.*?)```', content, yaml_re.DOTALL)
                    if yaml_match:
                        manifest_yaml = yaml_match.group(1).strip()
                    else:
                        # Try to extract bare YAML (lines starting with apiVersion)
                        lines = content.split('\n')
                        yaml_lines = []
                        in_yaml = False
                        for line in lines:
                            if line.strip().startswith('apiVersion:'):
                                in_yaml = True
                            if in_yaml:
                                if line.strip() == '' and yaml_lines and not yaml_lines[-1].strip().startswith('-'):
                                    break
                                yaml_lines.append(line)
                        manifest_yaml = '\n'.join(yaml_lines).strip()
                    
                    if manifest_yaml and 'apiVersion:' in manifest_yaml:
                        yield {"status": "🔧 Auto-applying detected manifest..."}
                        result = self.execute_tool("apply_manifest", {"manifest_yaml": manifest_yaml})
                        
                        summary_prompt = [
                            {"role": "user", "content": f"Task: {user_query}\n\nI applied the manifest and got:\n{json.dumps(result, indent=2)}\n\nProvide a brief summary of what was deployed."}
                        ]
                        final_stream = self.brain.get_response(skill, summary_prompt, tools=None, stream=True)
                        if isinstance(final_stream, str):
                            yield {"message": {"content": final_stream}}
                        else:
                            for chunk in final_stream:
                                yield chunk
                        return
                
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
