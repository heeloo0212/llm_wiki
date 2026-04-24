"""Wiki 核心操作 — ingest, query, lint"""
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from .cache import IngestCache
from .indexer import IndexManager, LogManager
from .models import IngestResult, LintIssue, PageType, WikiPage
from .schema import SchemaManager
from .llm import BaseLLMProvider
from .prompts import ingest as ingest_prompts
from .prompts import query as query_prompts
from .prompts import lint as lint_prompts


class LLMWiki:
    """LLM Wiki 核心引擎"""

    def __init__(self, data_dir, llm: BaseLLMProvider, language: str = "zh"):
        self.data_dir = Path(data_dir)
        self.llm = llm
        self.language = language

        self.raw_dir = self.data_dir / "raw"
        self.wiki_dir = self.data_dir / "wiki"

        self.cache = IngestCache(self.data_dir / ".wiki-cache.json")
        self.indexer = IndexManager(self.data_dir / "index.md")
        self.logger = LogManager(self.data_dir / "log.md")
        self.schema_mgr = SchemaManager(self.data_dir / "schema.md")

    # ── 初始化 ──────────────────────────────────────────────

    def init(self, name: str = "My Wiki"):
        """初始化知识库目录结构"""
        dirs = [
            self.raw_dir / "articles",
            self.raw_dir / "papers",
            self.raw_dir / "notes",
            self.wiki_dir / "entities",
            self.wiki_dir / "concepts",
            self.wiki_dir / "sources",
            self.wiki_dir / "syntheses",
            self.wiki_dir / "queries",
            self.data_dir / "graph",
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

        self.indexer.init(name)
        self.logger.init()
        self.schema_mgr.init_default()

        purpose_path = self.data_dir / "purpose.md"
        if not purpose_path.exists():
            purpose_path.write_text(
                f"# {name} — 研究方向\n\n> 定义此知识库的目标和方向。\n\n## 目标\n\n\n## 关键问题\n\n\n## 研究范围\n\n",
                encoding="utf-8",
            )

        overview_path = self.wiki_dir / "overview.md"
        if not overview_path.exists():
            overview_path.write_text(
                f"# {name} — 概览\n\n> 此页面反映知识库当前的综合状态，每次 ingest 后更新。\n\n",
                encoding="utf-8",
            )

    # ── Ingest ──────────────────────────────────────────────

    def ingest(self, source_path) -> IngestResult:
        """消化单个源文件，两步式链式思考"""
        source_path = Path(source_path)
        result = IngestResult(source_file=str(source_path))

        if not source_path.exists():
            result.error = f"文件不存在: {source_path}"
            return result

        if self.cache.is_cached(source_path):
            result.skipped = True
            return result

        try:
            source_content = source_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            source_content = source_path.read_text(encoding="gbk", errors="replace")

        # 计算相对路径
        try:
            rel_path = str(source_path.relative_to(self.raw_dir))
        except ValueError:
            dest = self.raw_dir / "articles" / source_path.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, dest)
            source_path = dest
            rel_path = str(source_path.relative_to(self.raw_dir))
            source_content = source_path.read_text(encoding="utf-8")

        index_content = self.indexer.load()
        schema_content = self.schema_mgr.load()
        purpose_content = self._read_purpose()

        # Step 1: 分析
        analysis, raw_analysis = self._analyze_source(source_content, rel_path, index_content, schema_content, purpose_content)
        if not isinstance(analysis, dict):
            self._save_debug_log("analysis_failed", raw_analysis)
            result.error = "LLM 分析失败：无法解析为有效的 JSON (原始响应已保存到 .llm_debug/)"
            return result

        # Step 2: 生成
        existing_pages = self._read_existing_pages(analysis)
        pages_result, raw_generate = self._generate_pages(analysis, rel_path, existing_pages, schema_content)
        if not isinstance(pages_result, dict):
            self._save_debug_log("generate_failed", raw_generate)
            result.error = "LLM 生成失败：无法解析为有效的 JSON (原始响应已保存到 .llm_debug/)"
            return result

        # 提取页面列表
        page_list = pages_result.get("pages", [])
        if not isinstance(page_list, list):
            page_list = []

        # 写入 wiki 页面
        for page_data in page_list:
            if isinstance(page_data, dict):
                self._write_page(page_data)

        # 更新 overview.md
        overview_update = pages_result.get("overview_update", "")
        if isinstance(overview_update, str) and overview_update:
            self._update_overview(overview_update)

        # 更新缓存
        self.cache.mark_processed(source_path)

        # 更新 log
        log_entry = pages_result.get("log_entry", f"Ingested {rel_path}")
        self.logger.append("ingest", log_entry)

        # 更新 index
        for page_data in page_list:
            if not isinstance(page_data, dict):
                continue
            fp = page_data.get("file_path", "")
            fm = page_data.get("frontmatter", {})
            if not isinstance(fm, dict):
                fm = {}
            title = fm.get("title", "")
            page_type = fm.get("type", "concept")
            if fp and title:
                self.indexer.add_page(page_type, title, Path(fp).stem, "")

        # 收集结果
        for page_data in page_list:
            if not isinstance(page_data, dict):
                continue
            fp = page_data.get("file_path", "")
            if fp:
                if self._page_exists(fp):
                    result.pages_updated.append(fp)
                else:
                    result.pages_created.append(fp)

        result.entities_found = [e.get("name", "") for e in analysis.get("entities", []) if isinstance(e, dict)]
        result.concepts_found = [c.get("name", "") for c in analysis.get("concepts", []) if isinstance(c, dict)]
        result.contradictions = [c.get("claim", "") for c in analysis.get("contradictions", []) if isinstance(c, dict)]

        return result

    def ingest_dir(self, dir_path) -> list:
        """批量消化目录下所有文件"""
        dir_path = Path(dir_path)
        results = []
        for f in sorted(dir_path.rglob("*")):
            if f.is_file() and f.suffix in (".md", ".txt", ".markdown"):
                results.append(self.ingest(f))
        return results

    def _analyze_source(self, source_content, rel_path,
                        index_content, schema_content,
                        purpose_content):
        """Step 1: 分析源文档，返回 (parsed_dict_or_None, raw_response)"""
        prompt = ingest_prompts.ANALYSIS_PROMPT.format(
            source_content=source_content[:8000],
            index_content=index_content[:4000],
            schema_content=schema_content[:3000],
            purpose_content=purpose_content[:2000],
        )
        resp = self.llm.generate(prompt, system=ingest_prompts.ANALYSIS_SYSTEM)
        return self._parse_json(resp.content), resp.content

    def _generate_pages(self, analysis, rel_path,
                        existing_pages, schema_content):
        """Step 2: 生成 wiki 页面，返回 (parsed_dict_or_None, raw_response)"""
        prompt = ingest_prompts.GENERATE_PROMPT.format(
            analysis_json=json.dumps(analysis, ensure_ascii=False, indent=2)[:6000],
            existing_pages=existing_pages[:4000],
            schema_content=schema_content[:3000],
        )
        resp = self.llm.generate(prompt, system=ingest_prompts.GENERATE_SYSTEM)
        return self._parse_json(resp.content), resp.content

    def _read_existing_pages(self, analysis) -> str:
        """读取分析结果中提到的已有 wiki 页面"""
        pages_content = []
        if not isinstance(analysis, dict):
            return ""

        for key in ["entities", "concepts"]:
            for item in analysis.get(key, []):
                if not isinstance(item, dict):
                    continue
                existing = item.get("existing_page")
                if existing:
                    path = self.wiki_dir / f"{existing}.md"
                    if path.exists():
                        content = path.read_text(encoding="utf-8")[:2000]
                        pages_content.append(f"### {existing}\n{content}")

        return "\n\n".join(pages_content)

    # ── Query ───────────────────────────────────────────────

    def query(self, question: str) -> str:
        """查询知识库"""
        from .search.keyword import KeywordSearch
        searcher = KeywordSearch(self.wiki_dir, self.data_dir / "index.md")
        relevant_files = searcher.search(question, top_k=10)

        # 向量搜索 (可选)
        try:
            from .search.vector import VectorSearch
            vec_searcher = VectorSearch(self.data_dir / ".vectordb", self.llm)
            vec_results = vec_searcher.search(question, top_k=10)
            existing_set = set(relevant_files)
            for vf in vec_results:
                if vf not in existing_set:
                    relevant_files.append(vf)
                    existing_set.add(vf)
        except Exception:
            pass

        relevant_pages = []
        for fp in relevant_files[:8]:
            path = self.wiki_dir / fp if not fp.startswith(str(self.wiki_dir)) else Path(fp)
            if path.exists():
                content = path.read_text(encoding="utf-8")[:2000]
                relevant_pages.append(f"### {path.stem}\n{content}")

        if not relevant_pages:
            return "未找到与问题相关的 wiki 页面。请先 ingest 一些源文档。"

        schema_content = self.schema_mgr.load()
        purpose_content = self._read_purpose()

        prompt = query_prompts.QUERY_PROMPT.format(
            question=question,
            relevant_pages="\n\n".join(relevant_pages),
            schema_content=schema_content[:2000],
            purpose_content=purpose_content[:1000],
        )
        resp = self.llm.generate(prompt, system=query_prompts.QUERY_SYSTEM)

        answer = resp.content
        if "**save_as_page: true**" in answer.lower() or "save_as_page: true" in answer:
            self._try_save_query(question, answer)

        return answer

    def _try_save_query(self, question: str, answer: str):
        """尝试保存有价值的查询结果"""
        title_match = re.search(r"\*\*suggested_title\*\*:\s*(.+)", answer)
        if not title_match:
            return
        title = title_match.group(1).strip()

        file_name = re.sub(r"[^\w\s-]", "", title.lower()).replace(" ", "-")[:50]
        file_path = self.wiki_dir / "queries" / f"{file_name}.md"

        if file_path.exists():
            return

        now = datetime.now().strftime("%Y-%m-%d")
        frontmatter = (
            f"---\n"
            f"type: query\n"
            f"title: {title}\n"
            f"sources: []\n"
            f"tags: [query-result]\n"
            f"created: {now}\n"
            f"updated: {now}\n"
            f"---"
        )
        clean_answer = re.sub(r"\n---\n\*\*save_as_page.*?\*\*\n.*", "", answer, flags=re.DOTALL)

        content = f"{frontmatter}\n\n## 问题\n\n{question}\n\n## 回答\n\n{clean_answer}\n"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        self.indexer.add_page("query", title, file_name, f"关于 {question[:50]}")
        self.logger.append("query", f"保存查询结果: {title}")

    # ── Lint ────────────────────────────────────────────────

    def lint(self) -> list:
        """健康检查 wiki"""
        issues = []
        issues.extend(self._lint_rules())
        issues.extend(self._lint_deep())
        return issues

    def _lint_rules(self) -> list:
        """规则层面检查 (不调用 LLM)"""
        issues = []
        all_pages = self._collect_all_pages()
        page_names = {p.stem for p in all_pages}

        # 1. 断链检测
        for page_path in all_pages:
            try:
                content = page_path.read_text(encoding="utf-8")
            except Exception:
                continue
            wikilinks = re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", content)
            for link in wikilinks:
                if link not in page_names:
                    issues.append(LintIssue(
                        issue_type="broken_link",
                        severity="warning",
                        page=str(page_path.relative_to(self.wiki_dir)),
                        detail=f"断链: [[{link}]]",
                        suggestion=f"创建 {link}.md 或修正链接",
                    ))

        # 2. 孤立页面检测
        inbound_links = {p.stem: 0 for p in all_pages}
        for page_path in all_pages:
            try:
                content = page_path.read_text(encoding="utf-8")
            except Exception:
                continue
            wikilinks = re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", content)
            for link in wikilinks:
                if link in inbound_links:
                    inbound_links[link] += 1

        for name, count in inbound_links.items():
            if count == 0 and name != "overview":
                issues.append(LintIssue(
                    issue_type="orphan",
                    severity="warning",
                    page=f"{name}.md",
                    detail=f"孤立页面: 无入站链接",
                    suggestion="添加从其他页面的链接，或考虑合并/删除",
                ))

        # 3. Index 一致性
        index_content = self.indexer.load()
        for page_path in all_pages:
            stem = page_path.stem
            if f"[[{stem}]" not in index_content and f"|{stem}]]" not in index_content:
                issues.append(LintIssue(
                    issue_type="index_mismatch",
                    severity="warning",
                    page=f"{stem}.md",
                    detail=f"页面未在 index.md 中记录",
                    suggestion=f"在 index.md 中添加 [[{stem}]]",
                ))

        return issues

    def _lint_deep(self) -> list:
        """LLM 深度检查"""
        issues = []

        all_pages = self._collect_all_pages()
        pages_summary = []
        for p in all_pages[:50]:
            try:
                content = p.read_text(encoding="utf-8")[:500]
                pages_summary.append(f"- {p.stem}: {content[:200]}...")
            except Exception:
                continue

        rule_issues_str = "\n".join(f"- {i.detail}" for i in self._lint_rules())

        prompt = lint_prompts.LINT_PROMPT.format(
            index_content=self.indexer.load()[:4000],
            pages_summary="\n".join(pages_summary)[:6000],
            rule_issues=rule_issues_str[:2000],
        )

        resp = self.llm.generate(prompt, system=lint_prompts.LINT_SYSTEM)
        result = self._parse_json(resp.content)

        if not isinstance(result, dict):
            return issues

        for c in result.get("contradictions", []):
            if isinstance(c, dict):
                issues.append(LintIssue(
                    issue_type="contradiction",
                    severity="error",
                    page=c.get("page1", ""),
                    detail=c.get("description", ""),
                    suggestion=c.get("suggestion", ""),
                ))

        for g in result.get("knowledge_gaps", []):
            if isinstance(g, dict):
                issues.append(LintIssue(
                    issue_type="gap",
                    severity="warning",
                    page=g.get("concept", ""),
                    detail=f"知识缺口: {g.get('description', g.get('concept', ''))}",
                    suggestion=g.get("suggestion", ""),
                ))

        self.logger.append("lint", f"检查完成，发现 {len(issues)} 个问题")
        return issues

    # ── 工具方法 ────────────────────────────────────────────

    def _parse_json(self, text):
        """从 LLM 响应中提取 JSON，确保返回 dict 或 None"""
        if not text or not isinstance(text, str):
            return None

        # 按优先级尝试多种提取策略
        candidates = []

        # 策略1: ```json ... ``` 代码块
        for match in re.finditer(r"```json\s*(.*?)\s*```", text, re.DOTALL):
            candidates.append(match.group(1).strip())

        # 策略2: ``` ... ``` 代码块（无语言标记）
        for match in re.finditer(r"```\s*(.*?)\s*```", text, re.DOTALL):
            content = match.group(1).strip()
            if content.startswith("{"):
                candidates.append(content)

        # 策略3: 用大括号匹配找最外层 JSON 对象
        depth = 0
        start = -1
        for i, ch in enumerate(text):
            if ch == '{':
                if depth == 0:
                    start = i
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0 and start >= 0:
                    candidates.append(text[start:i + 1])
                    start = -1

        # 逐个尝试解析
        for candidate in candidates:
            # 先直接尝试
            result = self._try_loads(candidate)
            if result is not None:
                return result
            # 修复常见问题后重试
            fixed = self._fix_json(candidate)
            if fixed != candidate:
                result = self._try_loads(fixed)
                if result is not None:
                    return result

        return None

    @staticmethod
    def _try_loads(text):
        """尝试 json.loads，只返回 dict"""
        try:
            result = json.loads(text)
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
        return None

    @staticmethod
    def _fix_json(text):
        """修复常见的 LLM JSON 输出问题"""
        # 移除尾部逗号 (JSON 不允许)
        text = re.sub(r",\s*([}\]])", r"\1", text)
        # 修复单引号为双引号
        # 只在 key/value 外层简单替换，避免破坏内容中的引号
        text = re.sub(r"'([^']*)'(\s*:)", r'"\1"\2', text)  # key
        text = re.sub(r":\s*'([^']*)'", r': "\1"', text)    # string value
        # 移除 // 注释
        text = re.sub(r"//.*$", "", text, flags=re.MULTILINE)
        return text

    def _write_page(self, page_data):
        """写入 wiki 页面"""
        if not isinstance(page_data, dict):
            return

        fp = page_data.get("file_path", "")
        fm = page_data.get("frontmatter", {})
        content = page_data.get("content", "")

        if not fp:
            return
        if not isinstance(fm, dict):
            fm = {}

        now = datetime.now().strftime("%Y-%m-%d")
        fm.setdefault("created", now)
        fm.setdefault("updated", now)

        full_path = self.wiki_dir / fp
        full_path.parent.mkdir(parents=True, exist_ok=True)

        fm_str = yaml.dump(fm, allow_unicode=True, default_flow_style=False).strip()
        full_content = f"---\n{fm_str}\n---\n\n{content}\n"
        full_path.write_text(full_content, encoding="utf-8")

    def _page_exists(self, file_path: str) -> bool:
        return (self.wiki_dir / file_path).exists()

    def _update_overview(self, update: str):
        """更新 overview.md"""
        overview_path = self.wiki_dir / "overview.md"
        existing = ""
        if overview_path.exists():
            existing = overview_path.read_text(encoding="utf-8")
        overview_path.write_text(existing.rstrip() + "\n\n" + update + "\n", encoding="utf-8")

    def _read_purpose(self) -> str:
        purpose_path = self.data_dir / "purpose.md"
        if purpose_path.exists():
            return purpose_path.read_text(encoding="utf-8")[:2000]
        return ""

    def _collect_all_pages(self):
        """收集 wiki 目录下所有 markdown 页面"""
        pages = []
        for p in self.wiki_dir.rglob("*.md"):
            if p.name != "overview.md":
                pages.append(p)
        return sorted(pages)

    def get_all_pages(self):
        """获取所有 wiki 页面对象"""
        pages = []
        for p in self._collect_all_pages():
            page = WikiPage.from_file(p)
            if page:
                pages.append(page)
        return pages

    def _save_debug_log(self, label, raw_text):
        """保存 LLM 原始响应用于调试"""
        debug_dir = self.data_dir / ".llm_debug"
        debug_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = debug_dir / f"{label}_{ts}.txt"
        path.write_text(str(raw_text), encoding="utf-8")