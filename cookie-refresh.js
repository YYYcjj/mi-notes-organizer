/**
 * 一键刷新 Cookie 并更新 GitHub Secret
 *
 * 用法：在任意页面 F12 → Console → 粘贴 → 回车
 * - 不在 i.mi.com？自动跳转到登录页
 * - 已登录？自动提取 Cookie 并更新 Secret
 * - PAT 存浏览器本地，不上传任何第三方
 */

(async function() {
  'use strict';

  const REPO = 'YYYcjj/mi-notes-organizer';
  const SECRET_NAME = 'MI_COOKIE';
  const LS_KEY = 'mi_notes_gh_pat';
  const MI_URL = 'https://i.mi.com/note/h5';

  const SCRIPT_URL = 'https://raw.githubusercontent.com/YYYcjj/mi-notes-organizer/master/cookie-refresh.js';

  // ========== 来源判断 ==========
  const isMiCom = location.hostname.includes('i.mi.com');
  const isNotePage = location.pathname.includes('/note');

  // ========== 存/取 PAT ==========
  function getPat() {
    // 先查 URL hash（跨域传递），再查 localStorage（本地存储）
    const hash = location.hash;
    if (hash.includes('mi_pat=')) {
      const pat = decodeURIComponent(hash.split('mi_pat=')[1].split('&')[0]);
      if (pat && pat.startsWith('ghp_')) {
        localStorage.setItem(LS_KEY, pat);
        // 清除 hash 中的 PAT，避免留在历史记录
        history.replaceState(null, '', location.pathname + location.search);
        return pat;
      }
    }
    return localStorage.getItem(LS_KEY);
  }

  function savePat(pat) {
    localStorage.setItem(LS_KEY, pat);
  }

  // ========== 提取 Cookie ==========
  function getMiCookie() {
    return document.cookie;
  }

  // ========== 更新 GitHub Secret ==========
  async function updateSecret(pat, cookie) {
    const pkUrl = `https://api.github.com/repos/${REPO}/actions/secrets/public-key`;
    const pkResp = await fetch(pkUrl, {
      headers: { Authorization: `token ${pat}`, Accept: 'application/vnd.github+json' }
    });
    if (!pkResp.ok) throw new Error('GitHub 认证失败，PAT 可能已过期');
    const { key_id, key } = await pkResp.json();

    const encoder = new TextEncoder();
    const keyBytes = Uint8Array.from(atob(key), c => c.charCodeAt(0));
    const secretBytes = encoder.encode(cookie);

    const cryptoKey = await crypto.subtle.importKey(
      'raw', keyBytes, { name: 'AES-GCM' }, false, ['encrypt']
    );
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const encrypted = await crypto.subtle.encrypt(
      { name: 'AES-GCM', iv }, cryptoKey, secretBytes
    );
    const combined = new Uint8Array(iv.length + encrypted.byteLength);
    combined.set(iv);
    combined.set(new Uint8Array(encrypted), iv.length);
    const encryptedValue = btoa(String.fromCharCode(...combined));

    const putUrl = `https://api.github.com/repos/${REPO}/actions/secrets/${SECRET_NAME}`;
    const putResp = await fetch(putUrl, {
      method: 'PUT',
      headers: { Authorization: `token ${pat}`, Accept: 'application/vnd.github+json' },
      body: JSON.stringify({ encrypted_value: encryptedValue, key_id })
    });

    if (putResp.ok || putResp.status === 201) return true;
    throw new Error(`更新失败: HTTP ${putResp.status}`);
  }

  // ========== UI ==========
  function log(msg, type) {
    const colors = { info: '#58a6ff', success: '#3fb950', error: '#da3633', title: '#ff6700', dim: '#8b949e' };
    const weight = type === 'title' ? 'bold' : 'normal';
    console.log('%c' + msg, `color:${colors[type] || '#c9d1d9'};font-weight:${weight}`);
  }

  function bigBanner(text) {
    console.log(
      '%c' + text,
      'background:#ff6700;color:#fff;padding:12px 24px;font-size:16px;font-weight:bold;border-radius:8px'
    );
  }

  // ========== 非 i.mi.com：提示跳转 ==========
  function redirectToMi(pats) {
    log('\n📍 当前不在小米云页面，自动跳转到登录页...', 'info');
    log('   目标: ' + MI_URL, 'dim');
    if (pats) {
      log('   ✅ PAT 已缓存，跳转后无需再次输入', 'success');
    }
    log('\n⏳ 正在跳转...', 'info');

    // 构建跳转 URL，通过 hash 传递 PAT
    let url = MI_URL;
    if (pats) {
      url += '#mi_pat=' + encodeURIComponent(pats);
    }
    location.href = url;
  }

  // ========== i.mi.com 但 Cookie 不足 ==========
  function showNotLoggedIn() {
    log('\n⚠️ 请先登录小米账号', 'title');
    log('   当前页面: ' + location.href, 'dim');
    log('   如果还没登录，点击页面上的登录按钮', 'info');
    log('   登录后 → F12 → Console → 重新粘贴脚本', 'info');
    log(`\n💡 脚本地址: ${SCRIPT_URL}`, 'dim');
  }

  // ========== 主流程 ==========
  async function main() {
    log('');

    // ---- 阶段 0: 不在小米云 → 跳转 ----
    if (!isMiCom) {
      const pat = getPat();
      if (!pat) {
        const input = prompt(
          '🔑 首次使用需要 GitHub PAT\n\n' +
          '（仅存浏览器本地，不上传，跳转后无需重复输入）\n\n' +
          '获取方式: https://github.com/settings/tokens/new\n' +
          '勾选 repo → Generate → 粘贴到此处'
        );
        if (!input || !input.trim().startsWith('ghp_')) {
          log('⏸ 已取消（需要有效的 GitHub PAT）', 'info');
          return;
        }
        savePat(input.trim());
      }
      redirectToMi(getPat());
      return;
    }

    // ---- 阶段 1: 在小米云，检查登录状态 ----
    const cookie = getMiCookie();
    if (!cookie || cookie.length < 50) {
      showNotLoggedIn();
      return;
    }

    bigBanner('🔄 小米笔记 Cookie 自动刷新');
    log(`✅ 已提取 Cookie（${cookie.length} 字符）`, 'success');

    // ---- 阶段 2: 获取/验证 PAT ----
    let pat = getPat();
    if (!pat) {
      const input = prompt(
        '🔑 需要 GitHub PAT 来更新 Secret（仅存浏览器本地）\n\n' +
        '获取方式: https://github.com/settings/tokens/new\n' +
        '勾选 repo → Generate → 粘贴到此处'
      );
      if (!input) { log('⏸ 已取消', 'info'); return; }
      pat = input.trim();
      savePat(pat);
      log('💾 PAT 已保存', 'success');
    }

    // ---- 阶段 3: 更新 Secret ----
    try {
      log('📡 正在更新 GitHub Secret...', 'info');
      await updateSecret(pat, cookie);

      bigBanner('✅ 成功！MI_COOKIE 已更新');
      log('', 'dim');
      log('   📅 约 2-4 周后 Cookie 过期', 'info');
      log('   🔄 届时再次运行本脚本即可自动续期', 'info');
      log('   ⏰ 每周日 GitHub Actions 自动同步笔记', 'info');
      log('', 'dim');

    } catch(e) {
      if (e.message.includes('401') || e.message.includes('认证失败')) {
        localStorage.removeItem(LS_KEY);
        log('❌ PAT 已过期，请刷新页面重新输入', 'error');
      } else {
        log('❌ ' + e.message, 'error');
      }
    }
  }

  main();
})();
