"""测试笔记整理器"""
import tempfile
from pathlib import Path

from src.config import OrganizerConfig
from src.models import Note, NoteCollection
from src.parsers import MarkdownParser, JsonParser
from src.organizers import NoteOrganizer
from src.generators import MarkdownGenerator, SiteGenerator


def test_markdown_parser():
    """测试 Markdown 解析器"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        # 创建测试文件
        (tmp / "test1.md").write_text("# 测试笔记1\n\n这是内容", encoding="utf-8")
        (tmp / "test2.md").write_text("## 笔记2\n\n更多内容", encoding="utf-8")

        config = OrganizerConfig(input_dir=tmp)
        parser = MarkdownParser(config)
        collection = parser.parse(tmp)

        assert collection.total_count == 2
        assert collection.notes[0].title == "测试笔记1"


def test_json_parser():
    """测试 JSON 解析器"""
    import json
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        data = [
            {"title": "JSON笔记", "content": "JSON内容", "folder": "技术"},
            {"title": "", "content": "只有内容无标题的笔记"},
        ]
        (tmp / "notes.json").write_text(json.dumps(data), encoding="utf-8")

        config = OrganizerConfig(input_dir=tmp)
        parser = JsonParser(config)
        collection = parser.parse(tmp / "notes.json")

        assert collection.total_count == 2
        assert collection.notes[0].title == "JSON笔记"
        assert collection.notes[1].title != ""


def test_categorize():
    """测试自动分类"""
    config = OrganizerConfig()
    organizer = NoteOrganizer(config)

    note = Note(
        title="Python交易策略回测",
        content="用Python写了一个合约交易的回测框架，支持做多做空",
    )
    collection = NoteCollection(notes=[note], total_count=1)

    result = organizer._categorize_all(collection)
    # 应该匹配到"技术"或"交易"
    assert result.notes[0].category in ["技术", "交易"]


def test_generate_markdown():
    """测试 Markdown 生成"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        config = OrganizerConfig(output_dir=tmp / "output")

        note = Note(
            title="测试笔记",
            content="内容正文",
            category="技术",
            tags=["Python", "测试"],
        )
        collection = NoteCollection(notes=[note], total_count=1)

        generator = MarkdownGenerator(config)
        output = generator.generate(collection)

        # 检查输出文件
        md_file = output / "技术" / "测试笔记.md"
        assert md_file.exists()
        content = md_file.read_text()
        assert "测试笔记" in content
        assert "内容正文" in content


def test_generate_site():
    """测试站点生成"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        config = OrganizerConfig(site_dir=tmp / "site")

        notes = [
            Note(title=f"笔记{i}", content=f"内容{i}", category="技术" if i % 2 == 0 else "生活")
            for i in range(5)
        ]
        collection = NoteCollection(notes=notes, total_count=5)

        generator = SiteGenerator(config)
        output = generator.generate(collection)

        index = output / "index.html"
        assert index.exists()
        html = index.read_text()
        assert "笔记0" in html
        assert "技术" in html
        assert "生活" in html


if __name__ == "__main__":
    test_markdown_parser()
    test_json_parser()
    test_categorize()
    test_generate_markdown()
    test_generate_site()
    print("✅ 所有测试通过！")
