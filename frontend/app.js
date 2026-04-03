/* ============================================================
   Ops Sentinel — Command Center Application Logic
   ============================================================ */

const API_BASE = window.location.origin;

// DOM elements
const chatMessages = document.getElementById("chat-messages");
const chatInput = document.getElementById("chat-input");
const btnSend = document.getElementById("btn-send");
const serviceList = document.getElementById("service-list");
const btnRefresh = document.getElementById("btn-refresh-services");
const statusTemporal = document.getElementById("status-temporal");
const statusDocker = document.getElementById("status-docker");
const toastContainer = document.getElementById("toast-container");

// ---- State ----
let isExecuting = false;

// ---- Initialization ----
document.addEventListener("DOMContentLoaded", () => {
  checkHealth();
  loadServices();

  // Auto-refresh every 30s
  setInterval(checkHealth, 30000);
  setInterval(loadServices, 30000);

  // Event listeners
  btnSend.addEventListener("click", handleSend);
  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  });

  btnRefresh.addEventListener("click", () => {
    loadServices(true);
  });

  // Hint buttons (delegated)
  chatMessages.addEventListener("click", (e) => {
    const hintBtn = e.target.closest(".hint-btn");
    if (hintBtn) {
      chatInput.value = hintBtn.dataset.hint;
      chatInput.focus();
    }
  });
});

// ---- Health Check ----
async function checkHealth() {
  try {
    const resp = await fetch(`${API_BASE}/api/health`);
    const data = await resp.json();

    updateStatusPill(statusTemporal, data.temporal_connected);
    updateStatusPill(statusDocker, data.docker_connected);
  } catch {
    updateStatusPill(statusTemporal, false);
    updateStatusPill(statusDocker, false);
  }
}

function updateStatusPill(el, connected) {
  el.classList.remove("connected", "disconnected");
  el.classList.add(connected ? "connected" : "disconnected");
}

// ---- Services ----
async function loadServices(showSpinner = false) {
  if (showSpinner) {
    btnRefresh.classList.add("spinning");
  }

  try {
    const resp = await fetch(`${API_BASE}/api/services`);
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || resp.statusText);
    }
    const services = await resp.json();
    renderServices(services);
  } catch (err) {
    serviceList.innerHTML = `
      <div class="sidebar__empty">
        <p>Cannot load services<br><small style="color:var(--text-muted)">${escapeHtml(err.message)}</small></p>
      </div>`;
  } finally {
    btnRefresh.classList.remove("spinning");
  }
}

function renderServices(services) {
  if (!services.length) {
    serviceList.innerHTML = `<div class="sidebar__empty"><p>No containers found</p></div>`;
    return;
  }

  serviceList.innerHTML = services
    .map((svc, i) => {
      const stateClass = getStateClass(svc.state);
      const ports = Object.entries(svc.ports || {})
        .map(([k, v]) => `${k} → ${v.join(", ")}`)
        .join("\n") || "No ports";
      const image = svc.image || "unknown";

      return `
        <div class="svc-card" style="animation-delay: ${i * 60}ms">
          <div class="svc-card__row">
            <span class="svc-card__name">${escapeHtml(svc.name)}</span>
            <span class="svc-card__state ${stateClass}">${escapeHtml(svc.state)}</span>
          </div>
          <div class="svc-card__meta">${escapeHtml(image)}\n${escapeHtml(ports)}</div>
        </div>`;
    })
    .join("");
}

function getStateClass(state) {
  const s = (state || "").toLowerCase();
  if (s === "running") return "svc-card__state--running";
  if (s === "exited" || s === "stopped") return "svc-card__state--exited";
  if (s === "paused") return "svc-card__state--paused";
  if (s === "restarting") return "svc-card__state--restarting";
  return "";
}

// ---- Chat ----
async function handleSend() {
  const text = chatInput.value.trim();
  if (!text || isExecuting) return;

  appendMessage("user", text);
  chatInput.value = "";
  chatInput.focus();

  isExecuting = true;
  btnSend.disabled = true;

  const typingEl = showTypingIndicator();

  try {
    const resp = await fetch(`${API_BASE}/api/execute`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ request: text }),
    });

    removeTypingIndicator(typingEl);

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || `Server error (${resp.status})`);
    }

    const data = await resp.json();
    appendMessage("system", data.result, data.workflow_id);

    // Refresh services after action
    loadServices();
  } catch (err) {
    removeTypingIndicator(typingEl);
    appendMessage("system", `⚠️ Error: ${err.message}`);
    showToast(err.message, "error");
  } finally {
    isExecuting = false;
    btnSend.disabled = false;
  }
}

