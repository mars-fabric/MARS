"""
Centralized LLM Provider Configuration Module

Auto-detects the active LLM provider from environment variables and provides
unified client creation and model config generation.

Supported providers:
- OpenAI (default)
- Azure OpenAI
- Anthropic
- Google Gemini
- Mistral

Usage:
    from cmbagent.llm_provider import create_openai_client, get_provider_config

    client = create_openai_client()  # auto-detects Azure or OpenAI
    config = get_provider_config()
    print(config.active_provider)  # "azure" or "openai"
"""

import os
import json
import logging
import ssl
from typing import Any, Dict, Optional, Literal

logger = logging.getLogger(__name__)


class LLMProviderConfig:
    """
    Singleton that auto-detects and stores the active LLM provider configuration.

    Detection priority:
    1. CMBAGENT_LLM_PROVIDER env var (explicit override)
    2. OPENAI_API_TYPE=azure -> Azure
    3. AZURE_OPENAI_API_KEY + AZURE_OPENAI_ENDPOINT present -> Azure
    4. OPENAI_API_KEY present -> OpenAI
    5. First configured provider as fallback
    """

    _instance: Optional["LLMProviderConfig"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._detect_provider()

    def _detect_provider(self):
        """Detect the active provider from environment variables."""
        # Read all relevant env vars
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.openai_api_type = os.getenv("OPENAI_API_TYPE", "").lower()
        self.openai_api_base = os.getenv("OPENAI_API_BASE", "")
        self.openai_api_version = os.getenv("OPENAI_API_VERSION", "")

        self.azure_api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
        self.azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        self.azure_api_base = os.getenv("AZURE_OPENAI_API_BASE", "")
        self.azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
        self.azure_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
        self.azure_verify_ssl = os.getenv("AZURE_OPENAI_VERIFY_SSL", "true").lower() != "false"

        # Fallback Azure config
        self.azure_fallback_api_key = os.getenv("AZURE_OPENAI_FALLBACK_API_KEY", "")
        self.azure_fallback_endpoint = os.getenv("AZURE_OPENAI_FALLBACK_ENDPOINT", "")
        self.azure_fallback_deployment = os.getenv("AZURE_OPENAI_FALLBACK_DEPLOYMENT", "")
        self.azure_fallback_api_version = os.getenv("AZURE_OPENAI_FALLBACK_API_VERSION", "2024-12-01-preview")

        # Deployment map: JSON mapping deployment names to model names
        deployment_map_str = os.getenv("AZURE_OPENAI_DEPLOYMENT_MAP", "")
        self.azure_deployment_map: Dict[str, str] = {}
        if deployment_map_str:
            try:
                self.azure_deployment_map = json.loads(deployment_map_str)
            except json.JSONDecodeError:
                logger.warning("Invalid AZURE_OPENAI_DEPLOYMENT_MAP JSON, ignoring")

        # Other providers
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        self.mistral_api_key = os.getenv("MISTRAL_API_KEY", "")

        # Auto-detect active provider
        explicit_provider = os.getenv("CMBAGENT_LLM_PROVIDER", "").lower()
        if explicit_provider:
            self.active_provider = explicit_provider
        elif self.openai_api_type == "azure":
            self.active_provider = "azure"
        elif self.azure_api_key and self.azure_endpoint:
            self.active_provider = "azure"
        elif self.openai_api_key:
            self.active_provider = "openai"
        elif self.anthropic_api_key:
            self.active_provider = "anthropic"
        elif self.gemini_api_key:
            self.active_provider = "google"
        elif self.mistral_api_key:
            self.active_provider = "mistral"
        else:
            self.active_provider = "openai"  # default fallback

        logger.info("LLM provider detected: %s", self.active_provider)

    @property
    def is_azure(self) -> bool:
        return self.active_provider == "azure"

    @property
    def effective_api_key(self) -> str:
        """Return the effective API key for OpenAI-compatible calls."""
        if self.is_azure:
            return self.azure_api_key or self.openai_api_key
        return self.openai_api_key

    @property
    def effective_endpoint(self) -> str:
        """Return the Azure endpoint / base URL."""
        if self.is_azure:
            return self.azure_endpoint or self.azure_api_base or self.openai_api_base
        return self.openai_api_base

    @property
    def effective_api_version(self) -> str:
        """Return the Azure API version."""
        return self.azure_api_version or self.openai_api_version

    def get_azure_deployment_for_model(self, model: str) -> str:
        """
        Map a model name to an Azure deployment name.

        If a deployment map is configured, look up the model.
        Otherwise, fall back to the single configured deployment.
        If nothing is configured, return the model name as-is.
        """
        # Check explicit deployment map first
        if self.azure_deployment_map:
            # Try exact match
            if model in self.azure_deployment_map:
                return self.azure_deployment_map[model]
            # Try reverse lookup (deployment -> model)
            for deployment, mapped_model in self.azure_deployment_map.items():
                if mapped_model == model:
                    return deployment
            # Fall through to default deployment
        
        # Use the single deployment for all OpenAI-style models
        if self.azure_deployment:
            return self.azure_deployment

        # Last resort: use model name as deployment name
        return model

    def refresh(self):
        """Re-detect provider from environment (useful after env changes)."""
        self._initialized = False
        self.__init__()

    def to_dict(self) -> Dict[str, Any]:
        """Return config as dict (safe for logging - no secrets)."""
        return {
            "active_provider": self.active_provider,
            "is_azure": self.is_azure,
            "azure_endpoint": self.effective_endpoint if self.is_azure else None,
            "azure_deployment": self.azure_deployment if self.is_azure else None,
            "azure_api_version": self.effective_api_version if self.is_azure else None,
            "azure_verify_ssl": self.azure_verify_ssl if self.is_azure else None,
            "has_azure_fallback": bool(self.azure_fallback_api_key and self.azure_fallback_endpoint),
            "has_openai_key": bool(self.openai_api_key),
            "has_azure_key": bool(self.azure_api_key),
            "has_anthropic_key": bool(self.anthropic_api_key),
            "has_gemini_key": bool(self.gemini_api_key),
            "has_mistral_key": bool(self.mistral_api_key),
        }


def get_provider_config() -> LLMProviderConfig:
    """Get the global LLMProviderConfig singleton."""
    return LLMProviderConfig()


def create_openai_client(api_key: Optional[str] = None, **kwargs) -> Any:
    """
    Create an OpenAI-compatible client, auto-detecting Azure vs OpenAI.

    Args:
        api_key: Optional override API key. If not provided, uses env config.
        **kwargs: Additional keyword args passed to the client constructor.

    Returns:
        openai.OpenAI or openai.AzureOpenAI instance
    """
    config = get_provider_config()

    if config.is_azure:
        try:
            from openai import AzureOpenAI
        except ImportError:
            raise ImportError(
                "openai package with Azure support required. "
                "Install with: pip install openai>=1.0"
            )

        effective_key = api_key or config.effective_api_key
        effective_endpoint = config.effective_endpoint

        if not effective_key:
            raise ValueError(
                "Azure OpenAI API key not found. Set AZURE_OPENAI_API_KEY or OPENAI_API_KEY."
            )
        if not effective_endpoint:
            raise ValueError(
                "Azure OpenAI endpoint not found. Set AZURE_OPENAI_ENDPOINT."
            )

        client_kwargs = {
            "api_key": effective_key,
            "azure_endpoint": effective_endpoint,
            "api_version": config.effective_api_version,
        }

        # Handle SSL verification
        if not config.azure_verify_ssl:
            import httpx
            client_kwargs["http_client"] = httpx.Client(verify=False)

        client_kwargs.update(kwargs)
        logger.info("Creating AzureOpenAI client (endpoint=%s, api_version=%s)",
                     effective_endpoint, config.effective_api_version)
        return AzureOpenAI(**client_kwargs)
    else:
        from openai import OpenAI

        effective_key = api_key or config.openai_api_key
        client_kwargs = {"api_key": effective_key}
        if config.openai_api_base:
            client_kwargs["base_url"] = config.openai_api_base
        client_kwargs.update(kwargs)
        return OpenAI(**client_kwargs)


def get_azure_headers(api_key: Optional[str] = None) -> Dict[str, str]:
    """
    Get appropriate HTTP headers for direct REST API calls.
    Works for both Azure OpenAI and standard OpenAI.

    Returns:
        Dict of HTTP headers
    """
    config = get_provider_config()

    if config.is_azure:
        effective_key = api_key or config.effective_api_key
        return {
            "api-key": effective_key,
            "Content-Type": "application/json",
        }
    else:
        effective_key = api_key or config.openai_api_key
        return {
            "Authorization": f"Bearer {effective_key}",
            "Content-Type": "application/json",
            "OpenAI-Beta": "assistants=v2",
        }


def get_base_url() -> str:
    """
    Get the base URL for REST API calls.
    For Azure, returns the endpoint with openai path.
    For OpenAI, returns the standard API URL.
    """
    config = get_provider_config()

    if config.is_azure:
        endpoint = config.effective_endpoint.rstrip("/")
        return f"{endpoint}/openai"
    else:
        return "https://api.openai.com/v1"


def get_vector_store_url() -> str:
    """Get the URL for vector store operations."""
    config = get_provider_config()

    if config.is_azure:
        base = get_base_url()
        version = config.effective_api_version
        return f"{base}/vector_stores?api-version={version}"
    else:
        return "https://api.openai.com/v1/vector_stores"


def resolve_model_for_provider(model: str) -> str:
    """
    Resolve a model name for the current provider.
    For Azure, maps to deployment name.
    For others, returns model as-is.
    """
    config = get_provider_config()

    if config.is_azure:
        # Only map OpenAI-style models to Azure deployments
        openai_prefixes = ("gpt-", "gpt4", "o3-", "o1-", "o3", "text-", "dall-e", "whisper", "tts")
        if any(model.startswith(prefix) or model.startswith(prefix.upper()) for prefix in openai_prefixes):
            return config.get_azure_deployment_for_model(model)
    return model
