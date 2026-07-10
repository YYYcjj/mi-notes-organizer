/**
 * 一键刷新 Cookie 并更新 GitHub Secret
 *
 * 使用方法：
 * 1. 打开 i.mi.com 并登录小米账号
 * 2. F12 → Console → 粘贴本脚本 → 回车
 * 3. 自动提取 Cookie → 更新到 GitHub Actions Secret
 *
 * 首次需要提供 GitHub PAT（只存浏览器 localStorage，不上传）
 */

(async function() {
  'use strict';

  const REPO = 'YYYcjj/mi-notes-organizer';
  const SECRET_NAME = 'MI_COOKIE';
  const LS_KEY = 'mi_notes_gh_pat';

  // ========== 存/取 GitHub PAT ==========
  function getPat() {
    return localStorage.getItem(LS_KEY);
  }
  function savePat(pat) {
    localStorage.setItem(LS_KEY, pat);
  }

  // ========== 提取当前 Cookie ==========
  function getCookie() {
    return document.cookie;
  }

  // ========== 更新 GitHub Secret ==========
  async function updateSecret(pat, cookie) {
    // 1. 获取 public key
    const pkUrl = `https://api.github.com/repos/${REPO}/actions/secrets/public-key`;
    const pkResp = await fetch(pkUrl, {
      headers: { Authorization: `token ${pat}`, Accept: 'application/vnd.github+json' }
    });
    if (!pkResp.ok) throw new Error('GitHub 认证失败，PAT 可能已过期');
    const { key_id, key } = await pkResp.json();

    // 2. 用 libsodium 加密
    const encoder = new TextEncoder();
    const keyBytes = Uint8Array.from(atob(key), c => c.charCodeAt(0));
    const secretBytes = encoder.encode(cookie);

    // 使用 Web Crypto API 加密
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

    // 3. 更新 Secret
    const putUrl = `https://api.github.com/repos/${REPO}/actions/secrets/${SECRET_NAME}`;
    const putResp = await fetch(putUrl, {
      method: 'PUT',
      headers: { Authorization: `token ${pat}`, Accept: 'application/vnd.github+json' },
      body: JSON.stringify({ encrypted_value: encryptedValue, key_id })
    });

    if (putResp.ok || putResp.status === 201) {
      return true;
    }
    throw new Error(`更新失败: ${putResp.status}`);
  }

  // ========== UI ==========
  function log(msg, type) {
    const colors = { info: '#58a6ff', success: '#3fb950', error: '#da3633', title: '#ff6700' };
    console.log('%c' + msg, `color:${colors[type] || '#c9d1d9'};font-weight:${type==='title'?'bold':'normal'}`);
  }

  // ========== 主流程 ==========
  async function main() {
    log('\n🔄 小米笔记 Cookie 自动刷新\n', 'title');

    const cookie = getCookie();
    if (!cookie || cookie.length < 20) {
      log('❌ 未检测到有效 Cookie，请确认已登录 i.mi.com', 'error');
      return;
    }
    log(`✅ 已提取 Cookie（${cookie.length} 字符）`, 'success');

    let pat = getPat();
    if (!pat) {
      const input = prompt(
        '🔑 需要 GitHub PAT 来更新 Secret（仅存浏览器本地）\n\n' +
        '获取方式：https://github.com/settings/tokens/new\n' +
        '勾选 repo 权限 → Generate → 复制到这里'
      );
      if (!input) { log('⏸ 已取消', 'info'); return; }
      pat = input.trim();
      savePat(pat);
      log('💾 PAT 已保存', 'success');
    }

    try {
      log('📡 正在更新 GitHub Secret...', 'info');
      await updateSecret(pat, cookie);
      log(`\n🎉 成功！MI_COOKIE 已更新`, 'success');
      log('   ⏰ 下一次自动同步将使用新 Cookie', 'info');
      log('   📅 约 2-4 周后需再次刷新', 'info');
    } catch(e) {
      if (e.message.includes('401') || e.message.includes('认证失败')) {
        localStorage.removeItem(LS_KEY);
        log('❌ PAT 已过期，请刷新页面重新执行', 'error');
      } else {
        log('❌ ' + e.message, 'error');
      }
    }
  }

  main();
})();
