"""小米笔记 Web 应用 - FastAPI 服务端"""
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from ..config import OrganizerConfig
from ..models import Note, NoteCollection
from ..organizers import NoteOrganizer
from ..parsers import create_parser

app = FastAPI(title="小米笔记", version="0.1.0")

# 全局笔记数据
_collection: Optional[NoteCollection] = None
_data_dir: Path = Path("data")


def load_notes(data_path: Optional[Path] = None) -> NoteCollection:
    """加载并整理笔记"""
    global _collection
    path = data_path or _data_dir

    if not path.exists():
        return NoteCollection(notes=[], total_count=0)

    config = OrganizerConfig(input_dir=path)
    collection = NoteCollection()

    if path.is_file():
        parser = create_parser(path, config)
        collection = parser.parse(path)
    elif path.is_dir():
        # 扫描目录下所有支持的文件
        for f in sorted(path.rglob("*")):
            if f.is_file() and f.suffix.lower() in (".json", ".md", ".zip"):
                try:
                    parser = create_parser(f, config)
                    sub = parser.parse(f)
                    for note in sub.notes:
                        collection.add(note)
                except Exception as e:
                    print(f"⚠️  跳过 {f}: {e}")

    collection.total_count = len(collection.notes)

    if collection.total_count > 0:
        organizer = NoteOrganizer(config)
        collection = organizer.organize(collection)

    _collection = collection
    return collection


