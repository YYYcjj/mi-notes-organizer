"""小米笔记后端 - 可部署到 Render/Railway 等平台"""
import json
import re
import asyncio
import httpx
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Header
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="小米笔记")

STATIC_DIR = Path("static")
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")


# ==================== 主页 ====================
@app.get("/", response_class=HTMLResponse)
async def index():
    idx = STATIC_DIR / "index.html"
    if idx.exists():
        return idx.read_text(encoding="utf-8")
    return "<h1>部署正常</h1><p>static/index.html 未找到</p>"


# ==================== 小米云代理 ====================
@app.get("/api/mi-fetch")
async def fetch_mi_notes(x_mi_cookie: str = Header(default="")):
    """从小米云拉取笔记"""
    if not x_mi_cookie:
        return {"status": "error", "message": "缺少 Cookie，请在请求时带上"}

    async with httpx.AsyncClient(timeout=30) as client:
        # 1. 扫描列表
        entries = []
        sync_tag = ""
        page = 1
        while True:
            url = f"https://i.mi.com/note/full/page/?ts={int(datetime.now().timestamp()*1000)}&limit=300"
            if sync_tag:
                url += f"&syncTag={sync_tag}"
            try:
                resp = await client.get(url, headers={"Cookie": x_mi_cookie})
                data = resp.json()
                batch = data.get("data", {}).get("entries", [])
                if not batch:
                    break
                entries.extend(batch)
                sync_tag = data["data"].get("syncTag", "")
                if not sync_tag:
                    break
                page += 1
                await asyncio.sleep(0.2)
            except Exception:
                if page == 1:
                    return {"status": "error", "message": "Cookie 无效或过期"}
                break

        if not entries:
            return {"status": "ok", "notes": [], "message": "没有笔记"}

        # 2. 并发获取详情
        sem = asyncio.Semaphore(10)
        total = len(entries[:200])

        async def fetch_one(note):
            async with sem:
                try:
                    url = f"https://i.mi.com/note/note/{note['id']}/?ts={int(datetime.now().timestamp()*1000)}"
                    resp = await client.get(url, headers={"Cookie": x_mi_cookie})
                    entry = resp.json().get("data", {}).get("entry", {})
                    if not entry:
                        return None

                    title = "无标题"
                    try:
                        ex = json.loads(entry.get("extraInfo", "{}"))
                        if ex.get("title"):
                            title = ex["title"]
                    except Exception:
                        pass

                    content = (entry.get("content") or "")
                    content = re.sub(r"<br\s*/?>", "\n", content)
                    content = re.sub(r"</p>", "\n", content)
                    content = re.sub(r"<[^>]+>", "", content)
                    content = re.sub(r"&nbsp;", " ", content)
                    content = re.sub(r"&amp;", "&", content)
                    content = re.sub(r"&lt;", "<", content)
                    content = re.sub(r"&gt;", ">", content)
                    content = re.sub(r"\n{3,}", "\n\n", content).strip()

                    return {
                        "title": title,
                        "content": content,
                        "folder": entry.get("folderId", ""),
                        "createdAt": note.get("createDate"),
                        "modifiedAt": note.get("modifyDate"),
                    }
                except Exception:
                    return None

        tasks = [fetch_one(n) for n in entries[:200]]
        results = await asyncio.gather(*tasks)
        result = [r for r in results if r is not None]

        return {
            "status": "ok",
            "notes": result,
            "total_found": len(entries),
            "fetched": len(result),
        }


@app.get("/api/mi-check-cookie")
async def check_cookie(x_mi_cookie: str = Header(default="")):
    """检查 Cookie 是否有效"""
    if not x_mi_cookie:
        return {"valid": False}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            url = f"https://i.mi.com/note/full/page/?ts={int(datetime.now().timestamp()*1000)}&limit=1"
            resp = await client.get(url, headers={"Cookie": x_mi_cookie})
            return {"valid": bool(resp.json().get("data"))}
    except Exception:
        return {"valid": False}
