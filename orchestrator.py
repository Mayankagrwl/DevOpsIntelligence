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
        """Returns tool definitions for Ollama based on MCP capabilities."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "list_pods",
                    "description": "List all pods in a given namespace",
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
                    "description": "Retrieve logs for a specific pod",
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
                    "description": "Perform full cluster analysis using K8sGPT",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "query_metrics",
                    "description": "Query Grafana/Prometheus metrics",
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
                    "description": "Execute a SQL query against the database",
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
        return {"error": f"Tool {name} not found"}

    def run_step(self, skill, user_query, session_messages):
        """
        Executes a multi-turn ReAct loop using tool calling.
        Yields chunks for streaming UI support.
        """
        # 1. Universal RAG
        context = self.memory.retrieve_context(user_query)
        prompt_prefix = f"Relevant Context from Documentation/History:\n{context}\n\n" if context else ""
        current_messages = session_messages + [{"role": "user", "content": f"{prompt_prefix}User Query: {user_query}"}]
        
        tools = self.get_tool_definitions()
        
        # Limit loop to prevent infinite runs
        for _ in range(5):
            response = self.brain.get_response(skill, current_messages, tools=tools, stream=False)
            message = response.get("message", {})
            
            # If the model wants to call tools
            if "tool_calls" in message and message["tool_calls"]:
                current_messages.append(message)
                
                for tool in message["tool_calls"]:
                    name = tool["function"]["name"]
                    args = tool["function"]["arguments"]
                    
                    # Notify UI of tool execution via a custom yield format
                    yield {"status": f"🔧 Executing {name}...", "tool": name, "args": args}
                    
                    result = self.execute_tool(name, args)
                    current_messages.append({
                        "role": "tool",
                        "name": name,
                        "content": json.dumps(result)
                    })
                
                # After tool results are added, loop back to let the LLM reason
                continue
            
            # If no tools, it's the final turn - stream it to the UI
            if "tool_calls" not in message or not message["tool_calls"]:
                final_stream = self.brain.get_response(skill, current_messages, tools=tools, stream=True)
                for chunk in final_stream:
                    yield chunk
                break
            
            break

    def langgraph_statemachine_placeholder(self):
        """
        [TODO] Integration for 'LangGraph-lite' StateMachine.
        This will manage state transitions and Human-in-the-Loop (HITL) 
        approvals for destructive Kubernetes actions.
        """
        # Future state machine logic goes here
        pass

    def extract_thinking(self, text):
        """Extracts text within <think> tags for deepseek models."""
        if not text: return None, ""
        match = re.search(r'<think>(.*?)</think>', text, re.DOTALL)
        if match:
            return match.group(1).strip(), text.replace(match.group(0), "").strip()
        return None, text
