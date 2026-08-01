// A6: read API base URL from <meta name="distributor-api"> first (set at
// container start by nginx envsubst), fall back to window override (dev /
// test injection), then localhost. The unsubstituted "${API_BASE_URL}"
// literal is treated as "use the fallback".
const _META_API = document.querySelector('meta[name="distributor-api"]')?.content?.trim();
const API_BASE = (_META_API && !_META_API.startsWith("$"))
  ? _META_API
  : (window.SOCIAL_DISTRIBUTOR_API ?? "http://localhost:5000");

// Operator bearer token (set by login.html after password login). Sent on
// every API call so the cross-origin frontend/api split works without a
// SameSite cookie, and so the X-API-Key wall lets the logged-in operator
// through. Falls back to "" when absent.
const SD_TOKEN_KEY = "sd_operator_token";
function sdToken() { try { return localStorage.getItem(SD_TOKEN_KEY) || ""; } catch (_) { return ""; } }
function sdAuthHeaders() { const t = sdToken(); return t ? { Authorization: "Bearer " + t } : {}; }
function sdGoLogin() {
  try { localStorage.removeItem(SD_TOKEN_KEY); } catch (_) {}
  if (!/login\.html$/.test(location.pathname)) location.href = "login.html";
}

// Register the service worker for PWA / offline shell support.
if ("serviceWorker" in navigator) {
  // When a new SW takes control (a new deploy landed), reload once so the
  // fresh shell/app.js is used immediately instead of the page that loaded
  // the old build. Guarded so it can't loop.
  let _swRefreshing = false;
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (_swRefreshing) return;
    _swRefreshing = true;
    location.reload();
  });
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("./sw.js").catch(() => {
      /* SW registration is a progressive enhancement; ignore failures. */
    });
  });
}

const userIdInput = document.getElementById("userId");

// === Phase 1 hardening: surface every failure ========================
// Before: 12 load functions ran bare; a backend error failed silently and
// the user saw a stale/blank panel with no signal. Now every unhandled
// rejection throws a toast, and consecutive api() failures raise a top banner.
let _consecutiveApiFailures = 0;
let _apiHealthBanner = null;

function _showToast(msg, kind = "error") {
  const t = document.createElement("div");
  t.className = `toast toast-${kind}`;
  t.textContent = msg;
  t.style.cssText =
    "position:fixed;top:16px;right:16px;max-width:380px;padding:12px 16px;border-radius:8px;z-index:10000;font-size:13px;line-height:1.45;box-shadow:0 4px 16px rgba(0,0,0,.45);" +
    (kind === "error"
      ? "background:#3a1a1a;color:#ff9b9b;border:1px solid #5a2d2d;"
      : "background:#1a3a1a;color:#6abf69;border:1px solid #2d5a2d;");
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 6000);
}

function _setApiHealthBanner(show, msg) {
  if (show) {
    if (!_apiHealthBanner) {
      _apiHealthBanner = document.createElement("div");
      _apiHealthBanner.style.cssText =
        "position:fixed;top:0;left:0;right:0;background:#5a1f1f;color:#ffd9d9;padding:8px 16px;text-align:center;z-index:10001;font-size:13px;border-bottom:1px solid #7a2d2d;";
      document.body.appendChild(_apiHealthBanner);
    }
    _apiHealthBanner.textContent = msg;
  } else if (_apiHealthBanner) {
    _apiHealthBanner.remove();
    _apiHealthBanner = null;
  }
}

window.addEventListener("unhandledrejection", (e) => {
  const msg = e.reason?.message || String(e.reason || "未知錯誤");
  _showToast(`操作失敗：${msg}`);
  console.error("[unhandledrejection]", e.reason);
});
window.addEventListener("error", (e) => {
  console.error("[error]", e.error || e.message);
});

// safe URL for href injection — block javascript:/data: schemes.
function safeUrl(u) {
  const s = String(u ?? "").trim();
  return /^(https?:|\/|#)/i.test(s) ? escapeHtml(s) : "#";
}

const API_TIMEOUT_MS = 15000;
async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...sdAuthHeaders(), ...(options.headers ?? {}) };
  // Phase 1: 15s timeout via AbortController so a hung backend route can't
  // freeze the UI indefinitely (the original bare fetch had no ceiling).
  const controller = new AbortController();
  const timeoutMs = options.timeoutMs ?? API_TIMEOUT_MS;
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let res;
  try {
    // C3: send the session cookie cross-origin (CORS supports_credentials).
    res = await fetch(`${API_BASE}${path}`, {
      credentials: "include",
      signal: controller.signal,
      ...options,
      headers,
    });
  } catch (err) {
    _consecutiveApiFailures++;
    if (_consecutiveApiFailures >= 3)
      _setApiHealthBanner(true, `⚠ 後端連續 ${_consecutiveApiFailures} 次無回應——可能離線或逾時。`);
    if (err.name === "AbortError")
      throw new Error(`請求逾時（>${timeoutMs / 1000}s）：${path}`);
    throw err;
  } finally {
    clearTimeout(timer);
  }
  if (!res.ok) {
    // Not authenticated → bounce to the login page instead of spamming the
    // error banner. (401 is the api-key wall / session guard saying "log in".)
    if (res.status === 401) {
      sdGoLogin();
      throw new Error("尚未登入，導向登入頁");
    }
    _consecutiveApiFailures++;
    if (_consecutiveApiFailures >= 3)
      _setApiHealthBanner(true, `⚠ 後端連續 ${_consecutiveApiFailures} 次錯誤回應。`);
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  _consecutiveApiFailures = 0;
  _setApiHealthBanner(false);
  if (res.status === 204) return null;
  return res.json();
}

// C3: at startup, check session. If logged in, hide the manual User ID
// box and use the authenticated id everywhere. If not logged in, the
// user can either click "登入" (top right) or keep typing user_id manually
// for backcompat.
(async function _bootstrapIdentity() {
  try {
    const me = await fetch(`${API_BASE}/auth/me`, {
      credentials: "include",
      headers: { ...sdAuthHeaders() },
    }).then((r) => (r.ok ? r.json() : null));
    if (me && me.authenticated) {
      // Reveal the dashboard (index.html keeps <body> hidden until auth passes).
      document.documentElement.classList.add("sd-authed");
      const userIdEl = document.getElementById("userId");
      if (userIdEl) {
        userIdEl.value = String(me.id);
        userIdEl.disabled = true;
        const wrap = userIdEl.closest("label");
        if (wrap) wrap.title = `signed in as ${me.email}`;
      }
    } else {
      // No valid session/token → require login before showing the dashboard.
      sdGoLogin();
    }
  } catch {
    sdGoLogin();
  }
})();

// --- Tabs -------------------------------------------------------------
document.querySelectorAll(".topbar nav button").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".topbar nav button").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
    if (btn.dataset.tab === "status") loadStatus();
    if (btn.dataset.tab === "accounts") loadAccounts();
    if (btn.dataset.tab === "audit") loadAudit();
    if (btn.dataset.tab === "groups") loadGroups();
    if (btn.dataset.tab === "media") loadMedia();
    if (btn.dataset.tab === "distribute") loadDistributeGroups();
    if (btn.dataset.tab === "insights") loadInsights();
    if (btn.dataset.tab === "daily") loadDailyDeps();
    if (btn.dataset.tab === "permissions") { loadGrants(); loadDrift(); }
    if (btn.dataset.tab === "transfers") loadTransfers();
    if (btn.dataset.tab === "rebroadcast") { loadRbDeps().then(loadRbCandidates); }
    if (btn.dataset.tab === "browser") renderBrowserTier();
    if (btn.dataset.tab === "console") loadConsole();
  });
});

// --- Compose: drag-drop upload ----------------------------------------
const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const uploadStatus = document.getElementById("uploadStatus");
const mediaIdField = document.querySelector('input[name="media_id"]');

document.getElementById("pickFile").addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => {
  if (fileInput.files[0]) handleFile(fileInput.files[0]);
});
["dragenter", "dragover"].forEach((ev) =>
  dropzone.addEventListener(ev, (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  })
);
["dragleave", "drop"].forEach((ev) =>
  dropzone.addEventListener(ev, (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
  })
);
dropzone.addEventListener("drop", (e) => {
  if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
});

async function sha256Hex(file) {
  const buf = await file.arrayBuffer();
  const hash = await crypto.subtle.digest("SHA-256", buf);
  return Array.from(new Uint8Array(hash))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

async function handleFile(file) {
  const userId = Number(userIdInput.value);
  const kind = file.type.startsWith("video/") ? "video" : "image";

  uploadStatus.textContent = `Hashing ${file.name}…`;
  let sha;
  try {
    sha = await sha256Hex(file);
  } catch (err) {
    uploadStatus.textContent = `Hashing failed: ${err.message}`;
    return;
  }

  // Skip the upload entirely if we already have this exact file.
  try {
    const dup = await api(`/api/uploads/check?sha256=${sha}&user_id=${userId}`);
    if (dup.found) {
      mediaIdField.value = dup.media_id;
      uploadStatus.textContent = `已存在 ✓ media_id=${dup.media_id}（重複檔案，省 ${(file.size / 1024 / 1024).toFixed(1)} MB 上傳）`;
      return;
    }
  } catch {}

  uploadStatus.textContent = `Requesting upload URL for ${file.name}…`;
  let presign;
  try {
    presign = await api("/api/uploads/presign", {
      method: "POST",
      body: JSON.stringify({ user_id: userId, kind, content_type: file.type }),
    });
  } catch (err) {
    uploadStatus.textContent = `Presign failed: ${err.message}`;
    return;
  }
  uploadStatus.textContent = `Uploading ${file.name} (${(file.size / 1024 / 1024).toFixed(1)} MB)…`;
  const putRes = await fetch(presign.put_url, {
    method: "PUT",
    headers: presign.headers,
    body: file,
  });
  if (!putRes.ok) {
    uploadStatus.textContent = `Upload failed: ${putRes.status}`;
    return;
  }
  const media = await api("/api/uploads/complete", {
    method: "POST",
    body: JSON.stringify({
      user_id: userId,
      kind,
      content_type: file.type,
      bucket: presign.bucket,
      key: presign.key,
      public_get_url: presign.public_get_url,
      sha256: sha,
    }),
  });
  mediaIdField.value = media.id;
  const note = media.deduped ? " (race-deduped to existing)" : "";
  uploadStatus.textContent = `Uploaded ✓ media_id=${media.id}${note} (transcode: ${media.transcode_status})`;
}

// --- Compose: form submit ---------------------------------------------
const postForm = document.getElementById("postForm");
postForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const out = document.getElementById("postOutput");
  try {
    const fd = new FormData(postForm);
    const userId = Number(userIdInput.value);

    let mediaId = fd.get("media_id") ? Number(fd.get("media_id")) : null;

    // Allow URL fallback for users who already have hosted media.
    const mediaUrl = fd.get("media_url");
    const mediaKind = fd.get("media_kind");
    if (!mediaId && mediaUrl) {
      const inferredKind = mediaKind || (/\.(mp4|mov|webm)$/i.test(mediaUrl) ? "video" : "image");
      const media = await api("/api/posts/media", {
        method: "POST",
        body: JSON.stringify({
          user_id: userId,
          kind: inferredKind,
          storage_url: mediaUrl,
          mime_type: inferredKind === "video" ? "video/mp4" : "image/jpeg",
        }),
      });
      mediaId = media.id;
    }

    const post = await api("/api/posts", {
      method: "POST",
      body: JSON.stringify({
        user_id: userId,
        title: fd.get("title") ?? "",
        caption: fd.get("caption") ?? "",
        link_url: fd.get("link_url") || null,
        media_id: mediaId,
      }),
    });
    out.textContent = JSON.stringify(post, null, 2);
  } catch (err) {
    out.textContent = `❌ 建立失敗：${err.message}`;
    _showToast(`貼文建立失敗：${err.message}`);
  }
});

