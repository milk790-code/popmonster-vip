const API_BASE = window.SOCIAL_DISTRIBUTOR_API ?? "http://localhost:5000";

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
