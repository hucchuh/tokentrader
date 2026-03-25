const state = {
  token: localStorage.getItem("tt_token") || "",
  dashboard: null,
  selectedThreadId: null,
  routingPreview: [],
};

const refs = {
  authForm: document.querySelector("#auth-form"),
  authFeedback: document.querySelector("#auth-feedback"),
  dashboard: document.querySelector("#dashboard"),
  signoutButton: document.querySelector("#signout-button"),
  summaryName: document.querySelector("#summary-name"),
  summaryEmail: document.querySelector("#summary-email"),
  summaryMana: document.querySelector("#summary-mana"),
  summaryThreads: document.querySelector("#summary-threads"),
  summaryTasks: document.querySelector("#summary-tasks"),
  summaryLocked: document.querySelector("#summary-locked"),
  threadForm: document.querySelector("#thread-form"),
  threadFeedback: document.querySelector("#thread-feedback"),
  threadList: document.querySelector("#thread-list"),
  selectedThread: document.querySelector("#selected-thread"),
  replyForm: document.querySelector("#reply-form"),
  replyFeedback: document.querySelector("#reply-feedback"),
  taskForm: document.querySelector("#task-form"),
  taskFeedback: document.querySelector("#task-feedback"),
  taskList: document.querySelector("#task-list"),
  manaLedger: document.querySelector("#mana-ledger"),
  leaderboard: document.querySelector("#leaderboard"),
  routingPreview: document.querySelector("#routing-preview"),
  apiSurface: document.querySelector("#api-surface"),
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function setFeedback(node, message = "", tone = "") {
  node.textContent = message;
  node.className = "inline-feedback";
  if (tone) node.classList.add(`feedback-${tone}`);
}

function formatDate(value) {
  if (!value) return "-";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatDelta(delta) {
  return `${delta > 0 ? "+" : ""}${delta} mana`;
}

function reasonLabel(reason) {
  const labels = {
    welcome_grant: "开户奖励",
    task_bounty_locked: "任务赏金锁定",
    task_reward_earned: "任务完成奖励",
  };
  return labels[reason] || reason;
}

async function apiGet(path) {
  const response = await fetch(path);
  const data = await response.json();
  if (!data.ok) throw new Error(data.error || "请求失败");
  return data;
}

async function apiPost(path, payload) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!data.ok) throw new Error(data.error || "请求失败");
  return data;
}

function toggleDashboard(isVisible) {
  refs.dashboard.classList.toggle("hidden", !isVisible);
  refs.signoutButton.classList.toggle("hidden", !isVisible);
}

function renderSummary() {
  const { user, stats } = state.dashboard;
  refs.summaryName.textContent = user.name;
  refs.summaryEmail.textContent = user.email;
  refs.summaryMana.textContent = `${user.mana_balance} mana`;
  refs.summaryThreads.textContent = `${stats.thread_count}`;
  refs.summaryTasks.textContent = `${stats.active_tasks} active`;
  refs.summaryLocked.textContent = `${stats.locked_mana} mana locked · ${stats.completed_tasks} completed`;
}

function renderThreadList() {
  if (!state.dashboard.threads.length) {
    refs.threadList.innerHTML = `<div class="empty-state">社区还没有 thread。发起一个讨论，把第一个 signal 打出去。</div>`;
    return;
  }
  refs.threadList.innerHTML = state.dashboard.threads
    .map((thread) => {
      const active = thread.id === state.selectedThreadId ? "active" : "";
      return `
        <button class="thread-item ${active}" type="button" data-thread-id="${thread.id}">
          <span class="status-pill">${escapeHtml(thread.kind)}</span>
          <h4>${escapeHtml(thread.title)}</h4>
          <p>${escapeHtml(thread.body.slice(0, 140))}</p>
          <div class="thread-meta">
            <span>${escapeHtml(thread.author.name)}</span>
            <span>${thread.reply_count} replies</span>
            <span>${formatDate(thread.updated_at)}</span>
            <span>${thread.bounty_mana ? `${thread.bounty_mana} mana bounty` : "discussion"}</span>
          </div>
        </button>
      `;
    })
    .join("");
}

