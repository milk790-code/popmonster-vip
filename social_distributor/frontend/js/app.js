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
  });
});

// --- Compose ----------------------------------------------------------
const postForm = document.getElementById("postForm");
postForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(postForm);
  const userId = Number(userIdInput.value);

  const mediaUrl = fd.get("media_url");
  const mediaKind = fd.get("media_kind");
  let mediaId = null;
  if (mediaUrl && mediaKind) {
    const media = await api("/api/posts/media", {
      method: "POST",
      body: JSON.stringify({
        user_id: userId,
        kind: mediaKind,
        storage_url: mediaUrl,
        mime_type: mediaKind === "video" ? "video/mp4" : "image/jpeg",
        s3_bucket: fd.get("s3_bucket") || null,
        s3_key: fd.get("s3_key") || null,
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
