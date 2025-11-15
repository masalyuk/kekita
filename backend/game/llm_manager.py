"""LLMManager class for Ollama API integration."""

import aiohttp
import json
import re


class LLMManager:
    """Manage local LLM inference via Ollama."""

    def __init__(self, model_name: str = "gemma3:1b", ollama_url: str = "http://localhost:11434"):
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

    async def chat(self, prompt: str, max_tokens: int = 15) -> str:
        """
        Call Ollama chat API to generate LLM response using chat format.
        Each call creates a fresh chat session with no conversation history.
        
        Args:
            prompt: Input prompt text (will be sent as user message)
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated text response
        """
        if not self.session:
            raise Exception("LLM session not initialized")
        
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "stream": False,
            "options": {
                "temperature": 0.3,
                "num_predict": max_tokens,
                "stop": ["\n", ".", "\n\n"]
            }
        }

        try:
            async with self.session.post(
                f"{self.ollama_url}/api/chat",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=2.0)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Chat API returns message object with content
                    message = data.get("message", {})
                    return message.get("content", "").strip()
                else:
                    error_text = await resp.text()
                    raise Exception(f"Ollama API error: {resp.status} - {error_text}")
        except aiohttp.ClientError as e:
            print(f"LLM chat call failed (network error): {e}")
            raise
        except Exception as e:
            print(f"LLM chat call failed: {e}")
            raise

    async def parse_prompt(self, prompt_text: str) -> str:
        """
        Parse a creature description prompt using LLM to extract traits.
        
        Args:
            prompt_text: Player's natural language description of their creature
            
        Returns:
            JSON string with extracted traits
        """
        if not self.session:
            raise Exception("LLM session not initialized")
        
        extraction_prompt = f"""Analyze this creature description and extract traits. Return ONLY valid JSON, no explanations.

Description: "{prompt_text}"

Extract these traits:
- color: MUST be one of: blue, red, green, yellow, purple, orange, pink, cyan, brown, black, white
- speed: integer 1-5 where 1=very slow, 3=average, 5=very fast
- diet: MUST be one of: herbivore, carnivore, omnivore
- population: integer number (use 20 if not mentioned)
- social: MUST be one of: social, solitary
- aggression: MUST be one of: low, medium, high
- size: MUST be one of: small, medium, large

Return ONLY this JSON format (no markdown, no code blocks, no extra text):
{{"color": "blue", "speed": 4, "diet": "herbivore", "population": 20, "social": "social", "aggression": "low", "size": "small"}}"""
        
        payload = {
            "model": self.model_name,
            "prompt": extraction_prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,  # Higher temperature for more creative/varied parsing
                "num_predict": 200,
                "stop": ["\n\n", "```", "```json"]
            }
        }
        
        print(f"[LLMManager] Sending prompt to LLM: {extraction_prompt[:100]}...")

        try:
            async with self.session.post(
                f"{self.ollama_url}/api/generate",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=5.0)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    response = data.get("response", "").strip()
                    print(f"[LLMManager] Raw LLM response: {response[:300]}...")
                    # Extract JSON from response (handle cases where LLM adds extra text)
                    # Try to find JSON object in response (handle nested objects)
                    # Find first { and match balanced braces
                    start_idx = response.find('{')
                    if start_idx != -1:
                        brace_count = 0
                        end_idx = start_idx
                        for i in range(start_idx, len(response)):
                            if response[i] == '{':
                                brace_count += 1
                            elif response[i] == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    end_idx = i + 1
                                    break
                        if brace_count == 0:
                            extracted = response[start_idx:end_idx]
                            print(f"[LLMManager] Extracted JSON: {extracted}")
                            return extracted
                    print(f"[LLMManager] No JSON found in response, returning full response")
                    return response
                else:
                    error_text = await resp.text()
                    raise Exception(f"Ollama API error: {resp.status} - {error_text}")
        except aiohttp.ClientError as e:
            print(f"LLM parse_prompt failed (network error): {e}")
            raise
        except Exception as e:
            print(f"LLM parse_prompt failed: {e}")
            raise

    async def merge_traits(self, current_traits: dict, evolution_description: str) -> str:
        """
        Intelligently merge current traits with evolution description using LLM.
        
        Args:
            current_traits: Dict with existing creature traits (color, speed, diet, etc.)
            evolution_description: Player's description of how the creature evolved
            
        Returns:
            JSON string with merged traits (preserves unchanged traits, updates only what's mentioned)
        """
        if not self.session:
            raise Exception("LLM session not initialized")
        
        # Format current traits for the prompt
        current_traits_str = json.dumps(current_traits, indent=2)
        
        merge_prompt = f"""Merge creature traits intelligently. Current traits and evolution description are provided.

Current traits:
{current_traits_str}

Evolution description: "{evolution_description}"

Instructions:
- PRESERVE all existing traits that are NOT mentioned in the evolution description
- UPDATE only traits that are explicitly mentioned or changed in the evolution description
- If evolution description mentions a new color, use that color
- If evolution description does NOT mention color, keep the existing color from current traits
- Same logic applies to all traits: speed, diet, population, social, aggression, size

Return ONLY valid JSON with all traits (no markdown, no code blocks, no extra text):
- color: MUST be one of: blue, red, green, yellow, purple, orange, pink, cyan, brown, black, white
- speed: integer 1-5 where 1=very slow, 3=average, 5=very fast
- diet: MUST be one of: herbivore, carnivore, omnivore
- population: integer number
- social: MUST be one of: social, solitary
- aggression: MUST be one of: low, medium, high
- size: MUST be one of: small, medium, large

Return ONLY this JSON format:
{{"color": "blue", "speed": 4, "diet": "herbivore", "population": 20, "social": "social", "aggression": "low", "size": "small"}}"""
        
        payload = {
            "model": self.model_name,
            "prompt": merge_prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,  # Higher temperature for more creative/varied parsing
                "num_predict": 200,
                "stop": ["\n\n", "```", "```json"]
            }
        }
        
        print(f"[LLMManager] Merging traits with evolution: '{evolution_description[:50]}...'")
        
        try:
            async with self.session.post(
                f"{self.ollama_url}/api/generate",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=5.0)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    response = data.get("response", "").strip()
                    print(f"[LLMManager] Raw merge response: {response[:300]}...")
                    # Extract JSON from response (handle cases where LLM adds extra text)
                    start_idx = response.find('{')
                    if start_idx != -1:
                        brace_count = 0
                        end_idx = start_idx
                        for i in range(start_idx, len(response)):
                            if response[i] == '{':
                                brace_count += 1
                            elif response[i] == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    end_idx = i + 1
                                    break
                        if brace_count == 0:
                            extracted = response[start_idx:end_idx]
                            print(f"[LLMManager] Extracted merged JSON: {extracted}")
                            return extracted
                    print(f"[LLMManager] No JSON found in merge response, returning full response")
                    return response
                else:
                    error_text = await resp.text()
                    raise Exception(f"Ollama API error: {resp.status} - {error_text}")
        except aiohttp.ClientError as e:
            print(f"LLM merge_traits failed (network error): {e}")
            raise
        except Exception as e:
            print(f"LLM merge_traits failed: {e}")
            raise

    async def close(self):
        """Close HTTP session."""
        if self.session:
            await self.session.close()