const previewForm = document.getElementById("previewForm");
previewForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(previewForm);
  const postId = Number(fd.get("post_id"));
  const accountIds = (fd.get("account_ids") ?? "")
    .split(",")
    .map((s) => Number(s.trim()))
    .filter(Boolean);
  const result = await api(`/api/posts/${postId}/preview-compliance`, {
    method: "POST",
    body: JSON.stringify({ account_ids: accountIds }),
  });
  document.getElementById("previewOutput").textContent = JSON.stringify(result, null, 2);
});

// --- Schedule ---------------------------------------------------------
// --- Schedule mode toggle (once / cron) --------------------------------
function onScheduleModeChange(val) {
  document.getElementById("scheduleOnceRow").style.display = val === "once" ? "" : "none";
  document.getElementById("scheduleCronRow").style.display = val === "cron" ? "flex" : "none";
  if (val === "once") {
    const ci = document.getElementById("cronInput");
    if (ci) ci.value = "";
  } else {
    const sf = document.querySelector('#scheduleForm [name="scheduled_for"]');
    if (sf) sf.value = "";
  }
}

function onCronPreset(val) {
  if (val) document.getElementById("cronInput").value = val;
}

// init: hide cron row on load (scheduleMode defaults to "once")
document.addEventListener("DOMContentLoaded", () => {
  const cronRow = document.getElementById("scheduleCronRow");
  if (cronRow) cronRow.style.display = "none";
});

const scheduleForm = document.getElementById("scheduleForm");
scheduleForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(scheduleForm);
  let overrides = {};
  try {
    overrides = JSON.parse(fd.get("overrides") || "{}");
  } catch (err) {
    alert(`overrides must be valid JSON: ${err.message}`);
    return;
  }
  const body = {
    post_id: Number(fd.get("post_id")),
    items: [
      {
        account_id: Number(fd.get("account_id")),
        scheduled_for: fd.get("scheduled_for") || null,
        cron: fd.get("cron") || null,
        timezone: fd.get("timezone") || "UTC",
        overrides,
      },
    ],
  };
  const result = await api("/api/schedules", {
    method: "POST",
    body: JSON.stringify(body),
  });
  document.getElementById("scheduleOutput").textContent = JSON.stringify(result, null, 2);
  loadStatus();
});

// --- Status -----------------------------------------------------------
document.getElementById("refreshStatus").addEventListener("click", loadStatus);
async function loadStatus() {
  const userId = Number(userIdInput.value);
  const rows = await api(`/api/schedules?user_id=${userId}`);
  const tbody = document.querySelector("#statusTable tbody");
  tbody.innerHTML = "";
  // Phase 1: 13k+ schedules would blow up the DOM. Cap render at 300, failures
  // first so the rows that need action are always on screen.
  const STATUS_RENDER_CAP = 300;
  const prio = (s) => (s === "failed" ? 0 : ["pending", "queued"].includes(s) ? 1 : 2);
  const sorted = [...rows].sort((a, b) => prio(a.status) - prio(b.status));
  const shown = sorted.slice(0, STATUS_RENDER_CAP);
  for (const row of shown) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${row.id}</td>
      <td>${escapeHtml(row.platform)}</td>
      <td>${escapeHtml(row.handle ?? "")}</td>
      <td><span class="status-pill ${escapeHtml(row.status)}">${escapeHtml(row.status)}</span></td>
      <td>${escapeHtml(row.scheduled_for ?? "")}</td>
      <td>${escapeHtml(row.cron ?? "")}</td>
      <td>${row.attempt_count}</td>
      <td>${escapeHtml(row.external_post_id ?? "")}</td>
      <td>${escapeHtml(row.last_error ?? "")}</td>
      <td></td>
    `;
    const actions = tr.lastElementChild;
    if (row.status === "failed") {
      const btn = document.createElement("button");
      btn.textContent = "Retry";
      btn.addEventListener("click", async () => {
        await api(`/api/schedules/${row.id}/retry`, { method: "POST" });
        loadStatus();
      });
      actions.appendChild(btn);
    }
    if (["pending", "queued"].includes(row.status)) {
      const btn = document.createElement("button");
      btn.textContent = "Cancel";
      btn.addEventListener("click", async () => {
        await api(`/api/schedules/${row.id}/cancel`, { method: "POST" });
        loadStatus();
      });
      actions.appendChild(btn);
    }
    tbody.appendChild(tr);
  }
  if (rows.length > STATUS_RENDER_CAP) {
    const note = document.createElement("tr");
    note.innerHTML = `<td colspan="10" class="hint">顯示前 ${STATUS_RENDER_CAP} 筆（失敗優先），共 ${rows.length} 筆。請用上游篩選縮小範圍。</td>`;
    tbody.appendChild(note);
  }
}

// --- Accounts ---------------------------------------------------------
document.querySelectorAll(".connect-row button").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const popup = window.open(
      "about:blank",
      "oauth_popup",
      "width=620,height=720,scrollbars=yes,resizable=yes"
    );
    let result;
    try {
      result = await api(`/auth/${btn.dataset.provider}/start-url`);
    } catch (err) {
      if (popup && !popup.closed) popup.close();
      throw err;
    }
    const redirectUrl = result.redirect_url || result.authorization_url;
    if (!redirectUrl) {
      if (popup && !popup.closed) popup.close();
      throw new Error("OAuth start-url did not return redirect_url");
    }
    // Fix: remove "noopener" so the callback popup can reach window.opener
    // and send postMessage back. "noopener" sets opener=null in the popup,
    // which silently breaks the entire OAuth completion flow.
    if (popup && !popup.closed) {
      popup.location.href = redirectUrl;
    } else {
      window.location.href = redirectUrl;
    }
  });
});

// Fix: listen for OAuth completion message from the callback popup.
// The backend callback HTML does window.opener.postMessage({type:"distributor.oauth.complete"})
// but the original code never listened for this message, so accounts never auto-refreshed.
window.addEventListener("message", (event) => {
  if (!event.data || event.data.type !== "distributor.oauth.complete") return;
  const result = event.data.result;
  if (result && result.ok) {
    // Refresh accounts table so newly connected pages appear immediately
    loadAccounts();
    // Brief visual feedback
    const banner = document.createElement("div");
    banner.textContent = `✓ 連接成功：${(result.connected || []).map(a => a.handle).join("、")}`;
    banner.style.cssText = "position:fixed;top:16px;right:16px;background:#1a3a1a;color:#6abf69;padding:12px 20px;border-radius:8px;z-index:9999;font-size:14px;border:1px solid #2d5a2d;";
    document.body.appendChild(banner);
    setTimeout(() => banner.remove(), 4000);
  } else if (result && !result.ok) {
    console.error("[OAuth]", result.message);
  }
});

// --- TikTok Cookie binding -------------------------------------------
document.getElementById("tiktokCookieBind").addEventListener("click", async () => {
  const userId = Number(userIdInput.value);
  const sessionid = document.getElementById("tiktokSessionId").value.trim();
  const msg = document.getElementById("tiktokCookieMsg");
  if (!userId) { msg.style.color = "#e57373"; msg.textContent = "請先填入 User ID"; return; }
  if (!sessionid) { msg.style.color = "#e57373"; msg.textContent = "請貼上 sessionid"; return; }
  msg.style.color = "#9aa0a6"; msg.textContent = "驗證中…";
  try {
    const res = await api("/auth/tiktok/cookie", {
      method: "POST",
      body: JSON.stringify({ user_id: userId, sessionid }),
    });
    if (res.ok) {
      const handles = (res.connected || []).map(a => a.handle).join("、");
      msg.style.color = "#6abf69";
      msg.textContent = `✓ 已綁定：@${handles}`;
      document.getElementById("tiktokSessionId").value = "";
      loadAccounts();
    } else {
      msg.style.color = "#e57373";
      msg.textContent = `✗ ${res.error || "綁定失敗"}`;
    }
  } catch (err) {
    msg.style.color = "#e57373";
    msg.textContent = `✗ ${err.message}`;
  }
});

async function loadAccounts() {
  const userId = Number(userIdInput.value);
  const rows = await api(`/api/accounts?user_id=${userId}`);
  const tbody = document.querySelector("#accountsTable tbody");
  tbody.innerHTML = "";
  for (const row of rows) {
    const tr = document.createElement("tr");
    const proxySet = !!(row.proxy_configured);
    tr.innerHTML = `
      <td>${row.id}</td>
      <td>${escapeHtml(row.platform)}</td>
      <td>${escapeHtml(row.handle)}</td>
      <td>${escapeHtml(row.token_expires_at ?? "—")}</td>
      <td><span class="proxy-badge" data-id="${row.id}" style="font-size:11px;color:${proxySet ? "#6abf69" : "#555"};">${proxySet ? "🔀 已設定" : "—"}</span></td>
      <td></td>
    `;
    const actions = tr.lastElementChild;
    // Proxy button
    const proxyBtn = document.createElement("button");
    proxyBtn.textContent = proxySet ? "改 Proxy" : "設 Proxy";
    proxyBtn.style.cssText = "margin-right:4px;font-size:11px;padding:2px 8px;";
    proxyBtn.addEventListener("click", async () => {
      const url = prompt(
        `帳號 #${row.id} (${row.handle}) 的 Proxy URL\n格式: socks5://user:pass@host:port 或 http://host:port\n留空 = 清除`,
        "" // current proxy not exposed for security
      );
      if (url === null) return; // cancelled
      await api(`/api/accounts/${row.id}/proxy`, {
        method: "PATCH",
        body: JSON.stringify({ proxy_url: url || null }),
      });
      loadAccounts();
    });
    actions.appendChild(proxyBtn);
    // Revoke button
    const revoke = document.createElement("button");
    revoke.textContent = "Revoke";
    revoke.style.cssText = "font-size:11px;padding:2px 8px;";
    revoke.addEventListener("click", async () => {
      await api(`/auth/${row.id}/revoke`, { method: "POST" });
      loadAccounts();
    });
    actions.appendChild(revoke);
    tbody.appendChild(tr);
  }
}

