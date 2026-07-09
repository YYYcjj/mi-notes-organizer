"""生成器 - 输出 Markdown 文件和静态站点"""
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..config import OrganizerConfig
from ..models import Note, NoteCollection


class MarkdownGenerator:
    """生成 Markdown 文件"""

    def __init__(self, config: OrganizerConfig):
        self.config = config

    def generate(self, collection: NoteCollection) -> Path:
        """生成分类整理的 Markdown 文件"""
        output_dir = self.config.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        # 按分类创建目录
        by_category: dict[str, list[Note]] = {}
        for note in collection.notes:
            cat_dir = note.category or "未分类"
            if cat_dir not in by_category:
                by_category[cat_dir] = []
            by_category[cat_dir].append(note)

        # 为每个分类生成文件
        for category, notes in sorted(by_category.items()):
            cat_dir = output_dir / category
            cat_dir.mkdir(exist_ok=True)

            for note in notes:
                self._write_note(note, cat_dir)

        # 生成索引
        self._generate_index(collection, by_category)

        print(f"   ✅ Markdown 文件已生成到: {output_dir}")
        return output_dir

    def _write_note(self, note: Note, cat_dir: Path) -> None:
        """写入单篇笔记"""
        safe_title = self._safe_filename(note.title)
        filepath = cat_dir / f"{safe_title}.md"

        # 处理重名
        counter = 1
        while filepath.exists():
            filepath = cat_dir / f"{safe_title}_{counter}.md"
            counter += 1

        lines = ["---"]
        lines.append(f"title: {note.title}")
        lines.append(f"category: {note.category}")
        if note.tags:
            lines.append(f"tags: [{', '.join(note.tags)}]")
        if note.created_at:
            lines.append(f"date: {note.created_at.isoformat()}")
        if note.modified_at:
            lines.append(f"modified: {note.modified_at.isoformat()}")
        lines.append(f"source: {note.source_file}")
        lines.append("---")
        lines.append("")
        lines.append(note.content)

        filepath.write_text("\n".join(lines), encoding="utf-8")

    def _generate_index(
        self, collection: NoteCollection, by_category: dict[str, list[Note]]
    ) -> None:
        """生成 README 索引"""
        lines = [
            f"# {self.config.site_title}",
            "",
            f"*最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
            "",
            f"共 **{collection.total_count}** 篇笔记",
            "",
            "## 📂 分类导航",
            "",
        ]

        for category, notes in sorted(by_category.items()):
            lines.append(f"### {category} ({len(notes)} 篇)")
            lines.append("")
            for note in sorted(notes, key=lambda n: n.date_str, reverse=True):
                date_prefix = f"[{note.date_str}] " if note.date_str != "未知日期" else ""
                safe_title = self._safe_filename(note.title)
                link = f"[{date_prefix}{note.title}](./{category}/{safe_title}.md)"
                lines.append(f"- {link}")
            lines.append("")

        readme_path = self.config.output_dir / "README.md"
        readme_path.write_text("\n".join(lines), encoding="utf-8")

    @staticmethod
    def _safe_filename(name: str) -> str:
        """生成安全文件名"""
        safe = name.replace("/", "-").replace("\\", "-")
        safe = "".join(c for c in safe if c not in r'<>:"|?*')
        return safe[:100].strip() or "untitled"


