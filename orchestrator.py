import os
import re
from brain import OllamaBrain
from memory import DevOpsMemory
from mcp_client import K8sMCPClient, ChromaMCPClient, DatabaseMCPClient, GrafanaMCPClient, K8sGPTMCPClient
import json

class DevOpsOrchestrator:
    def __init__(self):
        self.brain = OllamaBrain()
        self.memory = DevOpsMemory()
        self.k8s_client = K8sMCPClient()
        self.chroma_mcp = ChromaMCPClient()
        self.db_mcp = DatabaseMCPClient()
        self.grafana_mcp = GrafanaMCPClient()
        self.k8sgpt_mcp = K8sGPTMCPClient()
        
    def get_tool_definitions(self):
        """
        Tool definitions for Ollama — names match containers/kubernetes-mcp-server.
        These are the names the LLM will output, and execute_tool will route them.
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": "pods_list_in_namespace",
                    "description": "List all Kubernetes pods in a specific namespace. Use when user asks about pods, workloads, or deployments in a namespace.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "namespace": {"type": "string", "description": "Namespace to list pods from (required)"}
                        },
                        "required": ["namespace"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "pods_list",
                    "description": "List all Kubernetes pods across ALL namespaces. Use when user asks about all pods in the cluster without specifying a namespace.",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "pods_log",
                    "description": "Get logs from a specific Kubernetes pod. Use when the user asks to see logs or debug a specific pod.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Name of the Pod to get logs from"},
                            "namespace": {"type": "string", "description": "Namespace of the Pod"},
                            "tail": {"type": "integer", "description": "Number of lines from end (default: 100)"}
                        },
                        "required": ["name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "pods_get",
                    "description": "Get details of a specific Kubernetes pod by name.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Name of the Pod"},
                            "namespace": {"type": "string", "description": "Namespace of the Pod"}
                        },
                        "required": ["name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "namespaces_list",
                    "description": "List all Kubernetes namespaces in the cluster.",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "events_list",
                    "description": "List Kubernetes events for debugging and troubleshooting.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "namespace": {"type": "string", "description": "Optional namespace to filter events"}
                        }
                    }
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
        """Routes tool calls to the correct MCP client."""
        try:
            # --- K8s MCP tools (containers/kubernetes-mcp-server) ---
            if name == "pods_list_in_namespace":
                return self.k8s_client.list_pods(namespace=args.get("namespace"))
            elif name == "pods_list":
                return self.k8s_client.list_pods()
            elif name == "pods_log":
                return self.k8s_client.get_pod_logs(args.get("name"), namespace=args.get("namespace"))
            elif name == "pods_get":
                return self.k8s_client.get_pod(args.get("name"), namespace=args.get("namespace"))
            elif name == "namespaces_list":
                return self.k8s_client.list_namespaces()
            elif name == "events_list":
                return self.k8s_client.list_events(namespace=args.get("namespace"))
            # --- Legacy tool names (fallback for models that use our old names) ---
            elif name == "list_pods":
                return self.k8s_client.list_pods(namespace=args.get("namespace", "default"))
            elif name == "get_pod_logs":
                return self.k8s_client.get_pod_logs(args.get("pod_name") or args.get("name"), namespace=args.get("namespace"))
            elif name == "analyze_cluster":
                return self.k8sgpt_mcp.analyze_cluster()
            # --- Other MCP tools ---
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
            "pod", "pods", "cluster", "node", "deploy", "namespace",
            "log", "logs", "metric", "metrics", "alert",
            "database", "sql", "table", "schema",
            "repo", "repository", "pr", "pull request", "issue",
            "artifact", "image", "scan",
            "health", "status", "running", "crashed", "error",
            "analyze", "triage", "diagnose"
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
            
            # 2. Fallback: Foolproof detection of tool calls embedded as JSON TEXT in content
            # This handles cases where models don't use the official API but still try to use tools.
            if content and ('"name"' in content or '"arguments"' in content):
                try:
                    # Search for the outermost JSON-like structure in the content
                    # We look for something starting with { and ending with }
                    match = re.search(r'(\{.*\})', content, re.DOTALL)
                    if match:
                        obj_str = match.group(1)
                        try:
                            tool_json = json.loads(obj_str)
                            name = tool_json.get("name")
                            args = tool_json.get("arguments", {})
                            
                            # Normalization map
                            name_map = {
                                "list_pods": "pods_list_in_namespace",
                                "pods_list": "pods_list_in_namespace",
                                "get_pod_logs": "pods_log",
                                "pods_get": "pods_get"
                            }
                            mapped_name = name_map.get(name, name)
                            
                            if mapped_name and (mapped_name in [t["function"]["name"] for t in tools]):
                                yield {"status": f"🔧 Intercepted tool call: {mapped_name}..."}
                                
                                # Execute
                                result = self.execute_tool(mapped_name, args)
                                
                                # Force a summary response
                                summary_msg = [
                                    {"role": "assistant", "content": content},
                                    {"role": "user", "content": f"The tool '{mapped_name}' returned:\n{json.dumps(result, indent=2)}\n\nSummarize this for me in a natural, helpful way. Skip any raw technical details."}
                                ]
                                final_res = self.brain.get_response(skill, current_messages + summary_msg, tools=None, stream=True)
                                
                                if isinstance(final_res, str):
                                    yield {"message": {"content": final_res}}
                                else:
                                    for chunk in final_res:
                                        yield chunk
                                return
                        except:
                            pass
                except Exception as e:
                    pass # Fall through if regex or logic fails
            
            # 3. Final answer — regular text content
            # If we reached here and haven't returned, this is the final answer.
            # Safety: If it looks like JSON, but we couldn't execute it, don't show it as a final answer.
            if content:
                if '{"name":' in content and '"arguments":' in content:
                    yield {"message": {"content": "I tried to fetch that information for you but encountered a formatting issue. Could you please specify which pods or namespace you're interested in?"}}
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
