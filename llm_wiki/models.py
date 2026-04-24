"""数据模型"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml


class PageType(str, Enum):
    ENTITY = "entity"
    CONCEPT = "concept"
    SOURCE = "source"
    SYNTHESIS = "synthesis"
    QUERY = "query"
    OVERVIEW = "overview"
    INDEX = "index"
    LOG = "log"


class EdgeType(str, Enum):
    EXTRACTED = "EXTRACTED"      # 从 [[wikilinks]] 提取
    INFERRED = "INFERRED"        # LLM 推断
    AMBIGUOUS = "AMBIGUOUS"      # 不确定


@dataclass
class WikiPage:
    """Wiki 页面"""
    title: str
    page_type: PageType
    file_path: str
    sources: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    created: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    updated: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    wikilinks: list[str] = field(default_factory=list)
    content: str = ""

    def to_frontmatter_dict(self) -> dict:
        return {
            "type": self.page_type.value,
            "title": self.title,
            "sources": self.sources,
            "tags": self.tags,
            "created": self.created,
            "updated": self.updated,
        }

    def to_markdown(self) -> str:
        fm = yaml.dump(self.to_frontmatter_dict(), allow_unicode=True, default_flow_style=False).strip()
        return f"---\n{fm}\n---\n\n{self.content}"

    @classmethod
    def from_file(cls, path: Path) -> Optional["WikiPage"]:
        """从 markdown 文件读取 WikiPage"""
        try:
            import frontmatter
            post = frontmatter.load(str(path))
            page_type = PageType(post.metadata.get("type", "concept"))
            return cls(
                title=post.metadata.get("title", path.stem),
                page_type=page_type,
                file_path=str(path),
                sources=post.metadata.get("sources", []),
                tags=post.metadata.get("tags", []),
                created=post.metadata.get("created", ""),
                updated=post.metadata.get("updated", ""),
                content=post.content,
            )
        except Exception:
            return None


@dataclass
class GraphNode:
    """知识图谱节点"""
    id: str
    label: str
    page_type: PageType
    community: int = -1
    degree: int = 0


@dataclass
class GraphEdge:
    """知识图谱边"""
    source: str
    target: str
    edge_type: EdgeType = EdgeType.EXTRACTED
    weight: float = 1.0
    label: str = ""


@dataclass
class IngestResult:
    """Ingest 操作结果"""
    source_file: str
    pages_created: list[str] = field(default_factory=list)
    pages_updated: list[str] = field(default_factory=list)
    entities_found: list[str] = field(default_factory=list)
    concepts_found: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    skipped: bool = False
    error: Optional[str] = None


@dataclass
class LintIssue:
    """Lint 检查结果"""
    issue_type: str  # "orphan" | "broken_link" | "contradiction" | "gap" | "index_mismatch"
    severity: str    # "warning" | "error"
    page: str
    detail: str
    suggestion: str = ""