// --- Audit ------------------------------------------------------------
document.getElementById("refreshAudit").addEventListener("click", loadAudit);
async function loadAudit() {
  const userId = Number(userIdInput.value);
  const rows = await api(`/api/audit?user_id=${userId}`);
  const tbody = document.querySelector("#auditTable tbody");
  tbody.innerHTML = "";
  for (const row of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(row.created_at)}</td>
      <td>${escapeHtml(row.actor_user_id ?? "")}</td>
      <td>${escapeHtml(row.action)}</td>
      <td>${escapeHtml(row.resource_type)}#${escapeHtml(row.resource_id ?? "")}</td>
      <td><pre style="max-height:120px">${escapeHtml(JSON.stringify(row.detail, null, 2))}</pre></td>
    `;
    tbody.appendChild(tr);
  }
}

// --- Groups -----------------------------------------------------------
const groupForm = document.getElementById("groupForm");
groupForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(groupForm);
  let style = {};
  try {
    style = JSON.parse(fd.get("style_profile") || "{}");
  } catch (err) {
    alert(`style_profile 必須是合法 JSON：${err.message}`);
    return;
  }
  const result = await api("/api/groups", {
    method: "POST",
    body: JSON.stringify({
      user_id: Number(userIdInput.value),
      name: fd.get("name"),
      description: fd.get("description") || "",
      default_timezone: fd.get("default_timezone") || "UTC",
      style_profile: style,
    }),
  });
  document.getElementById("groupCreateOutput").textContent = JSON.stringify(result, null, 2);
  loadGroups();
});

document.getElementById("refreshGroups").addEventListener("click", loadGroups);

async function loadGroups() {
  const userId = Number(userIdInput.value);
  const groups = await api(`/api/groups?user_id=${userId}`);
  const accounts = await api(`/api/accounts?user_id=${userId}`);
  const list = document.getElementById("groupsList");
  list.innerHTML = "";
  for (const group of groups) {
    const card = document.createElement("div");
    card.className = "group-card";
    const memberRows = group.members
      .map(
        (m) =>
          `<li>${escapeHtml(m.platform)} · ${escapeHtml(m.handle)} <button data-account="${m.account_id}" data-group="${group.id}" class="rm-member">移除</button></li>`
      )
      .join("");

    const availableOptions = accounts
      .filter((a) => !group.members.find((m) => m.account_id === a.id))
      .map((a) => `<option value="${a.id}">${escapeHtml(a.platform)} · ${escapeHtml(a.handle)}</option>`)
      .join("");

    card.innerHTML = `
      <header>
        <strong>${escapeHtml(group.name)}</strong>
        <span class="hint">${group.is_active ? "active" : "inactive"} · ${group.members.length} 個帳號</span>
        <button class="del-group" data-group="${group.id}">刪除</button>
      </header>
      <p class="hint">${escapeHtml(group.description || "")}</p>
      <details>
        <summary>Style profile</summary>
        <pre>${escapeHtml(JSON.stringify(group.style_profile, null, 2))}</pre>
        <button data-group="${group.id}" class="edit-style">修改 style</button>
      </details>
      <ul>${memberRows || "<li class='hint'>尚未加入任何帳號</li>"}</ul>
      <div class="add-member-row">
        <select data-group="${group.id}">${availableOptions}</select>
        <button data-group="${group.id}" class="add-member">加入帳號</button>
      </div>
    `;
    list.appendChild(card);
  }

  list.querySelectorAll(".rm-member").forEach((btn) =>
    btn.addEventListener("click", async () => {
      await api(`/api/groups/${btn.dataset.group}/members/${btn.dataset.account}`, {
        method: "DELETE",
      });
      loadGroups();
    })
  );
  list.querySelectorAll(".add-member").forEach((btn) =>
    btn.addEventListener("click", async () => {
      const select = btn.previousElementSibling;
      if (!select.value) return;
      await api(`/api/groups/${btn.dataset.group}/members`, {
        method: "POST",
        body: JSON.stringify({ account_id: Number(select.value) }),
      });
      loadGroups();
    })
  );
  list.querySelectorAll(".del-group").forEach((btn) =>
    btn.addEventListener("click", async () => {
      if (!confirm("刪除這個群組？這不會解除已連接的帳號。")) return;
      await api(`/api/groups/${btn.dataset.group}`, { method: "DELETE" });
      loadGroups();
    })
  );
  list.querySelectorAll(".edit-style").forEach((btn) =>
    btn.addEventListener("click", async () => {
      const groupId = btn.dataset.group;
      const current = await api(`/api/groups/${groupId}`);
      const next = prompt(
        "貼入新的 style profile JSON：",
        JSON.stringify(current.style_profile, null, 2)
      );
      if (!next) return;
      try {
        const parsed = JSON.parse(next);
        await api(`/api/groups/${groupId}`, {
          method: "PUT",
          body: JSON.stringify({ style_profile: parsed }),
        });
        loadGroups();
      } catch (err) {
        alert(`JSON 解析失敗：${err.message}`);
      }
    })
  );
}

// --- Distribute -------------------------------------------------------
async function loadDistributeGroups() {
  const userId = Number(userIdInput.value);
  const groups = await api(`/api/groups?user_id=${userId}`);
  const select = document.getElementById("distributeGroupSelect");
  select.innerHTML = groups
    .map(
      (g) =>
        `<option value="${g.id}">${escapeHtml(g.name)} (${g.members.length} accounts)</option>`
    )
    .join("");
  populateAbGroupSelect(groups);
}

// Populate A/B group select from the same groups list used by distribute.
function populateAbGroupSelect(groups) {
  const sel = document.getElementById("distributeAbGroupSelect");
  if (!sel) return;
  sel.innerHTML = "";
  groups.forEach((g) => {
    const opt = document.createElement("option");
    opt.value = g.id;
    opt.textContent = `${g.name} (${g.accounts?.length ?? 0} accounts)`;
    sel.appendChild(opt);
  });
}

const distributeAbForm = document.getElementById("distributeAbForm");
distributeAbForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(distributeAbForm);
  const groupId = Number(document.getElementById("distributeAbGroupSelect").value);
  if (!groupId) { alert("請選擇一個群組"); return; }
  const referralCode = (fd.get("referral_code") || "").trim().toUpperCase();
  const body = {
    group_id: groupId,
    engine_a: fd.get("engine_a"),
    engine_b: fd.get("engine_b"),
    jitter_minutes: Number(fd.get("jitter_minutes") || 0),
    referral_code: referralCode || null,
    dry_run: fd.get("dry_run") === "on",
  };
  const postId = Number(fd.get("post_id"));
  const result = await api(`/api/posts/${postId}/distribute_ab`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  document.getElementById("distributeAbOutput").textContent = JSON.stringify(result, null, 2);
});

const distributeForm = document.getElementById("distributeForm");
distributeForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(distributeForm);
  const select = document.getElementById("distributeGroupSelect");
  const groupIds = Array.from(select.selectedOptions).map((o) => Number(o.value));
  if (!groupIds.length) {
    alert("請選擇至少一個群組");
    return;
  }
  const referralCode = (fd.get("referral_code") || "").trim().toUpperCase();
  const body = {
    group_ids: groupIds,
    scheduled_for: fd.get("scheduled_for") || null,
    timezone: fd.get("timezone") || "UTC",
    jitter_minutes: Number(fd.get("jitter_minutes") || 0),
    referral_code: referralCode || null,
    generate_variants: fd.get("generate_variants") === "on",
    use_best_time: fd.get("use_best_time") === "on",
    dry_run: fd.get("dry_run") === "on",
  };
  const result = await api(`/api/posts/${fd.get("post_id")}/distribute`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  document.getElementById("distributeOutput").textContent = JSON.stringify(result, null, 2);
});

function escapeHtml(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

// --- WYSIWYG preview --------------------------------------------------
const PLATFORM_PREVIEW_RULES = {
  facebook:  { label: "Facebook",  caption_max: 63206, title_max: null, aspect: "16:9" },
  instagram: { label: "Instagram", caption_max: 2200,  title_max: null, aspect: "9:16" },
  tiktok:    { label: "TikTok",    caption_max: 2200,  title_max: null, aspect: "9:16" },
  youtube:   { label: "YouTube",   caption_max: 5000,  title_max: 100,  aspect: "16:9" },
};

function renderPreview() {
  const fd = new FormData(postForm);
  const title = fd.get("title") ?? "";
  const caption = fd.get("caption") ?? "";
  const grid = document.getElementById("previewGrid");
  grid.innerHTML = "";
  for (const [platform, rule] of Object.entries(PLATFORM_PREVIEW_RULES)) {
    const captionTooLong = caption.length > rule.caption_max;
    const titleTooLong = rule.title_max !== null && title.length > rule.title_max;
    const captionShown = captionTooLong ? caption.slice(0, rule.caption_max) + "…" : caption;
    const titleShown = titleTooLong ? title.slice(0, rule.title_max) + "…" : title;
    const card = document.createElement("article");
    card.className = `preview-card preview-${platform}`;
    card.innerHTML = `
      <header>
        <strong>${rule.label}</strong>
        <span class="hint">${rule.aspect}</span>
      </header>
      <div class="preview-frame preview-${rule.aspect.replace(":", "x")}">
        <div class="preview-media-placeholder">媒體預覽位</div>
      </div>
      ${rule.title_max !== null
        ? `<div class="preview-title ${titleTooLong ? "over" : ""}">${escapeHtml(titleShown) || "<em>未填標題</em>"}</div>`
        : ""}
      <div class="preview-caption ${captionTooLong ? "over" : ""}">${escapeHtml(captionShown) || "<em>未填內文</em>"}</div>
      <div class="preview-meta">
        <span>內文 ${caption.length} / ${rule.caption_max}</span>
        ${rule.title_max !== null ? `<span>標題 ${title.length} / ${rule.title_max}</span>` : ""}
      </div>
    `;
    grid.appendChild(card);
  }
}
postForm.addEventListener("input", renderPreview);
renderPreview();

document.getElementById("hashtagSuggestBtn").addEventListener("click", async () => {
  const captionEl = postForm.querySelector('textarea[name="caption"]');
  const out = document.getElementById("hashtagSuggestOut");
  const body = {
    caption: captionEl.value,
    platform: document.getElementById("hashtagPlatform").value,
    count: 5,
  };
  const gid = document.getElementById("hashtagGroupId").value;
  if (gid) body.group_id = Number(gid);
  out.textContent = "Suggesting…";
  try {
    const res = await api("/api/hashtags/suggest", {
      method: "POST", body: JSON.stringify(body),
    });
    if (!res.hashtags.length) {
      out.textContent = "（無建議——可能是群組 hashtag_pool 為空）";
      return;
    }
    const tags = res.hashtags.join(" ");
    out.textContent = `[${res.used_engine}] ${tags}（已附加到內文）`;
    captionEl.value = (captionEl.value.trimEnd() + "\n\n" + tags).trim();
    renderPreview();
  } catch (err) {
    out.textContent = `失敗：${err.message}`;
  }
});

// --- Insights ---------------------------------------------------------
async function loadInsights() {
  const postId = document.getElementById("insightsPostId").value;
  const groupId = document.getElementById("insightsGroupId").value;
  const tbody = document.querySelector("#insightsTable tbody");
  let rows;
  if (postId || groupId) {
    // Filtered path uses the healthy post_id/group_id branch.
    const params = new URLSearchParams();
    if (postId) params.set("post_id", postId);
    if (groupId) params.set("group_id", groupId);
    rows = await api(`/api/insights?${params.toString()}`);
  } else {
    // Phase 1: the unfiltered /api/insights branch hangs ~30s on the backend.
    // Fan out instead — pull recent posts, query each by post_id (healthy
    // branch), merge. Per-post failures are swallowed so one bad post can't
    // sink the whole panel. (Assumes GET /api/posts returns a list or {items}.)
    tbody.innerHTML = `<tr><td colspan="10" class="hint">載入最近貼文成效中…</td></tr>`;
    const userId = Number(userIdInput.value);
    const posts = await api(`/api/posts?user_id=${userId}`);
    const list = Array.isArray(posts) ? posts : posts.items || [];
    const recent = list.slice(0, 8);
    const chunks = await Promise.all(
      recent.map((p) => api(`/api/insights?post_id=${p.id}`).catch(() => []))
    );
    rows = chunks.flat();
  }
  tbody.innerHTML = "";
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="10" class="hint">無資料。可用上方 Post ID / Group ID 篩選查特定貼文。</td></tr>`;
    return;
  }
  for (const r of rows) {
    const m = r.metric;
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${r.platform}</td>
      <td>${escapeHtml(r.handle)}</td>
      <td>${m.reach ?? ""}</td>
      <td>${m.impressions ?? ""}</td>
      <td>${m.likes ?? ""}</td>
      <td>${m.comments ?? ""}</td>
      <td>${m.shares ?? ""}</td>
      <td>${m.plays ?? ""}</td>
      <td>${m.avg_view_pct != null ? m.avg_view_pct.toFixed(1) + "%" : ""}</td>
      <td>${escapeHtml(r.external_post_id ?? "")}</td>
    `;
    tbody.appendChild(tr);
  }
}
document.getElementById("loadInsights").addEventListener("click", loadInsights);

document.getElementById("loadBestTimes").addEventListener("click", async () => {
  const accountId = document.getElementById("bestAccountId").value;
  const groupId = document.getElementById("bestGroupId").value;
  const params = new URLSearchParams();
  if (accountId) params.set("account_id", accountId);
  else if (groupId) params.set("group_id", groupId);
  else { alert("請填 Account ID 或 Group ID"); return; }
  const rows = await api(`/api/insights/best-times?${params.toString()}`);
  const tbody = document.querySelector("#bestTimesTable tbody");
  tbody.innerHTML = "";
  for (const r of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${r.day}</td><td>${String(r.hour).padStart(2,"0")}:00</td>
      <td>${r.sample_count}</td><td>${(r.avg_engagement_rate * 100).toFixed(2)}%</td>`;
    tbody.appendChild(tr);
  }
  if (rows.length === 0) tbody.innerHTML = `<tr><td colspan="4" class="hint">資料不足，繼續累積發文成效後再回來查。</td></tr>`;
});

