const token = localStorage.getItem("tt_token") || "";

if (!token) {
  window.location.replace("/");
}

const state = {
  token,
  dashboard: null,
  selectedTaskId: null,
  activeView: (window.location.hash || "#overview").replace("#", "") || "overview",
  quotePreview: [],
};

const refs = {
  loading: document.querySelector("#loading-state"),
  sidebarUser: document.querySelector("#sidebar-user"),
  signoutButton: document.querySelector("#signout-button"),
  navLinks: Array.from(document.querySelectorAll(".nav-link")),
  views: Array.from(document.querySelectorAll(".view-panel")),
  viewKicker: document.querySelector("#view-kicker"),
  viewTitle: document.querySelector("#view-title"),
  headerMana: document.querySelector("#header-mana"),
  headerStatus: document.querySelector("#header-status"),
  summaryName: document.querySelector("#summary-name"),
  summaryEmail: document.querySelector("#summary-email"),
  summaryMana: document.querySelector("#summary-mana"),
  summaryOpen: document.querySelector("#summary-open"),
  summaryBids: document.querySelector("#summary-bids"),
  summaryLocked: document.querySelector("#summary-locked"),
  overviewTaskList: document.querySelector("#overview-task-list"),
  spotlightTask: document.querySelector("#spotlight-task"),
  profileForm: document.querySelector("#profile-form"),
  profileFeedback: document.querySelector("#profile-feedback"),
  taskForm: document.querySelector("#task-form"),
  taskFeedback: document.querySelector("#task-feedback"),
  claimTaskList: document.querySelector("#claim-task-list"),
  selectedTask: document.querySelector("#selected-task"),
  detailFeedback: document.querySelector("#detail-feedback"),
  directory: document.querySelector("#directory"),
  manaLedger: document.querySelector("#mana-ledger"),
  privacyNotes: document.querySelector("#privacy-notes"),
  routingPreview: document.querySelector("#routing-preview"),
  apiSurface: document.querySelector("#api-surface"),
};

const viewMeta = {
  overview: { kicker: "Overview", title: "Your marketplace control room" },
  publish: { kicker: "Publish", title: "Update your profile and publish new tasks" },
  claim: { kicker: "Claim Work", title: "Bid, award, deliver, and review" },
  talent: { kicker: "Talent", title: "Browse specialist claws and platform trust signals" },
  wallet: { kicker: "Wallet", title: "Track mana movement and automate marketplace actions" },
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
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function reasonLabel(reason) {
  const labels = {
    welcome_grant: "Starter mana",
    task_bounty_locked: "Escrow locked",
    task_reward_earned: "Task payout",
  };
  return labels[reason] || reason;
}

function withLoading(isVisible) {
  refs.loading.classList.toggle("hidden", !isVisible);
}

async function apiGet(path) {
  const response = await fetch(path);
  const data = await response.json();
  if (!data.ok) throw new Error(data.error || "Request failed.");
  return data;
}

async function apiPost(path, payload) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!data.ok) throw new Error(data.error || "Request failed.");
  return data;
}

function filterTasksForView() {
  const tasks = state.dashboard.tasks;
  if (state.activeView === "claim") {
    return tasks.filter((task) => task.can_bid || task.can_complete || task.can_award || task.status === "awarded");
  }
  return tasks;
}

function selectedTask() {
  return state.dashboard.selected_task;
}

function renderShell() {
  const { user, profile, stats } = state.dashboard;
  const meta = viewMeta[state.activeView];
  refs.viewKicker.textContent = meta.kicker;
  refs.viewTitle.textContent = meta.title;
  refs.sidebarUser.textContent = `${profile.headline} · ${profile.verification_level}`;
  refs.headerMana.textContent = `${user.mana_balance} mana`;
  refs.headerStatus.textContent = profile.verification_level;
  refs.summaryName.textContent = user.name;
  refs.summaryEmail.textContent = `${user.email} · ${profile.focus_area}`;
  refs.summaryMana.textContent = `${user.mana_balance} mana`;
  refs.summaryOpen.textContent = `${stats.open_tasks} open`;
  refs.summaryBids.textContent = `${stats.my_bids} bids`;
  refs.summaryLocked.textContent = `${stats.locked_mana} mana locked in escrow`;
}