def get_collection() -> NoteCollection:
    global _collection
    if _collection is None:
        _collection = load_notes()
    return _collection


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>📝 小米笔记</title>
<style>
:root{--bg:#0d1117;--card:#161b22;--border:#30363d;--text:#c9d1d9;--muted:#8b949e;--accent:#ff6700;--accent2:#58a6ff;--tag-bg:#1f2a37;--tag-text:#79c0ff;--radius:6px;--shadow:0 1px 4px rgba(0,0,0,.3)}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans SC",sans-serif;background:var(--bg);color:var(--text);line-height:1.6;min-height:100vh}
header{background:var(--card);border-bottom:1px solid var(--border);position:sticky;top:0;z-index:100;backdrop-filter:blur(12px)}
.hd{max-width:1100px;margin:0 auto;padding:14px 20px;display:flex;justify-content:space-between;align-items:center;gap:12px}
.hd h1{font-size:1.25rem;white-space:nowrap}
.hd h1 a{color:var(--text);text-decoration:none}
.hd h1 span{color:var(--accent)}
.search{flex:1;max-width:400px;padding:7px 14px;border:1px solid var(--border);border-radius:20px;background:var(--bg);color:var(--text);font-size:.9rem;outline:none;transition:border-color .2s}
.search:focus{border-color:var(--accent)}
main{max-width:1100px;margin:0 auto;padding:20px}
.stats{color:var(--muted);font-size:.85rem;margin-bottom:16px}
.tabs{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:20px}
.tab{padding:5px 14px;border:1px solid var(--border);border-radius:16px;background:var(--card);cursor:pointer;font-size:.85rem;transition:all .15s;user-select:none;color:var(--muted)}
.tab:hover{border-color:var(--accent);color:var(--text)}
.tab.active{background:var(--accent);color:#fff;border-color:var(--accent)}
.tab .n{font-size:.75rem;opacity:.7;margin-left:3px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:12px}
.card{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:18px 20px;cursor:pointer;transition:all .15s}
.card:hover{border-color:var(--accent2);box-shadow:var(--shadow)}
.card h3{font-size:1rem;margin-bottom:4px;color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.card .meta{font-size:.8rem;color:var(--muted);margin-bottom:6px}
.card .summary{font-size:.88rem;color:var(--muted);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;line-height:1.5}
.card .tags{display:flex;flex-wrap:wrap;gap:4px;margin-top:8px}
.tag{padding:2px 8px;background:var(--tag-bg);color:var(--tag-text);border-radius:10px;font-size:.75rem}
.empty{text-align:center;color:var(--muted);padding:80px 20px;font-size:1.1rem}
/* 笔记详情 */
.back{display:inline-block;margin-bottom:16px;color:var(--accent2);text-decoration:none;font-size:.9rem;cursor:pointer}
.back:hover{text-decoration:underline}
.detail{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:28px 32px}
.detail h2{font-size:1.5rem;margin-bottom:10px}
.detail .dm{font-size:.85rem;color:var(--muted);margin-bottom:16px}
.detail .body{font-size:1rem;line-height:1.85;color:#e6edf3}
.detail .body h1{font-size:1.3rem;margin:20px 0 8px;border-bottom:1px solid var(--border);padding-bottom:4px}
.detail .body h2{font-size:1.15rem;margin:16px 0 6px}
.detail .body h3{font-size:1.05rem;margin:12px 0 4px}
.detail .body p{margin-bottom:10px}
.detail .body pre{background:#0d1117;padding:14px 16px;border-radius:var(--radius);overflow-x:auto;margin:10px 0;font-size:.88rem;border:1px solid var(--border)}
.detail .body code{background:#1f2a37;padding:2px 6px;border-radius:4px;font-size:.88em}
.detail .body pre code{background:none;padding:0}
.detail .body blockquote{border-left:3px solid var(--accent);padding:4px 14px;color:var(--muted);margin:10px 0}
.detail .body ul,.detail .body ol{padding-left:22px;margin:8px 0}
.detail .body li{margin:4px 0}
.detail .body img{max-width:100%;border-radius:var(--radius)}
.detail .body a{color:var(--accent2)}
.detail .body table{width:100%;border-collapse:collapse;margin:12px 0}
.detail .body th,.detail .body td{border:1px solid var(--border);padding:8px 12px;text-align:left}
.detail .body th{background:#1f2a37}
@media(max-width:640px){.hd{flex-wrap:wrap}.search{max-width:100%}.grid{grid-template-columns:1fr}.detail{padding:18px 16px}}
</style>
</head>
<body>
<header><div class="hd">
<h1><a href="/">📝 <span>小米笔记</span></a></h1>
<input class="search" id="search" placeholder="搜索笔记..." autocomplete="off">
</div></header>
<main>
<div id="app"></div>
</main>
<script>
const DATA = __NOTES__;
const NOTES = DATA.notes || [];
const STATS = DATA.stats || {};

let currentView = 'list';
let currentNote = null;

function init() {
    const hash = window.location.hash;
    if (hash.startsWith('#note-')) {
        showNote(parseInt(hash.slice(6)));
    } else {
        showList(STATS.active_category || '全部');
    }
    document.getElementById('search').addEventListener('input', debounce(function(e){
        showList(STATS.active_category || '全部', e.target.value);
    }, 200));
}

function showList(cat, query) {
    currentView = 'list';
    const app = document.getElementById('app');
    const cats = {};
    NOTES.forEach(n => { const c = n.category || '未分类'; cats[c] = (cats[c]||0)+1; });

    let q = query || document.getElementById('search').value || '';
    let filtered = NOTES;
    if (cat !== '全部') filtered = filtered.filter(n => (n.category||'未分类') === cat);
    if (q) {
        const lq = q.toLowerCase();
        filtered = filtered.filter(n =>
            n.title.toLowerCase().includes(lq) ||
            (n.content||'').toLowerCase().includes(lq) ||
            (n.tags||[]).some(t => t.toLowerCase().includes(lq))
        );
    }

    let html = `<div class="stats">共 ${NOTES.length} 篇笔记 · ${Object.keys(cats).length} 个分类 · ${STATS.total_words||0} 字</div>`;
    html += '<div class="tabs">';
    html += `<span class="tab${cat==='全部'?' active':''}" onclick="showList('全部')">全部<span class="n">${NOTES.length}</span></span>`;
    Object.entries(cats).sort().forEach(([c,n]) => {
        html += `<span class="tab${cat===c?' active':''}" onclick="showList('${c}')">${c}<span class="n">${n}</span></span>`;
    });
    html += '</div>';

    if (!filtered.length) {
        html += '<div class="empty">🔍 没有匹配的笔记</div>';
    } else {
        html += '<div class="grid">';
        filtered.forEach((n,i) => {
            html += `<div class="card" onclick="showNote(${n.id||i})">
                <h3>${esc(n.title)}</h3>
                <div class="meta">${n.date||''} · ${n.category||'未分类'} · ${n.word_count||0} 字</div>
                <div class="summary">${esc((n.summary||n.content||'').substring(0,150))}</div>
                ${(n.tags||[]).length ? '<div class="tags">'+n.tags.slice(0,5).map(t=>`<span class="tag">${esc(t)}</span>`).join('')+'</div>' : ''}
            </div>`;
        });
        html += '</div>';
    }
    app.innerHTML = html;
    window.location.hash = '';
    document.title = '📝 小米笔记';
}

function showNote(id) {
    currentView = 'note';
    const n = NOTES.find(x => x.id === id);
    if (!n) { showList('全部'); return; }

    const app = document.getElementById('app');
    app.innerHTML = `
        <span class="back" onclick="showList('全部')">← 返回列表</span>
        <div class="detail">
            <h2>${esc(n.title)}</h2>
            <div class="dm">${n.date||''} · ${n.category||'未分类'} · ${n.word_count||0} 字</div>
            ${(n.tags||[]).length ? '<div class="tags" style="margin-bottom:16px">'+n.tags.map(t=>`<span class="tag">${esc(t)}</span>`).join('')+'</div>' : ''}
            <div class="body">${md2html(n.content||'')}</div>
        </div>`;
    window.location.hash = 'note-' + id;
    document.title = n.title + ' - 小米笔记';
}

function esc(s) { return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

function md2html(t) {
    if (!t) return '';
    // code blocks first
    t = t.replace(/```(\w*)\n([\s\S]*?)```/g, function(_,lang,code){
        return '<pre><code>' + esc(code.trim()) + '</code></pre>';
    });
    // inline code
    t = t.replace(/`([^`]+)`/g, '<code>$1</code>');
    // headers
    t = t.replace(/^#### (.+)$/gm, '<h4>$1</h4>');
    t = t.replace(/^### (.+)$/gm, '<h3>$1</h3>');
    t = t.replace(/^## (.+)$/gm, '<h2>$1</h2>');
    t = t.replace(/^# (.+)$/gm, '<h1>$1</h1>');
    // bold/italic
    t = t.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
    t = t.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    t = t.replace(/\*(.+?)\*/g, '<em>$1</em>');
    // links
    t = t.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');
    // images
    t = t.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1">');
    // blockquotes
    t = t.replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>');
    // horizontal rule
    t = t.replace(/^---$/gm, '<hr>');
    // unordered lists
    t = t.replace(/^[*-] (.+)$/gm, '<li>$1</li>');
    // ordered lists
    t = t.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');
    // wrap consecutive li
    t = t.replace(/(<li>[\s\S]*?<\/li>)/g, function(m){
        if (!m.includes('<li>')) return m;
        var items = m.match(/<li>[\s\S]*?<\/li>/g);
        return '<ul>' + items.join('') + '</ul>';
    });
    // paragraphs
    t = t.split(/\n\n+/).map(function(p){
        p = p.trim();
        if (!p) return '';
        if (/^<(h[1-4]|pre|ul|ol|blockquote|hr|table|img)/.test(p)) return p;
        return '<p>' + p.replace(/\n/g, '<br>') + '</p>';
    }).join('\n');
    return t;
}

function debounce(fn, ms) { let t; return function(){ clearTimeout(t); t=setTimeout(()=>fn.apply(this,arguments),ms); }; }

init();
</script>
</body>
</html>"""


def notes_to_json(collection: NoteCollection) -> list:
    """将笔记转为前端 JSON"""
    result = []
    for i, note in enumerate(collection.notes):
        result.append({
            "id": i,
            "title": note.title,
            "content": note.content,
            "summary": note.summary,
            "date": note.date_str,
            "category": note.category,
            "tags": note.tags,
            "word_count": note.word_count,
            "folder": note.folder,
        })
    return result


@app.get("/", response_class=HTMLResponse)
async def index(data: str = "data"):
    """主页"""
    global _data_dir
    if not _collection:
        _data_dir = Path(data)
        load_notes(_data_dir)

    collection = get_collection()
    notes_json = json.dumps({
        "notes": notes_to_json(collection),
        "stats": collection.stats(),
    }, ensure_ascii=False)

    # 替换模板变量
    html = HTML_TEMPLATE.replace("__NOTES__", notes_json)

    return html


@app.get("/api/notes")
async def api_notes(
    q: str = Query(default=""),
    cat: str = Query(default=""),
    page: int = Query(default=1),
    size: int = Query(default=50),
):
    """API: 获取笔记列表"""
    collection = get_collection()
    notes = notes_to_json(collection)

    if cat:
        notes = [n for n in notes if n["category"] == cat]
    if q:
        ql = q.lower()
        notes = [n for n in notes if
                 ql in n["title"].lower() or
                 ql in n["content"].lower() or
                 any(ql in t.lower() for t in n.get("tags", []))]

    total = len(notes)
    start = (page - 1) * size
    notes = notes[start:start + size]

    return {"total": total, "page": page, "size": size, "notes": notes}


@app.get("/api/note/{note_id}")
async def api_note(note_id: int):
    """API: 获取单条笔记"""
    collection = get_collection()
    if 0 <= note_id < len(collection.notes):
        return notes_to_json(collection)[note_id]
    return {"error": "not found"}


@app.get("/api/categories")
async def api_categories():
    """API: 获取分类统计"""
    collection = get_collection()
    cats = {}
    for note in collection.notes:
        c = note.category or "未分类"
        cats[c] = cats.get(c, 0) + 1
    return {"categories": cats, "total": collection.total_count}


@app.get("/api/reload")
async def api_reload():
    """API: 重新加载数据"""
    global _collection
    _collection = None
    collection = get_collection()
    return {"status": "ok", "total": collection.total_count}


def start_server(
    data_dir: str = "data",
    host: str = "0.0.0.0",
    port: int = 8080,
    reload: bool = False,
):
    """启动 Web 服务"""
    import uvicorn

    global _data_dir
    _data_dir = Path(data_dir)
    load_notes(_data_dir)

    print(f"\n📝 小米笔记 Web 已启动")
    print(f"   数据目录: {_data_dir.absolute()}")
    print(f"   访问地址: http://{host}:{port}")
    print(f"   笔记数: {get_collection().total_count}")
    print()

    uvicorn.run(
        "src.web.server:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )
