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
                "default_model": "deepseek-r1:8b"
            },
            "K8s Specialist": {
                "model_key": "MODEL_K8S",
                "prompt_key": "PROMPT_K8S_SPECIALIST",
                "default_model": "qwen2.5-coder:7b"
            },
            "SRE": {
                "model_key": "MODEL_SRE",
                "prompt_key": "PROMPT_SRE_OBSERVABILITY",
                "default_model": "llama3.1:8b"
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
                "default_model": "gemma3:4b"
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
        system_prompt = config.get("prompt") or os.getenv(config.get("prompt_key"), "")
        
        # Prepare messages for Ollama
        ollama_messages = [{"role": "system", "content": system_prompt}] + messages
        
        try:
            return self.client.chat(
                model=model, 
                messages=ollama_messages, 
                tools=tools,
                stream=stream
            )
        except Exception as e:
            return f"Error communicating with Ollama: {str(e)}"

    def check_ollama_status(self):
        """Checks if Ollama is reachable."""
        try:
            self.client.list()
            return True
        except:
            return False
