"""LLM Wiki Streamlit Web UI"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st

from config import LLMConfig, WikiConfig, load_config, save_config
from llm_wiki.llm import get_provider


def _create_llm(llm_cfg: LLMConfig):
    ProviderCls = get_provider(llm_cfg.provider)
    kwargs = dict(api_key=llm_cfg.api_key, model=llm_cfg.model,
                  temperature=llm_cfg.temperature, max_tokens=llm_cfg.max_tokens)
    if llm_cfg.provider == "claude":
        return ProviderCls(**kwargs)
    return ProviderCls(base_url=llm_cfg.base_url, embedding_model=llm_cfg.embedding_model,
                       embedding_base_url=llm_cfg.embedding_base_url, **kwargs)


def _create_wiki(llm_cfg, wiki_cfg):
    from llm_wiki.wiki import LLMWiki
    llm = _create_llm(llm_cfg)
    return LLMWiki(data_dir=wiki_cfg.data_dir, llm=llm, language=wiki_cfg.language)


# ── 页面配置 ────────────────────────────────────────────

st.set_page_config(page_title="LLM Wiki", page_icon="📚", layout="wide")
st.title("📚 LLM Wiki")

llm_cfg, wiki_cfg = load_config()

# ── 侧边栏 ──────────────────────────────────────────────

with st.sidebar:
    st.header("⚙️ 配置")

    provider = st.selectbox("LLM Provider", ["openai", "claude"],
                            index=["openai", "claude"].index(llm_cfg.provider))
    model = st.text_input("Model", value=llm_cfg.model)
    api_key = st.text_input("API Key", value=llm_cfg.api_key, type="password")
    base_url = st.text_input("Base URL", value=llm_cfg.base_url)
    data_dir = st.text_input("Data Dir", value=wiki_cfg.data_dir)
    language = st.selectbox("Language", ["zh", "en"],
                            index=["zh", "en"].index(wiki_cfg.language))

    if st.button("💾 保存配置"):
        llm_cfg.provider = provider
        llm_cfg.model = model
        llm_cfg.api_key = api_key
        llm_cfg.base_url = base_url
        wiki_cfg.data_dir = data_dir
        wiki_cfg.language = language
        save_config(llm_cfg, wiki_cfg)
        st.success("配置已保存")
        st.rerun()

    st.divider()

    # 操作按钮
    st.header("🔧 操作")
    if st.button("初始化知识库"):
        try:
            wiki = _create_wiki(llm_cfg, wiki_cfg)
            wiki.init(wiki_cfg.name)
            st.success(f"知识库已初始化: {wiki_cfg.data_dir}")
        except Exception as e:
            st.error(f"初始化失败: {e}")

    if st.button("构建知识图谱"):
        try:
            from llm_wiki.graph.builder import GraphBuilder
            from llm_wiki.graph.visualizer import GraphVisualizer
            wiki_dir = Path(wiki_cfg.data_dir) / "wiki"
            builder = GraphBuilder(wiki_dir)
            nodes, edges = builder.build()
            vis = GraphVisualizer(nodes, edges)
            output_path = Path(wiki_cfg.data_dir) / "graph" / "knowledge-graph.html"
            vis.render(output_path, title=f"{wiki_cfg.name} — Knowledge Graph")
            st.success(f"图谱已生成: {len(nodes)} 节点, {len(edges)} 边")
        except Exception as e:
            st.error(f"构建图谱失败: {e}")

    if st.button("健康检查 (Lint)"):
        try:
            wiki = _create_wiki(llm_cfg, wiki_cfg)
            issues = wiki.lint()
            if issues:
                for issue in issues:
                    icon = "⚠️" if issue.severity == "warning" else "❌"
                    st.warning(f"{icon} [{issue.issue_type}] {issue.page}: {issue.detail}")
            else:
                st.success("知识库健康状态良好")
        except Exception as e:
            st.error(f"Lint 失败: {e}")

# ── 主界面 ──────────────────────────────────────────────

tab_ingest, tab_query, tab_pages, tab_log = st.tabs(["📥 Ingest", "🔍 Query", "📄 Pages", "📋 Log"])

with tab_ingest:
    st.header("消化源文件")

    source_file = st.text_input("源文件路径 (支持文件或目录)")
    if st.button("消化", key="ingest_btn"):
        if not source_file:
            st.warning("请输入源文件路径")
        else:
            with st.spinner("LLM 正在消化源文件..."):
                try:
                    wiki = _create_wiki(llm_cfg, wiki_cfg)
                    path = Path(source_file)
                    if path.is_dir():
                        results = wiki.ingest_dir(path)
                        for r in results:
                            if r.skipped:
                                st.info(f"[SKIP] {r.source_file}")
                            elif r.error:
                                st.error(f"[ERROR] {r.source_file}: {r.error}")
                            else:
                                st.success(f"[OK] {r.source_file}: 新建 {len(r.pages_created)} 页, 更新 {len(r.pages_updated)} 页")
                    else:
                        result = wiki.ingest(path)
                        if result.skipped:
                            st.info(f"文件未变更，跳过: {result.source_file}")
                        elif result.error:
                            st.error(f"消化失败: {result.error}")
                        else:
                            st.success(f"消化成功: 新建 {len(result.pages_created)} 页, 更新 {len(result.pages_updated)} 页")
                            for p in result.pages_created:
                                st.write(f"  + {p}")
                            for p in result.pages_updated:
                                st.write(f"  ~ {p}")
                except Exception as e:
                    st.error(f"消化失败: {e}")

    # 文件上传
    uploaded = st.file_uploader("或上传文件", type=["md", "txt", "markdown"])
    if uploaded and st.button("消化上传文件"):
        raw_dir = Path(wiki_cfg.data_dir) / "raw" / "articles"
        raw_dir.mkdir(parents=True, exist_ok=True)
        dest = raw_dir / uploaded.name
        dest.write_bytes(uploaded.getbuffer())
        with st.spinner("LLM 正在消化..."):
            try:
                wiki = _create_wiki(llm_cfg, wiki_cfg)
                result = wiki.ingest(dest)
                if result.error:
                    st.error(f"消化失败: {result.error}")
                else:
                    st.success(f"消化成功: 新建 {len(result.pages_created)} 页")
            except Exception as e:
                st.error(f"消化失败: {e}")

with tab_query:
    st.header("查询知识库")

    question = st.text_input("输入你的问题")
    if st.button("查询", key="query_btn"):
        if not question:
            st.warning("请输入问题")
        else:
            with st.spinner("LLM 正在思考..."):
                try:
                    wiki = _create_wiki(llm_cfg, wiki_cfg)
                    answer = wiki.query(question)
                    st.markdown(answer)
                except Exception as e:
                    st.error(f"查询失败: {e}")

with tab_pages:
    st.header("Wiki 页面浏览")

    wiki_dir = Path(wiki_cfg.data_dir) / "wiki"
    if wiki_dir.exists():
        # 页面类型选择
        page_types = ["all", "entities", "concepts", "sources", "syntheses", "queries"]
        selected_type = st.selectbox("页面类型", page_types)

        # 收集页面
        pages = []
        search_dir = wiki_dir if selected_type == "all" else wiki_dir / selected_type
        if search_dir.exists():
            for md in search_dir.rglob("*.md"):
                pages.append(md)

        if pages:
            page_names = [str(p.relative_to(wiki_dir)) for p in pages]
            selected_page = st.selectbox("选择页面", page_names)

            if selected_page:
                page_path = wiki_dir / selected_page
                if page_path.exists():
                    content = page_path.read_text(encoding="utf-8")
                    st.markdown(content)
        else:
            st.info("暂无 wiki 页面，请先 ingest 一些源文件。")
    else:
        st.info("知识库尚未初始化，请先在侧边栏点击「初始化知识库」。")

with tab_log:
    st.header("操作日志")

    from llm_wiki.indexer import LogManager
    log_path = Path(wiki_cfg.data_dir) / "log.md"
    log_mgr = LogManager(log_path)

    if log_path.exists():
        entries = log_mgr.get_recent(20)
        for entry in entries:
            st.write(f"**[{entry['timestamp']}] {entry['operation']}**")
            st.write(entry["detail"])
            st.divider()
    else:
        st.info("暂无操作日志。")