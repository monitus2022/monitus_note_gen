"""LLM backends and a provider factory."""

from .client import OllamaClient, OpenRouterClient


def build_client(cfg):
    """Return the client for `cfg.provider` (keeps Ollama available for local runs)."""
    if cfg.provider == "ollama":
        return OllamaClient(cfg.ollama_host, cfg.model)
    return OpenRouterClient(cfg.openrouter_api_key, cfg.model, base_url=cfg.openrouter_base_url)


__all__ = ["OllamaClient", "OpenRouterClient", "build_client"]