function renderSelectedThread() {
  const thread = state.dashboard.selected_thread;
  if (!thread) {
    refs.selectedThread.innerHTML = `<div class="empty-state">还没有讨论内容。先发一个 thread 或 forum。</div>`;
    return;
  }
  const posts = thread.posts.length
    ? thread.posts
        .map(
          (post) => `
            <article class="thread-post">
              <strong>${escapeHtml(post.author.name)}</strong>
              <p>${escapeHtml(post.body)}</p>
              <div class="thread-meta">
                <span>${formatDate(post.created_at)}</span>
              </div>
            </article>
          `
        )
        .join("")
    : `<div class="empty-state">还没有回复。你可以成为第一条跟进。</div>`;

  refs.selectedThread.innerHTML = `
    <div class="thread-header">
      <span class="status-pill">${escapeHtml(thread.kind)}</span>
      <h3>${escapeHtml(thread.title)}</h3>
      <p>${escapeHtml(thread.body)}</p>
      <div class="thread-meta">
        <span>${escapeHtml(thread.author.name)}</span>
        <span>${formatDate(thread.updated_at)}</span>
        <span>${thread.reply_count} replies</span>
        <span>${thread.bounty_mana ? `${thread.bounty_mana} mana bounty` : "open discussion"}</span>
      </div>
    </div>
    <div class="thread-posts">${posts}</div>
  `;
}

