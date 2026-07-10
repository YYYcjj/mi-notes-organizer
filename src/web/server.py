"""小米笔记 Web 应用 - FastAPI 服务端"""
import json
import re
import shutil
import tempfile
import zipfile
import asyncio
import httpx
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Query, UploadFile, File, Header
from fastapi.responses import HTMLResponse, JSONResponse

from ..config import OrganizerConfig
from ..models import Note, NoteCollection
from ..organizers import NoteOrganizer
from ..parsers import create_parser, MarkdownParser, JsonParser, ZipParser

app = FastAPI(title="小米笔记", version="0.1.0")

_collection: Optional[NoteCollection] = None
_data_dir: Path = Path("data")
_upload_dir: Path = Path("/tmp/mi-notes-uploads")
_upload_dir.mkdir(parents=True, exist_ok=True)


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


def parse_uploaded_file(filepath: Path, filename: str) -> NoteCollection:
    """解析上传的文件"""
    config = OrganizerConfig(input_dir=filepath.parent)
    collection = NoteCollection()
    suffix = filename.lower()

    try:
        if suffix.endswith(".zip"):
            # ZIP 可能是小米笔记直接导出，也可能是 Chrome 扩展导出的多文件包
            with zipfile.ZipFile(filepath, "r") as zf:
                namelist = zf.namelist()
                # 检查是否是 Markdown 目录的 ZIP
                md_files = [n for n in namelist if n.endswith(".md")]
                json_files = [n for n in namelist if n.endswith(".json")]

                if md_files:
                    # 解压到临时目录，用 MarkdownParser
                    tmpdir = Path(tempfile.mkdtemp(dir=_upload_dir))
                    zf.extractall(tmpdir)
                    parser = MarkdownParser(config)
                    collection = parser.parse(tmpdir)
                    shutil.rmtree(tmpdir, ignore_errors=True)
                elif json_files:
                    # 解压 JSON 文件解析
                    zf.extractall(_upload_dir / "zip_extract")
                    for jf in json_files:
                        jp = _upload_dir / "zip_extract" / jf
                        if jp.exists():
                            parser = JsonParser(config)
                            sub = parser.parse(jp)
                            for note in sub.notes:
                                collection.add(note)
                    shutil.rmtree(_upload_dir / "zip_extract", ignore_errors=True)
                else:
                    # 尝试直接解析 ZIP 内文件
                    parser = ZipParser(config)
                    collection = parser.parse(filepath)

        elif suffix.endswith(".json"):
            parser = JsonParser(config)
            collection = parser.parse(filepath)

        elif suffix.endswith(".md"):
            parser = MarkdownParser(config)
            collection = parser.parse(filepath)

        else:
            # 尝试作为文本文件
            content = filepath.read_text(encoding="utf-8", errors="ignore")
            if content.strip().startswith("[") or content.strip().startswith("{"):
                parser = JsonParser(config)
                collection = parser.parse(filepath)
            else:
                parser = MarkdownParser(config)
                collection = parser.parse(filepath)

    except Exception as e:
        print(f"⚠️  解析文件失败: {filename} - {e}")

    collection.total_count = len(collection.notes)
    return collection


