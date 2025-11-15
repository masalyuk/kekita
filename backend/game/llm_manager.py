"""LLMManager class for Ollama API integration."""

import aiohttp


class LLMManager:
    """Manage local LLM inference via Ollama."""

    def __init__(self, model_name: str = "qwen2:0.5b", ollama_url: str = "http://localhost:11434"):
        """
        Initialize LLM manager.
        
        Args:
            model_name: Ollama model name
            ollama_url: Ollama server URL
        """
        self.model_name = model_name
        self.ollama_url = ollama_url
        self.session = None

    async def initialize(self):
        """Create async HTTP session."""
        self.session = aiohttp.ClientSession()

    async def generate(self, prompt: str, max_tokens: int = 15) -> str:
        """
        Call Ollama API to generate LLM response.
        
        Args:
            prompt: Input prompt text
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated text response
        """
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "num_predict": max_tokens,
                "stop": ["\n", ".", "\n\n"]
            }
        }

        try:
            async with self.session.post(
                f"{self.ollama_url}/api/generate",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=2.0)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("response", "").strip()
                else:
                    error_text = await resp.text()
                    raise Exception(f"Ollama API error: {resp.status} - {error_text}")
        except aiohttp.ClientError as e:
            print(f"LLM call failed (network error): {e}")
            raise
        except Exception as e:
            print(f"LLM call failed: {e}")
            raise

    async def close(self):
        """Close HTTP session."""
        if self.session:
            await self.session.close()