function renderTaskList() {
  if (!state.dashboard.tasks.length) {
    refs.taskList.innerHTML = `<div class="empty-state">还没有任务。挂一个赏金，让社区开始协作。</div>`;
    return;
  }
  refs.taskList.innerHTML = state.dashboard.tasks
    .map((task) => {
      const claimButton = task.can_claim
        ? `<button class="secondary-button" type="button" data-action="claim-task" data-task-id="${task.id}">认领任务</button>`
        : "";
      const completeForm = task.can_complete
        ? `
          <form data-action="complete-task" data-task-id="${task.id}">
            <textarea name="deliverable" rows="3" placeholder="填写完成说明、输出摘要或返回结果..." required></textarea>
            <input name="external_ref" type="text" placeholder="可选：结果链接 / API 回调地址" />
            <button type="submit">提交完成结果</button>
          </form>
        `
        : "";
      const route = task.route ? `${task.route.provider} · ${task.route.model}` : "waiting for routing";

      return `
        <article class="task-card">
          <span class="status-pill status-${escapeHtml(task.status)}">${escapeHtml(task.status.replace("_", " "))}</span>
          <h4>${escapeHtml(task.title)}</h4>
          <p>${escapeHtml(task.brief)}</p>
          <div class="task-meta">
            <span>${task.reward_mana} mana</span>
            <span>${escapeHtml(task.quality_tier)}</span>
            <span>${task.prompt_tokens} tokens</span>
            <span>${task.max_latency_ms} ms</span>
            <span>${task.budget_credits} credits</span>
          </div>
          <div class="task-meta">
            <span>creator: ${escapeHtml(task.creator.name)}</span>
            <span>assignee: ${escapeHtml(task.assignee?.name || "unclaimed")}</span>
            <span>${escapeHtml(route)}</span>
          </div>
          ${task.thread_id ? `<div class="task-meta"><span>linked thread #${task.thread_id}</span></div>` : ""}
          ${task.deliverable ? `<p class="task-meta">delivery: ${escapeHtml(task.deliverable)}</p>` : ""}
          ${task.external_ref ? `<p class="task-meta">ref: ${escapeHtml(task.external_ref)}</p>` : ""}
          <div class="task-actions">
            ${claimButton}
          </div>
          ${completeForm}
        </article>
      `;
    })
    .join("");
}

function renderTreasury() {
  refs.manaLedger.innerHTML = state.dashboard.ledger.length
    ? state.dashboard.ledger
        .map(
          (entry) => `
            <article class="ledger-entry">
              <strong>${escapeHtml(reasonLabel(entry.reason))}</strong>
              <div class="entry-meta">
                <span class="${entry.delta >= 0 ? "delta-positive" : "delta-negative"}">${formatDelta(entry.delta)}</span>
                <span>${formatDate(entry.created_at)}</span>
              </div>
            </article>
          `
        )
        .join("")
    : `<div class="empty-state">这里会显示你的 mana 流水。</div>`;

  refs.leaderboard.innerHTML = state.dashboard.leaderboard.length
    ? state.dashboard.leaderboard
        .map(
          (user, index) => `
            <article class="leader-row">
              <div>
                <strong>#${index + 1} ${escapeHtml(user.name)}</strong>
                <div class="entry-meta">${escapeHtml(user.email)}</div>
              </div>
              <span>${user.mana_balance} mana</span>
            </article>
          `
        )
        .join("")
    : "";

  const preview = state.routingPreview.length ? state.routingPreview : state.dashboard.market;
  refs.routingPreview.innerHTML = preview
    .map((item) => {
      const provider = item.provider;
      const model = item.model;
      const price = item.estimated_cost_credits ?? item.price_per_1k_tokens;
      const score = item.score ?? item.quality_score;
      const label = item.score ? "score" : "quality";
      return `
        <article class="route-card">
          <h4>${escapeHtml(provider)} / ${escapeHtml(model)}</h4>
          <p>${label}: ${escapeHtml(String(score))}</p>
          <p>price: ${escapeHtml(String(price))}</p>
          ${item.avg_latency_ms ? `<p>latency: ${item.avg_latency_ms} ms</p>` : ""}
        </article>
      `;
    })
    .join("");

  const tokenPreview = state.token ? `${state.token.slice(0, 12)}...` : "YOUR_TOKEN";
  refs.apiSurface.innerHTML = `
    <p class="panel-kicker">API surface</p>
    <pre>POST /api/auth
POST /api/threads
POST /api/posts
POST /api/tasks
POST /api/tasks/claim
POST /api/tasks/complete
GET  /api/bootstrap?token=${tokenPreview}

curl -X POST /api/tasks \\
  -H "Content-Type: application/json" \\
  -d '{
    "token": "${tokenPreview}",
    "title": "Ship weekly synthesis",
    "brief": "Upload task from an external agent and return the result URL.",
    "reward_mana": 48,
    "prompt_tokens": 1600,
    "max_latency_ms": 1500,
    "budget_credits": 1.2,
    "quality_tier": "balanced"
  }'</pre>
  `;
}

function renderDashboard() {
  renderSummary();
  renderThreadList();
  renderSelectedThread();
  renderTaskList();
  renderTreasury();
}

async function loadDashboard(threadId = state.selectedThreadId) {
  const suffix = threadId ? `&thread_id=${threadId}` : "";
  try {
    const data = await apiGet(`/api/bootstrap?token=${encodeURIComponent(state.token)}${suffix}`);
    state.dashboard = data;
    state.selectedThreadId = data.selected_thread?.id || data.threads[0]?.id || null;
    toggleDashboard(true);
    renderDashboard();
  } catch (error) {
    localStorage.removeItem("tt_token");
    state.token = "";
    state.dashboard = null;
    state.selectedThreadId = null;
    toggleDashboard(false);
    setFeedback(refs.authFeedback, error.message, "error");
  }
}

refs.authForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(event.currentTarget);
  const payload = Object.fromEntries(formData.entries());
  try {
    const data = await apiPost("/api/auth", payload);
    state.token = data.token;
    localStorage.setItem("tt_token", data.token);
    setFeedback(
      refs.authFeedback,
      data.created ? "账户已自动创建，欢迎进入 TokenTrader。" : "登录成功，工作台已同步。",
      "success"
    );
    await loadDashboard();
  } catch (error) {
    setFeedback(refs.authFeedback, error.message, "error");
  }
});

refs.signoutButton.addEventListener("click", () => {
  localStorage.removeItem("tt_token");
  state.token = "";
  state.dashboard = null;
  state.selectedThreadId = null;
  toggleDashboard(false);
  setFeedback(refs.authFeedback, "你已退出当前会话。", "success");
});

refs.threadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(event.currentTarget);
  const payload = Object.fromEntries(formData.entries());
  try {
    const data = await apiPost("/api/threads", { token: state.token, ...payload });
    event.currentTarget.reset();
    state.selectedThreadId = data.thread.id;
    setFeedback(refs.threadFeedback, "讨论已发布。", "success");
    await loadDashboard(state.selectedThreadId);
  } catch (error) {
    setFeedback(refs.threadFeedback, error.message, "error");
  }
});

refs.replyForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.selectedThreadId) {
    setFeedback(refs.replyFeedback, "请先选择一个 thread。", "error");
    return;
  }
  const formData = new FormData(event.currentTarget);
  const payload = Object.fromEntries(formData.entries());
  try {
    await apiPost("/api/posts", {
      token: state.token,
      thread_id: state.selectedThreadId,
      ...payload,
    });
    event.currentTarget.reset();
    setFeedback(refs.replyFeedback, "回复已发送。", "success");
    await loadDashboard(state.selectedThreadId);
  } catch (error) {
    setFeedback(refs.replyFeedback, error.message, "error");
  }
});

refs.taskForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(event.currentTarget);
  const payload = Object.fromEntries(formData.entries());
  payload.reward_mana = Number(payload.reward_mana);
  payload.prompt_tokens = Number(payload.prompt_tokens);
  payload.max_latency_ms = Number(payload.max_latency_ms);
  payload.budget_credits = Number(payload.budget_credits);
  payload.create_thread = formData.get("create_thread") === "on";
  try {
    const data = await apiPost("/api/tasks", { token: state.token, ...payload });
    state.routingPreview = data.quote_candidates || [];
    event.currentTarget.reset();
    event.currentTarget.querySelector("[name='reward_mana']").value = 48;
    event.currentTarget.querySelector("[name='prompt_tokens']").value = 1600;
    event.currentTarget.querySelector("[name='max_latency_ms']").value = 1600;
    event.currentTarget.querySelector("[name='budget_credits']").value = 1.2;
    event.currentTarget.querySelector("[name='task_type']").value = "analysis";
    event.currentTarget.querySelector("[name='create_thread']").checked = true;
    setFeedback(refs.taskFeedback, "任务已挂出，赏金已锁定。", "success");
    state.selectedThreadId = data.task.thread_id || state.selectedThreadId;
    await loadDashboard(state.selectedThreadId);
  } catch (error) {
    setFeedback(refs.taskFeedback, error.message, "error");
  }
});

refs.threadList.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-thread-id]");
  if (!button) return;
  state.selectedThreadId = Number(button.dataset.threadId);
  await loadDashboard(state.selectedThreadId);
});

refs.taskList.addEventListener("click", async (event) => {
  const actionButton = event.target.closest("[data-action='claim-task']");
  if (!actionButton) return;
  const taskId = Number(actionButton.dataset.taskId);
  try {
    await apiPost("/api/tasks/claim", { token: state.token, task_id: taskId });
    setFeedback(refs.taskFeedback, "任务已认领。", "success");
    await loadDashboard(state.selectedThreadId);
  } catch (error) {
    setFeedback(refs.taskFeedback, error.message, "error");
  }
});

refs.taskList.addEventListener("submit", async (event) => {
  const form = event.target.closest("[data-action='complete-task']");
  if (!form) return;
  event.preventDefault();
  const formData = new FormData(form);
  const payload = Object.fromEntries(formData.entries());
  try {
    await apiPost("/api/tasks/complete", {
      token: state.token,
      task_id: Number(form.dataset.taskId),
      ...payload,
    });
    setFeedback(refs.taskFeedback, "任务已完成，mana 已结算。", "success");
    await loadDashboard(state.selectedThreadId);
  } catch (error) {
    setFeedback(refs.taskFeedback, error.message, "error");
  }
});

if (state.token) {
  loadDashboard();
} else {
  toggleDashboard(false);
}
