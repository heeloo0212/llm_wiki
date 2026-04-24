"""Schema 管理 — Wiki 的规则和约定"""
from pathlib import Path

DEFAULT_SCHEMA = """# Wiki Schema

此文件定义了 LLM Wiki 的结构规则和约定。

## 页面类型

- **entity**: 人物、组织、项目、工具等实体
- **concept**: 思想、框架、方法、理论等概念
- **source**: 原始素材的摘要页
- **synthesis**: 综合分析页（跨源对比、深度报告等）
- **query**: 保存的有价值的查询结果

## 页面格式

每个 wiki 页面必须包含 YAML frontmatter：

```yaml
---
type: entity|concept|source|synthesis|query
title: 页面标题
sources:
  - raw/articles/xxx.md
tags:
  - tag1
  - tag2
created: 2026-04-24
updated: 2026-04-24
---
```

## 命名规范

- 文件名使用小写英文 + 连字符: `attention-mechanism.md`
- 实体页放入 `wiki/entities/`
- 概念页放入 `wiki/concepts/`
- 素材摘要放入 `wiki/sources/`
- 综合分析放入 `wiki/syntheses/`
- 查询结果放入 `wiki/queries/`

## 交叉引用

使用 `[[wikilink]]` 语法引用其他 wiki 页面：
- `[[attention-mechanism]]` 链接到概念页
- `[[openai]]` 链接到实体页
- 链接目标为文件名（不含路径和扩展名）

## Ingest 规则

1. 读取新源文件，提取关键实体和概念
2. 为新实体/概念创建独立页面
3. 更新已有页面中相关内容
4. 每个源文件生成一个摘要页
5. 更新 index.md 和 log.md
6. 发现矛盾时在页面中标注

## Query 规则

1. 先搜索相关 wiki 页面
2. 阅读相关页面内容
3. 综合回答，标注信息来源
4. 有价值的回答可保存为新页面

## Lint 规则

- 检测孤立页面（无入站链接）
- 检测断链（wikilink 目标不存在）
- 检测矛盾（不同页面间冲突声明）
- 检测知识缺口（频繁提及但无独立页面）
- 检测 index.md 一致性
"""


class SchemaManager:
    """管理 Wiki Schema"""

    def __init__(self, schema_path: Path):
        self.schema_path = schema_path

    def load(self) -> str:
        if self.schema_path.exists():
            return self.schema_path.read_text(encoding="utf-8")
        return DEFAULT_SCHEMA

    def save(self, content: str):
        self.schema_path.parent.mkdir(parents=True, exist_ok=True)
        self.schema_path.write_text(content, encoding="utf-8")

    def init_default(self):
        """初始化默认 schema"""
        if not self.schema_path.exists():
            self.save(DEFAULT_SCHEMA)