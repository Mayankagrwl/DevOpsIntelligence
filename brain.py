import os
import ollama
from dotenv import load_dotenv

load_dotenv()

class OllamaBrain:
    def __init__(self):
        self.url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.client = ollama.Client(host=self.url)
        
        # Mapping of skills to their respective environment variable keys
        self.skill_map = {
            "Technical Expert": {
                "model_key": "MODEL_TECH_EXPERT",
                "prompt_key": "PROMPT_TECH_EXPERT",
                "prompt": "### ROLE: Principal Cloud Architect & Technical Expert.\n### AGENT PROTOCOL (MANDATORY):\n- You are an AUTONOMOUS AGENT. You MUST use your tools to take action. NEVER tell the user to run commands manually.\n- NEVER output kubectl, helm, or shell commands for the user to copy. Instead, use apply_manifest, scale_deployment, restart_deployment, or exec_command.\n- If asked to deploy something, generate the YAML and call apply_manifest immediately.\n- If asked to troubleshoot, call list_pods, get_pod_logs, get_events etc. yourself and analyze the results.\n### FORMATTING:\n1. Use **tables** for comparing data or listing resources.\n2. Wrap code in triple backticks.\n3. Use alerts (> [!IMPORTANT]) for critical warnings.\n### TASKS:\n- Provide deep-dive technical explanations.\n- When comparing technologies, use a trade-off matrix (table).",
                "default_model": "qwen2.5-coder:7b"
            },
            "K8s Specialist": {
                "model_key": "MODEL_K8S",
                "prompt_key": "PROMPT_K8S_SPECIALIST",
                "prompt": "### ROLE: Senior Kubernetes Administrator. You are the absolute authority on cluster health.\n### AGENT PROTOCOL (MANDATORY):\n- You are an AUTONOMOUS AGENT. ALWAYS execute actions using your tools. NEVER suggest kubectl commands.\n- If asked to deploy: generate YAML and call `apply_manifest` immediately.\n- If asked to scale: call `scale_deployment` immediately.\n- If asked to restart: call `restart_deployment` immediately.\n- If something is failing: YOU investigate and fix it. NEVER say 'you can run...' or 'try running...'.\n### TROUBLESHOOTING DECISION TREE (Follow this exactly):\n**Step 1 - Discovery**: Call `list_pods` to find unhealthy pods (status != Running).\n**Step 2 - For each failing pod**:\n  - If status=CrashLoopBackOff: Call `get_pod_logs` → analyze error → if config issue, fix and `apply_manifest`; if OOM, call `scale_deployment` or fix limits.\n  - If status=ImagePullBackOff: Call `get_pod_details` → check image name/tag → report exact issue.\n  - If status=Pending: Call `get_events` → check for scheduling failures (insufficient resources, node affinity) → if resources, call `get_node_metrics`.\n  - If status=Error: Call `get_pod_logs` + `get_events` → correlate timestamps → identify root cause.\n  - If status=Running but not Ready: Call `get_pod_details` → check readiness probe → call `get_pod_logs` for probe failures.\n**Step 3 - Auto-Heal**: If you can fix it (restart, scale, apply new config), DO IT immediately.\n**Step 4 - Report**: Summarize what you found, what you fixed, and what still needs attention.\n### FORMATTING:\n- Use **tables** for pod listings.\n- Use **code blocks** for YAML or logs.",
                "default_model": "qwen2.5-coder:7b"
            },
            "SRE": {
                "model_key": "MODEL_SRE",
                "prompt_key": "PROMPT_SRE_OBSERVABILITY",
                "prompt": "### ROLE: Site Reliability Engineer (Senior). Focus on SLIs, SLOs, and MTTR.\n### AGENT PROTOCOL (MANDATORY):\n- You are an AUTONOMOUS AGENT. ALWAYS take action using tools. NEVER suggest commands for the user to run.\n- Proactively investigate issues: call get_events, get_pod_logs, query_metrics, list_pods without being asked.\n- If you identify a fix (scale, restart, apply), execute it immediately.\n### OPERATIONAL GOALS:\n- Identify failing services using `query_metrics` and `get_events`.\n- Correlate latency spikes with cluster-level changes.\n### FORMATTING:\n- Use **bold headers** for investigation phases.\n- Use **blockquotes** for log highlights.",
                "default_model": "qwen2.5-coder:7b"
            },
            "GitHub Specialist": {
                "model_key": "MODEL_GITHUB",
                "prompt_key": "PROMPT_GITHUB_SPECIALIST",
                "default_model": "qwen2.5-coder:7b"
            },
            "JFrog Admin": {
                "model_key": "MODEL_JFROG",
                "prompt_key": "PROMPT_JFROG_ADMIN",
                "default_model": "qwen2.5-coder:7b"
            },
            "Database Admin": {
                "model_key": "MODEL_DB",
                "prompt_key": "PROMPT_DB_ADMIN",
                "default_model": "qwen2.5-coder:7b"
            },
            "Document Expert": {
                "model_key": "MODEL_TECH_EXPERT",
                "prompt": "### ROLE: Documentation Specialist. Answer questions using the provided context. If the information is not in the context, say so.",
                "default_model": "qwen2.5-coder:7b"
            }
        }


    def get_response(self, skill, messages, tools=None, stream=True):
        """
        Generates a response using the model assigned to the skill, resolved at runtime.
        Supports tool calling if tools are provided.
        """
        config = self.skill_map.get(skill)
        if not config:
            raise ValueError(f"Unknown skill: {skill}")
        
        # Resolve model and prompt from environment or defaults
        model = os.getenv(config["model_key"], config["default_model"])
        
        # Prefer prompt from environment variable if set, otherwise use the hardcoded default
        env_prompt_key = config.get("prompt_key")
        system_prompt = os.getenv(env_prompt_key) if env_prompt_key else None
        if not system_prompt:
            system_prompt = config.get("prompt", "")
        
        # --- Inject Global Guardrails ---
        system_prompt += "\n\n### CRITICAL GUARDRAILS:\n1. **Strict JSON**: When calling a function, output ONLY the valid JSON block.\n2. **Resource Consciousness**: Cluster is capped at 16GB RAM. Suggest lean limits (64Mi-256Mi).\n3. **NEVER SUGGEST COMMANDS**: Do NOT tell the user to run kubectl, helm, docker, or any CLI command. YOU execute actions using your tools. You are an agent, not a chatbot."

        # Prepare messages for Ollama
        ollama_messages = [{"role": "system", "content": system_prompt}] + messages
        
        # Build kwargs — only pass tools if explicitly provided
        kwargs = {
            "model": model,
            "messages": ollama_messages,
            "stream": stream,
            "options": {
                "num_ctx": 4096,      # Reduced context window for faster inference
                "num_predict": 1024,  # Cap response length
            },
        }
        if tools:
            kwargs["tools"] = tools
        
        try:
            return self.client.chat(**kwargs)
        except Exception as e:
            return f"Error communicating with Ollama: {str(e)}"

    def check_ollama_status(self):
        """Checks if Ollama is reachable."""
        try:
            self.client.list()
            return True
        except:
            return False
