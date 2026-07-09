"""整理器 - 分类、标签、清洗"""
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List

import jieba
import jieba.analyse

from ..config import OrganizerConfig
from ..models import Note, NoteCollection


class NoteOrganizer:
    """笔记整理器"""

    def __init__(self, config: OrganizerConfig):
        self.config = config
        self._stopwords: set = set()

    def organize(self, collection: NoteCollection) -> NoteCollection:
        """执行完整整理流程"""
        print(f"\n📝 开始整理 {collection.total_count} 条笔记...")

        # 1. 清洗内容
        collection = self._clean_all(collection)
        print(f"   ✅ 内容清洗完成")

        # 2. 自动分类
        if self.config.auto_categorize:
            collection = self._categorize_all(collection)
            print(f"   ✅ 自动分类完成")

        # 3. 提取标签
        collection = self._tag_all(collection)
        print(f"   ✅ 标签提取完成")

        # 4. 统计
        stats = collection.stats()
        print(f"\n📊 整理统计:")
        print(f"   总笔记数: {stats['total']}")
        print(f"   总字数: {stats['total_words']:,}")
        print(f"   平均字数: {stats['avg_words']}")
        print(f"   分类分布:")
        for cat, count in sorted(stats["categories"].items()):
            print(f"     - {cat}: {count} 篇")

        return collection

    def _clean_all(self, collection: NoteCollection) -> NoteCollection:
        """清洗所有笔记"""
        for note in collection.notes:
            content = note.content

            if self.config.remove_empty_lines:
                content = re.sub(r"\n{3,}", "\n\n", content)

            if self.config.normalize_whitespace:
                content = re.sub(r"[ \t]+", " ", content)
                # 保留代码块内的空格
                content = re.sub(r" +$", "", content, flags=re.MULTILINE)

            # 修复常见 Markdown 问题
            content = re.sub(r"^\s*[-*]\s*$", "", content, flags=re.MULTILINE)  # 空列表项
            content = re.sub(r"```\s*```", "", content)  # 空代码块

            note.content = content.strip()

        return collection

    def _categorize_all(self, collection: NoteCollection) -> NoteCollection:
        """自动分类所有笔记"""
        keywords = self.config.category_keywords

        for note in collection.notes:
            # 如果已有分类则跳过
            if note.category:
                continue

            # 根据关键词匹配
            text = note.title + " " + note.content[:500]
            scores: Dict[str, int] = {}

            for cat, kws in keywords.items():
                score = sum(1 for kw in kws if kw.lower() in text.lower())
                if score > 0:
                    scores[cat] = score

            if scores:
                note.category = max(scores, key=scores.get)
            else:
                note.category = "其他"

        return collection

    def _tag_all(self, collection: NoteCollection) -> NoteCollection:
        """为笔记提取标签"""
        for note in collection.notes:
            if note.tags:
                continue

            # 使用 jieba 提取关键词
            text = note.title + " " + note.content[:1000]
            # 清理文本
            text = re.sub(r"[#*`>\[\]!\-\[\]\(\)]", " ", text)

            try:
                tags = jieba.analyse.extract_tags(
                    text, topK=5, allowPOS=("n", "nr", "ns", "nt", "nz", "eng")
                )
                note.tags = [t for t in tags if len(t) > 1 and not t.isdigit()]
            except Exception:
                pass

        return collection