function appendMessage(role, text, workflowId = null) {
  const msg = document.createElement("div");
  msg.className = `msg msg--${role} msg--fadein`;

  const time = new Date().toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });

  if (role === "user") {
    msg.innerHTML = `
      <div class="msg__avatar msg__avatar--user">U</div>
      <div class="msg__body">
        <div class="msg__name">You</div>
        <div class="msg__text">${escapeHtml(text)}</div>
        <div class="msg__time">${time}</div>
      </div>`;
  } else {
    const terminal = formatTerminalOutput(text);
    const wfLabel = workflowId
      ? `<span style="color:var(--text-muted);font-size:11px;font-family:var(--font-mono)">workflow: ${escapeHtml(workflowId.substring(0, 22))}…</span>`
      : "";

    msg.innerHTML = `
      <div class="msg__avatar msg__avatar--system">
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <circle cx="10" cy="10" r="8" stroke="currentColor" stroke-width="1.5"/>
          <path d="M7 10h6M10 7v6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
      </div>
      <div class="msg__body">
        <div class="msg__name">Ops Sentinel ${wfLabel}</div>
        <div class="msg__text">
          <div class="msg__terminal">${terminal}</div>
        </div>
        <div class="msg__time">${time}</div>
      </div>`;
  }

  chatMessages.appendChild(msg);
  scrollToBottom();
}

function formatTerminalOutput(raw) {
  const escaped = escapeHtml(raw);
  return escaped
    .split("\n")
    .map((line) => {
      // Health indicators
      if (line.startsWith("✓") || line.includes(": Healthy"))
        return `<span class="term-ok">${line}</span>`;
      if (line.startsWith("✗") || line.includes(": Unhealthy"))
        return `<span class="term-fail">${line}</span>`;

      // Warnings
      if (/\[WARN\]|\[WARNING\]/i.test(line) || line.includes("Concerns:"))
        return `<span class="term-warn">${line}</span>`;

      // Errors
      if (/\[ERROR\]|failed|error/i.test(line))
        return `<span class="term-fail">${line}</span>`;

      // Info / headings
      if (
        line.startsWith("Discovered") ||
        line.startsWith("Health overview") ||
        line.startsWith("Summary:") ||
        line.startsWith("Last ")
      )
        return `<span class="term-heading">${line}</span>`;

      if (line.startsWith("Service:") || line.startsWith("  State:"))
        return `<span class="term-info">${line}</span>`;

      return line;
    })
    .join("\n");
}

// ---- Typing Indicator ----
function showTypingIndicator() {
  const wrapper = document.createElement("div");
  wrapper.className = "msg msg--system msg--fadein";
  wrapper.id = "typing-msg";

  wrapper.innerHTML = `
    <div class="msg__avatar msg__avatar--system">
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <circle cx="10" cy="10" r="8" stroke="currentColor" stroke-width="1.5"/>
        <path d="M7 10h6M10 7v6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
      </svg>
    </div>
    <div class="msg__body">
      <div class="msg__name">Ops Sentinel</div>
      <div class="typing-indicator">
        <span></span><span></span><span></span>
      </div>
    </div>`;

  chatMessages.appendChild(wrapper);
  scrollToBottom();
  return wrapper;
}

function removeTypingIndicator(el) {
  if (el && el.parentNode) {
    el.parentNode.removeChild(el);
  }
}

// ---- Toast Notifications ----
function showToast(message, type = "error") {
  const toast = document.createElement("div");
  toast.className = `toast toast--${type}`;
  toast.textContent = message;
  toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(8px)";
    toast.style.transition = "all 300ms ease";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// ---- Helpers ----
function escapeHtml(text) {
  const el = document.createElement("span");
  el.textContent = text;
  return el.innerHTML;
}

function scrollToBottom() {
  chatMessages.scrollTo({
    top: chatMessages.scrollHeight,
    behavior: "smooth",
  });
}
