"""Lint 提示词模板"""

LINT_SYSTEM = "你是一个知识库质量检查专家。检查 wiki 的健康状态，发现问题并给出改进建议。"


LINT_PROMPT = """## 任务：Wiki 健康检查

### Wiki 索引
{index_content}

### 所有页面列表和摘要
{pages_summary}

### 已发现的规则层面问题
{rule_issues}

请基于以上信息进行深度检查，输出 JSON：

{{
  "contradictions": [
    {{
      "page1": "页面1路径",
      "page2": "页面2路径",
      "description": "矛盾描述",
      "suggestion": "建议处理方式"
    }}
  ],
  "knowledge_gaps": [
    {{
      "concept": "缺失概念",
      "mentioned_in": ["提及此概念的页面列表"],
      "suggestion": "建议补充方向"
    }}
  ],
  "improvement_suggestions": [
    "改进建议1",
    "改进建议2"
  ],
  "overall_health": "good|fair|poor",
  "health_detail": "健康状态详细说明"
}}

请特别关注：
1. 不同页面间的矛盾声明
2. 频繁提及但无独立页面的重要概念
3. 可以深化或扩展的主题
4. 建议的下一步研究方向
"""