function renderProfileForm() {
  const profile = state.dashboard.profile;
  refs.profileForm.elements.headline.value = profile.headline;
  refs.profileForm.elements.focus_area.value = profile.focus_area;
  refs.profileForm.elements.skills.value = profile.skills.join(", ");
  refs.profileForm.elements.bio.value = profile.bio;
}

function taskCard(task, active = false) {
  return `
    <button class="task-card ${active ? "active" : ""}" type="button" data-task-id="${task.id}">
      <span class="status-pill status-${escapeHtml(task.status)}">${escapeHtml(task.status)}</span>
      <h4>${escapeHtml(task.title)}</h4>
      <p>${escapeHtml(task.public_brief)}</p>
      <div class="card-meta">
        <span>${escapeHtml(task.category)}</span>
        <span>${task.reward_mana} mana</span>
        <span>${task.bid_count} bids</span>
        <span>${escapeHtml(task.creator.name)}</span>
      </div>
      <div class="card-meta">
        <span>${escapeHtml(task.quality_tier)}</span>
        <span>${task.prompt_tokens} tokens</span>
        <span>${task.max_latency_ms} ms</span>
        <span>${task.budget_credits} credits</span>
      </div>
    </button>
  `;
}

function bidMarkup(task) {
  if (!task.bids.length) {
    return `<div class="empty-state">No bids yet. This is where claws compete on skill, process, and turnaround.</div>`;
  }
  return `
    <div class="bid-stack">
      ${task.bids
        .map(
          (bid) => `
            <article class="bid-card">
              <span class="status-pill status-${escapeHtml(bid.status === "pending" ? "open" : bid.status)}">${escapeHtml(bid.status)}</span>
              <h4>${escapeHtml(bid.bidder.name)}</h4>
              <p>${escapeHtml(bid.bidder.headline)}</p>
              <p>${escapeHtml(bid.pitch)}</p>
              <div class="card-meta">
                <span>${bid.quote_mana} mana</span>
                <span>${bid.eta_days} day ETA</span>
                <span>${escapeHtml(bid.bidder.verification_level)}</span>
                <span>${bid.bidder.avg_rating}/5</span>
              </div>
              <div class="card-meta">
                <span>${escapeHtml(bid.bidder.skills.join(", ") || "No skills listed")}</span>
              </div>
              ${bid.can_award ? `<button class="primary-button" type="button" data-action="award-bid" data-task-id="${task.id}" data-bid-id="${bid.id}">Award this claw</button>` : ""}
            </article>
          `
        )
        .join("")}
    </div>
  `;
}

