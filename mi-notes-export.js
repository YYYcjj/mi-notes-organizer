/**
 * 小米笔记导出脚本 - 导出为 JSON 格式（兼容 mi-notes-organizer）
 *
 * 使用方法:
 * 1. 电脑浏览器打开 https://i.mi.com/note/h5 并登录
 * 2. 按 F12 打开开发者工具 → Console 控制台
 * 3. 复制本文件全部代码，粘贴到控制台，按回车
 * 4. 等待自动下载 mi-notes-export.json
 * 5. 将下载的 JSON 文件拖入 mi-notes 网页即可导入
 *
 * 特点:
 * - 导出格式与 mi-notes-organizer 完全兼容
 * - 保留笔记标题、内容、文件夹、创建/修改时间
 * - 自动延迟防封控，支持随时中断
 */

(async function() {
  'use strict';

  // ========== 配置 ==========
  const CONFIG = {
    listLimit: 200,       // 每次列表请求条数
    delay: 400,           // 请求间隔 (ms)
    longDelay: 1500,      // 长间隔 (每20条)
    longDelayEvery: 20,   // 间隔频率
  };

  // ========== 状态 ==========
  let stopSignal = false;

  // ========== 工具函数 ==========
  function sleep(ms) {
    return new Promise(r => setTimeout(r, ms));
  }

  function fmtDate(ts) {
    const d = new Date(ts);
    return d.getFullYear() + '-' +
      String(d.getMonth()+1).padStart(2,'0') + '-' +
      String(d.getDate()).padStart(2,'0') + ' ' +
      String(d.getHours()).padStart(2,'0') + ':' +
      String(d.getMinutes()).padStart(2,'0');
  }

  function log(msg, type) {
    const styles = {
      info: 'color: #58a6ff',
      success: 'color: #3fb950',
      warn: 'color: #d2991d',
      error: 'color: #da3633',
      title: 'color: #ff6700; font-size: 16px; font-weight: bold',
    };
    console.log('%c' + msg, styles[type] || '');
  }

  // ========== 创建停止按钮 ==========
  function createStopBtn() {
    const btn = document.createElement('button');
    btn.textContent = '⏹ 停止导出';
    btn.style.cssText = `
      position: fixed; top: 16px; right: 16px; z-index: 99999;
      padding: 10px 20px; background: #da3633; color: #fff;
      border: none; border-radius: 8px; cursor: pointer;
      font-size: 14px; box-shadow: 0 2px 8px rgba(0,0,0,.4);
    `;
    btn.onclick = () => {
      stopSignal = true;
      btn.textContent = '⏸ 停止中...';
      btn.disabled = true;
      btn.style.opacity = '0.6';
    };
    document.body.appendChild(btn);
    return btn;
  }

  // ========== 阶段1: 获取笔记列表 ==========
  async function fetchList() {
    log('\n📋 阶段 1/2: 扫描笔记列表...', 'title');

    let entries = [];
    let syncTag = '';
    let page = 1;

    while (!stopSignal) {
      const url = `https://i.mi.com/note/full/page/?ts=${Date.now()}&limit=${CONFIG.listLimit}${syncTag ? '&syncTag=' + syncTag : ''}`;
      const res = await fetch(url).then(r => r.json());

      if (!res.data || !res.data.entries) {
        log('⚠️ API 响应异常，请确认已登录 i.mi.com', 'error');
        break;
      }

      const batch = res.data.entries;
      if (batch.length === 0) break;

      entries = entries.concat(batch);
      syncTag = res.data.syncTag;

      log(`   第 ${page} 页: +${batch.length} 条 (累计 ${entries.length})`, 'info');

      if (!syncTag) break;
      page++;
      await sleep(CONFIG.delay);
    }

    log(`\n✅ 扫描完成: 共 ${entries.length} 条笔记`, 'success');
    return entries;
  }

  // ========== 阶段2: 并发获取笔记详情 ==========
  async function fetchDetail(note) {
    try {
      const res = await fetch(`https://i.mi.com/note/note/${note.id}/?ts=${Date.now()}`).then(r => r.json());
      const entry = res.data?.entry;
      if (!entry) return null;

      let title = '无标题';
      try {
        const extra = JSON.parse(entry.extraInfo || '{}');
        if (extra.title) title = extra.title;
      } catch(e) {}

      let content = (entry.content || '')
        // 保留图片信息：<img> → ☺ 标记
        .replace(/<img[^>]+src="[^"]*?\/file\/([^"]+)"[^>]*>/gi, '\n☺ $1\n')
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
      };
    } catch(e) {
      return null;
    }
  }

  async function fetchDetails(list) {
    log('\n📄 阶段 2/2: 并发获取笔记内容...', 'title');

    const results = [];
    const total = list.length;
    const BATCH = 8;

    for (let i = 0; i < total; i += BATCH) {
      if (stopSignal) {
        log('\n⏸ 用户中止，已保存 ' + results.length + ' 条笔记', 'warn');
        break;
      }

      const batch = list.slice(i, i + BATCH);
      const resps = await Promise.all(batch.map(fetchDetail));

      for (const r of resps) {
        if (r) results.push(r);
      }

      const done = Math.min(i + BATCH, total);
      const pct = Math.round((done / total) * 100);
      if (results.length > 0) {
        log(`   ⚡ [${done}/${total}] ${results[results.length-1].title.slice(0, 25)}`, 'info');
      }

      if (i + BATCH < total) await sleep(300);
    }

    log(`\n✅ 内容获取完成: ${results.length} 条`, 'success');
    return results;
  }

  // ========== 下载文件 ==========
  function download(notes) {
    log('\n💾 生成导出文件...', 'title');

    const data = JSON.stringify(notes, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    const now = new Date();
    const dateStr = now.getFullYear() +
      String(now.getMonth()+1).padStart(2,'0') +
      String(now.getDate()).padStart(2,'0') + '_' +
      String(now.getHours()).padStart(2,'0') +
      String(now.getMinutes()).padStart(2,'0');

    a.href = url;
    a.download = `mi-notes-export_${dateStr}.json`;
    a.click();

    setTimeout(() => URL.revokeObjectURL(url), 60000);

    log(`\n🎉 导出完成！共 ${notes.length} 条笔记`, 'success');
    log(`   文件: ${a.download}`, 'info');
    log(`\n📥 下一步: 打开 mi-notes 网页，将下载的 JSON 文件拖入即可导入`, 'title');
  }

  // ========== 主流程 ==========
  try {
    log('\n╔══════════════════════════════════╗', 'title');
    log('║   📝 小米笔记导出工具          ║', 'title');
    log('║   格式: JSON (mi-notes 兼容)    ║', 'title');
    log('╚══════════════════════════════════╝\n', 'title');

    const stopBtn = createStopBtn();

    const list = await fetchList();

    if (stopSignal) {
      log('⏸ 已停止', 'warn');
      if (stopBtn) stopBtn.remove();
      return;
    }

    if (list.length === 0) {
      log('📭 没有找到笔记，请确认已登录小米云服务', 'warn');
      if (stopBtn) stopBtn.remove();
      return;
    }

    const notes = await fetchDetails(list);

    if (notes.length > 0) {
      download(notes);
    } else {
      log('⚠️ 没有成功获取任何笔记内容', 'error');
    }

    if (stopBtn) stopBtn.remove();
    log('\n✅ 脚本执行完毕\n', 'success');

  } catch(e) {
    log('\n❌ 严重错误: ' + e.message, 'error');
    console.error(e);
  }

})();
