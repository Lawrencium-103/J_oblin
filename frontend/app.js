const API = "http://127.0.0.1:8002";
function getToken() { return localStorage.getItem("joblin_token"); }
function apiHeaders() { const h = { "Content-Type": "application/json" }; const t = getToken(); if (t) h["Authorization"] = `Bearer ${t}`; return h; }
async function apiFetch(method, path, body) {
  const opts = { method, headers: apiHeaders() };
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(API + path, opts);
  if (r.status === 401) {
    localStorage.removeItem("joblin_token"); localStorage.removeItem("joblin_user");
    window.location.href = "/login.html";
    throw new Error("Unauthorized");
  }
  const text = await r.text();
  if (!text && !r.ok) throw new Error("Server error (empty response)");
  let data;
  try { data = JSON.parse(text); } catch (e) {
    throw new Error((r.status === 500 ? "Server error: " : "Request failed: ") + text.slice(0, 200));
  }
  if (!r.ok) {
    let msg = "Request failed";
    if (typeof data.detail === "string") msg = data.detail;
    else if (Array.isArray(data.detail)) msg = data.detail.map(e => e.msg || e).join("; ");
    throw new Error(msg);
  }
  return data;
}
function showToast(msg, type = "success") {
  let t = document.getElementById("toast");
  if (!t) { t = document.createElement("div"); t.id = "toast"; t.className = "toast"; document.body.appendChild(t); }
  t.className = `toast ${type} show`; t.textContent = msg;
  clearTimeout(t._timeout); t._timeout = setTimeout(() => t.classList.remove("show"), 3000);
}
function getCurrentUser() { const u = localStorage.getItem("joblin_user"); return u ? JSON.parse(u) : null; }
function setCurrentUser(user) { localStorage.setItem("joblin_user", JSON.stringify(user)); }
function updateHeader() {
  const user = getCurrentUser();
  const nameEl = document.getElementById("user-name");
  const emailEl = document.getElementById("user-email");
  const avatarEl = document.getElementById("avatarInitial");
  if (nameEl && user) nameEl.textContent = user.name || user.email;
  if (emailEl && user) emailEl.textContent = user.email || "";
  if (avatarEl && user) {
    const initial = (user.name || user.email || "U")[0].toUpperCase();
    avatarEl.textContent = initial;
  }
  const path = window.location.pathname.split("/").pop() || "dashboard.html";
  document.querySelectorAll(".nav-item").forEach(a => {
    a.classList.toggle("active", a.getAttribute("href") === path);
  });
}
function logout() { localStorage.removeItem("joblin_token"); localStorage.removeItem("joblin_user"); window.location.href = "/login.html"; }
function escHtml(s) { if (!s) return ""; return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }

function renderQualityScores(scores) {
  if (!scores || !Object.keys(scores).length) return "";
  const labels = {
    achievement_density: "Achievement Density",
    bullet_depth: "Bullet Depth",
    skills: "Skills",
    summary: "Summary",
    education: "Education",
    cover_letter: "Cover Letter",
  };
  return `<div class="quality-scores">
    <div style="font-size:11px;font-weight:600;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em;margin-bottom:10px;display:flex;align-items:center;gap:6px">
      <span style="width:3px;height:14px;border-radius:2px;background:linear-gradient(180deg,var(--color-primary-400),var(--color-primary-600));display:inline-block"></span>
      Quality Scores
    </div>
    <div class="quality-grid">${Object.entries(scores).map(([k, v]) => {
      const label = labels[k] || k;
      const pct = v.pass ? 100 : Math.min(Math.max((v.score || 0) * 100, 0), 100);
      const barColor = v.pass ? "#059669" : (pct > 50 ? "#d97706" : "#dc2626");
      const bgColor = v.pass ? "rgba(5,150,105,0.08)" : (pct > 50 ? "rgba(217,119,6,0.08)" : "rgba(220,38,38,0.08)");
      const borderColor = v.pass ? "rgba(5,150,105,0.15)" : (pct > 50 ? "rgba(217,119,6,0.15)" : "rgba(220,38,38,0.15)");
      return `<div class="quality-item" style="background:${bgColor};border-color:${borderColor}">
        <div class="quality-header">
          <span class="quality-label">${label}</span>
          <span class="quality-badge" style="color:${barColor};background:${barColor}12">${v.pass ? "PASS" : "FAIL"}</span>
        </div>
        <div class="quality-bar-track"><div class="quality-bar-fill" style="width:${pct}%;background:${barColor}"></div></div>
        <span class="quality-value">${escHtml(v.reason)}</span>
      </div>`;
    }).join("")}</div>
  </div>`;
}

