"""index.md 和 log.md 管理"""
import re
from datetime import datetime
from pathlib import Path


class IndexManager:
    """管理 index.md — 内容目录"""

    def __init__(self, index_path: Path):
        self.index_path = index_path

    def load(self) -> str:
        if self.index_path.exists():
            return self.index_path.read_text(encoding="utf-8")
        return ""

    def save(self, content: str):
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(content, encoding="utf-8")

    def init(self, wiki_name: str = "My Wiki"):
        """初始化 index.md"""
        content = f"# {wiki_name} — Index\n\n> 此文件由 LLM Wiki 自动维护，记录所有 wiki 页面目录。\n\n"
        for section in ["Entities", "Concepts", "Sources", "Syntheses", "Queries"]:
            content += f"## {section}\n\n\n"
        self.save(content)

    def add_page(self, page_type: str, title: str, file_name: str, summary: str = ""):
        """添加页面到 index"""
        content = self.load()
        section_header = f"## {page_type.capitalize()}"

        # 找到对应 section
        sections = content.split(section_header)
        if len(sections) < 2:
            # section 不存在，追加
            content += f"\n{section_header}\n\n- [[{file_name}|{title}]] — {summary}\n"
        else:
            # 在 section 末尾追加条目
            parts = sections[1].split("\n## ")
            entry = f"- [[{file_name}|{title}]] — {summary}\n"
            parts[0] = parts[0].rstrip() + "\n" + entry + "\n"
            sections[1] = "\n## ".join(parts)
            content = section_header.join(sections)

        self.save(content)

    def remove_page(self, file_name: str):
        """从 index 移除页面"""
        content = self.load()
        # 移除包含该文件名的行
        lines = content.split("\n")
        lines = [l for l in lines if f"[[{file_name}]" not in l and f"|{file_name}]]" not in l]
        self.save("\n".join(lines))


class LogManager:
    """管理 log.md — 操作日志"""

    def __init__(self, log_path: Path):
        self.log_path = log_path

    def load(self) -> str:
        if self.log_path.exists():
            return self.log_path.read_text(encoding="utf-8")
        return ""

    def save(self, content: str):
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text(content, encoding="utf-8")

    def init(self):
        if not self.log_path.exists():
            self.save("# Wiki Log\n\n> 按时间顺序记录所有操作。\n\n")

    def append(self, operation: str, detail: str):
        """追加日志条目"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"## [{timestamp}] {operation}\n\n{detail}\n\n"
        content = self.load()
        content += entry
        self.save(content)

    def get_recent(self, n: int = 5) -> list[dict]:
        """获取最近 n 条日志"""
        content = self.load()
        pattern = r"## \[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\] (\w+)\n\n(.*?)(?=\n## \[|\Z)"
        entries = []
        for match in re.finditer(pattern, content, re.DOTALL):
            entries.append({
                "timestamp": match.group(1),
                "operation": match.group(2),
                "detail": match.group(3).strip(),
            })
        return entries[-n:]