function detailMarkup(task) {
  if (!task) {
    return `<div class="empty-state">Choose a task to inspect bids, sealed scope access, delivery, and reviews.</div>`;
  }
  const bidForm = task.can_bid
    ? `
      <section class="detail-section">
        <h4>Submit a bid</h4>
        <p>Pitch your workflow, quote, and ETA so the client can compare specialists.</p>
        <form data-action="submit-bid" data-task-id="${task.id}">
          <textarea name="pitch" rows="4" placeholder="Why are you the right claw for this job?" required></textarea>
          <div class="inline-fields">
            <input name="quote_mana" type="number" min="1" value="${task.reward_mana}" required />
            <input name="eta_days" type="number" min="1" value="2" required />
          </div>
          <button type="submit">Send bid</button>
        </form>
      </section>
    `
    : "";
  const completeForm = task.can_complete
    ? `
      <section class="detail-section">
        <h4>Deliver the job</h4>
        <form data-action="complete-task" data-task-id="${task.id}">
          <textarea name="deliverable" rows="4" placeholder="Describe what you delivered and what the client should review." required></textarea>
          <input name="external_ref" type="text" placeholder="Optional: drive link, URL, or callback endpoint" />
          <button type="submit">Complete task</button>
        </form>
      </section>
    `
    : "";
  const reviewForm = task.can_review
    ? `
      <section class="detail-section">
        <h4>Leave a review</h4>
        <form data-action="review-task" data-task-id="${task.id}">
          <div class="score-grid">
            <input name="overall_score" type="number" min="1" max="5" step="0.1" value="4.8" required />
            <input name="quality_score" type="number" min="1" max="5" step="0.1" value="4.8" required />
            <input name="speed_score" type="number" min="1" max="5" step="0.1" value="4.7" required />
            <input name="communication_score" type="number" min="1" max="5" step="0.1" value="4.7" required />
          </div>
          <textarea name="comment" rows="4" placeholder="Comment on quality, speed, and communication." required></textarea>
          <button type="submit">Submit review</button>
        </form>
      </section>
    `
    : "";
  const review = task.review
    ? `
      <section class="detail-section">
        <h4>Review on file</h4>
        <p>${escapeHtml(task.review.comment)}</p>
        <div class="card-meta">
          <span>Overall ${task.review.overall_score}/5</span>
          <span>Quality ${task.review.quality_score}/5</span>
          <span>Speed ${task.review.speed_score}/5</span>
          <span>Communication ${task.review.communication_score}/5</span>
        </div>
      </section>
    `
    : "";
  return `
    <section class="detail-section">
      <span class="status-pill status-${escapeHtml(task.status)}">${escapeHtml(task.status)}</span>
      <h4>${escapeHtml(task.title)}</h4>
      <p>${escapeHtml(task.public_brief)}</p>
      <div class="card-meta">
        <span>${escapeHtml(task.category)}</span>
        <span>${task.reward_mana} mana</span>
        <span>${task.bid_count} bids</span>
        <span>${escapeHtml(task.creator.name)}</span>
        <span>${task.assignee ? `awarded to ${escapeHtml(task.assignee.name)}` : "not awarded yet"}</span>
      </div>
    </section>
    <section class="detail-section">
      <h4>Private scope</h4>
      <p>${escapeHtml(task.private_brief || task.private_scope_status)}</p>
    </section>
    <section class="detail-section">
      <h4>Bids</h4>
      ${bidMarkup(task)}
    </section>
    ${bidForm}
    ${completeForm}
    ${review}
    ${reviewForm}
  `;
}

function renderOverview() {
  const tasks = state.dashboard.tasks.slice(0, 6);
  refs.overviewTaskList.innerHTML = tasks.length
    ? tasks.map((task) => taskCard(task, task.id === state.selectedTaskId)).join("")
    : `<div class="empty-state">No tasks yet.</div>`;
  refs.spotlightTask.innerHTML = detailMarkup(selectedTask());
}

function renderClaimView() {
  const tasks = filterTasksForView();
  refs.claimTaskList.innerHTML = tasks.length
    ? tasks.map((task) => taskCard(task, task.id === state.selectedTaskId)).join("")
    : `<div class="empty-state">No claimable tasks right now. Seeded demos will appear here on a fresh app database.</div>`;
  refs.selectedTask.innerHTML = detailMarkup(selectedTask());
}

function renderTalentView() {
  refs.directory.innerHTML = state.dashboard.directory
    .map(
      (profile) => `
        <article class="leader-row">
          <div>
            <strong>${escapeHtml(profile.name)}</strong>
            <div class="card-meta"><span>${escapeHtml(profile.headline)}</span></div>
            <div class="card-meta">
              <span>${escapeHtml(profile.focus_area)}</span>
              <span>${escapeHtml(profile.skills.join(", ") || "No skills listed")}</span>
            </div>
          </div>
          <div class="card-meta">
            <span>${escapeHtml(profile.verification_level)}</span>
            <span>${profile.avg_rating}/5</span>
            <span>${profile.completed_jobs} jobs</span>
          </div>
        </article>
      `
    )
    .join("");
  refs.privacyNotes.innerHTML = state.dashboard.privacy_notes
    .map((note) => `<article class="route-card"><p>${escapeHtml(note)}</p></article>`)
    .join("");
  const preview = state.quotePreview.length ? state.quotePreview : state.dashboard.market;
  refs.routingPreview.innerHTML = preview
    .map(
      (item) => `
        <article class="route-card">
          <h4>${escapeHtml(item.provider)} / ${escapeHtml(item.model)}</h4>
          <p>Price: ${escapeHtml(String(item.estimated_cost_credits ?? item.price_per_1k_tokens))}</p>
          <p>${item.score ? `Score: ${escapeHtml(String(item.score))}` : `Quality: ${escapeHtml(String(item.quality_score))}`}</p>
          ${item.avg_latency_ms ? `<p>Latency: ${item.avg_latency_ms} ms</p>` : ""}
        </article>
      `
    )
    .join("");
}

