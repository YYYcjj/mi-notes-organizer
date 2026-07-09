"""解析器 - 支持多种小米笔记导出格式"""
import json
import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from bs4 import BeautifulSoup

from ..config import OrganizerConfig
from ..models import Note, NoteCollection


class BaseParser:
    """解析器基类"""

    def __init__(self, config: OrganizerConfig):
        self.config = config

    def parse(self, source: Path) -> NoteCollection:
        raise NotImplementedError

    def _clean_html(self, html: str) -> str:
        """HTML 转纯文本/Markdown"""
        soup = BeautifulSoup(html, "html.parser")

        # 转换常见标签
        for tag in soup.find_all(["strong", "b"]):
            tag.replace_with(f"**{tag.get_text()}**")
        for tag in soup.find_all(["em", "i"]):
            tag.replace_with(f"*{tag.get_text()}*")
        for tag in soup.find_all("h1"):
            tag.replace_with(f"\n# {tag.get_text()}\n")
        for tag in soup.find_all("h2"):
            tag.replace_with(f"\n## {tag.get_text()}\n")
        for tag in soup.find_all("h3"):
            tag.replace_with(f"\n### {tag.get_text()}\n")
        for tag in soup.find_all("li"):
            tag.replace_with(f"- {tag.get_text()}\n")
        for tag in soup.find_all("br"):
            tag.replace_with("\n")
        for tag in soup.find_all("p"):
            tag.replace_with(f"\n{tag.get_text()}\n")
        for tag in soup.find_all("a"):
            href = tag.get("href", "")
            text = tag.get_text()
            if href:
                tag.replace_with(f"[{text}]({href})")
            else:
                tag.replace_with(text)
        for tag in soup.find_all("img"):
            src = tag.get("src", "")
            alt = tag.get("alt", "图片")
            tag.replace_with(f"![{alt}]({src})")

        text = soup.get_text()
        if self.config.normalize_whitespace:
            text = re.sub(r"\n{3,}", "\n\n", text)
            text = re.sub(r" +", " ", text)
        return text.strip()

    def _extract_title(self, text: str, filename: str = "") -> str:
        """从内容提取标题"""
        # 尝试匹配 Markdown 标题
        match = re.match(r"^#\s+(.+)$", text, re.MULTILINE)
        if match:
            return match.group(1).strip()
        # 使用第一行非空文本
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if lines:
            title = lines[0]
            return title[:100] if len(title) > 100 else title
        # 回退到文件名
        return Path(filename).stem if filename else "无标题"


class ZipParser(BaseParser):
    """解析小米笔记导出的 ZIP 文件"""

    def parse(self, source: Path) -> NoteCollection:
        collection = NoteCollection()

        if not source.exists():
            print(f"⚠️  文件不存在: {source}")
            return collection

        with zipfile.ZipFile(source, "r") as zf:
            for entry in zf.namelist():
                if entry.endswith("/"):
                    continue
                try:
                    content = zf.read(entry).decode("utf-8", errors="ignore")
                    folder = str(Path(entry).parent) if "/" in entry else ""
                    note = self._parse_single(content, entry, folder)
                    if note:
                        collection.add(note)
                except Exception as e:
                    print(f"⚠️  解析失败: {entry} - {e}")

        collection.total_count = len(collection.notes)
        return collection

    def _parse_single(self, content: str, filename: str, folder: str) -> Optional[Note]:
        """解析单条笔记"""
        if not content.strip():
            return None

        # 检测 HTML
        if content.strip().startswith("<"):
            content = self._clean_html(content)

        title = self._extract_title(content, filename)

        # 尝试解析 JSON 格式 (mi-note-export 格式)
        if content.strip().startswith("{"):
            try:
                data = json.loads(content)
                return self._parse_json_note(data, filename)
            except json.JSONDecodeError:
                pass

        return Note(
            title=title,
            content=content.strip(),
            source_file=filename,
            folder=folder,
        )

    def _parse_json_note(self, data: dict, filename: str) -> Optional[Note]:
        """解析 JSON 格式的笔记数据"""
        title = data.get("title", "") or self._extract_title(
            data.get("content", ""), filename
        )
        content = data.get("content", "")

        # 处理 HTML 内容
        if content.strip().startswith("<"):
            content = self._clean_html(content)

        created = None
        modified = None
        if "createdAt" in data:
            try:
                created = datetime.fromtimestamp(data["createdAt"] / 1000)
            except (ValueError, TypeError, OSError):
                pass
        if "modifiedAt" in data:
            try:
                modified = datetime.fromtimestamp(data["modifiedAt"] / 1000)
            except (ValueError, TypeError, OSError):
                pass

        return Note(
            title=title,
            content=content.strip(),
            created_at=created,
            modified_at=modified,
            source_file=filename,
            folder=data.get("folder", ""),
            is_pinned=data.get("isPinned", False),
        )