// --- C5: 週報 ---------------------------------------------------------
document.getElementById("previewDigest")?.addEventListener("click", async () => {
  const userId = Number(userIdInput.value);
  const out = document.getElementById("digestOut");
  out.textContent = "Loading…";
  try {
    const data = await api(`/api/insights/digest/preview?user_id=${userId}`);
    out.textContent = JSON.stringify(data, null, 2);
  } catch (err) { out.textContent = err.message; }
});

document.getElementById("sendDigest")?.addEventListener("click", async () => {
  const userId = Number(userIdInput.value);
  const out = document.getElementById("digestOut");
  if (!confirm("確定寄一份週報到 user.email？")) return;
  out.textContent = "Sending…";
  try {
    const data = await api(`/api/insights/digest/send`, {
      method: "POST", body: JSON.stringify({ user_id: userId }),
    });
    out.textContent = JSON.stringify(data, null, 2);
  } catch (err) { out.textContent = err.message; }
});

// --- C2: A/B 結果 -----------------------------------------------------
document.getElementById("loadAb")?.addEventListener("click", async () => {
  const gid = Number(document.getElementById("abGroupId").value);
  const slot = document.getElementById("abResults");
  if (!gid) { slot.innerHTML = `<p class="hint">輸入 group id</p>`; return; }
  slot.innerHTML = "Loading…";
  try {
    const data = await api(`/api/experiments/results?group_id=${gid}`);
    const rows = data.by_engine.map((e) => `
      <tr>
        <td>${e.engine}${e.engine === data.winner ? ' 🏆' : ''}</td>
        <td>${e.samples}</td>
        <td>${e.total_reach.toLocaleString()}</td>
        <td>${e.total_engagement.toLocaleString()}</td>
        <td>${(e.rate * 100).toFixed(2)}%</td>
      </tr>`).join("");
    slot.innerHTML = `
      <p><strong>${data.group_name}</strong> · since ${data.since.slice(0,10)}</p>
      <p class="hint">${data.note}</p>
      <table>
        <thead><tr><th>Engine</th><th>樣本</th><th>觸及</th><th>互動</th><th>互動率</th></tr></thead>
        <tbody>${rows || `<tr><td colspan="5" class="hint">no data</td></tr>`}</tbody>
      </table>`;
  } catch (err) {
    slot.innerHTML = `<p class="error">${err.message}</p>`;
  }
});

document.getElementById("runBacktestNow")?.addEventListener("click", async () => {
  const slot = document.getElementById("abResults");
  slot.innerHTML = "回測中…";
  try {
    const data = await api(`/api/experiments/backtest`, { method: "POST" });
    const rows = data.results.map((r) => `
      <tr>
        <td>${r.group_name}</td>
        <td>${r.winner ?? '—'}${r.updated ? ' (寫入)' : ''}</td>
        <td>${r.note}</td>
      </tr>`).join("");
    slot.innerHTML = `
      <p>${data.results.length} 個 group 回測完成</p>
      <table>
        <thead><tr><th>Group</th><th>Winner</th><th>Note</th></tr></thead>
        <tbody>${rows || `<tr><td colspan="3" class="hint">no groups</td></tr>`}</tbody>
      </table>`;
  } catch (err) {
    slot.innerHTML = `<p class="error">${err.message}</p>`;
  }
});

// --- SSE real-time status updates -------------------------------------
let _eventSource = null;
function connectEvents() {
  if (_eventSource) _eventSource.close();
  const userId = Number(userIdInput.value);
  if (!userId) return;
  // EventSource can't set headers; pass the operator token as ?op_token= so
  // the api-key wall / login guard recognize it (server reads op_token query).
  const _tok = sdToken();
  const _q = `user_id=${userId}` + (_tok ? `&op_token=${encodeURIComponent(_tok)}` : "");
  _eventSource = new EventSource(`${API_BASE}/api/events/stream?${_q}`);
  _eventSource.onmessage = (ev) => {
    try {
      const data = JSON.parse(ev.data);
      if (data.type === "target.status_changed") {
        // If user is on the status board, refresh in place.
        const isOnStatus = document.getElementById("tab-status").classList.contains("active");
        if (isOnStatus) loadStatus();
      }
    } catch {}
  };
  _eventSource.onerror = () => {
    // EventSource auto-reconnects; nothing to do.
  };
}
userIdInput.addEventListener("change", connectEvents);
connectEvents();

// --- Daily workflow ---------------------------------------------------
const dailyState = {
  mediaId: null,
  selectedGroups: new Set(),
  groups: [],
  lastTargets: [],
};

async function loadDailyDeps() {
  const userId = Number(userIdInput.value);
  // A8: load all three deps so we can show the right empty-state guide.
  const [groups, accounts] = await Promise.all([
    api(`/api/groups?user_id=${userId}`),
    api(`/api/accounts?user_id=${userId}`),
  ]);
  dailyState.groups = groups;
  dailyState.accounts = accounts;
  renderDailyOnboarding();
  renderDailyChips();
  renderDailyPreview();
}

function renderDailyOnboarding() {
  // Three contextual onboarding states. The wizard banner sits above step 1
  // and switches the user to the right tab with one click.
  const slot = document.getElementById("dailyOnboarding");
  if (!slot) return;
  const accounts = dailyState.accounts || [];
  const groups = dailyState.groups || [];
  if (accounts.length === 0) {
    slot.innerHTML = `
      <div class="onboarding accent">
        <strong>👋 第一步：連一個社群帳號</strong>
        <p>沒連帳號就發不出去。建議先連 Instagram Business + Facebook Page，這條路徑最少坑。</p>
        <button type="button" data-go="accounts">→ 到 Accounts tab</button>
      </div>`;
  } else if (groups.length === 0) {
    slot.innerHTML = `
      <div class="onboarding accent">
        <strong>👌 ${accounts.length} 個帳號連好了。下一步：建第一個人設群組</strong>
        <p>把幾個帳號綁成一個「人設」，發文時選人設就會一鍵分發到該人設下所有平台。</p>
        <button type="button" data-go="groups">→ 到 人設群組 tab</button>
      </div>`;
  } else {
    slot.innerHTML = "";  // clear any previous banner
  }
  slot.querySelectorAll("button[data-go]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = document.querySelector(`.topbar nav button[data-tab="${btn.dataset.go}"]`);
      target?.click();
    });
  });
}

function renderDailyChips() {
  const wrap = document.getElementById("dailyGroupChips");
  if (!dailyState.groups.length) {
    wrap.innerHTML = `<p class="hint">尚無群組——先到「人設群組」分頁建立。</p>`;
    return;
  }
  wrap.innerHTML = "";
  for (const g of dailyState.groups) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "chip";
    chip.dataset.groupId = g.id;
    chip.innerHTML = `<strong>${escapeHtml(g.name)}</strong><small>${g.members.length} 帳號</small>`;
    if (dailyState.selectedGroups.has(g.id)) chip.classList.add("on");
    chip.addEventListener("click", () => {
      if (dailyState.selectedGroups.has(g.id)) {
        dailyState.selectedGroups.delete(g.id);
        chip.classList.remove("on");
      } else {
        dailyState.selectedGroups.add(g.id);
        chip.classList.add("on");
      }
      refreshBestHint();
    });
    wrap.appendChild(chip);
  }
}

async function refreshBestHint() {
  const hint = document.getElementById("dailyBestHint");
  hint.textContent = "";
  if (dailyState.selectedGroups.size !== 1) return;
  const groupId = Array.from(dailyState.selectedGroups)[0];
  try {
    const slots = await api(`/api/insights/best-times?group_id=${groupId}`);
    if (!slots.length) {
      hint.textContent = "（資料不足，先用「立刻發」或自定時間）";
      return;
    }
    const top = slots[0];
    hint.textContent = `→ 建議：${top.day} ${String(top.hour).padStart(2, "0")}:00（互動率 ${(top.avg_engagement_rate * 100).toFixed(1)}%）`;
  } catch {}
}

// Drag-drop upload
const dailyDz = document.getElementById("dailyDropzone");
const dailyFi = document.getElementById("dailyFileInput");
const dailyHint = document.getElementById("dailyMediaHint");
document.getElementById("dailyPickFile").addEventListener("click", () => dailyFi.click());
dailyFi.addEventListener("change", () => dailyFi.files[0] && handleDailyFile(dailyFi.files[0]));
["dragenter", "dragover"].forEach((ev) => dailyDz.addEventListener(ev, (e) => { e.preventDefault(); dailyDz.classList.add("dragover"); }));
["dragleave", "drop"].forEach((ev) => dailyDz.addEventListener(ev, (e) => { e.preventDefault(); dailyDz.classList.remove("dragover"); }));
dailyDz.addEventListener("drop", (e) => e.dataTransfer.files[0] && handleDailyFile(e.dataTransfer.files[0]));

async function handleDailyFile(file) {
  const userId = Number(userIdInput.value);
  const kind = file.type.startsWith("video/") ? "video" : "image";
  dailyHint.textContent = `Hashing ${file.name}…`;
  try {
    const sha = await sha256Hex(file);
    const dup = await api(`/api/uploads/check?sha256=${sha}&user_id=${userId}`);
    if (dup.found) {
      dailyState.mediaId = dup.media_id;
      dailyHint.textContent = `已存在 ✓ media_id=${dup.media_id}（重複，省 ${(file.size / 1024 / 1024).toFixed(1)} MB 上傳）`;
      return;
    }
    dailyHint.textContent = `Uploading ${file.name}…`;
    const presign = await api("/api/uploads/presign", {
      method: "POST",
      body: JSON.stringify({ user_id: userId, kind, content_type: file.type }),
    });
    const put = await fetch(presign.put_url, { method: "PUT", headers: presign.headers, body: file });
    if (!put.ok) throw new Error(`upload failed ${put.status}`);
    const media = await api("/api/uploads/complete", {
      method: "POST",
      body: JSON.stringify({
        user_id: userId, kind, content_type: file.type,
        bucket: presign.bucket, key: presign.key, public_get_url: presign.public_get_url,
        sha256: sha,
      }),
    });
    dailyState.mediaId = media.id;
    dailyHint.textContent = `✓ media_id=${media.id} (transcode: ${media.transcode_status})`;
  } catch (err) {
    dailyHint.textContent = `失敗：${err.message}`;
  }
}

