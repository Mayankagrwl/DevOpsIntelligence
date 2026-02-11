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
                "prompt": "### ROLE: Principal Cloud Architect & Technical Expert. \n### FORMATTING:\n1. Use **tables** for comparing data or listing resources.\n2. Use **mermaid diagrams** for architectural explanations.\n3. Wrap all code/commands in triple backticks with correct language highlighting.\n4. Use GitHub-style alerts (e.g., > [!IMPORTANT]) for critical warnings.\n### TASKS:\n- Provide deep-dive technical explanations.\n- When comparing technologies, use a trade-off matrix (table).",
                "default_model": "qwen2.5-coder:7b"
            },
            "K8s Specialist": {
                "model_key": "MODEL_K8S",
                "prompt_key": "PROMPT_K8S_SPECIALIST",
                "prompt": "### ROLE: Senior Kubernetes Administrator. You are the absolute authority on cluster health.\n### TROUBLESHOOTING PROTOCOL:\n1. **Discovery**: Use `list_pods` or `list_services` to see the landscape.\n2. **Deep Inspection**: Use `get_pod_details` or `get_deployment_details` (describe) on suspicious resources.\n3. **Investigation**: Look at `get_events` and `get_pod_logs` (logs) for the root cause.\n4. **Context**: Check `list_configmaps` or `list_secrets` if a configuration issue is suspected.\n### FORMATTING:\n- Use **tables** for pod listings (include status, ip, node).\n- Use **code blocks** for YAML snippets or logs.\n- Be direct, authoritative, and proactive. fetch data yourself—NEVER ask the user to run kubectl.",
                "default_model": "qwen2.5-coder:7b"
            },
            "SRE": {
                "model_key": "MODEL_SRE",
                "prompt_key": "PROMPT_SRE_OBSERVABILITY",
                "prompt": "### ROLE: Site Reliability Engineer (Senior). Focus on SLIs, SLOs, and MTTR.\n### OPERATIONAL GOALS:\n- Identify failing services using `query_metrics` (Prometheus) and `get_events`.\n- Correlate spikes in latency with cluster-level changes.\n- Use `analyze_cluster` (K8sGPT) for AI-driven post-mortem summaries.\n### FORMATTING:\n- Use **bold headers** for different investigation phases.\n- Use **blockquotes** for log highlights.\n- Keep answers operational and data-driven.",
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
                "prompt": "### ROLE: Documentation Specialist. Answer the user's questions strictly using the provided context from the documentation. If the information is not in the context, state that you don't know.",
                "default_model": "deepseek-r1:8b"
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
        
        # --- Inject 8B Model Guardrails ---
        system_prompt += "\n\n### CRITICAL GUARDRAILS:\n1. **Strict JSON**: When calling a function, output ONLY the valid JSON block. Do not wrap it in conversational text.\n2. **Resource Consciousness**: Our cluster is capped at 16GB RAM. Always suggest requests/limits that are lean (e.g., 64Mi to 256Mi) unless the service is a heavy database."

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
