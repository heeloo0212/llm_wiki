"""配置管理模块"""
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class LLMConfig:
    provider: str = "openai"  # "openai" or "claude"
    model: str = "gpt-4o"
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    temperature: float = 0.3
    max_tokens: int = 4096

    # Embedding 配置
    embedding_model: str = "text-embedding-3-small"
    embedding_base_url: Optional[str] = None  # 默认与主 API 同


@dataclass
class WikiConfig:
    name: str = "my-wiki"
    data_dir: str = ""
    language: str = "zh"  # "zh" or "en"

    def __post_init__(self):
        if not self.data_dir:
            self.data_dir = str(Path(__file__).parent / "data")

    @property
    def raw_dir(self) -> Path:
        return Path(self.data_dir) / "raw"

    @property
    def wiki_dir(self) -> Path:
        return Path(self.data_dir) / "wiki"

    @property
    def index_path(self) -> Path:
        return Path(self.data_dir) / "index.md"

    @property
    def log_path(self) -> Path:
        return Path(self.data_dir) / "log.md"

    @property
    def schema_path(self) -> Path:
        return Path(self.data_dir) / "schema.md"

    @property
    def purpose_path(self) -> Path:
        return Path(self.data_dir) / "purpose.md"

    @property
    def cache_path(self) -> Path:
        return Path(self.data_dir) / ".wiki-cache.json"

    @property
    def graph_dir(self) -> Path:
        return Path(self.data_dir) / "graph"


DEFAULT_CONFIG_PATH = Path.home() / ".llm_wiki" / "config.yaml"


def load_config(config_path: Optional[str] = None) -> tuple[LLMConfig, WikiConfig]:
    """加载配置，优先级：配置文件 > 环境变量 > 默认值"""
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH

    llm_cfg = LLMConfig()
    wiki_cfg = WikiConfig()

    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if "llm" in data:
            for k, v in data["llm"].items():
                if hasattr(llm_cfg, k):
                    setattr(llm_cfg, k, v)
        if "wiki" in data:
            for k, v in data["wiki"].items():
                if hasattr(wiki_cfg, k):
                    setattr(wiki_cfg, k, v)

    # 环境变量覆盖
    if env_key := os.getenv("LLM_WIKI_API_KEY"):
        llm_cfg.api_key = env_key
    if env_base := os.getenv("LLM_WIKI_BASE_URL"):
        llm_cfg.base_url = env_base
    if env_model := os.getenv("LLM_WIKI_MODEL"):
        llm_cfg.model = env_model
    if env_provider := os.getenv("LLM_WIKI_PROVIDER"):
        llm_cfg.provider = env_provider
    if env_data := os.getenv("LLM_WIKI_DATA_DIR"):
        wiki_cfg.data_dir = env_data

    return llm_cfg, wiki_cfg


def save_config(llm_cfg: LLMConfig, wiki_cfg: WikiConfig, config_path: Optional[str] = None):
    """保存配置到文件"""
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "llm": {
            "provider": llm_cfg.provider,
            "model": llm_cfg.model,
            "api_key": llm_cfg.api_key,
            "base_url": llm_cfg.base_url,
            "temperature": llm_cfg.temperature,
            "max_tokens": llm_cfg.max_tokens,
            "embedding_model": llm_cfg.embedding_model,
            "embedding_base_url": llm_cfg.embedding_base_url,
        },
        "wiki": {
            "name": wiki_cfg.name,
            "data_dir": wiki_cfg.data_dir,
            "language": wiki_cfg.language,
        },
    }

    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)