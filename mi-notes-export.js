/**
 * 小米笔记导出脚本 (v2 - 含图片下载)
 *
 * 使用: i.mi.com → F12 → Console → 粘贴 → 回车
 * 自动下载图片并嵌入 base64，生成完整可离线查看的 JSON
 */
(async function() {
  'use strict';

  const CONFIG = { listLimit: 300, delay: 80 };

  let stopSignal = false;
  function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
  function log(msg, type) {
    const c = { info: '#58a6ff', success: '#3fb950', warn: '#d2991d', error: '#da3633', title: '#ff6700' };
    console.log('%c' + msg, 'color:' + (c[type] || '#c9d1d9'));
  }

  function createStopBtn() {
    const btn = document.createElement('button');
    btn.textContent = '⏹ 停止'; btn.style.cssText = 'position:fixed;top:12px;right:12px;z-index:99999;padding:8px 16px;background:#da3633;color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:13px';
    btn.onclick = () => { stopSignal = true; btn.textContent = '⏸ 停止中...'; btn.disabled = true; };
    document.body.appendChild(btn); return btn;
  }

  // ===== 图片下载 =====
  async function fetchImageAsBase64(imgUrl) {
    try {
      const resp = await fetch(imgUrl);
      if (!resp.ok) return null;
      const blob = await resp.blob();
      return new Promise((resolve) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => resolve(null);
        reader.readAsDataURL(blob);
      });
    } catch(e) { return null; }
  }

  // ===== 阶段1: 扫描列表 =====
  async function fetchList() {
    log('\n📋 扫描笔记列表...', 'title');
    let entries = [], syncTag = '', page = 1;
    while (!stopSignal) {
      const url = `https://i.mi.com/note/full/page/?ts=${Date.now()}&limit=${CONFIG.listLimit}${syncTag?'&syncTag='+syncTag:''}`;
      const res = await fetch(url).then(r => r.json());
      if (!res.data?.entries) break;
      const batch = res.data.entries;
      if (!batch.length) break;
      entries = entries.concat(batch);
      syncTag = res.data.syncTag;
      log(`   ${page}: +${batch.length} (共 ${entries.length})`, 'info');
      if (!syncTag) break;
      page++; await sleep(CONFIG.delay);
    }
    log(`✅ 共 ${entries.length} 条`, 'success');
    return entries;
  }

  // ===== 阶段2: 获取详情+下载图片 =====
  async function fetchAllDetails(list) {
    log('\n📄 获取内容+下载图片...', 'title');
    const results = [];
    const total = list.length;
    const BATCH = 12;

    // 全局图片缓存（避免重复下载）
    const imageCache = {};
    const debugFirstBatch = list.length > 0 ? list[0] : null;

    for (let i = 0; i < total; i += BATCH) {
      if (stopSignal) { log('⏸ 已中止', 'warn'); break; }

      // 并获取当前批次的详情
      const batchNotes = list.slice(i, i + BATCH);
      const batchResults = await Promise.all(batchNotes.map(async (note) => {
        try {
          const res = await fetch(`https://i.mi.com/note/note/${note.id}/?ts=${Date.now()}`).then(r => r.json());
          const entry = res.data?.entry;
          if (!entry) return null;

          let title = '无标题';
          try { const extra = JSON.parse(entry.extraInfo||'{}'); if (extra.title) title = extra.title; } catch(e) {}

          // 提取图片 URL（支持多种格式）
          const rawContent = entry.content || '';
          const imgMatches = [
            ...rawContent.matchAll(/<img[^>]+src="([^"]+)"[^>]*>/gi),
            ...rawContent.matchAll(/data-src="([^"]+)"/gi),
            ...rawContent.matchAll(/src="([^"]*\.(?:jpg|jpeg|png|gif|webp|bmp)[^"]*)"/gi),
          ];
          const imgUrls = imgMatches.map(m => m[1]);
          const uniqueUrls = [...new Set(imgUrls)];

          // 并发下载图片
          let downloadedImages = {};
          if (uniqueUrls.length > 0) {
            const dlResults = await Promise.all(
              uniqueUrls.map(async (url) => {
                if (imageCache[url]) return { url, base64: imageCache[url] };
                const b64 = await fetchImageAsBase64(url);
                if (b64) imageCache[url] = b64;
                return { url, base64: b64 };
              })
            );
            dlResults.forEach(r => { if (r.base64) downloadedImages[r.url] = r.base64; });
          }

          // 替换图片为 base64
          let content = rawContent;
          for (const [url, b64] of Object.entries(downloadedImages)) {
            content = content.replace(new RegExp(url.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'), b64);
          }

          // 清理 HTML
          content = content
            .replace(/<img[^>]+src="([^"]+)"[^>]*>/gi, '\n![图片]($1)\n')
            .replace(/<br\s*\/?>/gi, '\n')
            .replace(/<\/p>/gi, '\n')
            .replace(/<[^>]+>/g, '')
            .replace(/&nbsp;/g, ' ')
            .replace(/&amp;/g, '&')
            .replace(/&lt;/g, '<')
            .replace(/&gt;/g, '>')
            .replace(/&quot;/g, '"')
            .replace(/\n{3,}/g, '\n\n')
            .trim();

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

      const done = Math.min(i + BATCH, total);
      const imgCount = Object.keys(imageCache).length;
      const pct = Math.round(done / total * 100);
      log(`   ⚡ [${done}/${total}] ${results.length} 条 · ${imgCount} 张图 (${pct}%)`, 'info');

      // Debug: 检查第一条笔记的 content 格式
      if (i === 0 && results.length > 0) {
        const firstContent = results[0].content || '';
        const hasImg = /<img|☺/.test(firstContent);
        const rawSample = (batchResults[0] && batchResults[0].content) ? batchResults[0].content : '';
        log(`   🔍 调试：第一条 content 长度=${firstContent.length}, 含img标识=${hasImg}`, 'info');
        if (rawSample && i === 0) {
          // 从 entry.content 看原始 img 标签
          try {
            const r = await fetch(`https://i.mi.com/note/note/${list[0].id}/?ts=${Date.now()}`).then(r => r.json());
            const ec = r.data?.entry?.content || '';
            const imgs = ec.match(/<img[^>]+>/g) || [];
            log(`   🔍 原始 entry.content 含 ${imgs.length} 个 <img> 标签`, 'info');
            if (imgs[0]) log(`      样例: ${imgs[0].substring(0, 200)}`, 'info');
          } catch(e) {}
        }
      }

      if (i + BATCH < total) await sleep(200);
    }

    log(`\n✅ 内容完成: ${results.length} 条 · 图片 ${Object.keys(imageCache).length} 张`, 'success');
    return results;
  }

  // ===== 下载 JSON =====
  function download(notes) {
    log('\n💾 生成文件...', 'title');
    const data = JSON.stringify(notes, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    const now = new Date();
    const ds = now.getFullYear()+String(now.getMonth()+1).padStart(2,'0')+String(now.getDate()).padStart(2,'0')+'_'+String(now.getHours()).padStart(2,'0')+String(now.getMinutes()).padStart(2,'0');
    a.href = url; a.download = `mi-notes_${ds}.json`; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
    const sizeMB = (blob.size / 1024 / 1024).toFixed(1);
    log(`\n🎉 完成！${notes.length} 条 · ${sizeMB} MB`, 'success');
    log('   拖入 mi-notes 网页即可浏览', 'info');
  }

  // ===== 主流程 =====
  try {
    log('\n╔══════════════════════════════╗', 'title');
    log('║   📝 小米笔记导出 (含图片)  ║', 'title');
    log('╚══════════════════════════════╝', 'title');

    const stopBtn = createStopBtn();
    const list = await fetchList();
    if (stopSignal) { log('⏸ 停止', 'warn'); stopBtn.remove(); return; }
    if (!list.length) { log('📭 无笔记', 'warn'); stopBtn.remove(); return; }
    const notes = await fetchAllDetails(list);
    if (notes.length) download(notes);
    stopBtn.remove();
  } catch(e) { log('❌ ' + e.message, 'error'); console.error(e); }
})();
