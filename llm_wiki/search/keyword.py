"""BM25 关键词搜索 — 支持中英文"""
import math
import re
from collections import Counter
from pathlib import Path


# 英文停用词
EN_STOPS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "between", "out", "off", "over",
    "under", "again", "further", "then", "once", "and", "but", "or", "nor",
    "not", "so", "yet", "both", "either", "neither", "each", "every",
    "all", "any", "few", "more", "most", "other", "some", "such", "no",
    "only", "own", "same", "than", "too", "very", "just", "because",
    "this", "that", "these", "those", "it", "its", "i", "me", "my", "we",
    "our", "you", "your", "he", "him", "his", "she", "her", "they", "them",
    "what", "which", "who", "whom", "how", "when", "where", "why",
}

# 中文停用词
ZH_STOPS = {"的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一",
            "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有",
            "看", "好", "自己", "这", "他", "她", "它", "们", "那", "些", "什么",
            "怎么", "如果", "因为", "所以", "但是", "而且", "或者", "然后", "可以",
            "这个", "那个", "就是", "已经", "还是", "不是", "没有", "只是"}


def tokenize(text: str) -> list[str]:
    """混合中英文分词：英文按词，中文按 bigram"""
    tokens = []
    # 英文分词
    en_words = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]*", text.lower())
    for w in en_words:
        if w not in EN_STOPS and len(w) > 1:
            tokens.append(w)

    # 中文 CJK bigram
    cjk_chars = re.findall(r"[一-鿿]", text)
    cjk_text = "".join(cjk_chars)
    for ch in cjk_text:
        if ch not in ZH_STOPS:
            tokens.append(ch)
    for i in range(len(cjk_text) - 1):
        bigram = cjk_text[i:i + 2]
        if not all(c in ZH_STOPS for c in bigram):
            tokens.append(bigram)

    return tokens


class BM25Index:
    """BM25 倒排索引"""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.docs: dict[str, list[str]] = {}      # doc_id -> tokens
        self.df: Counter = Counter()               # token -> 文档频率
        self.avg_dl: float = 0
        self.n_docs: int = 0

    def add(self, doc_id: str, text: str):
        tokens = tokenize(text)
        self.docs[doc_id] = tokens
        self.n_docs = len(self.docs)
        unique_tokens = set(tokens)
        for t in unique_tokens:
            self.df[t] += 1
        self.avg_dl = sum(len(v) for v in self.docs.values()) / self.n_docs if self.n_docs else 0

    def search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        query_tokens = tokenize(query)
        scores: dict[str, float] = {}

        for doc_id, doc_tokens in self.docs.items():
            score = 0.0
            dl = len(doc_tokens)
            tf_counter = Counter(doc_tokens)

            for qt in query_tokens:
                if qt not in tf_counter:
                    continue
                tf = tf_counter[qt]
                df = self.df.get(qt, 0)
                idf = math.log((self.n_docs - df + 0.5) / (df + 0.5) + 1)
                tf_norm = (tf * (self.k1 + 1)) / (tf + self.k1 * (1 - self.b + self.b * dl / max(self.avg_dl, 1)))
                score += idf * tf_norm

            if score > 0:
                scores[doc_id] = score

        # 标题匹配加分
        for doc_id in scores:
            doc_name = Path(doc_id).stem.lower()
            for qt in query_tokens:
                if qt in doc_name:
                    scores[doc_id] += 10

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]


class KeywordSearch:
    """关键词搜索 — 在 wiki 页面上构建 BM25 索引"""

    def __init__(self, wiki_dir: Path, index_path: Path):
        self.wiki_dir = wiki_dir
        self.index_path = index_path

    def _build_index(self) -> BM25Index:
        idx = BM25Index()
        for md in self.wiki_dir.rglob("*.md"):
            try:
                content = md.read_text(encoding="utf-8")
                rel = str(md.relative_to(self.wiki_dir))
                idx.add(rel, content)
            except Exception:
                continue
        return idx

    def search(self, query: str, top_k: int = 10) -> list[str]:
        """搜索返回相对路径列表"""
        idx = self._build_index()
        results = idx.search(query, top_k)
        return [r[0] for r in results]