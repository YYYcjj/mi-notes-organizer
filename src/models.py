"""笔记数据模型"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Note:
    """单条笔记"""

    title: str
    content: str
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None

    # 元数据
    source_file: str = ""
    folder: str = ""  # 原始文件夹
    category: str = ""  # 自动分类
    tags: list = field(default_factory=list)
    is_pinned: bool = False
    has_images: bool = False
    word_count: int = 0

    def __post_init__(self):
        if not self.word_count and self.content:
            self.word_count = len(self.content)

    @property
    def summary(self) -> str:
        """生成摘要"""
        text = self.content.strip()
        # 去除 Markdown 标记
        import re
        text = re.sub(r'[#*`>\[\]!]', '', text)
        text = re.sub(r'\n+', ' ', text)
        return text[:200] + ('...' if len(text) > 200 else '')

    @property
    def date_str(self) -> str:
        """格式化日期"""
        dt = self.created_at or self.modified_at
        if dt:
            return dt.strftime("%Y-%m-%d")
        return "未知日期"


@dataclass
class NoteCollection:
    """笔记集合"""

    notes: list[Note] = field(default_factory=list)
    total_count: int = 0
    categories: dict = field(default_factory=dict)
    date_range: tuple = ()

    def add(self, note: Note) -> None:
        self.notes.append(note)

    def stats(self) -> dict:
        """统计信息"""
        categories = {}
        total_words = 0
        for note in self.notes:
            categories[note.category] = categories.get(note.category, 0) + 1
            total_words += note.word_count

        return {
            "total": len(self.notes),
            "categories": categories,
            "total_words": total_words,
            "avg_words": total_words // max(len(self.notes), 1),
        }
