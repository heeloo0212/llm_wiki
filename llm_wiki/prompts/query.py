"""Query 提示词模板"""

QUERY_SYSTEM = "你是一个知识库问答专家。根据 wiki 页面内容，综合回答用户问题。回答需标注信息来源页面，使用 [[wikilink]] 引用。如果信息不足以回答，请明确指出知识缺口。"


QUERY_PROMPT = """## 任务：基于 Wiki 回答问题

### 用户问题
{question}

### 相关 Wiki 页面
{relevant_pages}

### Wiki Schema
{schema_content}

### 研究方向
{purpose_content}

请综合以上信息回答用户问题。要求：

1. 回答需综合多个来源的信息
2. 使用 [[wikilink]] 引用相关 wiki 页面作为来源标注
3. 如果不同页面有矛盾观点，请指出
4. 如果信息不足以完整回答，列出知识缺口
5. 判断此回答是否有价值保存为新的 wiki 页面

如果回答值得保存，在回答末尾添加：

---
**save_as_page: true**
**suggested_title**: 建议的页面标题
**suggested_type**: query
**suggested_tags**: tag1, tag2
"""


SAVE_QUERY_SYSTEM = "你是一个知识库整理专家。将查询回答整理为规范的 wiki 页面。"


SAVE_QUERY_PROMPT = """## 任务：将查询结果保存为 Wiki 页面

### 查询问题
{question}

### 查询回答
{answer}

### 已有相关页面
{existing_pages}

请将此查询结果整理为 wiki 页面格式，输出 JSON：

{{
  "file_path": "queries/xxx.md",
  "frontmatter": {{
    "type": "query",
    "title": "页面标题",
    "sources": ["相关源文件路径"],
    "tags": ["tag1", "tag2"],
    "created": "2026-04-24",
    "updated": "2026-04-24"
  }},
  "content": "整理后的页面正文"
}}"""