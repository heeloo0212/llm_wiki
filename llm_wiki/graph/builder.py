"""知识图谱构建 — 解析 wikilinks + LLM 推断语义关系"""
import re
from pathlib import Path
from typing import Optional

from ..models import EdgeType, GraphEdge, GraphNode, PageType, WikiPage


class GraphBuilder:
    """从 wiki 页面构建知识图谱"""

    def __init__(self, wiki_dir: Path, llm: Optional[object] = None):
        self.wiki_dir = wiki_dir
        self.llm = llm

    def build(self) -> tuple[list[GraphNode], list[GraphEdge]]:
        """构建图谱，返回 (nodes, edges)"""
        pages = self._load_pages()
        nodes = self._build_nodes(pages)
        edges = self._extract_edges(pages)

        # 可选: LLM 推断语义关系
        if self.llm:
            inferred_edges = self._infer_edges(pages, nodes)
            edges.extend(inferred_edges)

        # 更新节点的度
        for edge in edges:
            for node in nodes:
                if node.id in (edge.source, edge.target):
                    node.degree += 1

        return nodes, edges

    def _load_pages(self) -> list[WikiPage]:
        """加载所有 wiki 页面"""
        pages = []
        for md in self.wiki_dir.rglob("*.md"):
            page = WikiPage.from_file(md)
            if page:
                pages.append(page)
        return pages

    def _build_nodes(self, pages: list[WikiPage]) -> list[GraphNode]:
        """从页面构建节点"""
        nodes = []
        for page in pages:
            stem = Path(page.file_path).stem
            nodes.append(GraphNode(
                id=stem,
                label=page.title,
                page_type=page.page_type,
            ))
        return nodes

    def _extract_edges(self, pages: list[WikiPage]) -> list[GraphEdge]:
        """从 [[wikilinks]] 提取确定边"""
        edges = []
        seen = set()

        for page in pages:
            source = Path(page.file_path).stem
            for link in page.wikilinks:
                target = link.strip()
                if not target:
                    continue
                key = (source, target)
                reverse_key = (target, source)
                if key not in seen and reverse_key not in seen:
                    edges.append(GraphEdge(
                        source=source,
                        target=target,
                        edge_type=EdgeType.EXTRACTED,
                        weight=1.0,
                    ))
                    seen.add(key)

        # 重新扫描文件内容提取 wikilinks (因为 WikiPage.wikilinks 可能不完整)
        for page in pages:
            source = Path(page.file_path).stem
            try:
                content = Path(page.file_path).read_text(encoding="utf-8")
            except Exception:
                continue
            wikilinks = re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", content)
            for target in wikilinks:
                target = target.strip()
                key = (source, target)
                reverse_key = (target, source)
                if key not in seen and reverse_key not in seen:
                    edges.append(GraphEdge(
                        source=source,
                        target=target,
                        edge_type=EdgeType.EXTRACTED,
                        weight=1.0,
                    ))
                    seen.add(key)

        return edges

    def _infer_edges(self, pages: list[WikiPage], nodes: list[GraphNode]) -> list[GraphEdge]:
        """使用 LLM 推断语义关系 (可选)"""
        if not self.llm:
            return []

        # 收集页面摘要
        summaries = []
        for page in pages[:30]:  # 限制数量
            stem = Path(page.file_path).stem
            content = page.content[:300]
            summaries.append(f"- {stem}: {content}")

        prompt = f"""分析以下 wiki 页面，推断它们之间隐含的语义关系（不是通过 [[wikilinks]] 已经标注的）。

页面列表：
{chr(10).join(summaries)}

请输出 JSON 格式的边列表：
```json
[
  {{"source": "页面1id", "target": "页面2id", "relation": "关系描述", "confidence": 0.8}}
]
```

只输出置信度 > 0.6 的关系。"""

        try:
            resp = self.llm.generate(prompt)
            import json
            match = re.search(r"\[.*\]", resp.content, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                edges = []
                existing_ids = {n.id for n in nodes}
                for item in data:
                    s, t = item.get("source", ""), item.get("target", "")
                    if s in existing_ids and t in existing_ids:
                        conf = item.get("confidence", 0.7)
                        edge_type = EdgeType.INFERRED if conf >= 0.8 else EdgeType.AMBIGUOUS
                        edges.append(GraphEdge(
                            source=s, target=t,
                            edge_type=edge_type,
                            weight=conf,
                            label=item.get("relation", ""),
                        ))
                return edges
        except Exception:
            pass

        return []