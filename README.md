# LLM Wiki

基于 [Karpathy 的 LLM Wiki 概念](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) 的个人知识库实现。

核心思想：LLM 增量构建和维护持久化的 wiki 知识库，而非每次查询都从原始文档重新推导。

## 功能

- **Ingest** — 两步式链式思考消化源文件，自动生成实体页、概念页、素材摘要
- **Query** — 多阶段检索（BM25 关键词 + 可选向量语义搜索），综合回答并标注来源
- **Lint** — 规则层面 + LLM 深度健康检查（断链、孤立页面、矛盾、知识缺口）
- **知识图谱** — 解析 wikilinks + LLM 推断语义关系，Louvain 社区检测，自包含 HTML 可视化
- **增量缓存** — SHA256 去重，未变更文件自动跳过
- **双 LLM 后端** — OpenAI 兼容接口 + Claude API
- **CLI + Web UI** — Click 命令行 + Streamlit 可视化界面
- **Obsidian 兼容** — 所有内容为本地 markdown，可用 Obsidian 打开

## 安装

```bash
cd llm_wiki
pip install -r requirements.txt
```

## 快速开始

```bash
# 1. 初始化知识库
python main.py init --name "我的知识库" --path ./data

# 2. 配置 LLM
python main.py configure --provider openai --model gpt-4o --api-key sk-xxx --base-url https://api.openai.com/v1

# 3. 消化源文件
python main.py ingest ./data/raw/articles/my-article.md

# 4. 查询
python main.py query "这篇文章的核心观点是什么？"

# 5. 健康检查
python main.py lint

# 6. 构建知识图谱
python main.py graph

# 7. 启动 Web UI
python main.py serve
```

## 目录结构

```
data/
├── raw/                    # 原始素材（不可变）
│   ├── articles/
│   ├── papers/
│   └── notes/
├── wiki/                   # LLM 生成的知识库
│   ├── entities/           # 实体页（人物、组织、项目）
│   ├── concepts/           # 概念页（思想、框架、方法）
│   ├── sources/            # 素材摘要
│   ├── syntheses/          # 综合分析
│   └── queries/            # 保存的查询结果
├── graph/                  # 知识图谱 HTML
├── purpose.md              # 研究方向与目标
├── schema.md               # Wiki 规则配置
├── index.md                # 内容目录
├── log.md                  # 操作日志
├── overview.md             # 综合概览
└── .wiki-cache.json        # 增量缓存
```

## 环境变量

| 变量 | 说明 |
|---|---|
| `LLM_WIKI_API_KEY` | LLM API Key |
| `LLM_WIKI_BASE_URL` | API Base URL |
| `LLM_WIKI_MODEL` | 模型名称 |
| `LLM_WIKI_PROVIDER` | openai / claude |
| `LLM_WIKI_DATA_DIR` | 数据目录路径 |

## 支持的 LLM 后端

- **OpenAI 兼容接口**: OpenAI、DeepSeek、Ollama、vLLM 等任何兼容 `/v1/chat/completions` 的服务
- **Claude API**: Anthropic Claude 系列（embedding 使用 OpenAI 兼容端点）