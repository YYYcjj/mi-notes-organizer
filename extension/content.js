// 小米笔记导出器 - Chrome Extension
(function() {
  'use strict';

  // 防止重复注入
  if (document.getElementById('mi-notes-exporter-btn')) return;

  // ===== UI: 浮动按钮 =====
  const btn = document.createElement('button');
  btn.id = 'mi-notes-exporter-btn';
  btn.textContent = '📥 导出笔记';
  btn.style.cssText = 'position:fixed;bottom:20px;right:20px;z-index:99999;padding:12px 20px;background:#ff6700;color:#fff;border:none;border-radius:12px;font-size:14px;font-weight:bold;cursor:pointer;box-shadow:0 4px 12px rgba(255,103,0,.4);transition:all .2s';
  btn.onmouseenter = () => btn.style.transform = 'scale(1.05)';
  btn.onmouseleave = () => btn.style.transform = 'scale(1)';
  document.body.appendChild(btn);

  // 进度条
  const progress = document.createElement('div');
  progress.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:99998;height:3px;background:#ff6700;width:0;transition:width .3s';
  document.body.appendChild(progress);

  const toast = document.createElement('div');
  toast.style.cssText = 'position:fixed;top:20px;left:50%;transform:translateX(-50%);z-index:100000;padding:10px 24px;background:#161b22;color:#ff6700;border:1px solid #ff6700;border-radius:20px;font-size:13px;display:none;box-shadow:0 4px 12px rgba(0,0,0,.3)';
  document.body.appendChild(toast);

  function showToast(msg, dur) {
    toast.textContent = msg; toast.style.display = 'block';
    setTimeout(() => { toast.style.display = 'none'; }, dur || 3000);
  }

  function setProgress(pct) {
    progress.style.width = pct + '%';
  }

  // ===== 核心导出逻辑 =====
  async function fetchImageAsBase64(url) {
    try {
      const resp = await fetch(url);
      if (!resp.ok) return null;
      const blob = await resp.blob();
      return new Promise(resolve => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => resolve(null);
        reader.readAsDataURL(blob);
      });
    } catch(e) { return null; }
  }

  async function exportNotes() {
    btn.textContent = '⏳ 扫描中...';
    btn.disabled = true;
    setProgress(0);

    try {
      // 阶段1: 扫描列表
      let entries = [], syncTag = '', page = 1;
      while (true) {
        const url = 'https://i.mi.com/note/full/page/?ts='+Date.now()+'&limit=300'+(syncTag?'&syncTag='+syncTag:'');
        const res = await fetch(url).then(r => r.json());
        const batch = res?.data?.entries;
        if (!batch || !batch.length) break;
        entries = entries.concat(batch);
        syncTag = res.data.syncTag;
        if (!syncTag) break;
        page++;
        await new Promise(r => setTimeout(r, 100));
      }
      showToast('找到 ' + entries.length + ' 条笔记，开始获取内容...');

      // 阶段2: 并发获取详情 + 图片
      const results = [];
      const total = entries.length;
      const imageCache = {};
      const BATCH = 6;

      for (let i = 0; i < total; i += BATCH) {
        const batch = entries.slice(i, Math.min(i + BATCH, total));
        const batchResults = await Promise.all(batch.map(async (note) => {
          try {
            const res = await fetch('https://i.mi.com/note/note/'+note.id+'/?ts='+Date.now()).then(r => r.json());
            const entry = res?.data?.entry;
            if (!entry) return null;

            let title = '无标题';
            try { const ex = JSON.parse(entry.extraInfo || '{}'); if (ex.title) title = ex.title; } catch(e) {}

            // 提取图片URL并下载
            const rawContent = entry.content || '';
            const imgMatches = [...rawContent.matchAll(/<img[^>]+src="([^"]+)"[^>]*>/gi)];
            const imgUrls = [...new Set(imgMatches.map(m => m[1]))];

            let downloadedImages = {};
            if (imgUrls.length > 0) {
              const dlResults = await Promise.all(imgUrls.map(async (url) => {
                if (imageCache[url]) return { url, base64: imageCache[url] };
                const b64 = await fetchImageAsBase64(url);
                if (b64) imageCache[url] = b64;
                return { url, base64: b64 };
              }));
              dlResults.forEach(r => { if (r.base64) downloadedImages[r.url] = r.base64; });
            }

            // 替换图片
            let content = rawContent;
            for (const [url, b64] of Object.entries(downloadedImages)) {
              const escaped = url.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
              content = content.replace(new RegExp(escaped, 'g'), b64);
            }

            // 清理HTML
            content = content
              .replace(/<br\s*\/?>/gi, '\n')
              .replace(/<\/p>/gi, '\n')
              .replace(/<[^>]+>/g, '')
              .replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"')
              .replace(/\n{3,}/g, '\n\n').trim();

            return {
              title, content,
              folder: entry.folderId || '',
              createdAt: note.createDate,
              modifiedAt: note.modifyDate || note.createDate,
              _images: Object.keys(downloadedImages).length,
            };
          } catch(e) { return null; }
        }));

        for (const r of batchResults) { if (r) results.push(r); }
        setProgress(Math.round(Math.min(i + BATCH, total) / total * 100));
        if (i + BATCH < total) await new Promise(r => setTimeout(r, 200));
      }

      // 阶段3: 下载
      const data = JSON.stringify(results, null, 2);
      const blob = new Blob([data], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      const now = new Date();
      const ds = now.getFullYear()+String(now.getMonth()+1).padStart(2,'0')+String(now.getDate()).padStart(2,'0')+'_'+String(now.getHours()).padStart(2,'0')+String(now.getMinutes()).padStart(2,'0');
      a.href = url; a.download = 'mi-notes_'+ds+'.json';
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 60000);

      const sizeMB = (blob.size / 1024 / 1024).toFixed(1);
      const imgCount = Object.keys(imageCache).length;
      showToast('✅ 导出完成！' + results.length + ' 条 · ' + imgCount + ' 张图 · ' + sizeMB + 'MB', 5000);
      setProgress(100);

    } catch(e) {
      showToast('❌ 错误: ' + e.message, 5000);
    } finally {
      btn.textContent = '📥 导出笔记';
      btn.disabled = false;
      setTimeout(() => setProgress(0), 2000);
    }
  }

  btn.onclick = exportNotes;
})();
