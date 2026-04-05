"""Abstraction layer for AI providers."""
import requests
import time
import threading
from logging_config import logger
from config import Config


class AIClient:
    """Unified client for AI providers."""

    def __init__(self, provider: str = None):
        """
        Initialize the appropriate AI provider.

        Args:
            provider: Force a specific provider ('ollama', 'openrouter', 'gemini').
                      If None, auto-select based on available config.
        """
        self.provider_name = provider
        self.use_openrouter = False
        self.use_gemini = False
        self.use_ollama = False

        # Validate configuration
        has_openrouter = bool(Config.OPENROUTER_API_KEY)
        has_gemini = bool(Config.GOOGLE_API_KEY)
        has_ollama = bool(Config.OLLAMA_BASE_URL and Config.OLLAMA_MODEL)

        if not has_openrouter and not has_gemini and not has_ollama:
            raise ValueError(
                "At least one AI provider must be configured: "
                "OPENROUTER_API_KEY, GOOGLE_API_KEY, or OLLAMA_BASE_URL+OLLAMA_MODEL"
            )

        if self.provider_name == "ollama" or (provider is None and not has_openrouter and not has_gemini):
            self._init_ollama()
        elif self.provider_name == "openrouter" or (provider is None and has_openrouter):
            self._init_openrouter()
        elif self.provider_name == "gemini" or (provider is None and has_gemini):
            self._init_gemini()
        else:
            # Fallback to first available
            if has_openrouter:
                self._init_openrouter()
            elif has_gemini:
                self._init_gemini()
            elif has_ollama:
                self._init_ollama()

    def _init_openrouter(self):
        """Initialize OpenRouter provider."""
        self.use_openrouter = True
        self.api_key = Config.OPENROUTER_API_KEY
        self.model = Config.OPENROUTER_MODEL
        self.provider = "OpenRouter"
        logger.info(f"Using OpenRouter with model: {self.model}")

    def _init_gemini(self):
        """Initialize Gemini provider."""
        from google import genai
        self.use_gemini = True
        self.client = genai.Client(api_key=Config.GOOGLE_API_KEY)
        self.api_key = Config.GOOGLE_API_KEY
        self.model = Config.GEMINI_MODEL
        self.provider = "Gemini"
        logger.info(f"Using Gemini with model: {self.model}")

    def _init_ollama(self):
        """Initialize Ollama provider."""
        self.use_ollama = True
        self.base_url = Config.OLLAMA_BASE_URL.rstrip("/")
        self.model = Config.OLLAMA_MODEL
        self.provider = "Ollama"
        logger.info(f"Using Ollama with model: {self.model} at {self.base_url}")

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
        elif self.use_gemini:
            return self._gemini_generate(
                prompt, system_instruction, temperature
            )
        else:
            return self._ollama_generate(
                prompt, system_instruction, temperature, timeout
            )

    def _openrouter_generate(
        self,
        prompt: str,
        system_instruction: str,
        temperature: float,
        timeout: int
    ) -> str:
        """Generate content using OpenRouter API with rate limit handling."""
        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
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

                logger.debug(f"OpenRouter request (attempt {attempt + 1}/{max_retries}): {self.model}")
                response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=timeout
                )

                # Check for rate limit (429)
                if response.status_code == 429:
                    # Extract retry-after if available
                    retry_after = response.headers.get("Retry-After")
                    if retry_after:
                        try:
                            wait_time = int(retry_after)
                        except ValueError:
                            wait_time = retry_delay * (2 ** attempt)
                    else:
                        wait_time = retry_delay * (2 ** attempt)

                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get("message", "Rate limited")
                    logger.warning(
                        f"OpenRouter rate limited (429): {error_msg}. "
                        f"Retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})"
                    )

                    if attempt < max_retries - 1:
                        time.sleep(wait_time)
                        continue
                    else:
                        raise requests.exceptions.HTTPError(
                            f"Rate limited after {max_retries} attempts: {error_msg}"
                        )

                response.raise_for_status()
                result = response.json()

                if "choices" not in result or not result["choices"]:
                    raise ValueError("No content in OpenRouter response")

                return result["choices"][0]["message"]["content"]

            except requests.exceptions.RequestException as e:
                logger.error(f"OpenRouter API error (attempt {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    raise
            except Exception as e:
                logger.error(f"Error generating content with OpenRouter (attempt {attempt + 1}): {e}")
                if attempt == max_retries - 1:
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

    def _ollama_generate(
        self,
        prompt: str,
        system_instruction: str,
        temperature: float,
        timeout: int
    ) -> str:
        """Generate content using Ollama API."""
        max_retries = 3
        retry_delay = 2

        for attempt in range(max_retries):
            try:
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
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                    }
                }

                logger.debug(f"Ollama request (attempt {attempt + 1}/{max_retries}): {self.model}")
                response = requests.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                    timeout=timeout
                )

                response.raise_for_status()
                result = response.json()

                if "message" not in result or "content" not in result["message"]:
                    raise ValueError("No content in Ollama response")

                return result["message"]["content"]

            except requests.exceptions.ConnectionError as e:
                logger.error(f"Ollama connection failed (attempt {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    raise
                time.sleep(retry_delay)
            except requests.exceptions.RequestException as e:
                logger.error(f"Ollama API error (attempt {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    raise
                time.sleep(retry_delay)
            except Exception as e:
                logger.error(f"Error generating content with Ollama (attempt {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    raise


# Global client instances with thread safety
_clients = {}
_client_lock = threading.Lock()


def get_ai_client(provider: str = None) -> AIClient:
    """Get or create the global AI client instance (thread-safe).

    Args:
        provider: Optional provider name ('ollama', 'openrouter', 'gemini').
                  Creates a separate cached instance per provider.
    """
    cache_key = provider or "default"
    if cache_key not in _clients:
        with _client_lock:
            if cache_key not in _clients:
                _clients[cache_key] = AIClient(provider=provider)
    return _clients[cache_key]
