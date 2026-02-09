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
        
    def run_step(self, skill, user_query, session_messages):
        """
        Executes a single workflow step using ReAct logic.
        """
        # 1. Universal RAG: Retrieve Context from Memory for ALL specialists
        # This ensures the LLM always has the latest documentation context
        context = self.memory.retrieve_context(user_query)
        
        # 2. Prepare Messages with RAG context
        prompt_prefix = f"Relevant Context from Documentation/History:\n{context}\n\n" if context else ""
        messages = session_messages + [{"role": "user", "content": f"{prompt_prefix}User Query: {user_query}"}]
        
        # 3. Call Brain (Stream)
        return self.brain.get_response(skill, messages, stream=True)

    def process_tool_calls(self, model_output):
        """
        Detects and executes tool calls in the model output.
        [PLACEHOLDER for ReAct Loop execution]
        """
        # Simple regex or JSON detection for tool calls in the output
        # For a standard ReAct loop, we would parse headers like 'Action: list_pods'
        pass

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
        match = re.search(r'<think>(.*?)</think>', text, re.DOTALL)
        if match:
            return match.group(1).strip(), text.replace(match.group(0), "").strip()
        return None, text
