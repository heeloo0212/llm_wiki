"""SHA256 增量缓存"""
import hashlib
import json
from pathlib import Path
from typing import Optional


class IngestCache:
    """基于 SHA256 的文件增量缓存，跳过未变更的源文件"""

    def __init__(self, cache_path: Path):
        self.cache_path = cache_path
        self._data: dict[str, str] = {}  # file_path -> sha256
        self._load()

    def _load(self):
        if self.cache_path.exists():
            try:
                self._data = json.loads(self.cache_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def save(self):
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @staticmethod
    def _hash_file(path: Path) -> str:
        h = hashlib.sha256()
        h.update(path.read_bytes())
        return h.hexdigest()

    def is_cached(self, file_path) -> bool:
        """检查文件是否已缓存且内容未变"""
        path = Path(file_path)
        if not path.exists():
            return False
        current_hash = self._hash_file(path)
        return self._data.get(str(path)) == current_hash

    def mark_processed(self, file_path):
        """标记文件为已处理"""
        path = Path(file_path)
        self._data[str(path)] = self._hash_file(path)
        self.save()

    def remove(self, file_path):
        """移除缓存条目"""
        self._data.pop(str(file_path), None)
        self.save()

    def clear(self):
        self._data.clear()
        self.save()