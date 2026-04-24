"""LLM Wiki CLI 入口"""
import sys
from pathlib import Path

import click

# 将项目根目录加入 path
sys.path.insert(0, str(Path(__file__).parent))

from config import LLMConfig, WikiConfig, load_config, save_config
from llm_wiki.llm import get_provider


def _create_llm(llm_cfg: LLMConfig):
    """根据配置创建 LLM Provider"""
    ProviderCls = get_provider(llm_cfg.provider)
    kwargs = dict(
        api_key=llm_cfg.api_key,
        model=llm_cfg.model,
        temperature=llm_cfg.temperature,
        max_tokens=llm_cfg.max_tokens,
    )
    if llm_cfg.provider == "claude":
        return ProviderCls(**kwargs)
    else:
        return ProviderCls(
            base_url=llm_cfg.base_url,
            embedding_model=llm_cfg.embedding_model,
            embedding_base_url=llm_cfg.embedding_base_url,
            **kwargs,
        )


def _create_wiki(llm_cfg: LLMConfig, wiki_cfg: WikiConfig):
    """创建 LLMWiki 实例"""
    from llm_wiki.wiki import LLMWiki
    llm = _create_llm(llm_cfg)
    return LLMWiki(data_dir=wiki_cfg.data_dir, llm=llm, language=wiki_cfg.language)


@click.group()
@click.option("--config", "config_path", default=None, help="配置文件路径")
@click.pass_context
def cli(ctx, config_path):
    """LLM Wiki — 基于 Karpathy 概念的个人知识库"""
    ctx.ensure_object(dict)
    llm_cfg, wiki_cfg = load_config(config_path)
    ctx.obj["llm_cfg"] = llm_cfg
    ctx.obj["wiki_cfg"] = wiki_cfg
    ctx.obj["config_path"] = config_path


@cli.command()
@click.option("--name", default="My Wiki", help="知识库名称")
@click.option("--path", "data_dir", default=None, help="数据目录路径")
@click.pass_context
def init(ctx, name, data_dir):
    """初始化一个新的知识库"""
    wiki_cfg: WikiConfig = ctx.obj["wiki_cfg"]
    if data_dir:
        wiki_cfg.data_dir = data_dir
    wiki_cfg.name = name

    wiki = _create_wiki(ctx.obj["llm_cfg"], wiki_cfg)
    wiki.init(name)

    # 保存配置
    save_config(ctx.obj["llm_cfg"], wiki_cfg, ctx.obj["config_path"])
    click.echo(f"知识库 '{name}' 已初始化在: {wiki_cfg.data_dir}")


@cli.command()
@click.argument("source", type=click.Path(exists=True))
@click.pass_context
def ingest(ctx, source):
    """消化源文件或目录"""
    source_path = Path(source)
    wiki = _create_wiki(ctx.obj["llm_cfg"], ctx.obj["wiki_cfg"])

    if source_path.is_dir():
        results = wiki.ingest_dir(source_path)
        for r in results:
            if r.skipped:
                click.echo(f"[SKIP] {r.source_file} (未变更)")
            elif r.error:
                click.echo(f"[ERROR] {r.source_file}: {r.error}")
            else:
                click.echo(f"[OK] {r.source_file}")
                click.echo(f"  新建: {len(r.pages_created)} 页, 更新: {len(r.pages_updated)} 页")
                if r.contradictions:
                    click.echo(f"  矛盾: {len(r.contradictions)} 个")
    else:
        result = wiki.ingest(source_path)
        if result.skipped:
            click.echo(f"[SKIP] {result.source_file} (未变更)")
        elif result.error:
            click.echo(f"[ERROR] {result.source_file}: {result.error}")
        else:
            click.echo(f"[OK] {result.source_file}")
            click.echo(f"  新建: {len(result.pages_created)} 页, 更新: {len(result.pages_updated)} 页")
            for p in result.pages_created:
                click.echo(f"  + {p}")
            for p in result.pages_updated:
                click.echo(f"  ~ {p}")