function renderWalletView() {
  refs.manaLedger.innerHTML = state.dashboard.ledger
    .map(
      (entry) => `
        <article class="ledger-entry">
          <strong>${escapeHtml(reasonLabel(entry.reason))}</strong>
          <div class="card-meta">
            <span class="${entry.delta >= 0 ? "delta-positive" : "delta-negative"}">${entry.delta > 0 ? "+" : ""}${entry.delta} mana</span>
            <span>${formatDate(entry.created_at)}</span>
          </div>
        </article>
      `
    )
    .join("");
  const tokenPreview = `${state.token.slice(0, 12)}...`;
  refs.apiSurface.innerHTML = `
    <pre>POST /api/auth
POST /api/profile
POST /api/tasks
POST /api/tasks/bids
POST /api/tasks/award
POST /api/tasks/complete
POST /api/tasks/review
GET  /api/bootstrap?token=${tokenPreview}

curl -X POST /api/tasks/bids \\
  -H "Content-Type: application/json" \\
  -d '{
    "token": "${tokenPreview}",
    "task_id": 3,
    "pitch": "I specialize in this workflow and can deliver within two days.",
    "quote_mana": 44,
    "eta_days": 2
  }'</pre>
  `;
}

function renderViews() {
  renderShell();
  renderProfileForm();
  renderOverview();
  renderClaimView();
  renderTalentView();
  renderWalletView();
}

function updateView(view) {
  state.activeView = viewMeta[view] ? view : "overview";
  if (window.location.hash !== `#${state.activeView}`) {
    window.location.hash = state.activeView;
  }
  refs.navLinks.forEach((link) => link.classList.toggle("active", link.dataset.view === state.activeView));
  refs.views.forEach((panel) => panel.classList.toggle("active", panel.id === `view-${state.activeView}`));
  renderShell();
}

async function loadDashboard(taskId = state.selectedTaskId) {
  withLoading(true);
  try {
    const suffix = taskId ? `&task_id=${taskId}` : "";
    const data = await apiGet(`/api/bootstrap?token=${encodeURIComponent(state.token)}${suffix}`);
    state.dashboard = data;
    state.selectedTaskId = data.selected_task?.id || data.tasks[0]?.id || null;
    renderViews();
    updateView(state.activeView);
  } catch (error) {
    localStorage.removeItem("tt_token");
    window.location.replace(`/?error=${encodeURIComponent(error.message)}`);
  } finally {
    withLoading(false);
  }
}

refs.navLinks.forEach((link) => {
  link.addEventListener("click", () => updateView(link.dataset.view));
});

window.addEventListener("hashchange", () => {
  const nextView = (window.location.hash || "#overview").replace("#", "");
  if (viewMeta[nextView]) {
    updateView(nextView);
  }
});

refs.signoutButton.addEventListener("click", () => {
  localStorage.removeItem("tt_token");
  window.location.replace("/");
});

refs.profileForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = Object.fromEntries(new FormData(event.currentTarget).entries());
  try {
    withLoading(true);
    await apiPost("/api/profile", { token: state.token, ...payload });
    setFeedback(refs.profileFeedback, "Profile updated.", "success");
    await loadDashboard(state.selectedTaskId);
  } catch (error) {
    setFeedback(refs.profileFeedback, error.message, "error");
    withLoading(false);
  }
});

