# -*- coding: utf-8 -*-
"""零依赖企业知识库：摄取 markdown/txt → 按段落分块 → 字符二元组相似度检索。

设计取舍：不用向量数据库、不用网络嵌入服务——保证「可移植复刻、全本地、离线可跑」。
知识库规模在几百个段落以内检索质量足够；后续可平滑替换为向量检索（接口不变）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Chunk:
    text: str
    source: str      # 来源文档名（不含扩展名）
    heading: str     # 所属小节标题


def _bigrams(text: str) -> set[str]:
    cleaned = re.sub(r"[\s，。、：；！？\-#*（）()]", "", text)
    return {cleaned[i:i + 2] for i in range(len(cleaned) - 1)} if len(cleaned) > 1 else {cleaned}


class KnowledgeBase:
    def __init__(self, kb_dir: Path):
        self.kb_dir = Path(kb_dir)
        self.chunks: list[Chunk] = []

    def load(self) -> int:
        """摄取目录下全部 .md/.txt 文件。返回分块数。"""
        self.chunks = []
        if not self.kb_dir.exists():
            return 0
        for path in sorted(self.kb_dir.glob("*")):
            if path.suffix not in (".md", ".txt"):
                continue
            self._ingest_file(path)
        return len(self.chunks)

    def _ingest_file(self, path: Path) -> None:
        source = path.stem
        heading = ""
        current: list[str] = []

        def flush():
            if current:
                text = "\n".join(current).strip()
                if text:
                    self.chunks.append(Chunk(text=text, source=source, heading=heading))
                current.clear()

        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.rstrip()
                if line.startswith("#"):
                    flush()
                    heading = line.lstrip("#").strip()
                elif not line.strip():
                    flush()
                else:
                    current.append(line)
        flush()

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        """检索最相关分块。返回 [{text, source, heading, score}]，按分数降序。"""
        if not self.chunks:
            return []
        q = _bigrams(query)
        results = []
        for chunk in self.chunks:
            c = _bigrams(chunk.text + " " + chunk.heading + " " + chunk.source)
            overlap = len(q & c)
            if overlap == 0:
                continue
            score = overlap / (len(q) ** 0.5)  # 归一化：偏短查询不被长文档稀释
            results.append({
                "text": chunk.text,
                "source": chunk.source,
                "heading": chunk.heading,
                "score": round(score, 3),
            })
        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:top_k]

    def answer(self, query: str) -> Optional[str]:
        """直接生成带来源标注的答案；无命中返回 None。"""
        hits = self.search(query)
        if not hits or hits[0]["score"] < 0.5:
            return None
        top = hits[0]
        excerpt = top["text"].split("\n")[0]
        for para in top["text"].split("\n"):
            if len(para) > len(excerpt):
                excerpt = para
        return f"{excerpt}（出处：《{top['source']}》{top['heading']}）"
