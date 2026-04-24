"""LLM 抽象基类"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    content: str
    model: str = ""
    usage: dict = None

    def __post_init__(self):
        if self.usage is None:
            self.usage = {}


class BaseLLMProvider(ABC):
    """LLM Provider 抽象基类"""

    def __init__(self, api_key: str, model: str, base_url: str = "",
                 temperature: float = 0.3, max_tokens: int = 4096):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.temperature = temperature
        self.max_tokens = max_tokens

    @abstractmethod
    def generate(self, prompt: str, system: str = "") -> LLMResponse:
        """同步生成"""
        ...

    @abstractmethod
    async def agenerate(self, prompt: str, system: str = "") -> LLMResponse:
        """异步生成"""
        ...

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """生成 embedding 向量"""
        ...