class SiteGenerator:
    """生成静态博客站点"""

    TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        :root {{
            --bg: #fafafa;
            --card-bg: #ffffff;
            --text: #1a1a1a;
            --text-secondary: #666;
            --border: #e5e5e5;
            --accent: #ff6700;
            --tag-bg: #fff3e6;
            --tag-text: #cc5500;
            --radius: 8px;
            --shadow: 0 1px 3px rgba(0,0,0,0.08);
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans SC", sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.7;
        }}
        header {{
            background: var(--card-bg);
            border-bottom: 1px solid var(--border);
            padding: 20px 0;
            position: sticky;
            top: 0;
            z-index: 100;
        }}
        .header-inner {{
            max-width: 900px;
            margin: 0 auto;
            padding: 0 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .header-inner h1 {{ font-size: 1.5rem; color: var(--accent); }}
        .search-box {{
            padding: 8px 16px;
            border: 1px solid var(--border);
            border-radius: var(--radius);
            font-size: 0.95rem;
            width: 240px;
            outline: none;
            transition: border-color 0.2s;
        }}
        .search-box:focus {{ border-color: var(--accent); }}
        main {{
            max-width: 900px;
            margin: 0 auto;
            padding: 24px 20px;
        }}
        .stats {{
            color: var(--text-secondary);
            font-size: 0.9rem;
            margin-bottom: 24px;
        }}
        .category-tabs {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-bottom: 24px;
        }}
        .cat-tab {{
            padding: 6px 16px;
            border: 1px solid var(--border);
            border-radius: 20px;
            background: var(--card-bg);
            cursor: pointer;
            font-size: 0.9rem;
            transition: all 0.15s;
            user-select: none;
        }}
        .cat-tab:hover {{ border-color: var(--accent); }}
        .cat-tab.active {{
            background: var(--accent);
            color: #fff;
            border-color: var(--accent);
        }}
        .cat-tab .count {{
            font-size: 0.8rem;
            opacity: 0.7;
            margin-left: 4px;
        }}
        .note-list {{ list-style: none; }}
        .note-card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 20px 24px;
            margin-bottom: 12px;
            box-shadow: var(--shadow);
            transition: box-shadow 0.15s;
        }}
        .note-card:hover {{ box-shadow: 0 2px 8px rgba(0,0,0,0.12); }}
        .note-card h3 {{
            font-size: 1.1rem;
            margin-bottom: 6px;
        }}
        .note-card h3 a {{
            color: var(--text);
            text-decoration: none;
        }}
        .note-card h3 a:hover {{ color: var(--accent); }}
        .note-meta {{
            font-size: 0.85rem;
            color: var(--text-secondary);
            margin-bottom: 8px;
        }}
        .note-summary {{
            font-size: 0.95rem;
            color: #444;
            line-height: 1.6;
        }}
        .tags {{
            display: flex;
            flex-wrap: wrap;
            gap: 4px;
            margin-top: 8px;
        }}
        .tag {{
            padding: 2px 10px;
            background: var(--tag-bg);
            color: var(--tag-text);
            border-radius: 12px;
            font-size: 0.8rem;
        }}
        .note-detail {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 32px;
            box-shadow: var(--shadow);
        }}
        .note-detail h1 {{ font-size: 1.8rem; margin-bottom: 12px; }}
        .note-detail .content {{
            margin-top: 20px;
            font-size: 1.05rem;
            line-height: 1.8;
        }}
        .note-detail .content h1 {{ font-size: 1.4rem; margin: 24px 0 8px; }}
        .note-detail .content h2 {{ font-size: 1.2rem; margin: 20px 0 6px; }}
        .note-detail .content p {{ margin-bottom: 12px; }}
        .note-detail .content pre {{
            background: #f5f5f5;
            padding: 16px;
            border-radius: var(--radius);
            overflow-x: auto;
            margin: 12px 0;
            font-size: 0.9rem;
        }}
        .note-detail .content code {{
            background: #f5f5f5;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.9em;
        }}
        .note-detail .content pre code {{
            background: none;
            padding: 0;
        }}
        .note-detail .content blockquote {{
            border-left: 3px solid var(--accent);
            padding-left: 16px;
            color: #666;
            margin: 12px 0;
        }}
        .note-detail .content img {{
            max-width: 100%;
            border-radius: var(--radius);
        }}
        .back-link {{
            display: inline-block;
            margin-bottom: 20px;
            color: var(--accent);
            text-decoration: none;
            font-size: 0.9rem;
        }}
        .back-link:hover {{ text-decoration: underline; }}
        .empty {{ text-align: center; color: var(--text-secondary); padding: 60px 0; }}
        .hidden {{ display: none; }}
        @media (max-width: 640px) {{
            .header-inner {{ flex-direction: column; gap: 12px; align-items: stretch; }}
            .search-box {{ width: 100%; }}
            .note-card {{ padding: 16px; }}
            .note-detail {{ padding: 20px; }}
        }}
    </style>