// Live preview
function renderDailyPreview() {
  const title = document.getElementById("dailyTitle").value;
  const caption = document.getElementById("dailyCaption").value;
  const grid = document.getElementById("dailyPreviewGrid");
  grid.innerHTML = "";
  for (const [platform, rule] of Object.entries(PLATFORM_PREVIEW_RULES)) {
    const captionTooLong = caption.length > rule.caption_max;
    const titleTooLong = rule.title_max !== null && title.length > rule.title_max;
    const card = document.createElement("article");
    card.className = `preview-card preview-${platform}`;
    card.innerHTML = `
      <header><strong>${rule.label}</strong><span class="hint">${rule.aspect}</span></header>
      ${rule.title_max !== null
        ? `<div class="preview-title ${titleTooLong ? "over" : ""}">${escapeHtml(title) || "<em>未填標題</em>"}</div>` : ""}
      <div class="preview-caption ${captionTooLong ? "over" : ""}">${escapeHtml(caption) || "<em>未填內文</em>"}</div>
      <div class="preview-meta"><span>${caption.length}/${rule.caption_max}</span>
        ${rule.title_max !== null ? `<span>標題 ${title.length}/${rule.title_max}</span>` : ""}</div>
    `;
    grid.appendChild(card);
  }
}
["dailyTitle", "dailyCaption"].forEach((id) =>
  document.getElementById(id).addEventListener("input", renderDailyPreview)
);

// When-to-send radio handling
document.querySelectorAll('input[name="dailyWhen"]').forEach((r) =>
  r.addEventListener("change", () => {
    document.getElementById("dailyAt").disabled = r.value !== "at" || !r.checked;
    if (r.value === "best" && r.checked) refreshBestHint();
  })
);

// Submit
document.getElementById("dailyGoBtn").addEventListener("click", async () => {
  const userId = Number(userIdInput.value);
  const out = document.getElementById("dailyOutput");
  if (!dailyState.selectedGroups.size) { out.textContent = "請先選擇至少一個群組"; return; }

  const title = document.getElementById("dailyTitle").value;
  const caption = document.getElementById("dailyCaption").value;
  if (!caption && !dailyState.mediaId) {
    out.textContent = "請至少給一段內文或一個媒體檔";
    return;
  }

  try {
    out.textContent = "建立 post…";
    const post = await api("/api/posts", {
      method: "POST",
      body: JSON.stringify({
        user_id: userId,
        title,
        caption,
        link_url: document.getElementById("dailyLinkUrl").value || null,
        media_id: dailyState.mediaId,
      }),
    });

    const when = document.querySelector('input[name="dailyWhen"]:checked').value;
    let scheduled_for = null;
    let use_best_time = false;
    if (when === "at") scheduled_for = document.getElementById("dailyAt").value || null;
    if (when === "best") use_best_time = true;  // backend handles fallback per-group

    const body = {
      group_ids: Array.from(dailyState.selectedGroups),
      scheduled_for,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
      jitter_minutes: Number(document.getElementById("dailyJitter").value || 0),
      generate_variants: document.getElementById("dailyVariants").checked,
      use_best_time,
      dry_run: document.getElementById("dailyDryRun").checked,
    };
    out.textContent = "Distribute…";
    const res = await api(`/api/posts/${post.id}/distribute`, {
      method: "POST",
      body: JSON.stringify(body),
    });
    out.innerHTML = `<strong>✓ ${res.dry_run ? "Dry-run 預覽" : `建立 ${res.created_target_ids.length} 個目標`}</strong>
      <pre>${escapeHtml(JSON.stringify(res.plan, null, 2))}</pre>`;
    dailyState.lastTargets = res.created_target_ids;
    loadDailyStatus();
  } catch (err) {
    out.textContent = `❌ 失敗：${err.message}`;
    _showToast(`一鍵發送失敗：${err.message}`);
  }
});

document.getElementById("dailyRefreshStatus").addEventListener("click", loadDailyStatus);

// --- Auto-schedule "today" ---------------------------------------------
async function runAutoSchedule(dryRun) {
  const userId = Number(userIdInput.value);
  const out = document.getElementById("autoOutput");
  const link = document.getElementById("autoLink").value.trim();
  const videosPerAccount = Number(document.getElementById("autoVideos").value);
  const postsPerAccount = Number(document.getElementById("autoPosts").value);
  const windowStart = Number(document.getElementById("autoStart").value);
  const windowEnd = Number(document.getElementById("autoEnd").value);
  // Use the browser's IANA timezone so window hours match what user sees.
  let tz = "Asia/Taipei";
  try { tz = Intl.DateTimeFormat().resolvedOptions().timeZone || tz; } catch {}
  out.textContent = dryRun ? "預覽中…" : "排程中…";
  try {
    const res = await api(`/api/auto-schedule/today?user_id=${userId}`, {
      method: "POST",
      body: JSON.stringify({
        videos_per_account: videosPerAccount,
        posts_per_account: postsPerAccount,
        link: link || null,
        window_start_hour: windowStart,
        window_end_hour: windowEnd,
        timezone: tz,
        platforms: ["facebook"],
        dry_run: dryRun,
      }),
    });
    const s = res.summary;
    let text = `${dryRun ? "🔍 預覽" : "✅ 已排程"}\n`;
    text += `帳號數：${s.accounts}\n`;
    text += `文案池：${s.captions_available} 個 caption\n`;
    text += `影片庫存：${s.videos_available} 個（ready）\n`;
    text += `圖片庫存：${s.images_available} 個\n`;
    text += `預計建立：${s.posts_created} 篇\n`;
    if (s.earliest_scheduled_at) {
      text += `最早：${new Date(s.earliest_scheduled_at).toLocaleString()}\n`;
      text += `最晚：${new Date(s.latest_scheduled_at).toLocaleString()}\n`;
    }
    if (s.warnings && s.warnings.length) {
      text += `\n⚠️ 警告：\n`;
      for (const w of s.warnings) text += `  - ${w}\n`;
    }
    if (res.by_account.length && res.by_account.length <= 10) {
      text += `\n各帳號明細：\n`;
      for (const a of res.by_account) {
        text += `  ${a.platform} @ ${a.handle}: ${a.scheduled_ats.length} 篇\n`;
      }
    } else if (res.by_account.length) {
      text += `\n各帳號明細：${res.by_account.length} 個帳號（折疊；前 5 個）\n`;
      for (const a of res.by_account.slice(0, 5)) {
        text += `  ${a.platform} @ ${a.handle}: ${a.scheduled_ats.length} 篇\n`;
      }
    }
    out.textContent = text;
  } catch (e) {
    out.textContent = `❌ 失敗：${e.message}`;
  }
}
document.getElementById("autoPreviewBtn").addEventListener(
  "click", () => runAutoSchedule(true)
);
document.getElementById("autoCommitBtn").addEventListener("click", () => {
  if (confirm("確定要建立排程嗎？所有帳號的貼文會在指定時段自動發出。")) {
    runAutoSchedule(false);
  }
});

async function loadDailyStatus() {
  if (!dailyState.lastTargets.length) return;
  const userId = Number(userIdInput.value);
  const all = await api(`/api/schedules?user_id=${userId}`);
  const set = new Set(dailyState.lastTargets);
  const tbody = document.querySelector("#dailyStatusTable tbody");
  tbody.innerHTML = "";
  for (const row of all.filter((r) => set.has(r.id))) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${row.platform}</td><td>${escapeHtml(row.handle ?? "")}</td>
      <td><span class="status-pill ${row.status}">${row.status}</span></td>
      <td>${row.scheduled_for ?? ""}</td>
      <td>${escapeHtml(row.external_post_id ?? "")}</td>
      <td>${escapeHtml(row.last_error ?? "")}</td>`;
    tbody.appendChild(tr);
  }
}

// Auto-refresh daily status when SSE fires.
const _origConnect = connectEvents;
connectEvents = function () {
  _origConnect();
  if (_eventSource) {
    _eventSource.addEventListener("message", () => {
      if (document.getElementById("tab-daily").classList.contains("active")) loadDailyStatus();
    });
  }
};
connectEvents();

// Render preview on initial load.
renderDailyPreview();

// --- Permissions ------------------------------------------------------
const grantForm = document.getElementById("grantForm");
grantForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(grantForm);
  const body = {
    user_id: Number(userIdInput.value),
    platform: fd.get("platform"),
    asset_kind: fd.get("asset_kind"),
    asset_external_id: fd.get("asset_external_id"),
    grantee_external_id: fd.get("grantee_external_id"),
    grantee_label: fd.get("grantee_label") || "",
    role: fd.get("role"),
  };
  if (fd.get("bc_id")) body.bc_id = fd.get("bc_id");
  try {
    const res = await api("/api/permissions/grants", {
      method: "POST", body: JSON.stringify(body),
    });
    document.getElementById("grantOutput").textContent = JSON.stringify(res, null, 2);
    loadGrants();
  } catch (err) {
    document.getElementById("grantOutput").textContent = `失敗：${err.message}`;
  }
});

document.getElementById("refreshGrants").addEventListener("click", loadGrants);
document.getElementById("runHealthSweep").addEventListener("click", async () => {
  const counts = await api("/api/permissions/health/run", { method: "POST" });
  alert(`掃描 ${counts.scanned} 個帳號 / token_invalid ${counts.token_invalid} / 漂移 ${counts.grant_disappeared + counts.grant_unexpected}`);
  loadDrift();
});
document.getElementById("permRunbookYT").addEventListener("click", async (e) => {
  e.preventDefault();
  const url = `${API_BASE}/api/permissions/runbooks/youtube_transfer.md`;
  window.open(url, "_blank", "noopener");
});

async function loadGrants() {
  const userId = Number(userIdInput.value);
  const rows = await api(`/api/permissions/grants?user_id=${userId}`);
  const tbody = document.querySelector("#grantsTable tbody");
  tbody.innerHTML = "";
  for (const g of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${g.platform}</td>
      <td>${escapeHtml(g.asset_label || g.asset_external_id)}</td>
      <td>${escapeHtml(g.grantee_label || g.grantee_external_id)}</td>
      <td>${g.role}</td>
      <td><span class="status-pill ${g.status}">${g.status}</span></td>
      <td>${g.granted_at ?? ""}</td>
      <td></td>
    `;
    if (g.status === "active") {
      const btn = document.createElement("button");
      btn.textContent = "撤回";
      btn.addEventListener("click", async () => {
        if (!confirm("確定撤回這個權限？")) return;
        await api(`/api/permissions/grants/${g.id}`, { method: "DELETE" });
        loadGrants();
      });
      tr.lastElementChild.appendChild(btn);
    }
    tbody.appendChild(tr);
  }
}

async function loadDrift() {
  const userId = Number(userIdInput.value);
  const rows = await api(`/api/permissions/drift?user_id=${userId}&unresolved=1`);
  const tbody = document.querySelector("#driftTable tbody");
  tbody.innerHTML = "";
  for (const a of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${a.detected_at ?? ""}</td>
      <td>${a.platform}</td>
      <td>${a.kind}</td>
      <td><pre style="max-height:120px">${escapeHtml(JSON.stringify(a.detail, null, 2))}</pre></td>
      <td><button class="resolve-drift" data-id="${a.id}">標記解決</button></td>
    `;
    tbody.appendChild(tr);
  }
  tbody.querySelectorAll(".resolve-drift").forEach((b) =>
    b.addEventListener("click", async () => {
      await api(`/api/permissions/drift/${b.dataset.id}/resolve`, { method: "POST" });
      loadDrift();
    })
  );
}

// --- Transfers --------------------------------------------------------
const transferForm = document.getElementById("transferForm");
transferForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(transferForm);
  const body = {
    user_id: Number(userIdInput.value),
    platform: fd.get("platform"),
    channel: fd.get("channel"),
    asset_kind: fd.get("asset_kind") || "page",
    asset_external_id: fd.get("asset_external_id"),
    asset_label: fd.get("asset_label") || "",
    source_label: fd.get("source_label") || "",
    target_label: fd.get("target_label") || "",
  };
  if (fd.get("from_business_id")) body.from_business_id = fd.get("from_business_id");
  if (fd.get("to_business_id")) body.to_business_id = fd.get("to_business_id");
  if (fd.get("expires_at")) body.expires_at = fd.get("expires_at");
  try {
    const res = await api("/api/transfers", {
      method: "POST", body: JSON.stringify(body),
    });
    document.getElementById("transferOutput").textContent = JSON.stringify(res, null, 2);
    loadTransfers();
  } catch (err) {
    document.getElementById("transferOutput").textContent = `失敗：${err.message}`;
  }
});

document.getElementById("refreshTransfers").addEventListener("click", loadTransfers);

async function loadTransfers() {
  const userId = Number(userIdInput.value);
  const rows = await api(`/api/transfers?user_id=${userId}`);
  const tbody = document.querySelector("#transfersTable tbody");
  tbody.innerHTML = "";
  for (const t of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${t.platform}</td>
      <td>${escapeHtml(t.asset_label || t.asset_external_id)}</td>
      <td>${escapeHtml(t.source_label || "?")} → ${escapeHtml(t.target_label || "?")}</td>
      <td>${t.channel}</td>
      <td><span class="status-pill ${t.status}">${t.status}</span></td>
      <td>${t.expires_at ?? ""}</td>
      <td></td>
    `;
    if (["requested", "awaiting_target"].includes(t.status)) {
      const done = document.createElement("button");
      done.textContent = "標記完成";
      done.addEventListener("click", async () => {
        await api(`/api/transfers/${t.id}/complete`, { method: "POST", body: JSON.stringify({}) });
        loadTransfers();
      });
      const reject = document.createElement("button");
      reject.textContent = "標記拒絕";
      reject.addEventListener("click", async () => {
        await api(`/api/transfers/${t.id}/reject`, { method: "POST", body: JSON.stringify({}) });
        loadTransfers();
      });
      tr.lastElementChild.append(done, reject);
    }
    tbody.appendChild(tr);
  }
}