function renderJobScore(score) {
  const pct = Math.round(score || 0);
  let color = "var(--text-subtle)";
  if (pct >= 70) color = "var(--color-primary-500)";
  else if (pct >= 40) color = "var(--color-warning-500)";
  return `<span class="job-score" style="color:${color}">${pct}%</span>`;
}

const CATEGORY_COLORS = {
  "data-analytics": "#059669", "monitoring-evaluation": "#0284c7",
  "ai-machine-learning": "#7c3aed", "software-dev": "#dc2626",
  "public-health": "#e11d48", "graduate-entry": "#d97706",
  "ngo-development": "#2563eb", "project-management": "#0f766e",
  "finance-accounting": "#9333ea", "admin-operations": "#64748b",
  "human-resources": "#db2777", "sales-marketing": "#ea580c",
  "customer-service": "#f59e0b", "engineering": "#b45309",
  "procurement-supply": "#0891b2", "legal-compliance": "#475569",
  "remote": "#0891b2", "other": "#94a3b8",
};
const CATEGORY_NAMES = {
  "data-analytics": "Data & Analytics", "monitoring-evaluation": "M&E",
  "ai-machine-learning": "AI/ML", "software-dev": "Software & IT",
  "public-health": "Public Health", "graduate-entry": "Graduate",
  "ngo-development": "NGO/Dev", "project-management": "Project Mgmt",
  "finance-accounting": "Finance & Acct", "admin-operations": "Admin & Ops",
  "human-resources": "HR", "sales-marketing": "Sales/Marketing",
  "customer-service": "Customer Svc", "engineering": "Engineering",
  "procurement-supply": "Procurement", "legal-compliance": "Legal",
  "remote": "Remote", "other": "Other",
};

function renderCategoryBadge(cat) {
  const color = CATEGORY_COLORS[cat] || "#94a3b8";
  const name = CATEGORY_NAMES[cat] || cat;
  return `<span class="cat-badge" style="background:${color}15;color:${color};border:1px solid ${color}30">${escHtml(name)}</span>`;
}

function renderJobItem(job, isNew = false) {
  const newClass = isNew ? "job-new" : "";
  const now = new Date();
  let ageClass = "job-age-old";
  let badge = "";
  if (isNew) {
    const found = new Date(job.date_found.replace(" ", "T"));
    const hoursOld = (now - found) / 3600000;
    if (hoursOld < 6) {
      ageClass = "job-age-fresh";
      badge = '<span class="new-badge new-badge-fresh">Fresh</span>';
    } else {
      ageClass = "job-age-today";
      badge = '<span class="new-badge">New</span>';
    }
  }
  return `
    <div class="job-item ${newClass} ${ageClass}" data-id="${job.id}" onclick="location.href='job-detail.html?id=${job.id}'" style="cursor:pointer">
      <div class="job-info">
        <div class="job-title">${escHtml(job.title)} ${badge}</div>
        <div class="job-company">${escHtml(job.company || "Unknown")} \u00b7 ${escHtml(job.source || "")} ${renderCategoryBadge(job.job_category)}</div>
      </div>
      <div class="job-actions">
        ${renderJobScore(job.match_score)}
        <button class="btn btn-primary btn-sm" onclick="event.stopPropagation();location.href='job-detail.html?id=${job.id}'">View</button>
      </div>
    </div>`;
}

function isNewJob(job) {
  if (!job.date_found) return false;
  const found = new Date(job.date_found.replace(" ", "T"));
  const now = new Date();
  return (now - found) < 86400000;
}

function timeSince(dateStr) {
  if (!dateStr) return "";
  const ts = new Date(dateStr.replace(" ", "T"));
  const now = new Date();
  const diffMs = now - ts;
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return mins + "m ago";
  const hours = Math.floor(mins / 60);
  if (hours < 24) return hours + "h ago";
  const days = Math.floor(hours / 24);
  return days + "d ago";
}