</head>
<body>
    <header>
        <div class="header-inner">
            <h1><a href="index.html" style="color:inherit;text-decoration:none;">📝 {title}</a></h1>
            <input type="text" class="search-box" id="search" placeholder="搜索笔记..." autocomplete="off">
        </div>
    </header>
    <main>
        <div class="stats" id="stats"></div>
        <div class="category-tabs" id="categoryTabs"></div>
        <div id="content"></div>
    </main>

    <script>
        const NOTES = {notes_json};
        const SITE_TITLE = "{title}";

        document.addEventListener("DOMContentLoaded", () => {{
            const params = new URLSearchParams(window.location.search);
            const noteId = params.get("note");
            const cat = params.get("cat");

            if (noteId) {{
                renderNote(noteId);
            }} else {{
                renderList(cat || "全部");
            }}

            document.getElementById("search").addEventListener("input", (e) => {{
                renderList("全部", e.target.value);
            }});
        }});

        function renderList(category, query = "") {{
            const tabs = document.getElementById("categoryTabs");
            const content = document.getElementById("content");
            const stats = document.getElementById("stats");

            // 统计分类
            const cats = {{}};
            NOTES.forEach(n => {{
                const c = n.category || "未分类";
                cats[c] = (cats[c] || 0) + 1;
            }});

            stats.textContent = `共 ${{NOTES.length}} 篇笔记 · ${{Object.keys(cats).length}} 个分类`;

            // 标签页
            let tabsHtml = `<span class="cat-tab ${{category === "全部" ? "active" : ""}}" onclick="renderList('全部')">全部<span class="count">${{NOTES.length}}</span></span>`;
            Object.entries(cats).sort().forEach(([c, count]) => {{
                tabsHtml += `<span class="cat-tab ${{category === c ? "active" : ""}}" onclick="renderList('${{c}}')">${{c}}<span class="count">${{count}}</span></span>`;
            }});
            tabs.innerHTML = tabsHtml;

            // 过滤
            let filtered = notes;
            if (category !== "全部") {{
                filtered = filtered.filter(n => (n.category || "未分类") === category);
            }}
            if (query) {{
                const q = query.toLowerCase();
                filtered = filtered.filter(n =>
                    n.title.toLowerCase().includes(q) ||
                    n.content.toLowerCase().includes(q) ||
                    (n.tags || []).some(t => t.toLowerCase().includes(q))
                );
            }}

            if (filtered.length === 0) {{
                content.innerHTML = '<div class="empty">🔍 没有找到匹配的笔记</div>';
                return;
            }}

            let html = '<ul class="note-list">';
            filtered.forEach(n => {{
                html += `
                    <li class="note-card">
                        <h3><a href="?note=${{n.id}}">${{n.title}}</a></h3>
                        <div class="note-meta">${{n.date}} · ${{n.category || "未分类"}} · ${{n.wordCount}} 字</div>
                        <div class="note-summary">${{escapeHtml(n.summary || n.content.substring(0, 200))}}</div>
                        ${{n.tags && n.tags.length ? '<div class="tags">' + n.tags.slice(0,5).map(t => `<span class="tag">${{t}}</span>`).join("") + '</div>' : ""}}
                    </li>`;
            }});
            html += '</ul>';
            content.innerHTML = html;
        }}

        function renderNote(id) {{
            const n = NOTES.find(n => n.id == id);
            if (!n) {{
                document.getElementById("content").innerHTML = '<div class="empty">笔记不存在</div>';
                return;
            }}

            document.getElementById("categoryTabs").innerHTML = "";
            document.getElementById("stats").textContent = "";

            let html = `
                <a href="index.html" class="back-link">← 返回列表</a>
                <div class="note-detail">
                    <h1>${{n.title}}</h1>
                    <div class="note-meta">${{n.date}} · ${{n.category || "未分类"}} · ${{n.wordCount}} 字</div>
                    ${{n.tags && n.tags.length ? '<div class="tags">' + n.tags.map(t => `<span class="tag">${{t}}</span>`).join("") + '</div>' : ""}}
                    <div class="content">${{markdownToHtml(n.content)}}</div>
                </div>`;
            document.getElementById("content").innerHTML = html;
            document.title = `${{n.title}} - ${{SITE_TITLE}}`;
        }}

        function markdownToHtml(text) {{
            if (!text) return "";
            return text
                .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
                .replace(/^### (.+)$/gm, "<h3>$1</h3>")
                .replace(/^## (.+)$/gm, "<h2>$1</h2>")
                .replace(/^# (.+)$/gm, "<h1>$1</h1>")
                .replace(/\\*\\*(.+?)\\*\\*/g, "<strong>$1</strong>")
                .replace(/\\*(.+?)\\*/g, "<em>$1</em>")
                .replace(/`([^`]+)`/g, "<code>$1</code>")
                .replace(/```([\\s\\S]*?)```/g, "<pre><code>$1</code></pre>")
                .replace(/^> (.+)$/gm, "<blockquote>$1</blockquote>")
                .replace(/^- (.+)$/gm, "<li>$1</li>")
                .replace(/!\\[(.*?)\\]\\((.*?)\\)/g, '<img src="$2" alt="$1">')
                .replace(/\\[(.*?)\\]\\((.*?)\\)/g, '<a href="$2">$1</a>')
                .replace(/\\n\\n/g, "</p><p>")
                .replace(/\\n/g, "<br>")
                .replace(/<li>/g, "<ul><li>").replace(/<\\/li>/g, "</li></ul>")
                .replace(/<\\/ul><ul>/g, "");
        }}

        function escapeHtml(text) {{
            if (!text) return "";
            return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        }}
    </script>
</body>
</html>"""

    def __init__(self, config: OrganizerConfig):
        self.config = config

    def generate(self, collection: NoteCollection) -> Path:
        """生成静态站点"""
        site_dir = self.config.site_dir
        site_dir.mkdir(parents=True, exist_ok=True)

        # 准备笔记数据
        notes_data = []
        for i, note in enumerate(collection.notes):
            notes_data.append({
                "id": i,
                "title": note.title,
                "content": note.content,
                "summary": note.summary,
                "date": note.date_str,
                "category": note.category,
                "tags": note.tags,
                "wordCount": note.word_count,
            })

        notes_json = json.dumps(notes_data, ensure_ascii=False)

        html = self.TEMPLATE.format(
            title=self.config.site_title,
            notes_json=notes_json,
        )

        index_path = site_dir / "index.html"
        index_path.write_text(html, encoding="utf-8")

        # 复制 assets（如果有）
        assets_src = self.config.input_dir / "assets" if self.config.input_dir else None
        if assets_src and assets_src.exists():
            assets_dst = site_dir / "assets"
            if not assets_dst.exists():
                shutil.copytree(assets_src, assets_dst)

        print(f"   ✅ 静态站点已生成到: {site_dir}")
        print(f"   🌐 用浏览器打开: file://{site_dir}/index.html")
        return site_dir