// --- Rebroadcast ------------------------------------------------------
const rbState = { accounts: [], groups: [] };

async function loadRbDeps() {
  const userId = Number(userIdInput.value);
  if (!userId) return;
  rbState.accounts = await api(`/api/accounts?user_id=${userId}`);
  rbState.groups = await api(`/api/groups?user_id=${userId}`);
  // Source picker (single, FB-only since rebroadcast scan currently supports FB)
  const src = document.getElementById("rbSourceSelect");
  const filt = document.getElementById("rbFilterSource");
  src.innerHTML = '<option value="">— 選一個來源帳號 —</option>';
  filt.innerHTML = '<option value="">全部</option>';
  for (const a of rbState.accounts.filter((x) => !x.revoked_at)) {
    const label = `${a.platform} · ${a.handle || a.external_account_id} (#${a.id})`;
    src.insertAdjacentHTML("beforeend", `<option value="${a.id}">${escapeHtml(label)}</option>`);
    filt.insertAdjacentHTML("beforeend", `<option value="${a.id}">${escapeHtml(label)}</option>`);
  }
  // Group multi-select
  const grp = document.getElementById("rbGroupSelect");
  grp.innerHTML = "";
  for (const g of rbState.groups) {
    const memberCount = (g.members || []).length;
    grp.insertAdjacentHTML(
      "beforeend",
      `<option value="${g.id}">${escapeHtml(g.name)} (${memberCount} 帳號)</option>`,
    );
  }
}

document.getElementById("rbScanBtn").addEventListener("click", async () => {
  const sourceId = Number(document.getElementById("rbSourceSelect").value);
  const limit = Number(document.getElementById("rbLimit").value || 25);
  if (!sourceId) { alert("請選來源帳號"); return; }
  document.getElementById("rbScanOutput").textContent = "Scanning…";
  try {
    const res = await api("/api/rebroadcast/scan", {
      method: "POST",
      body: JSON.stringify({ source_account_id: sourceId, limit }),
    });
    document.getElementById("rbScanOutput").textContent = JSON.stringify(res, null, 2);
    loadRbCandidates();
  } catch (err) {
    document.getElementById("rbScanOutput").textContent = `失敗：${err.message}`;
  }
});

document.getElementById("rbScanAllBtn").addEventListener("click", async () => {
  const limit = Number(document.getElementById("rbLimit").value || 25);
  const fbAccounts = rbState.accounts.filter(
    (a) => a.platform === "facebook" && !a.revoked_at
  );
  if (!fbAccounts.length) { alert("沒有任何 FB 帳號"); return; }
  if (!confirm(`即將掃描 ${fbAccounts.length} 個 FB 粉專，每個取 ${limit} 篇歷史貼文。確定？`)) return;
  const out = document.getElementById("rbScanOutput");
  out.textContent = `Scanning ${fbAccounts.length} accounts...\n`;
  let ok = 0, fail = 0, totalCandidates = 0;
  for (const acc of fbAccounts) {
    try {
      const res = await api("/api/rebroadcast/scan", {
        method: "POST",
        body: JSON.stringify({ source_account_id: acc.id, limit }),
      });
      const n = res.inserted ?? 0;
      const examined = res.examined ?? 0;
      totalCandidates += n;
      ok++;
      out.textContent += `✓ ${acc.handle}: +${n} new (examined ${examined})\n`;
    } catch (err) {
      fail++;
      out.textContent += `✗ ${acc.handle}: ${err.message}\n`;
    }
  }
  out.textContent += `\nDone. ok=${ok} fail=${fail} total_candidates=${totalCandidates}`;
  loadRbCandidates();
});

document.getElementById("rbRefresh").addEventListener("click", loadRbCandidates);
document.getElementById("rbHideUsed").addEventListener("change", loadRbCandidates);
document.getElementById("rbFilterSource").addEventListener("change", loadRbCandidates);
document.getElementById("rbSelectAll").addEventListener("click", () => {
  document.querySelectorAll(".rb-pick:not(:disabled)").forEach((cb) => { cb.checked = true; });
});
document.getElementById("rbDeselectAll").addEventListener("click", () => {
  document.querySelectorAll(".rb-pick").forEach((cb) => { cb.checked = false; });
});

async function loadRbCandidates() {
  const userId = Number(userIdInput.value);
  if (!userId) return;
  const rows = await api(`/api/rebroadcast/candidates?user_id=${userId}`);
  const filterSource = Number(document.getElementById("rbFilterSource").value || 0);
  const hideUsed = document.getElementById("rbHideUsed").checked;
  const accountById = new Map(rbState.accounts.map((a) => [a.id, a]));
  const tbody = document.querySelector("#rbTable tbody");
  tbody.innerHTML = "";
  let shown = 0;
  for (const c of rows) {
    if (filterSource && c.source_account_id !== filterSource) continue;
    if (hideUsed && c.used) continue;
    shown++;
    const acc = accountById.get(c.source_account_id);
    const sourceLabel = acc ? `${acc.platform} · ${acc.handle}` : `#${c.source_account_id}`;
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><input type="checkbox" class="rb-pick" data-id="${c.id}" ${c.used ? "disabled" : ""}/></td>
      <td>${escapeHtml(sourceLabel)}</td>
      <td>${escapeHtml(c.external_post_id)}</td>
      <td>${escapeHtml((c.snippet || "").slice(0, 200))}</td>
      <td>${c.permalink ? `<a href="${safeUrl(c.permalink)}" target="_blank" rel="noopener noreferrer">原文</a>` : ""}</td>
      <td>${c.used ? `→ post #${c.promoted_post_id}` : ""}</td>
    `;
    tbody.appendChild(tr);
  }
  if (!shown) {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:20px;color:#888;">沒有候選（先掃描或調整過濾條件）</td></tr>';
  }
}

document.getElementById("rbPromoteBtn").addEventListener("click", async () => {
  const picked = Array.from(document.querySelectorAll(".rb-pick:checked"))
    .map((cb) => Number(cb.dataset.id));
  if (!picked.length) { alert("先勾選至少一個候選"); return; }
  const groupIds = Array.from(document.getElementById("rbGroupSelect").selectedOptions)
    .map((o) => Number(o.value)).filter(Boolean);
  if (!groupIds.length) { alert("請選至少一個人設群組"); return; }
  const jitter = Number(document.getElementById("rbJitter").value || 0);
  const variants = document.getElementById("rbVariants").checked;

  const out = document.getElementById("rbPromoteOutput");
  const results = [];
  for (const candidateId of picked) {
    try {
      const promoted = await api("/api/rebroadcast/promote", {
        method: "POST",
        body: JSON.stringify({
          candidate_id: candidateId,
          group_ids: groupIds,
          jitter_minutes: jitter,
          generate_variants: variants,
        }),
      });
      // Now actually distribute via the canonical endpoint.
      const distRes = await api(`/api/posts/${promoted.post_id}/distribute`, {
        method: "POST",
        body: JSON.stringify(promoted.suggested_body),
      });
      results.push({ candidate_id: candidateId, post_id: promoted.post_id,
                     distribute: distRes });
    } catch (err) {
      results.push({ candidate_id: candidateId, error: err.message });
    }
  }
  out.textContent = JSON.stringify(results, null, 2);
  loadRbCandidates();
});

// --- C4: 素材庫 -------------------------------------------------------
const mediaState = { offset: 0, limit: 24, total: 0 };

async function loadMedia() {
  const userId = Number(userIdInput.value);
  if (!userId) return;
  const kind = document.getElementById("mediaKind").value;
  const ts = document.getElementById("mediaTranscode").value;
  const params = new URLSearchParams({
    user_id: userId, limit: mediaState.limit, offset: mediaState.offset,
  });
  if (kind) params.set("kind", kind);
  if (ts) params.set("transcode_status", ts);
  const grid = document.getElementById("mediaGrid");
  grid.textContent = "Loading…";
  try {
    const data = await api(`/api/uploads?${params}`);
    mediaState.total = data.total;
    grid.innerHTML = "";
    if (!data.items.length) {
      grid.innerHTML = `<p class="hint">沒有素材。先去 Daily 或 Compose 上傳一個檔案。</p>`;
    }
    for (const m of data.items) {
      const tile = document.createElement("div");
      tile.className = "media-tile";
      tile.dataset.mediaId = m.id;
      const cover = m.kind === "image"
        ? m.storage_url
        : (m.derivatives?.["1:1"] || m.derivatives?.["9:16"] || "");
      const thumb = cover
        ? `<div class="thumb" style="background-image:url('${cover}')"></div>`
        : `<div class="thumb">${m.kind === "video" ? "🎬" : "🖼"} ${m.transcode_status}</div>`;
      tile.innerHTML = `
        ${thumb}
        <div class="meta">
          <span>#${m.id} · ${m.kind}</span>
          <span class="pill ${m.transcode_status}">${m.transcode_status}</span>
        </div>`;
      tile.addEventListener("click", () => _useMediaInActiveForm(m.id));
      grid.appendChild(tile);
    }
    document.getElementById("mediaPageInfo").textContent =
      `${data.offset + 1}–${data.offset + data.items.length} / ${data.total}`;
  } catch (err) {
    grid.innerHTML = `<p class="error">${err.message}</p>`;
  }
}

function _useMediaInActiveForm(mediaId) {
  // Phase 1 fix: the original looked up element ids "composeMediaId" /
  // "dailyMediaId" that never existed in the DOM, so clicking a thumbnail did
  // nothing. The real targets are Compose's hidden <input name="media_id">
  // (mediaIdField) and the Daily flow's in-memory dailyState.mediaId.
  const activeTab = document.querySelector(".tab.active")?.id;
  if (activeTab === "tab-daily") {
    dailyState.mediaId = mediaId;
    if (typeof dailyHint !== "undefined" && dailyHint) {
      dailyHint.textContent = `✓ 已選素材 media_id=${mediaId}`;
    }
    _showToast(`素材 #${mediaId} 已填入 Daily 流程`, "ok");
    return;
  }
  if (mediaIdField) {
    mediaIdField.value = String(mediaId);
    _showToast(`素材 #${mediaId} 已填入 Compose（media_id）`, "ok");
    return;
  }
  // No form available — clipboard fallback.
  navigator.clipboard?.writeText(String(mediaId));
  _showToast(`media_id ${mediaId} 已複製到剪貼簿`, "ok");
}