class MarkdownParser(BaseParser):
    """解析已导出的 Markdown 文件"""

    def parse(self, source: Path) -> NoteCollection:
        collection = NoteCollection()

        if not source.exists():
            print(f"⚠️  路径不存在: {source}")
            return collection

        if source.is_file():
            note = self._parse_file(source)
            if note:
                collection.add(note)
        elif source.is_dir():
            for md_file in sorted(source.rglob("*.md")):
                note = self._parse_file(md_file)
                if note:
                    collection.add(note)

        collection.total_count = len(collection.notes)
        return collection

    def _parse_file(self, filepath: Path) -> Optional[Note]:
        """解析单个 Markdown 文件"""
        try:
            content = filepath.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return None

        if not content.strip():
            return None

        # 尝试解析 YAML frontmatter
        title = self._extract_title(content, filepath.name)
        frontmatter = {}
        body = content

        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                import yaml
                try:
                    frontmatter = yaml.safe_load(parts[1]) or {}
                except yaml.YAMLError:
                    pass
                body = parts[2] if len(parts) > 2 else content

        if frontmatter.get("title"):
            title = frontmatter["title"]

        # 获取文件时间
        stat = filepath.stat()
        created = datetime.fromtimestamp(stat.st_ctime)
        modified = datetime.fromtimestamp(stat.st_mtime)

        # 相对路径作为 folder
        folder = ""
        if source := self.config.input_dir:
            try:
                rel = filepath.relative_to(source)
                if rel.parent != Path("."):
                    folder = str(rel.parent)
            except ValueError:
                pass

        return Note(
            title=title,
            content=body.strip(),
            created_at=created,
            modified_at=modified,
            source_file=str(filepath),
            folder=folder,
            tags=frontmatter.get("tags", []),
            category=frontmatter.get("category", ""),
        )


class JsonParser(BaseParser):
    """解析 mi-note-export 的 notes.json"""

    def parse(self, source: Path) -> NoteCollection:
        collection = NoteCollection()

        if not source.exists():
            print(f"⚠️  文件不存在: {source}")
            return collection

        try:
            data = json.loads(source.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"⚠️  JSON 解析失败: {e}")
            return collection

        # 兼容多种 JSON 结构
        notes_list = data if isinstance(data, list) else data.get("notes", data.get("data", []))

        for item in notes_list:
            note = self._parse_item(item)
            if note:
                collection.add(note)

        collection.total_count = len(collection.notes)
        return collection

    def _parse_item(self, item: dict) -> Optional[Note]:
        title = item.get("title", "") or item.get("name", "")
        content = item.get("content", "") or item.get("text", "") or item.get("body", "")

        if not content.strip() and not title:
            return None

        if content.strip().startswith("<"):
            content = self._clean_html(content)

        created = self._parse_timestamp(item.get("createdAt") or item.get("createTime"))
        modified = self._parse_timestamp(item.get("modifiedAt") or item.get("modifyTime"))

        return Note(
            title=title or self._extract_title(content),
            content=content.strip(),
            created_at=created,
            modified_at=modified,
            source_file="notes.json",
            folder=item.get("folder", "") or item.get("directory", ""),
            is_pinned=item.get("isPinned", False) or item.get("pinned", False),
            tags=item.get("tags", []) or item.get("labels", []),
        )

    @staticmethod
    def _parse_timestamp(value) -> Optional[datetime]:
        if not value:
            return None
        try:
            # 毫秒时间戳
            if isinstance(value, (int, float)):
                return datetime.fromtimestamp(value / 1000 if value > 1e12 else value)
            # ISO 格式字符串
            if isinstance(value, str):
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, TypeError, OSError):
            pass
        return None


def create_parser(source_path: Path, config: OrganizerConfig) -> BaseParser:
    """自动检测并创建合适的解析器"""
    if not source_path.exists():
        raise FileNotFoundError(f"路径不存在: {source_path}")

    if source_path.is_file():
        suffix = source_path.suffix.lower()
        if suffix == ".zip":
            return ZipParser(config)
        if suffix == ".json":
            return JsonParser(config)
        if suffix == ".md":
            return MarkdownParser(config)

    if source_path.is_dir():
        # 检查目录下文件类型
        md_files = list(source_path.rglob("*.md"))
        if md_files:
            return MarkdownParser(config)
        json_files = list(source_path.glob("*.json"))
        if json_files:
            return JsonParser(config)

    raise ValueError(f"无法识别的输入格式: {source_path}")
