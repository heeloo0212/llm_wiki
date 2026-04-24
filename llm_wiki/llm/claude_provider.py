"""Claude API LLM Provider"""
import anthropic

from .base import BaseLLMProvider, LLMResponse


class ClaudeProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6-20250514",
                 temperature: float = 0.3, max_tokens: int = 4096,
                 embedding_base_url=None,
                 embedding_api_key=None,
                 embedding_model: str = "text-embedding-3-small"):
        # Claude 不使用 base_url 参数 (使用官方 API)
        super().__init__(api_key, model, "", temperature, max_tokens)
        self._client = anthropic.Anthropic(api_key=api_key)
        self._async_client = anthropic.AsyncAnthropic(api_key=api_key)
        # Claude 没有原生 embedding API，使用 OpenAI 兼容端点
        self._embedding_base_url = embedding_base_url or "https://api.openai.com/v1"
        self._embedding_api_key = embedding_api_key or api_key
        self._embedding_model = embedding_model
        self._embed_client = None

    def _get_embed_client(self):
        if self._embed_client is None:
            import openai
            self._embed_client = openai.OpenAI(
                api_key=self._embedding_api_key,
                base_url=self._embedding_base_url,
            )
        return self._embed_client

    def generate(self, prompt: str, system: str = "") -> LLMResponse:
        kwargs = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
        }
        if system:
            kwargs["system"] = system

        resp = self._client.messages.create(**kwargs)
        return LLMResponse(
            content=resp.content[0].text,
            model=resp.model,
            usage={"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens},
        )

    async def agenerate(self, prompt: str, system: str = "") -> LLMResponse:
        kwargs = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
        }
        if system:
            kwargs["system"] = system

        resp = await self._async_client.messages.create(**kwargs)
        return LLMResponse(
            content=resp.content[0].text,
            model=resp.model,
            usage={"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens},
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        client = self._get_embed_client()
        resp = client.embeddings.create(
            model=self._embedding_model,
            input=texts,
        )
        return [item.embedding for item in resp.data]