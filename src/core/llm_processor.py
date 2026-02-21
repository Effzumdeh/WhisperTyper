import logging
import requests
from typing import List, Optional

logger = logging.getLogger(__name__)

class LLMClient:
    """
    Client for interacting with local LLMs (like Ollama) using OpenAI-compatible APIs.
    """
    
    @staticmethod
    def fetch_ollama_models(endpoint: str) -> List[str]:
        """
        Fetches available models from an Ollama instance.
        Endpoint should be the base URL, e.g., 'http://localhost:11434'.
        """
        try:
            url = f"{endpoint.rstrip('/')}/api/tags"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            
            data = response.json()
            models = [model.get("name") for model in data.get("models", [])]
            return models
        except Exception as e:
            logger.error(f"Failed to fetch Ollama models from {endpoint}: {e}")
            return []

    @staticmethod
    def refine_text(raw_text: str, system_prompt: str, endpoint: str, model: str) -> str:
        """
        Passes the raw text through a local LLM for rewriting/refining.
        Uses the OpenAI chat completions compatibility endpoint.
        Returns the refined text, or the original raw_text if an error occurs.
        """
        if not raw_text or not raw_text.strip():
            return raw_text

        try:
            url = f"{endpoint.rstrip('/')}/v1/chat/completions"
            
            # OpenAI compatible payload structure
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": raw_text}
                ],
                "temperature": 0.3, # Keep it deterministic for rewriting
            }
            
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Extract content from response
            choices = data.get("choices", [])
            if choices and len(choices) > 0:
                refined_text = choices[0].get("message", {}).get("content", "").strip()
                if refined_text:
                    return refined_text
                    
            logger.warning("LLM response did not contain valid text. Falling back to raw text.")
            return raw_text
            
        except requests.exceptions.Timeout:
            logger.error("LLM request timed out. Falling back to raw text.")
            return raw_text
        except requests.exceptions.ConnectionError:
            logger.error(f"Could not connect to LLM at {endpoint}. Ensure the server is running.")
            return raw_text
        except Exception as e:
            logger.error(f"LLM text refinement failed: {e}")
            return raw_text
