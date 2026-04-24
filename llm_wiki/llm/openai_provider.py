"""OpenAI 兼容 LLM Provider (支持 DeepSeek, Ollama 等)"""
import openai

from .base import BaseLLMProvider, LLMResponse


class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o",
                 base_url: str = "https://api.openai.com/v1",
                 temperature: float = 0.3, max_tokens: int = 4096,
                 embedding_model: str = "text-embedding-3-small",
                 embedding_base_url=None):
        super().__init__(api_key, model, base_url, temperature, max_tokens)
        self.embedding_model = embedding_model
        self.embedding_base_url = embedding_base_url or base_url
        self._client = openai.OpenAI(api_key=api_key, base_url=base_url)
        self._async_client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)
        # Embedding 客户端可能使用不同的 base_url
        if embedding_base_url and embedding_base_url != base_url:
            self._embed_client = openai.OpenAI(api_key=api_key, base_url=embedding_base_url)
        else:
            self._embed_client = self._client

    def generate(self, prompt: str, system: str = "") -> LLMResponse:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        resp = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return LLMResponse(
            content=resp.choices[0].message.content,
            model=resp.model,
            usage={"prompt_tokens": resp.usage.prompt_tokens, "completion_tokens": resp.usage.completion_tokens} if resp.usage else {},
        )

    async def agenerate(self, prompt: str, system: str = "") -> LLMResponse:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        resp = await self._async_client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return LLMResponse(
            content=resp.choices[0].message.content,
            model=resp.model,
            usage={"prompt_tokens": resp.usage.prompt_tokens, "completion_tokens": resp.usage.completion_tokens} if resp.usage else {},
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        resp = self._embed_client.embeddings.create(
            model=self.embedding_model,
            input=texts,
        )
        return [item.embedding for item in resp.data]