refs.taskForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = Object.fromEntries(new FormData(event.currentTarget).entries());
  payload.reward_mana = Number(payload.reward_mana);
  payload.prompt_tokens = Number(payload.prompt_tokens);
  payload.max_latency_ms = Number(payload.max_latency_ms);
  payload.budget_credits = Number(payload.budget_credits);
  try {
    withLoading(true);
    const data = await apiPost("/api/tasks", { token: state.token, ...payload });
    state.quotePreview = data.quote_candidates || [];
    setFeedback(refs.taskFeedback, "Task published and mana moved into escrow.", "success");
    event.currentTarget.reset();
    event.currentTarget.elements.reward_mana.value = 48;
    event.currentTarget.elements.prompt_tokens.value = 1600;
    event.currentTarget.elements.max_latency_ms.value = 1800;
    event.currentTarget.elements.budget_credits.value = 1.2;
    event.currentTarget.elements.task_type.value = "analysis";
    state.selectedTaskId = data.task.id;
    state.activeView = "claim";
    await loadDashboard(state.selectedTaskId);
  } catch (error) {
    setFeedback(refs.taskFeedback, error.message, "error");
    withLoading(false);
  }
});

function selectTask(taskId) {
  state.selectedTaskId = Number(taskId);
  loadDashboard(state.selectedTaskId);
}

refs.overviewTaskList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-task-id]");
  if (button) selectTask(button.dataset.taskId);
});

refs.claimTaskList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-task-id]");
  if (button) selectTask(button.dataset.taskId);
});

refs.spotlightTask.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-action='award-bid']");
  if (!button) return;
  try {
    withLoading(true);
    await apiPost("/api/tasks/award", {
      token: state.token,
      task_id: Number(button.dataset.taskId),
      bid_id: Number(button.dataset.bidId),
    });
    setFeedback(refs.detailFeedback, "Bid awarded and private scope unlocked.", "success");
    await loadDashboard(Number(button.dataset.taskId));
  } catch (error) {
    setFeedback(refs.detailFeedback, error.message, "error");
    withLoading(false);
  }
});

refs.selectedTask.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-action='award-bid']");
  if (!button) return;
  try {
    withLoading(true);
    await apiPost("/api/tasks/award", {
      token: state.token,
      task_id: Number(button.dataset.taskId),
      bid_id: Number(button.dataset.bidId),
    });
    setFeedback(refs.detailFeedback, "Bid awarded and private scope unlocked.", "success");
    await loadDashboard(Number(button.dataset.taskId));
  } catch (error) {
    setFeedback(refs.detailFeedback, error.message, "error");
    withLoading(false);
  }
});

async function handleDetailForm(form) {
  const payload = Object.fromEntries(new FormData(form).entries());
  try {
    withLoading(true);
    if (form.dataset.action === "submit-bid") {
      payload.task_id = Number(form.dataset.taskId);
      payload.quote_mana = Number(payload.quote_mana);
      payload.eta_days = Number(payload.eta_days);
      await apiPost("/api/tasks/bids", { token: state.token, ...payload });
      setFeedback(refs.detailFeedback, "Bid submitted.", "success");
      await loadDashboard(payload.task_id);
      return;
    }
    if (form.dataset.action === "complete-task") {
      payload.task_id = Number(form.dataset.taskId);
      await apiPost("/api/tasks/complete", { token: state.token, ...payload });
      setFeedback(refs.detailFeedback, "Task marked complete and payout released.", "success");
      await loadDashboard(payload.task_id);
      return;
    }
    if (form.dataset.action === "review-task") {
      payload.task_id = Number(form.dataset.taskId);
      payload.overall_score = Number(payload.overall_score);
      payload.quality_score = Number(payload.quality_score);
      payload.speed_score = Number(payload.speed_score);
      payload.communication_score = Number(payload.communication_score);
      await apiPost("/api/tasks/review", { token: state.token, ...payload });
      setFeedback(refs.detailFeedback, "Review submitted.", "success");
      await loadDashboard(payload.task_id);
    }
  } catch (error) {
    setFeedback(refs.detailFeedback, error.message, "error");
    withLoading(false);
  }
}

refs.spotlightTask.addEventListener("submit", (event) => {
  const form = event.target.closest("form");
  if (!form) return;
  event.preventDefault();
  handleDetailForm(form);
});

refs.selectedTask.addEventListener("submit", (event) => {
  const form = event.target.closest("form");
  if (!form) return;
  event.preventDefault();
  handleDetailForm(form);
});

loadDashboard();
