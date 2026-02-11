import requests
import json

class OpenSourceLLM:
    def __init__(self, model_name="llama3"):
        self.model_name = model_name
        self.api_url = "http://localhost:11434/api/generate" # Default Ollama port

    def generate(self, prompt, system_prompt=None):
        """
        Tries to call a local Ollama instance. Falls back to mock if offline.
        """
        full_prompt = f"System: {system_prompt}\nUser: {prompt}" if system_prompt else prompt
        
        try:
            payload = {
                "model": self.model_name,
                "prompt": full_prompt,
                "stream": False
            }
            response = requests.post(self.api_url, json=payload, timeout=2)
            if response.status_code == 200:
                return response.json().get("response", "")
        except:
            pass
        
        # Fallback Mock (if no local model running)
        return f"[Mock {self.model_name} Output]: I have analyzed the context provided."
