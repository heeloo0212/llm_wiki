from .base import BaseLLMProvider, LLMResponse

def get_provider(name):
    """延迟加载 LLM Provider"""
    if name == "openai":
        from .openai_provider import OpenAIProvider
        return OpenAIProvider
    elif name == "claude":
        from .claude_provider import ClaudeProvider
        return ClaudeProvider
    else:
        raise ValueError(f"Unknown provider: {name}")

__all__ = ["BaseLLMProvider", "LLMResponse", "get_provider"]