@cli.command()
@click.argument("question")
@click.pass_context
def query(ctx, question):
    """查询知识库"""
    wiki = _create_wiki(ctx.obj["llm_cfg"], ctx.obj["wiki_cfg"])
    answer = wiki.query(question)
    click.echo(answer)


@cli.command()
@click.pass_context
def lint(ctx):
    """健康检查知识库"""
    wiki = _create_wiki(ctx.obj["llm_cfg"], ctx.obj["wiki_cfg"])
    issues = wiki.lint()

    if not issues:
        click.echo("知识库健康状态良好，未发现问题。")
        return

    click.echo(f"发现 {len(issues)} 个问题：\n")
    for issue in issues:
        icon = "⚠️" if issue.severity == "warning" else "❌"
        click.echo(f"{icon} [{issue.issue_type}] {issue.page}")
        click.echo(f"   {issue.detail}")
        if issue.suggestion:
            click.echo(f"   建议: {issue.suggestion}")
        click.echo()


@cli.command()
@click.option("--output", default=None, help="输出 HTML 路径")
@click.option("--infer/--no-infer", default=False, help="是否使用 LLM 推断语义关系")
@click.pass_context
def graph(ctx, output, infer):
    """构建知识图谱并生成可视化 HTML"""
    wiki_cfg: WikiConfig = ctx.obj["wiki_cfg"]
    llm = _create_llm(ctx.obj["llm_cfg"]) if infer else None

    from llm_wiki.graph.builder import GraphBuilder
    from llm_wiki.graph.visualizer import GraphVisualizer

    wiki_dir = Path(wiki_cfg.data_dir) / "wiki"
    builder = GraphBuilder(wiki_dir, llm=llm)
    nodes, edges = builder.build()

    if not nodes:
        click.echo("Wiki 中没有页面，请先 ingest 一些源文件。")
        return

    click.echo(f"构建图谱: {len(nodes)} 个节点, {len(edges)} 条边")

    vis = GraphVisualizer(nodes, edges)
    output_path = Path(output) if output else Path(wiki_cfg.data_dir) / "graph" / "knowledge-graph.html"
    vis.render(output_path, title=f"{wiki_cfg.name} — Knowledge Graph")

    click.echo(f"图谱已生成: {output_path}")
    click.echo("双击 HTML 文件即可在浏览器中查看。")


@cli.command()
@click.option("--port", default=8501, help="Web UI 端口")
@click.pass_context
def serve(ctx, port):
    """启动 Streamlit Web UI"""
    import subprocess
    web_app_path = Path(__file__).parent / "web_app.py"
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", str(web_app_path), "--server.port", str(port)],
    )


@cli.command()
@click.option("--provider", type=click.Choice(["openai", "claude"]), help="LLM 提供者")
@click.option("--model", help="模型名称")
@click.option("--api-key", help="API Key")
@click.option("--base-url", help="API Base URL (OpenAI 兼容接口)")
@click.pass_context
def configure(ctx, provider, model, api_key, base_url):
    """配置 LLM Wiki"""
    llm_cfg: LLMConfig = ctx.obj["llm_cfg"]
    wiki_cfg: WikiConfig = ctx.obj["wiki_cfg"]

    if provider:
        llm_cfg.provider = provider
    if model:
        llm_cfg.model = model
    if api_key:
        llm_cfg.api_key = api_key
    if base_url:
        llm_cfg.base_url = base_url

    save_config(llm_cfg, wiki_cfg, ctx.obj["config_path"])
    click.echo(f"配置已保存:")
    click.echo(f"  Provider: {llm_cfg.provider}")
    click.echo(f"  Model: {llm_cfg.model}")
    click.echo(f"  Base URL: {llm_cfg.base_url}")


if __name__ == "__main__":
    cli()