# HTML 模板 —— 保持之前的完整模板，但在 header 加导入按钮
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
.hd-right{display:flex;align-items:center;gap:8px}
.search{width:240px;padding:7px 14px;border:1px solid var(--border);border-radius:20px;background:var(--bg);color:var(--text);font-size:.9rem;outline:none;transition:border-color .2s}
.search:focus{border-color:var(--accent)}
.btn-import{padding:7px 16px;background:var(--accent);color:#fff;border:none;border-radius:20px;cursor:pointer;font-size:.85rem;white-space:nowrap;transition:opacity .15s}
.btn-import:hover{opacity:.85}
.btn-import input{display:none}
main{max-width:1100px;margin:0 auto;padding:20px}
.stats{color:var(--muted);font-size:.85rem;margin-bottom:16px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}
.stats-right{display:flex;align-items:center;gap:8px}
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
/* 上传区域 */
.upload-zone{border:2px dashed var(--border);border-radius:12px;padding:50px 20px;text-align:center;cursor:pointer;transition:all .2s;margin:20px 0}
.upload-zone:hover,.upload-zone.dragover{border-color:var(--accent);background:rgba(255,103,0,0.05)}
.upload-zone .icon{font-size:2.5rem;margin-bottom:12px}
.upload-zone .title{font-size:1.1rem;color:var(--text);margin-bottom:6px}
.upload-zone .hint{font-size:.85rem;color:var(--muted)}
.upload-zone input{display:none}
.upload-status{text-align:center;padding:20px;color:var(--accent)}
.upload-done{text-align:center;padding:20px;color:#3fb950;font-size:1rem}
.toast{position:fixed;top:20px;left:50%;transform:translateX(-50%);background:var(--accent);color:#fff;padding:10px 24px;border-radius:20px;font-size:.9rem;z-index:999;transition:all .3s;opacity:0;pointer-events:none}
.toast.show{opacity:1}
.toast.error{background:#da3633}
/* 详情 */
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
@media(max-width:640px){.hd{flex-wrap:wrap}.search{width:100%}.grid{grid-template-columns:1fr}.detail{padding:18px 16px}.btn-import{font-size:.8rem;padding:6px 12px}}
</style>
</head>
<body>
<header><div class="hd">
<h1><a href="/">📝 <span>小米笔记</span></a></h1>
<div class="hd-right">
  <input class="search" id="search" placeholder="搜索笔记..." autocomplete="off">
  <label class="btn-import" id="btnImport">
    📥 导入
    <input type="file" id="fileInput" accept=".zip,.json,.md" multiple>
  </label>
</div>
</div></header>
<main>
<div class="toast" id="toast"></div>
<div id="app"></div>
</main>
<script>
const DATA = __NOTES__;
let NOTES = DATA.notes || [];
let STATS = DATA.stats || {};

function init() {
    const hash = window.location.hash;
    if (hash.startsWith('#note-')) {
        showNote(parseInt(hash.slice(6)));
    } else {
        showList('全部');
    }
    document.getElementById('search').addEventListener('input', debounce(function(e){
        showList('全部', e.target.value);
    }, 200));

    // 文件导入
    const fileInput = document.getElementById('fileInput');
    fileInput.addEventListener('change', handleFiles);
    // 拖拽
    document.addEventListener('dragover', function(e){ e.preventDefault(); });
    document.addEventListener('drop', function(e){
        e.preventDefault();
        if (e.dataTransfer.files.length) handleFiles({target:{files:e.dataTransfer.files}});
    });
}

function handleFiles(e) {
    const files = e.target.files;
    if (!files.length) return;
    toast('正在解析笔记...');
    uploadFiles(files);
}

async function uploadFiles(files) {
    const formData = new FormData();
    for (const f of files) formData.append('files', f);

    try {
        const r = await fetch('/api/upload', { method:'POST', body:formData });
        const data = await r.json();
        if (data.status === 'ok') {
            NOTES = data.notes || [];
            STATS = data.stats || {};
            showList('全部');
            toast(data.message || '导入完成！', false);
        } else {
            toast(data.message || '导入失败', true);
        }
    } catch(err) {
        toast('导入失败: ' + err.message, true);
    }
}

function showList(cat, query) {
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

    let html = `<div class="stats"><span>共 ${NOTES.length} 篇笔记 · ${Object.keys(cats).length} 个分类 · ${STATS.total_words||0} 字</span><span class="stats-right"><label class="btn-import" style="font-size:.8rem;padding:4px 12px">📥 导入文件<input type="file" id="fileInput2" accept=".zip,.json,.md" multiple></label></span></div>`;
    html += '<div class="tabs">';
    html += `<span class="tab${cat==='全部'?' active':''}" onclick="showList('全部')">全部<span class="n">${NOTES.length}</span></span>`;
    Object.entries(cats).sort().forEach(([c,n]) => {
        html += `<span class="tab${cat===c?' active':''}" onclick="showList('${c}')">${c}<span class="n">${n}</span></span>`;
    });
    html += '</div>';

    if (!filtered.length) {
        html += `<div class="empty">${NOTES.length ? '🔍 没有匹配的笔记' : '还没有笔记'}<br><br><div class="upload-zone" onclick="document.getElementById(\'fileInput\').click()"><div class="icon">📂</div><div class="title">拖拽文件到这里，或点击上传</div><div class="hint">支持 ZIP · JSON · Markdown · 小米笔记导出文件 · mi-note-export 目录</div></div></div>`;
    } else {
        html += '<div class="grid">';
        filtered.forEach((n,i) => {
            html += `<div class="card" onclick="showNote(${n.id})">
                <h3>${esc(n.title)}</h3>
                <div class="meta">${n.date||''} · ${n.category||'未分类'} · ${n.word_count||0} 字</div>
                <div class="summary">${esc((n.summary||n.content||'').substring(0,150))}</div>
                ${(n.tags||[]).length ? '<div class="tags">'+n.tags.slice(0,5).map(t=>`<span class="tag">${esc(t)}</span>`).join('')+'</div>' : ''}
            </div>`;
        });
        html += '</div>';
    }
    app.innerHTML = html;

    // 重新绑定小上传按钮
    const fi2 = document.getElementById('fileInput2');
    if (fi2) { fi2.addEventListener('change', handleFiles); }

    window.location.hash = '';
    document.title = '📝 小米笔记';
}

function showNote(id) {
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
    t = t.replace(/```(\w*)\n([\s\S]*?)```/g, function(_,lang,code){
        return '<pre><code>' + esc(code.trim()) + '</code></pre>';
    });
    t = t.replace(/`([^`]+)`/g, '<code>$1</code>');
    t = t.replace(/^#### (.+)$/gm, '<h4>$1</h4>');
    t = t.replace(/^### (.+)$/gm, '<h3>$1</h3>');
    t = t.replace(/^## (.+)$/gm, '<h2>$1</h2>');
    t = t.replace(/^# (.+)$/gm, '<h1>$1</h1>');
    t = t.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
    t = t.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    t = t.replace(/\*(.+?)\*/g, '<em>$1</em>');
    t = t.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');
    t = t.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1">');
    t = t.replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>');
    t = t.replace(/^---$/gm, '<hr>');
    t = t.replace(/^[*-] (.+)$/gm, '<li>$1</li>');
    t = t.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');
    t = t.replace(/(<li>[\s\S]*?<\/li>)/g, function(m){
        if (!m.includes('<li>')) return m;
        var items = m.match(/<li>[\s\S]*?<\/li>/g);
        return '<ul>' + items.join('') + '</ul>';
    });
    t = t.split(/\n\n+/).map(function(p){
        p = p.trim();
        if (!p) return '';
        if (/^<(h[1-4]|pre|ul|ol|blockquote|hr|table|img)/.test(p)) return p;
        return '<p>' + p.replace(/\n/g, '<br>') + '</p>';
    }).join('\n');
    return t;
}

function debounce(fn, ms) { let t; return function(){ clearTimeout(t); t=setTimeout(()=>fn.apply(this,arguments),ms); }; }

function toast(msg, isError) {
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.className = 'toast' + (isError ? ' error' : '');
    setTimeout(function(){ el.className = 'toast show' + (isError ? ' error' : ''); }, 10);
    setTimeout(function(){ el.className = 'toast'; }, 2500);
}

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
async def index():
    """主页 — 优先返回静态 HTML，否则回退到内置模板"""
    # 尝试读取 static/index.html
    static_index = STATIC_DIR / "index.html" if STATIC_DIR else None
    if static_index and static_index.exists():
        return static_index.read_text(encoding="utf-8")
    
    # 回退到内置模板
    if not _collection:
        load_notes(_data_dir)
    collection = get_collection()
    notes_json = json.dumps({
        "notes": notes_to_json(collection),
        "stats": collection.stats(),
    }, ensure_ascii=False)
    return HTML_TEMPLATE.replace("__NOTES__", notes_json)


@app.post("/api/upload")
async def api_upload(files: list[UploadFile] = File(...)):
    """上传并导入笔记文件"""
    global _collection

    total = 0
    collection = _collection or NoteCollection()

    for file in files:
        # 保存到临时目录
        tmp_path = _upload_dir / file.filename
        try:
            content = await file.read()
            tmp_path.write_bytes(content)

            sub = parse_uploaded_file(tmp_path, file.filename)
            for note in sub.notes:
                # 去重：按标题
                existing_titles = {n.title for n in collection.notes}
                if note.title not in existing_titles:
                    collection.add(note)
                    total += 1

        except Exception as e:
            print(f"⚠️  上传解析失败: {file.filename} - {e}")
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    collection.total_count = len(collection.notes)

    # 重新整理
    if total > 0:
        config = OrganizerConfig()
        organizer = NoteOrganizer(config)
        collection = organizer.organize(collection)

    _collection = collection

    return {
        "status": "ok",
        "message": f"成功导入 {total} 篇新笔记（共 {collection.total_count} 篇）",
        "total": collection.total_count,
        "new": total,
        "notes": notes_to_json(collection),
        "stats": collection.stats(),
    }


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


@app.get("/api/mi-fetch")
async def api_mi_fetch(x_mi_cookie: str = Header(default="")):
    """代理获取小米云笔记列表——不传Cookie，用自定义Header"""
    if not x_mi_cookie:
        return {"status": "error", "message": "缺少 Cookie"}
    
    notes = []
    sync_tag = ""
    page = 1
    
    async with httpx.AsyncClient(timeout=30) as client:
        # 阶段1: 扫描列表
        while True:
            url = f"https://i.mi.com/note/full/page/?ts={int(datetime.now().timestamp()*1000)}&limit=300"
            if sync_tag:
                url += f"&syncTag={sync_tag}"
            
            try:
                resp = await client.get(url, headers={"Cookie": x_mi_cookie})
                data = resp.json()
                if not data.get("data", {}).get("entries"):
                    break
                
                entries = data["data"]["entries"]
                notes.extend(entries)
                sync_tag = data["data"].get("syncTag", "")
                
                if not sync_tag:
                    break
                page += 1
                await asyncio.sleep(0.3)
            except Exception as e:
                if page == 1:
                    return {"status": "error", "message": f"Cookie 无效或过期: {str(e)}"}
                break
        
        if not notes:
            return {"status": "ok", "notes": [], "message": "没有找到笔记"}
        
        # 阶段2: 获取详情
        result = []
        total = len(notes)
        
        for i, note in enumerate(notes[:200]):  # 限制200条
            try:
                detail_url = f"https://i.mi.com/note/note/{note['id']}/?ts={int(datetime.now().timestamp()*1000)}"
                resp = await client.get(detail_url, headers={"Cookie": x_mi_cookie})
                entry = resp.json().get("data", {}).get("entry", {})
                
                title = "无标题"
                try:
                    extra = json.loads(entry.get("extraInfo", "{}"))
                    if extra.get("title"):
                        title = extra["title"]
                except:
                    pass
                
                content = (entry.get("content", "") or "")
                content = re.sub(r"<br\s*/?>", "\n", content)
                content = re.sub(r"</p>", "\n", content)
                content = re.sub(r"<[^>]+>", "", content)
                content = re.sub(r"&nbsp;", " ", content)
                content = re.sub(r"&amp;", "&", content)
                content = re.sub(r"&lt;", "<", content)
                content = re.sub(r"&gt;", ">", content)
                content = re.sub(r"&quot;", '"', content)
                content = re.sub(r"\n{3,}", "\n\n", content).strip()
                
                result.append({
                    "title": title,
                    "content": content,
                    "folder": entry.get("folderId", ""),
                    "createdAt": note.get("createDate"),
                    "modifiedAt": note.get("modifyDate"),
                })
                
                await asyncio.sleep(0.2)
            except Exception as e:
                print(f"获取笔记 {note['id']} 失败: {e}")
        
        return {
            "status": "ok",
            "notes": result,
            "total_found": total,
            "fetched": len(result),
            "message": f"成功获取 {len(result)} / {total} 条笔记",
        }


@app.get("/api/mi-check-cookie")
async def api_mi_check_cookie(x_mi_cookie: str = Header(default="")):
    """检查 Cookie 是否有效"""
    if not x_mi_cookie:
        return {"valid": False, "message": "缺少 Cookie"}
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            url = f"https://i.mi.com/note/full/page/?ts={int(datetime.now().timestamp()*1000)}&limit=1"
            resp = await client.get(url, headers={"Cookie": x_mi_cookie})
            data = resp.json()
            if data.get("data"):
                return {"valid": True, "message": "Cookie 有效"}
            return {"valid": False, "message": "Cookie 无效或已过期"}
    except Exception as e:
        return {"valid": False, "message": str(e)}


def start_server(
    data_dir: str = "data",
    host: str = "0.0.0.0",
    port: int = 8080,
    reload: bool = False,
):
    """启动 Web 服务"""
    import uvicorn

    global _data_dir, _upload_dir
    _data_dir = Path(data_dir)
    _upload_dir.mkdir(parents=True, exist_ok=True)
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
