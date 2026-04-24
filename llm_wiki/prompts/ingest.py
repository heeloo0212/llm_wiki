"""Ingest 提示词模板"""


ANALYSIS_SYSTEM = "你是一个知识库分析专家。你的任务是分析源文档，提取关键信息，并识别与现有知识库的关联。请严格按照 JSON 格式输出。"


ANALYSIS_PROMPT = """## 任务：分析源文档

### 源文档内容
{source_content}

### 已有 Wiki 索引
{index_content}

### Wiki Schema 规则
{schema_content}

### 研究方向 (purpose)
{purpose_content}

请分析此源文档，输出以下 JSON：

{{
  "title": "源文档标题",
  "summary": "100-200字的源文档摘要",
  "entities": [
    {{"name": "实体名", "type": "person|org|project|tool", "description": "简述", "existing_page": "已有wiki页面文件名或null"}}
  ],
  "concepts": [
    {{"name": "概念名", "description": "简述", "existing_page": "已有wiki页面文件名或null"}}
  ],
  "key_arguments": ["主要论点1", "主要论点2"],
  "connections": [
    {{"from": "当前实体/概念", "to": "已有wiki页面", "relation": "关系描述"}}
  ],
  "contradictions": [
    {{"claim": "冲突声明", "existing_page": "已有页面", "existing_claim": "已有观点"}}
  ],
  "recommended_structure": {{
    "new_pages": ["需要新建的页面文件名列表"],
    "update_pages": ["需要更新的已有页面文件名列表"]
  }}
}}

注意：
1. entities 和 concepts 只提取文档中重要且值得独立建页的，不要过度拆分
2. connections 标注与已有 wiki 内容的关联
3. contradictions 标注新文档与已有观点的矛盾
4. 文件名使用小写英文+连字符，如 attention-mechanism.md
"""


GENERATE_SYSTEM = """你是一个知识库维护专家。根据分析结果，生成和更新 wiki 页面。
每个页面的格式为：

---
type: entity|concept|source|synthesis|query
title: 页面标题
sources:
  - raw/xxx.md
tags:
  - tag1
created: 2026-04-24
updated: 2026-04-24
---

页面正文内容，使用 [[wikilink]] 引用其他页面。
"""


GENERATE_PROMPT = """## 任务：根据分析结果生成 Wiki 页面

### 分析结果
{analysis_json}

### 已有 Wiki 页面内容（需要更新的页面）
{existing_pages}

### Schema 规则
{schema_content}

请输出以下 JSON：

{{
  "pages": [
    {{
      "file_path": "entities/openai.md",
      "frontmatter": {{
        "type": "entity",
        "title": "OpenAI",
        "sources": ["raw/articles/xxx.md"],
        "tags": ["company", "AI"],
        "created": "2026-04-24",
        "updated": "2026-04-24"
      }},
      "content": "页面正文（markdown格式，使用[[wikilink]]交叉引用）"
    }}
  ],
  "overview_update": "overview.md 的更新内容（反映新添加的知识）",
  "log_entry": "ingest 操作的简短日志描述"
}}

要求：
1. 每个页面必须有完整的 YAML frontmatter
2. 正文使用 [[wikilink]] 引用其他 wiki 页面
3. 新建页面和更新已有页面都包含在 pages 中
4. 对于已有页面的更新，在内容末尾追加新段落，标注来源
5. 源摘要页（source类型）是对原始文档的精炼总结
6. 实体/概念页应该整合来自多个源的信息
7. 发现矛盾时在页面中用 ⚠️ 标注
"""