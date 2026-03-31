"""Abstraction layer for AI providers (Gemini or OpenRouter)."""
import requests
from logging_config import logger
from config import Config


class AIClient:
    """Unified client for both Gemini and OpenRouter APIs."""

    def __init__(self):
        """Initialize the appropriate AI client based on configuration."""
        self.use_openrouter = bool(Config.OPENROUTER_API_KEY)
        self.use_gemini = bool(Config.GOOGLE_API_KEY)

        if not self.use_openrouter and not self.use_gemini:
            raise ValueError(
                "Neither OPENROUTER_API_KEY nor GOOGLE_API_KEY is configured"
            )

        if self.use_openrouter:
            self.api_key = Config.OPENROUTER_API_KEY
            self.model = Config.OPENROUTER_MODEL
            self.provider = "OpenRouter"
            logger.info(f"Using OpenRouter with model: {self.model}")
        else:
            from google import genai
            self.client = genai.Client(api_key=Config.GOOGLE_API_KEY)
            self.api_key = Config.GOOGLE_API_KEY
            self.model = Config.GEMINI_MODEL
            self.provider = "Gemini"
            logger.info(f"Using Gemini with model: {self.model}")

    def generate_content(
        self,
        prompt: str,
        system_instruction: str = "",
        temperature: float = 0.2,
        timeout: int = 60
    ) -> str:
        """
        Generate content using the configured AI provider.

        Args:
            prompt: The user prompt/content to analyze
            system_instruction: System instruction for the model
            temperature: Temperature for response generation (0.0-1.0)
            timeout: Request timeout in seconds

        Returns:
            Generated text response
        """
        if self.use_openrouter:
            return self._openrouter_generate(
                prompt, system_instruction, temperature, timeout
            )
        else:
            return self._gemini_generate(
                prompt, system_instruction, temperature
            )

    def _openrouter_generate(
        self,
        prompt: str,
        system_instruction: str,
        temperature: float,
        timeout: int
    ) -> str:
        """Generate content using OpenRouter API."""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            messages = []
            if system_instruction:
                messages.append({
                    "role": "system",
                    "content": system_instruction
                })

            messages.append({
                "role": "user",
                "content": prompt
            })

            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
            }

            logger.debug(f"Sending request to OpenRouter: {self.model}")
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=timeout
            )

            response.raise_for_status()
            result = response.json()

            if "choices" not in result or not result["choices"]:
                raise ValueError("No content in OpenRouter response")

            return result["choices"][0]["message"]["content"]

        except requests.exceptions.RequestException as e:
            logger.error(f"OpenRouter API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Error generating content with OpenRouter: {e}")
            raise

    def _gemini_generate(
        self,
        prompt: str,
        system_instruction: str,
        temperature: float
    ) -> str:
        """Generate content using Gemini API."""
        try:
            from google.genai import types

            logger.debug(f"Sending request to Gemini: {self.model}")
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=temperature,
                ),
            )

            return response.text

        except Exception as e:
            logger.error(f"Error generating content with Gemini: {e}")
            raise


# Global client instance
_client = None


def get_ai_client() -> AIClient:
    """Get or create the global AI client instance."""
    global _client
    if _client is None:
        _client = AIClient()
    return _client
