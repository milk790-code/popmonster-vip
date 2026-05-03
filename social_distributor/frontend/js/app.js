const API_BASE = window.SOCIAL_DISTRIBUTOR_API ?? "http://localhost:5000";

// Register the service worker for PWA / offline shell support.
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("./sw.js").catch(() => {
      /* SW registration is a progressive enhancement; ignore failures. */
    });
  });
}

const userIdInput = document.getElementById("userId");

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers ?? {}) };
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

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
    if (btn.dataset.tab === "distribute") loadDistributeGroups();
    if (btn.dataset.tab === "insights") loadInsights();
    if (btn.dataset.tab === "daily") loadDailyDeps();
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

async function handleFile(file) {
  const userId = Number(userIdInput.value);
  const kind = file.type.startsWith("video/") ? "video" : "image";
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
    }),
  });
  mediaIdField.value = media.id;
  uploadStatus.textContent = `Uploaded ✓ media_id=${media.id} (transcode: ${media.transcode_status})`;
}

// --- Compose: form submit ---------------------------------------------
const postForm = document.getElementById("postForm");
postForm.addEventListener("submit", async (e) => {
  e.preventDefault();
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
  document.getElementById("postOutput").textContent = JSON.stringify(post, null, 2);
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
  for (const row of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${row.id}</td>
      <td>${row.platform}</td>
      <td>${row.handle ?? ""}</td>
      <td><span class="status-pill ${row.status}">${row.status}</span></td>
      <td>${row.scheduled_for ?? ""}</td>
      <td>${row.cron ?? ""}</td>
      <td>${row.attempt_count}</td>
      <td>${row.external_post_id ?? ""}</td>
      <td>${row.last_error ?? ""}</td>
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
}

// --- Accounts ---------------------------------------------------------
document.querySelectorAll(".connect-row button").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const userId = Number(userIdInput.value);
    const result = await api(
      `/auth/${btn.dataset.provider}/start?user_id=${userId}`
    );
    window.open(result.authorization_url, "_blank", "noopener");
  });
});

async function loadAccounts() {
  const userId = Number(userIdInput.value);
  const rows = await api(`/api/accounts?user_id=${userId}`);
  const tbody = document.querySelector("#accountsTable tbody");
  tbody.innerHTML = "";
  for (const row of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${row.id}</td>
      <td>${row.platform}</td>
      <td>${row.handle}</td>
      <td>${row.token_expires_at ?? "—"}</td>
      <td></td>
    `;
    const actions = tr.lastElementChild;
    const revoke = document.createElement("button");
    revoke.textContent = "Revoke";
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
      <td>${row.created_at}</td>
      <td>${row.actor_user_id ?? ""}</td>
      <td>${row.action}</td>
      <td>${row.resource_type}#${row.resource_id ?? ""}</td>
      <td><pre style="max-height:120px">${JSON.stringify(row.detail, null, 2)}</pre></td>
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
          `<li>${m.platform} · ${m.handle} <button data-account="${m.account_id}" data-group="${group.id}" class="rm-member">移除</button></li>`
      )
      .join("");

    const availableOptions = accounts
      .filter((a) => !group.members.find((m) => m.account_id === a.id))
      .map((a) => `<option value="${a.id}">${a.platform} · ${a.handle}</option>`)
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
}

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
  const body = {
    group_ids: groupIds,
    scheduled_for: fd.get("scheduled_for") || null,
    timezone: fd.get("timezone") || "UTC",
    jitter_minutes: Number(fd.get("jitter_minutes") || 0),
    generate_variants: fd.get("generate_variants") === "on",
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
    .replaceAll('"', "&quot;");
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

// --- Insights ---------------------------------------------------------
async function loadInsights() {
  const postId = document.getElementById("insightsPostId").value;
  const groupId = document.getElementById("insightsGroupId").value;
  const params = new URLSearchParams();
  if (postId) params.set("post_id", postId);
  if (groupId) params.set("group_id", groupId);
  const rows = await api(`/api/insights?${params.toString()}`);
  const tbody = document.querySelector("#insightsTable tbody");
  tbody.innerHTML = "";
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

// --- SSE real-time status updates -------------------------------------
let _eventSource = null;
function connectEvents() {
  if (_eventSource) _eventSource.close();
  const userId = Number(userIdInput.value);
  if (!userId) return;
  _eventSource = new EventSource(`${API_BASE}/api/events/stream?user_id=${userId}`);
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
  dailyState.groups = await api(`/api/groups?user_id=${userId}`);
  renderDailyChips();
  renderDailyPreview();
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
  dailyHint.textContent = `Uploading ${file.name}…`;
  try {
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
  if (when === "at") scheduled_for = document.getElementById("dailyAt").value || null;
  if (when === "best") {
    const groupId = Array.from(dailyState.selectedGroups)[0];
    try {
      const slots = await api(`/api/insights/best-times?group_id=${groupId}`);
      if (slots.length) {
        // Find the next future occurrence of slot[0] (top engagement bucket).
        const top = slots[0];
        scheduled_for = nextOccurrence(top.day, top.hour);
      }
    } catch {}
  }

  const body = {
    group_ids: Array.from(dailyState.selectedGroups),
    scheduled_for,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
    jitter_minutes: Number(document.getElementById("dailyJitter").value || 0),
    generate_variants: document.getElementById("dailyVariants").checked,
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
});

function nextOccurrence(dayLabel, hour) {
  const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const target = days.indexOf(dayLabel);
  if (target < 0) return null;
  const now = new Date();
  const todayIdx = (now.getDay() + 6) % 7; // make Mon=0
  let delta = (target - todayIdx + 7) % 7;
  const candidate = new Date(now);
  candidate.setDate(candidate.getDate() + delta);
  candidate.setHours(hour, 0, 0, 0);
  if (candidate <= now) candidate.setDate(candidate.getDate() + 7);
  // Format as local naive ISO so backend localizes with the explicit tz field.
  const pad = (n) => String(n).padStart(2, "0");
  return `${candidate.getFullYear()}-${pad(candidate.getMonth() + 1)}-${pad(candidate.getDate())}T${pad(candidate.getHours())}:${pad(candidate.getMinutes())}`;
}

document.getElementById("dailyRefreshStatus").addEventListener("click", loadDailyStatus);

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
