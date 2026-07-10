/**
 * 小米笔记一键导出书签脚本
 *
 * 在 i.mi.com 页面点击书签 → 自动抓取全部笔记 → 发送到 mi-notes 网页
 *
 * 书签地址（复制到浏览器书签栏）：
 * javascript:(function(){var s=document.createElement('script');s.src='https://cdn.jsdelivr.net/gh/YYYcjj/mi-notes-organizer@master/bookmarklet-export.js';document.body.appendChild(s);})()
 */
(async function() {
  'use strict';

  const TARGET_ORIGIN = 'https://8df96c902ffa4eb59cab29c2422070bc.app.codebuddy.work';

  // ===== 检查环境 =====
  if (!location.hostname.includes('i.mi.com')) {
    alert('请在 i.mi.com 小米云笔记页面使用此书签');
    return;
  }

  // ===== 创建进度 UI =====
  const overlay = document.createElement('div');
  overlay.innerHTML = `
    <div style="position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);z-index:99999;
      background:#1a1a2e;color:#e0e0e0;border:1px solid #ff6700;border-radius:16px;
      padding:32px 40px;text-align:center;font-family:-apple-system,sans-serif;min-width:300px;
      box-shadow:0 8px 32px rgba(255,103,0,0.3)">
      <div style="font-size:40px;margin-bottom:12px" id="mi-status-icon">🔄</div>
      <div style="font-size:18px;font-weight:bold;color:#ff6700;margin-bottom:8px">小米笔记导出</div>
      <div style="font-size:14px;color:#8b949e" id="mi-status-text">正在扫描笔记列表...</div>
      <div style="background:#30363d;border-radius:8px;height:6px;margin-top:16px;overflow:hidden">
        <div id="mi-progress" style="background:#ff6700;height:100%;width:0%;border-radius:8px;transition:width 0.3s"></div>
      </div>
      <div style="font-size:12px;color:#8b949e;margin-top:8px" id="mi-count">0 / 0</div>
    </div>`;
  document.body.appendChild(overlay);

  function updateStatus(icon, text, progress, count) {
    document.getElementById('mi-status-icon').textContent = icon;
    document.getElementById('mi-status-text').textContent = text;
    if (progress !== undefined) {
      document.getElementById('mi-progress').style.width = progress + '%';
    }
    if (count !== undefined) {
      document.getElementById('mi-count').textContent = count;
    }
  }

  function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

  // ===== 阶段1: 扫描列表 =====
  async function fetchList() {
    let entries = [];
    let syncTag = '';
    let page = 1;

    while (true) {
      const url = `https://i.mi.com/note/full/page/?ts=${Date.now()}&limit=300${syncTag ? '&syncTag=' + syncTag : ''}`;
      const res = await fetch(url).then(r => r.json());

      if (!res.data || !res.data.entries) break;
      const batch = res.data.entries;
      if (batch.length === 0) break;

      entries = entries.concat(batch);
      syncTag = res.data.syncTag;
      updateStatus('📋', `扫描笔记列表 (第${page}页)`, undefined, `${entries.length} 条`);

      if (!syncTag) break;
      page++;
      await sleep(300);
    }
    return entries;
  }

  // ===== 阶段2: 获取详情 =====
  async function fetchDetails(list) {
    const notes = [];
    const total = list.length;

    for (let i = 0; i < total; i++) {
      const note = list[i];
      try {
        const res = await fetch(`https://i.mi.com/note/note/${note.id}/?ts=${Date.now()}`).then(r => r.json());
        const entry = res.data?.entry;
        if (!entry) continue;

        let title = '无标题';
        try {
          const extra = JSON.parse(entry.extraInfo || '{}');
          if (extra.title) title = extra.title;
        } catch(e) {}

        let content = (entry.content || '')
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

        notes.push({
          title, content,
          folder: entry.folderId || '',
          createdAt: note.createDate,
          modifiedAt: note.modifyDate || note.createDate,
        });

        const pct = Math.round(((i + 1) / total) * 100);
        updateStatus('📝', `获取笔记内容 "${title.slice(0,15)}..."`, pct, `${i + 1} / ${total}`);

      } catch(e) {
        console.warn('获取失败:', note.id, e);
      }

      await sleep(i % 15 === 0 ? 800 : 200);
    }

    return notes;
  }

  // ===== 阶段3: 发送数据 =====
  function sendToPage(notes) {
    const json = JSON.stringify(notes);

    // 方案A: 如果有 opener（从 mi-notes 网页打开的），用 postMessage
    if (window.opener && !window.opener.closed) {
      try {
        window.opener.postMessage({ type: 'mi-notes-import', data: json }, '*');
        updateStatus('✅', `已发送 ${notes.length} 条笔记到 mi-notes 页面`, 100, `${notes.length} 条`);
        overlay.querySelector('div').style.borderColor = '#3fb950';
        overlay.querySelector('div').style.boxShadow = '0 8px 32px rgba(63,185,80,0.3)';
        setTimeout(() => overlay.remove(), 3000);
        return true;
      } catch(e) {
        console.warn('postMessage 失败，尝试备用方案', e);
      }
    }

    // 方案B: 打开 mi-notes 页面，通过 sessionStorage 桥接
    // （同源限制，改用新标签页 + 手动导入提示）
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `mi-notes_${Date.now()}.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 60000);

    window.open(TARGET_ORIGIN, '_blank');
    updateStatus('📥', 'JSON 已下载，已打开 mi-notes 页面\n请拖入下载的 JSON 文件', 100, `${notes.length} 条`);
    overlay.querySelector('div').style.borderColor = '#ff6700';

    return false;
  }

  // ===== 主流程 =====
  try {
    // 检查登录
    if (document.cookie.length < 50) {
      updateStatus('🔐', '请先登录小米账号', 0, '');
      await sleep(2000);
      overlay.remove();
      return;
    }

    // 获取列表
    const list = await fetchList();
    if (!list.length) {
      updateStatus('📭', '没有找到笔记', 100, '0 条');
      await sleep(2000);
      overlay.remove();
      return;
    }

    // 获取详情
    const notes = await fetchDetails(list);

    // 发送
    sendToPage(notes);

  } catch(e) {
    updateStatus('❌', '导出失败: ' + e.message, 0, '');
    console.error(e);
    await sleep(3000);
    overlay.remove();
  }

})();