document.getElementById("reloadMedia")?.addEventListener("click", () => {
  mediaState.offset = 0;
  loadMedia();
});
document.getElementById("mediaPrevPage")?.addEventListener("click", () => {
  mediaState.offset = Math.max(0, mediaState.offset - mediaState.limit);
  loadMedia();
});
document.getElementById("mediaNextPage")?.addEventListener("click", () => {
  if (mediaState.offset + mediaState.limit < mediaState.total) {
    mediaState.offset += mediaState.limit;
    loadMedia();
  }
});

// --- 🌐 Browser publish (the 4th target type) -------------------------
// The control panel does NOT add a backend API for these platforms. It emits
// a self-contained "instruction pack" JSON that a browser-automation consumer
// (Cowork Computer Use / Claude in Chrome) executes. Two hardening additions
// over the original plan: (1) idempotency_key so re-running a pack never double
// posts on a follow-grow account; (2) a result_report skeleton the consumer
// must fill and return, so browser targets aren't fire-and-forget blind spots.
const BROWSER_PLATFORMS = {
  line_voom:   { label: "LINE VOOM",   tier: "green",  full_auto: true  },
  google_biz:  { label: "Google 商家",  tier: "green",  full_auto: true  },
  website:     { label: "官網後台",     tier: "green",  full_auto: true  },
  pinterest:   { label: "Pinterest",   tier: "green",  full_auto: true  },
  xiaohongshu: { label: "小紅書",       tier: "yellow", full_auto: false },
  x_twitter:   { label: "X (Twitter)", tier: "yellow", full_auto: false },
  dcard:       { label: "Dcard",       tier: "yellow", full_auto: false },
  coupang:     { label: "酷澎",         tier: "yellow", full_auto: false },
  shopee:      { label: "蝦皮",         tier: "red",    full_auto: false },
  douyin:      { label: "抖音",         tier: "red",    full_auto: false },
};
const TIER_BADGE = { green: "🟢 全自動", yellow: "🟡 半人工", red: "🔴 禁全自動" };

function renderBrowserTier() {
  const sel = document.getElementById("bpPlatform");
  if (sel && !sel.options.length) {
    sel.innerHTML = Object.entries(BROWSER_PLATFORMS)
      .map(([k, v]) => `<option value="${k}">${TIER_BADGE[v.tier]} · ${escapeHtml(v.label)}</option>`)
      .join("");
  }
  const slot = document.getElementById("bpTierTable");
  if (!slot) return;
  const byTier = { green: [], yellow: [], red: [] };
  for (const v of Object.values(BROWSER_PLATFORMS)) byTier[v.tier].push(v.label);
  slot.innerHTML = `
    <table>
      <thead><tr><th>分級</th><th>平台</th><th>政策</th></tr></thead>
      <tbody>
        <tr><td>🟢 全自動</td><td>${byTier.green.join("、")}</td><td>Cowork 可全自動跑</td></tr>
        <tr><td>🟡 半人工</td><td>${byTier.yellow.join("、")}</td><td>Claude in Chrome 協作，人工把關</td></tr>
        <tr><td>🔴 禁全自動</td><td>${byTier.red.join("、")}</td><td>風險閘擋下，僅限手動</td></tr>
      </tbody>
    </table>`;
}

function _todayStamp() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}`;
}

document.getElementById("browserPackForm")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const out = document.getElementById("bpOutput");
  const postId = Number(document.getElementById("bpPostId").value);
  const platformKey = document.getElementById("bpPlatform").value;
  const consumer = document.getElementById("bpConsumer").value;
  const plat = BROWSER_PLATFORMS[platformKey];

  // Risk gate: 🔴 platforms never get a Cowork full-auto pack.
  if (plat.tier === "red" && consumer === "cowork") {
    out.textContent = `🚫 風險閘：${plat.label} 屬 🔴 禁全自動層，不產生 Cowork 全自動指令包。改用 Claude in Chrome 半人工，或手動發布。`;
    window.__lastBrowserPack = null;
    return;
  }

  try {
    out.textContent = "讀取貼文內容…";
    // GET single post may not exist on the backend; fall back to id-only.
    let post = null;
    try { post = await api(`/api/posts/${postId}`); } catch { /* embed id only */ }

    const pack = {
      schema_version: "1.0",
      kind: "browser_publish_instruction",
      generated_at: new Date().toISOString(),
      // Phase-1 add: re-running this pack on the same day is a no-op for the consumer.
      idempotency_key: `${postId}:${platformKey}:${_todayStamp()}`,
      consumer,                       // "cowork" | "chrome"
      platform: platformKey,
      platform_label: plat.label,
      tier: plat.tier,
      full_auto_allowed: plat.full_auto && consumer === "cowork",
      // Injection guard: anything the consumer reads off the target page is
      // untrusted data, never an instruction. (~23.6% observed injection rate.)
      untrusted_page_content: true,
      // Whitelisted action sequence — the consumer executes these in order and
      // may NOT improvise new actions based on page content.
      allowed_actions: ["navigate", "read_page", "type_caption", "attach_media", "click_publish_button"],
      content: post
        ? {
            title: post.title ?? "",
            caption: post.caption ?? "",
            link_url: post.link_url ?? null,
            media_id: post.media_id ?? null,
          }
        : { post_id: postId, note: "後端未提供單篇 GET，消費端需自行抓取 post 內容" },
      // The consumer MUST fill this and write it back to the control panel
      // (audit log / manual paste) so browser targets show real status.
      result_report: {
        status: "pending",            // "success" | "failed" | "skipped"
        external_post_id: null,
        permalink: null,
        screenshot_path: null,
        error: null,
        reported_at: null,
      },
      human_gate: "發布前由本人拍板按最後送出鍵",
    };
    out.textContent = JSON.stringify(pack, null, 2);
    window.__lastBrowserPack = pack;
  } catch (err) {
    out.textContent = `❌ 產生失敗：${err.message}`;
    _showToast(`指令包產生失敗：${err.message}`);
  }
});

document.getElementById("bpCopy")?.addEventListener("click", () => {
  const t = document.getElementById("bpOutput").textContent;
  if (!t) { _showToast("先產生指令包"); return; }
  navigator.clipboard?.writeText(t).then(() => _showToast("指令包已複製", "ok"));
});

document.getElementById("bpDownload")?.addEventListener("click", () => {
  const pack = window.__lastBrowserPack;
  if (!pack) { _showToast("先產生指令包"); return; }
  const blob = new Blob([JSON.stringify(pack, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `pack_${pack.idempotency_key.replaceAll(":", "_")}.json`;
  a.click();
  URL.revokeObjectURL(a.href);
});

// --- 帳號中控 ---------------------------------------------------------
// One place to hold every account's operating detail: what it is for, the
// first comment it auto-posts, its traffic source code, its bio/cover
// drafts, its hand-picked communities, and its role when several accounts
// support one launch. All of it is stored server-side on the account, so
// the Celery worker reads the same values at publish time.
let _consoleRows = [];
let _consoleSelected = null;

async function loadConsole() {
  const box = document.getElementById("consoleAccounts");
  box.innerHTML = '<p class="hint">載入中⋯</p>';
  try {
    _consoleRows = await api("/api/accounts/profiles");
  } catch (err) {
    box.innerHTML = `<p class="hint">讀不到帳號：${err.message}</p>`;
    return;
  }
  renderConsoleList();
  if (_consoleSelected != null) selectConsoleAccount(_consoleSelected);
  loadBoostStatus();
}

function renderConsoleList() {
  const box = document.getElementById("consoleAccounts");
  const needle = (document.getElementById("consoleFilter").value || "")
    .trim().toLowerCase();
  const rows = needle
    ? _consoleRows.filter((r) =>
        `${r.handle} ${r.platform} ${(r.groups || []).map((g) => g.name).join(" ")}`
          .toLowerCase().includes(needle))
    : _consoleRows;

  if (!rows.length) {
    box.innerHTML = '<p class="hint" style="padding:12px;">沒有符合的帳號。</p>';
    return;
  }
  box.innerHTML = "";
  rows.forEach((row) => {
    const p = row.profile || {};
    // A filled dot means this account already carries settings worth keeping.
    const configured = !!(p.first_comment || (p.communities || []).length || p.note);
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "console-line" + (row.id === _consoleSelected ? " selected" : "");
    btn.dataset.id = row.id;
    const lines = (p.communities || []).length;
    const groups = (row.groups || []).map((g) => g.name).join("、") || "未分組";
    btn.innerHTML =
      `<span class="dot${configured ? " on" : ""}"></span>${escapeHtml(row.handle)}` +
      `<span class="console-line-sub">${escapeHtml(row.platform)}　${escapeHtml(groups)}` +
      (lines ? `　社團 ${lines}` : "") + `</span>`;
    btn.addEventListener("click", () => selectConsoleAccount(row.id));
    box.appendChild(btn);
  });
}

function selectConsoleAccount(id) {
  _consoleSelected = id;
  const row = _consoleRows.find((r) => r.id === id);
  if (!row) return;
  renderConsoleList();

  document.getElementById("consoleEmpty").hidden = true;
  const form = document.getElementById("consoleForm");
  form.hidden = false;

  const p = row.profile || {};
  document.getElementById("consoleHandle").textContent = row.handle;
  document.getElementById("consoleMeta").textContent =
    `${row.platform} · ${row.external_account_id} · ` +
    ((row.groups || []).map((g) => g.name).join("、") || "未分組");

  form.note.value = p.note || "";
  form.persona.value = p.persona || "";
  form.first_comment.value = p.first_comment || "";
  form.link_src.value = p.link_src || "";
  form.bio.value = p.bio || "";
  form.cta.value = p.cta || "";
  form.cover_asset.value = p.cover_asset || "";
  form.avatar_asset.value = p.avatar_asset || "";
  form.interaction_role.value = (p.interaction || {}).role || "off";
  form.interaction_max.value = (p.interaction || {}).max_per_day ?? 1;
  form.comment_pool.value = ((p.interaction || {}).comment_pool || []).join("\n");

  document.getElementById("consoleBioNote").textContent =
    row.platform === "facebook"
      ? "目前存草稿。粉專簡介與封面要用 API 直接改，需要多授權 pages_manage_metadata，"
        + "那要你本人重跑一次 OAuth。"
      : "目前存草稿，供你複製貼上到後台。";

  renderCommunityRows(p.communities || []);
  setConsoleMsg("");
}

function communityRow(entry = {}) {
  const wrap = document.createElement("div");
  wrap.className = "community-row";
  wrap.innerHTML = `
    <label>社團名稱<input class="c-name" value="${escapeHtml(entry.name || "")}" /></label>
    <label>社團連結<input class="c-url" placeholder="https://facebook.com/groups/…"
      value="${escapeHtml(entry.url || "")}" /></label>
    <label>間隔天數<input class="c-cadence" type="number" min="1" max="365"
      value="${entry.cadence_days ?? 14}" /></label>
    <label>優先度<input class="c-priority" type="number" min="1" max="5"
      value="${entry.priority ?? 3}" /></label>
    <button type="button" class="drop">移除</button>
    <div class="row-why">
      <label>為什麼挑這個社團
        <input class="c-why" value="${escapeHtml(entry.why || "")}"
          placeholder="例：問拋光問題的人最多，成交過 3 個" /></label>
      <div class="flags">
        <label><input type="checkbox" class="c-links" ${entry.allows_links === false ? "" : "checked"} /> 可以放連結</label>
        <label><input type="checkbox" class="c-active" ${entry.active === false ? "" : "checked"} /> 啟用</label>
        <span class="c-last">${entry.last_shared_at ? "上次分享 " + entry.last_shared_at.slice(0, 10) : "還沒分享過"}</span>
      </div>
    </div>`;
  wrap.querySelector(".drop").addEventListener("click", () => wrap.remove());
  wrap.dataset.lastShared = entry.last_shared_at || "";
  return wrap;
}

function renderCommunityRows(list) {
  const box = document.getElementById("consoleCommunities");
  box.innerHTML = "";
  list.forEach((entry) => box.appendChild(communityRow(entry)));
}

function collectCommunityRows() {
  return [...document.querySelectorAll("#consoleCommunities .community-row")]
    .map((row) => {
      const val = (sel) => row.querySelector(sel).value.trim();
      const entry = {
        name: val(".c-name"),
        url: val(".c-url"),
        why: val(".c-why"),
        cadence_days: Number(val(".c-cadence")) || 14,
        priority: Number(val(".c-priority")) || 3,
        allows_links: row.querySelector(".c-links").checked,
        active: row.querySelector(".c-active").checked,
      };
      // Preserve the share timestamp; dropping it would silently reset the
      // cadence guard and let a community be posted into again immediately.
      if (row.dataset.lastShared) entry.last_shared_at = row.dataset.lastShared;
      return entry;
    })
    .filter((e) => e.name || e.url);
}

// api() throws Error("400 BAD REQUEST: {json}"), so the validator's sentences
// are buried in the message string. Dig them out and say them in Chinese --
// dumping raw JSON at the operator is the same as saying nothing.
const _PROFILE_ERROR_ZH = [
  [/comment_pool\[(\d+)\] is too short/, (m) =>
    `留言素材第 ${Number(m[1]) + 1} 則太短了，要有實際內容（至少 8 個字），只寫「推」「+1」會被當成洗互動`],
  [/communities\[(\d+)\]\.url must start with https/, (m) =>
    `第 ${Number(m[1]) + 1} 個社團的連結要用 https:// 開頭`],
  [/communities\[(\d+)\]\.url is required/, (m) => `第 ${Number(m[1]) + 1} 個社團少了連結`],
  [/communities\[(\d+)\]\.name is required/, (m) => `第 ${Number(m[1]) + 1} 個社團少了名稱`],
  [/communities\[(\d+)\]\.url is a duplicate/, (m) =>
    `第 ${Number(m[1]) + 1} 個社團的連結跟前面重複了`],
  [/max_per_day must be between (\d+) and (\d+)/, (m) =>
    `每天互動次數要在 ${m[1]}–${m[2]} 之間`],
  [/interaction\.role must be one of/, () => "互動角色的值不對"],
];

