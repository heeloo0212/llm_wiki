"""向量语义搜索 — 基于 LanceDB"""
import json
from pathlib import Path
from typing import Optional

from ..llm.base import BaseLLMProvider


class VectorSearch:
    """使用 LanceDB 进行向量语义搜索"""

    def __init__(self, db_path: Path, llm: BaseLLMProvider):
        self.db_path = db_path
        self.llm = llm
        self._db = None
        self._table = None

    def _get_db(self):
        if self._db is None:
            try:
                import lancedb
                self._db = lancedb.connect(str(self.db_path))
            except ImportError:
                raise ImportError("请安装 lancedb: pip install lancedb")
        return self._db

    def _get_table(self):
        if self._table is None:
            try:
                db = self._get_db()
                self._table = db.open_table("wiki_embeddings")
            except Exception:
                self._table = None
        return self._table

    def index_pages(self, wiki_dir: Path):
        """为所有 wiki 页面建立向量索引"""
        import lancedb
        import pyarrow as pa

        db = self._get_db()

        # 收集所有页面
        pages = []
        for md in wiki_dir.rglob("*.md"):
            try:
                content = md.read_text(encoding="utf-8")[:3000]
                rel = str(md.relative_to(wiki_dir))
                pages.append({"path": rel, "content": content})
            except Exception:
                continue

        if not pages:
            return

        # 批量生成 embedding
        batch_size = 20
        all_embeddings = []
        all_paths = []
        for i in range(0, len(pages), batch_size):
            batch = pages[i:i + batch_size]
            texts = [p["content"] for p in batch]
            try:
                embeddings = self.llm.embed(texts)
                all_embeddings.extend(embeddings)
                all_paths.extend([p["path"] for p in batch])
            except Exception:
                continue

        if not all_embeddings:
            return

        # 构建表
        dim = len(all_embeddings[0])
        data = {
            "path": all_paths,
            "vector": all_embeddings,
        }
        table = pa.table(data)

        # 覆盖写入
        try:
            db.drop_table("wiki_embeddings")
        except Exception:
            pass
        db.create_table("wiki_embeddings", table)
        self._table = None  # 重新打开

    def search(self, query: str, top_k: int = 10) -> list[str]:
        """向量语义搜索"""
        try:
            table = self._get_table()
            if table is None:
                return []
        except Exception:
            return []

        # 生成查询向量
        try:
            query_embedding = self.llm.embed([query])[0]
        except Exception:
            return []

        # LanceDB 搜索
        try:
            results = table.search(query_embedding).limit(top_k).to_list()
            return [r["path"] for r in results]
        except Exception:
            return []

    def add_page(self, path: str, content: str):
        """添加单个页面到向量索引"""
        try:
            table = self._get_table()
            if table is None:
                return
        except Exception:
            return

        try:
            embedding = self.llm.embed([content[:3000]])[0]
        except Exception:
            return

        try:
            import pyarrow as pa
            data = pa.table({"path": [path], "vector": [embedding]})
            table.add(data)
        except Exception:
            pass