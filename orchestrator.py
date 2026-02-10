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
        """Returns tool definitions for Ollama's native tool calling."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "list_pods",
                    "description": "List all pods in a given Kubernetes namespace. Use this when the user asks about running pods, workloads, or deployments in their cluster.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "namespace": {"type": "string", "description": "The K8s namespace (default: default)"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_pod_logs",
                    "description": "Retrieve logs for a specific pod. Use when the user asks to see logs or debug a specific pod.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pod_name": {"type": "string", "description": "Name of the pod"},
                            "namespace": {"type": "string", "description": "The K8s namespace"}
                        },
                        "required": ["pod_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "analyze_cluster",
                    "description": "Perform full cluster health analysis using K8sGPT. Use when asked about cluster health, issues, or diagnostics.",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "query_metrics",
                    "description": "Query Grafana/Prometheus metrics using PromQL. Use when user asks about CPU, memory, network, or other metrics.",
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
                    "description": "Execute a SQL query against the database. Use when user asks to query, audit, or inspect database tables.",
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
        """Routes a tool call to the correct MCP client."""
        try:
            if name == "list_pods":
                return self.k8s_client.list_pods(args.get("namespace", "default"))
            elif name == "get_pod_logs":
                return self.k8s_client.get_pod_logs(args.get("pod_name"), args.get("namespace", "default"))
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
            
            message = response.get("message", {})
            content = message.get("content", "")
            
            # Check if model wants to call tools (structured tool_calls from Ollama)
            if message.get("tool_calls"):
                current_messages.append(message)
                
                for tool_call in message["tool_calls"]:
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
            
            # No tool calls — this is the final answer
            if content:
                # We already have the content from the non-streaming call
                yield response
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