function explainProfileError(err) {
  const raw = String(err && err.message ? err.message : err);
  let details = null;
  const brace = raw.indexOf("{");
  if (brace >= 0) {
    try { details = JSON.parse(raw.slice(brace)).details; } catch (_) { /* not JSON */ }
  }
  if (!Array.isArray(details) || !details.length) return raw;
  return details
    .map((d) => {
      for (const [re, say] of _PROFILE_ERROR_ZH) {
        const m = d.match(re);
        if (m) return say(m);
      }
      return d;
    })
    .join("；");
}

function setConsoleMsg(text, kind = "") {
  const el = document.getElementById("consoleMsg");
  el.textContent = text;
  el.className = "console-msg" + (kind ? " " + kind : "");
}

document.getElementById("consoleFilter")?.addEventListener("input", renderConsoleList);
document.getElementById("consoleAddCommunity")?.addEventListener("click", () => {
  document.getElementById("consoleCommunities").appendChild(communityRow());
});

document.getElementById("consoleForm")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (_consoleSelected == null) return;
  const form = e.target;
  const profile = {
    note: form.note.value.trim(),
    persona: form.persona.value.trim(),
    first_comment: form.first_comment.value.trim(),
    link_src: form.link_src.value.trim(),
    bio: form.bio.value.trim(),
    cta: form.cta.value.trim(),
    cover_asset: form.cover_asset.value.trim(),
    avatar_asset: form.avatar_asset.value.trim(),
    communities: collectCommunityRows(),
    interaction: {
      role: form.interaction_role.value,
      max_per_day: Number(form.interaction_max.value) || 0,
      comment_pool: form.comment_pool.value
        .split("\n").map((s) => s.trim()).filter(Boolean),
    },
  };
  setConsoleMsg("儲存中⋯");
  try {
    const saved = await api(`/api/accounts/${_consoleSelected}/profile`, {
      method: "PUT",
      body: JSON.stringify({ profile }),
    });
    const row = _consoleRows.find((r) => r.id === _consoleSelected);
    if (row) row.profile = saved.profile;
    renderConsoleList();
    setConsoleMsg("已儲存。下次這個帳號發文就會照這些設定跑。", "ok");
  } catch (err) {
    setConsoleMsg("存不進去：" + explainProfileError(err), "bad");
  }
});

// --- 社團分享清單 -----------------------------------------------------
document.getElementById("planRefresh")?.addEventListener("click", loadCommunityPlan);

// Three states, not two. "This community bans links" and "you didn't give me
// a link to carry" both left include_link false, and rendering them the same
// made a perfectly link-friendly community look like it forbade links.
function renderLinkLine(c) {
  if (c.include_link) return `<span class="why">帶連結：${escapeHtml(c.link_url)}</span>`;
  if (c.allows_links === false)
    return `<span class="nolink">${escapeHtml(c.link_note || "這個社團禁止外連")}</span>`;
  return '<span class="why">這次沒有指定貼文，所以沒帶連結</span>';
}

async function loadCommunityPlan() {
  const box = document.getElementById("consolePlan");
  const postId = document.getElementById("planPostId").value.trim();
  box.innerHTML = '<p class="hint">計算中⋯</p>';
  const body = postId ? { post_id: Number(postId) } : {};
  let plan;
  try {
    plan = await api("/api/communities/plan", {
      method: "POST",
      body: JSON.stringify(body),
    });
  } catch (err) {
    box.innerHTML = `<p class="hint">算不出來：${escapeHtml(err.message)}</p>`;
    return;
  }
  if (!plan.accounts.length) {
    box.innerHTML =
      '<p class="hint">還沒有任何帳號設過精選社團。先在上面挑一個帳號加社團。</p>';
    return;
  }
  box.innerHTML = "";
  plan.accounts.forEach((acct) => {
    const card = document.createElement("div");
    card.className = "plan-account";
    const due = acct.due.map((c) => `
      <div class="plan-item">
        <div>
          <a href="${escapeHtml(c.url)}" target="_blank" rel="noopener">${escapeHtml(c.name)}</a>
          ${c.why ? `<span class="why">${escapeHtml(c.why)}</span>` : ""}
          ${renderLinkLine(c)}
        </div>
        <button type="button" data-account="${acct.account_id}" data-url="${escapeHtml(c.url)}">記一筆</button>
      </div>`).join("");
    const holding = acct.holding.length
      ? `<p class="plan-holding">還沒到期：${acct.holding
          .map((h) => `${escapeHtml(h.name)}（再 ${h.days_remaining} 天）`).join("、")}</p>`
      : "";
    card.innerHTML =
      `<h4>${escapeHtml(acct.handle)}　可分享 ${acct.due.length}　等待 ${acct.holding.length}</h4>` +
      `<div class="plan-due">${due || '<p class="hint">目前沒有到期的社團。</p>'}</div>` +
      holding;
    box.appendChild(card);
  });

  box.querySelectorAll("button[data-url]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      try {
        await api("/api/communities/mark-shared", {
          method: "POST",
          body: JSON.stringify({
            account_id: Number(btn.dataset.account),
            urls: [btn.dataset.url],
          }),
        });
        btn.textContent = "已記錄";
      } catch (err) {
        btn.disabled = false;
        _showToast("記不起來：" + err.message);
      }
    });
  });
}

// --- 跨帳號互助（按讚＋自己的留言＋自己的引流連結）---------------------
//
// Read-only in the dashboard on purpose. The switch that lets these run for
// real is an environment variable on the worker, not a button here: turning
// on writes-to-Facebook-on-our-behalf should be a deliberate act, not a
// stray click on a settings page.

document.getElementById("boostPreview")?.addEventListener("click", previewBoost);

function boostRoleLabel(role) {
  return { supporter: "應援", leader: "主帳號", off: "不參與" }[role] || role;
}

async function loadBoostStatus() {
  const box = document.getElementById("boostStatus");
  if (!box) return;
  let data;
  try {
    data = await api("/api/boost/settings");
  } catch (err) {
    box.innerHTML = `<p class="hint">讀不到互助設定：${escapeHtml(err.message)}</p>`;
    return;
  }
  const supporters = data.accounts.filter((a) => a.role === "supporter");
  // The two numbers that actually matter, and they are not the same number:
  // "set to supporter" vs "can actually say something".
  const stuck = supporters.filter((a) => !a.ready);
  const rows = supporters.map((a) => `
    <div class="boost-row${a.ready ? "" : " stuck"}">
      <span class="dot${a.ready ? " on" : ""}"></span>
      <strong>${escapeHtml(a.handle)}</strong>
      <span class="why">每天最多 ${a.max_per_day} 次　素材 ${a.comment_pool_size} 句</span>
      <span class="why">${escapeHtml(a.link)}</span>
      ${a.ready ? "" : '<span class="nolink">素材池是空的，這個粉專永遠不會開口</span>'}
    </div>`).join("");

  box.innerHTML = `
    <p class="boost-switch">
      總開關：<strong>${data.enabled ? "開（會真的按讚與留言）" : "關（只做設定，不會動 Facebook）"}</strong>
      　每則貼文最多 ${data.max_supporters_per_post} 個粉專
      　時間打散在發文後 ${data.min_delay_minutes}–${data.window_minutes} 分鐘
    </p>
    <p class="hint">
      設成應援的有 ${supporters.length} 個，其中 ${data.supporters_ready} 個真的講得出話。
      ${stuck.length ? `${stuck.length} 個缺素材。` : ""}
    </p>
    ${rows || '<p class="hint">還沒有任何粉專設成「應援」。上面挑一個帳號改角色。</p>'}`;
}

async function previewBoost() {
  const box = document.getElementById("boostPlan");
  const targetId = document.getElementById("boostTargetId").value.trim();
  if (!targetId) {
    box.innerHTML = '<p class="hint">先填一個已經發出去的 target ID（狀態板上看得到）。</p>';
    return;
  }
  box.innerHTML = '<p class="hint">試算中⋯</p>';
  let plan;
  try {
    plan = await api(`/api/boost/preview?target_id=${encodeURIComponent(targetId)}`);
  } catch (err) {
    box.innerHTML = `<p class="hint">算不出來：${escapeHtml(err.message)}</p>`;
    return;
  }
  const actions = (plan.actions || []).map((a) => `
    <div class="plan-item">
      <div>
        <strong>${escapeHtml(a.handle)}</strong>
        <span class="why">發文後 ${a.delay_minutes} 分鐘　按讚＋留言</span>
        <span class="boost-msg">${escapeHtml(a.message)}</span>
      </div>
    </div>`).join("");
  const skipped = (plan.skipped || []).map((s) =>
    `<li>${escapeHtml(s.handle)}－${escapeHtml(s.reason)}</li>`).join("");
  box.innerHTML = `
    <div class="plan-account">
      <h4>${escapeHtml(plan.leader)} 這則貼文</h4>
      ${actions || '<p class="hint">沒有粉專會出來互動。</p>'}
      ${skipped ? `<p class="plan-holding">沒排到的：</p><ul class="boost-skipped">${skipped}</ul>` : ""}
      ${plan.enabled ? "" : '<p class="plan-holding">總開關是關的，上面這些現在不會真的發生。</p>'}
    </div>`;
}
