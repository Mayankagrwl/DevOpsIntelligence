import os
import ollama
from dotenv import load_dotenv

load_dotenv()

class OllamaBrain:
    def __init__(self):
        self.url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.client = ollama.Client(host=self.url)
        
        # Skill to Model mapping
        self.skill_config = {
            "Technical Expert": {
                "model": os.getenv("MODEL_TECH_EXPERT", "deepseek-r1:8b"),
                "prompt": os.getenv("PROMPT_TECH_EXPERT")
            },
            "K8s Specialist": {
                "model": os.getenv("MODEL_K8S", "qwen2.5-coder:7b"),
                "prompt": os.getenv("PROMPT_K8S_SPECIALIST")
            },
            "SRE": {
                "model": os.getenv("MODEL_SRE", "llama3.1:8b"),
                "prompt": os.getenv("PROMPT_SRE_OBSERVABILITY")
            },
            "GitHub Specialist": {
                "model": os.getenv("MODEL_GITHUB", "qwen2.5-coder:7b"),
                "prompt": os.getenv("PROMPT_GITHUB_SPECIALIST")
            },
            "JFrog Admin": {
                "model": os.getenv("MODEL_JFROG", "qwen2.5-coder:7b"),
                "prompt": os.getenv("PROMPT_JFROG_ADMIN")
            },
            "Database Admin": {
                "model": os.getenv("MODEL_DB", "gemma3:4b"),
                "prompt": os.getenv("PROMPT_DB_ADMIN")
            },
            "Document Expert": {
                "model": os.getenv("MODEL_TECH_EXPERT", "deepseek-r1:8b"),
                "prompt": "### ROLE: Documentation Specialist. Answer the user's questions strictly using the provided context from the documentation. If the information is not in the context, state that you don't know."
            }
        }

    def get_response(self, skill, messages, stream=True):
        """
        Generates a response using the model assigned to the skill.
        """
        config = self.skill_config.get(skill)
        if not config:
            raise ValueError(f"Unknown skill: {skill}")
        
        model = config["model"]
        system_prompt = config["prompt"]
        
        # Prepare messages for Ollama
        ollama_messages = [{"role": "system", "content": system_prompt}] + messages
        
        try:
            if stream:
                return self.client.chat(model=model, messages=ollama_messages, stream=True)
            else:
                return self.client.chat(model=model, messages=ollama_messages, stream=False)
        except Exception as e:
            return f"Error communicating with Ollama: {str(e)}"

    def check_ollama_status(self):
        """Checks if Ollama is reachable."""
        try:
            self.client.list()
            return True
        except:
            return False
