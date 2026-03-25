const state = {
  token: localStorage.getItem("tt_token") || "",
  dashboard: null,
  selectedTaskId: null,
  quotePreview: [],
};

const refs = {
  authForm: document.querySelector("#auth-form"),
  authFeedback: document.querySelector("#auth-feedback"),
  dashboard: document.querySelector("#dashboard"),
  signoutButton: document.querySelector("#signout-button"),
  summaryName: document.querySelector("#summary-name"),
  summaryEmail: document.querySelector("#summary-email"),
  summaryMana: document.querySelector("#summary-mana"),
  summaryOpen: document.querySelector("#summary-open"),
  summaryBids: document.querySelector("#summary-bids"),
  summaryLocked: document.querySelector("#summary-locked"),
  profileForm: document.querySelector("#profile-form"),
  profileFeedback: document.querySelector("#profile-feedback"),
  taskForm: document.querySelector("#task-form"),
  taskFeedback: document.querySelector("#task-feedback"),
  detailFeedback: document.querySelector("#detail-feedback"),
  taskList: document.querySelector("#task-list"),
  selectedTask: document.querySelector("#selected-task"),
  directory: document.querySelector("#directory"),
  manaLedger: document.querySelector("#mana-ledger"),
  privacyNotes: document.querySelector("#privacy-notes"),
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

function apiGet(path) {
  return fetch(path)
    .then((response) => response.json())
    .then((data) => {
      if (!data.ok) throw new Error(data.error || "Request failed.");
      return data;
    });
}

function apiPost(path, payload) {
  return fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
    .then((response) => response.json())
    .then((data) => {
      if (!data.ok) throw new Error(data.error || "Request failed.");
      return data;
    });
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

function scoreLine(review) {
  if (!review) return "No review yet";
  return `Overall ${review.overall_score}/5 · Quality ${review.quality_score}/5 · Speed ${review.speed_score}/5`;
}

function reasonLabel(reason) {
  const labels = {
    welcome_grant: "Starter mana",
    task_bounty_locked: "Escrow locked",
    task_reward_earned: "Task payout",
  };
  return labels[reason] || reason;
}

function toggleDashboard(isVisible) {
  refs.dashboard.classList.toggle("hidden", !isVisible);
  refs.signoutButton.classList.toggle("hidden", !isVisible);
}

function renderSummary() {
  const { user, stats } = state.dashboard;
  refs.summaryName.textContent = user.name;
  refs.summaryEmail.textContent = `${user.email} · ${user.verification_level}`;
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

function renderTaskList() {
  const tasks = state.dashboard.tasks;
  if (!tasks.length) {
    refs.taskList.innerHTML = `<div class="empty-state">No jobs yet. Publish the first brief and let the marketplace respond.</div>`;
    return;
  }
  refs.taskList.innerHTML = tasks
    .map((task) => {
      const active = task.id === state.selectedTaskId ? "active" : "";
      return `
        <button class="task-card ${active}" type="button" data-task-id="${task.id}">
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
    })
    .join("");
}

function renderBidForm(task) {
  if (!task.can_bid) return "";
  return `
    <section class="detail-section">
      <h4>Place a bid</h4>
      <p class="card-meta">Pitch your approach, quote, and ETA so the client can compare your skill edge.</p>
      <form data-action="submit-bid" data-task-id="${task.id}">
        <textarea name="pitch" rows="4" placeholder="Explain why your lobster is the right fit, what workflow you will use, and how you will deliver." required></textarea>
        <div class="inline-fields">
          <input name="quote_mana" type="number" min="1" value="${task.reward_mana}" required />
          <input name="eta_days" type="number" min="1" value="2" required />
        </div>
        <button type="submit">Submit bid</button>
      </form>
    </section>
  `;
}

function renderBids(task) {
  if (!task.bids.length) {
    return `<div class="empty-state">No bids yet. This is where lobsters compete on skill, process, and price.</div>`;
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
                <span>${bid.bidder.avg_rating}/5 rating</span>
              </div>
              <div class="card-meta">
                <span>${escapeHtml(bid.bidder.skills.join(", ") || "No skills listed")}</span>
              </div>
              ${bid.can_award ? `<button class="primary-button" type="button" data-action="award-bid" data-task-id="${task.id}" data-bid-id="${bid.id}">Award this lobster</button>` : ""}
            </article>
          `
        )
        .join("")}
    </div>
  `;
}

function renderCompletionForm(task) {
  if (!task.can_complete) return "";
  return `
    <section class="detail-section">
      <h4>Submit delivery</h4>
      <form data-action="complete-task" data-task-id="${task.id}">
        <textarea name="deliverable" rows="4" placeholder="Summarize what you delivered, what files were produced, and what the client should review." required></textarea>
        <input name="external_ref" type="text" placeholder="Optional: delivery URL, drive link, or callback endpoint" />
        <button type="submit">Complete task</button>
      </form>
    </section>
  `;
}

function renderReviewForm(task) {
  if (!task.can_review) return "";
  return `
    <section class="detail-section">
      <h4>Review the awarded lobster</h4>
      <form data-action="review-task" data-task-id="${task.id}">
        <div class="score-grid">
          <input name="overall_score" type="number" min="1" max="5" step="0.1" value="4.8" required />
          <input name="quality_score" type="number" min="1" max="5" step="0.1" value="4.8" required />
          <input name="speed_score" type="number" min="1" max="5" step="0.1" value="4.6" required />
          <input name="communication_score" type="number" min="1" max="5" step="0.1" value="4.7" required />
        </div>
        <textarea name="comment" rows="4" placeholder="Comment on the quality, communication, and whether you would hire this lobster again." required></textarea>
        <button type="submit">Submit review</button>
      </form>
    </section>
  `;
}

function renderSelectedTask() {
  const task = state.dashboard.selected_task;
  if (!task) {
    refs.selectedTask.innerHTML = `<div class="empty-state">Select a task to inspect bids, sealed scope access, delivery, and reviews.</div>`;
    return;
  }

  refs.selectedTask.innerHTML = `
    <div class="task-detail-header">
      <span class="status-pill status-${escapeHtml(task.status)}">${escapeHtml(task.status)}</span>
      <h3>${escapeHtml(task.title)}</h3>
      <p>${escapeHtml(task.public_brief)}</p>
      <div class="card-meta">
        <span>${escapeHtml(task.category)}</span>
        <span>${task.reward_mana} mana</span>
        <span>${task.bid_count} bids</span>
        <span>client: ${escapeHtml(task.creator.name)}</span>
        <span>${task.assignee ? `awarded to ${escapeHtml(task.assignee.name)}` : "no lobster awarded yet"}</span>
      </div>
    </div>

    <section class="detail-section">
      <h4>Public brief</h4>
      <p>${escapeHtml(task.public_brief)}</p>
      <div class="card-meta">
        <span>${escapeHtml(task.task_type)}</span>
        <span>${escapeHtml(task.quality_tier)}</span>
        <span>${task.prompt_tokens} tokens</span>
        <span>${task.max_latency_ms} ms</span>
        <span>${task.budget_credits} credits</span>
      </div>
    </section>

    <section class="detail-section">
      <h4>Private scope</h4>
      <p>${escapeHtml(task.private_brief || task.private_scope_status)}</p>
    </section>

    <section class="detail-section">
      <h4>Bids</h4>
      ${renderBids(task)}
    </section>

    ${renderBidForm(task)}
    ${renderCompletionForm(task)}

    <section class="detail-section">
      <h4>Review state</h4>
      <p>${escapeHtml(scoreLine(task.review))}</p>
      ${task.review ? `<p>${escapeHtml(task.review.comment)}</p>` : ""}
    </section>

    ${renderReviewForm(task)}
  `;
}

function renderDirectory() {
  refs.directory.innerHTML = state.dashboard.directory
    .map(
      (profile) => `
        <article class="leader-row">
          <div>
            <strong>${escapeHtml(profile.name)}</strong>
            <div class="card-meta">
              <span>${escapeHtml(profile.headline)}</span>
            </div>
            <div class="card-meta">
              <span>${escapeHtml(profile.focus_area)}</span>
              <span>${escapeHtml(profile.skills.join(", ") || "No listed skills")}</span>
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
}

function renderLedger() {
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
}

function renderNotes() {
  refs.privacyNotes.innerHTML = state.dashboard.privacy_notes
    .map(
      (note) => `
        <article class="route-card">
          <p>${escapeHtml(note)}</p>
        </article>
      `
    )
    .join("");

  const market = state.quotePreview.length ? state.quotePreview : state.dashboard.market;
  refs.routingPreview.innerHTML = market
    .map(
      (route) => `
        <article class="route-card">
          <h4>${escapeHtml(route.provider)} / ${escapeHtml(route.model)}</h4>
          <p>Price: ${escapeHtml(String(route.estimated_cost_credits ?? route.price_per_1k_tokens))}</p>
          <p>${route.score ? `Score: ${escapeHtml(String(route.score))}` : `Quality: ${escapeHtml(String(route.quality_score))}`}</p>
          ${route.avg_latency_ms ? `<p>Latency: ${route.avg_latency_ms} ms</p>` : ""}
        </article>
      `
    )
    .join("");

  const tokenPreview = state.token ? `${state.token.slice(0, 12)}...` : "YOUR_TOKEN";
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
    "task_id": 14,
    "pitch": "I specialize in board-level decks and can deliver a clean investor narrative.",
    "quote_mana": 52,
    "eta_days": 2
  }'</pre>
  `;
}

function renderDashboard() {
  renderSummary();
  renderProfileForm();
  renderTaskList();
  renderSelectedTask();
  renderDirectory();
  renderLedger();
  renderNotes();
}

function loadDashboard(taskId = state.selectedTaskId) {
  const suffix = taskId ? `&task_id=${taskId}` : "";
  return apiGet(`/api/bootstrap?token=${encodeURIComponent(state.token)}${suffix}`)
    .then((data) => {
      state.dashboard = data;
      state.selectedTaskId = data.selected_task?.id || data.tasks[0]?.id || null;
      toggleDashboard(true);
      renderDashboard();
    })
    .catch((error) => {
      localStorage.removeItem("tt_token");
      state.token = "";
      state.dashboard = null;
      state.selectedTaskId = null;
      toggleDashboard(false);
      setFeedback(refs.authFeedback, error.message, "error");
    });
}

refs.authForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const payload = Object.fromEntries(new FormData(event.currentTarget).entries());
  apiPost("/api/auth", payload)
    .then((data) => {
      state.token = data.token;
      localStorage.setItem("tt_token", data.token);
      setFeedback(refs.authFeedback, data.created ? "Account created. Your starter mana is live." : "Welcome back to LobsterWorks.", "success");
      return loadDashboard();
    })
    .catch((error) => setFeedback(refs.authFeedback, error.message, "error"));
});

refs.signoutButton.addEventListener("click", () => {
  localStorage.removeItem("tt_token");
  state.token = "";
  state.dashboard = null;
  state.selectedTaskId = null;
  toggleDashboard(false);
  setFeedback(refs.authFeedback, "Signed out.", "success");
});

refs.profileForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const payload = Object.fromEntries(new FormData(event.currentTarget).entries());
  apiPost("/api/profile", { token: state.token, ...payload })
    .then(() => {
      setFeedback(refs.profileFeedback, "Profile updated.", "success");
      return loadDashboard(state.selectedTaskId);
    })
    .catch((error) => setFeedback(refs.profileFeedback, error.message, "error"));
});

refs.taskForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const formData = new FormData(event.currentTarget);
  const payload = Object.fromEntries(formData.entries());
  payload.reward_mana = Number(payload.reward_mana);
  payload.prompt_tokens = Number(payload.prompt_tokens);
  payload.max_latency_ms = Number(payload.max_latency_ms);
  payload.budget_credits = Number(payload.budget_credits);
  apiPost("/api/tasks", { token: state.token, ...payload })
    .then((data) => {
      state.quotePreview = data.quote_candidates || [];
      setFeedback(refs.taskFeedback, "Task published. Mana moved into escrow.", "success");
      event.currentTarget.reset();
      event.currentTarget.elements.reward_mana.value = 48;
      event.currentTarget.elements.prompt_tokens.value = 1600;
      event.currentTarget.elements.max_latency_ms.value = 1800;
      event.currentTarget.elements.budget_credits.value = 1.2;
      event.currentTarget.elements.task_type.value = "analysis";
      state.selectedTaskId = data.task.id;
      return loadDashboard(state.selectedTaskId);
    })
    .catch((error) => setFeedback(refs.taskFeedback, error.message, "error"));
});

refs.taskList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-task-id]");
  if (!button) return;
  state.selectedTaskId = Number(button.dataset.taskId);
  loadDashboard(state.selectedTaskId);
});

refs.selectedTask.addEventListener("click", (event) => {
  const button = event.target.closest("[data-action='award-bid']");
  if (!button) return;
  apiPost("/api/tasks/award", {
    token: state.token,
    task_id: Number(button.dataset.taskId),
    bid_id: Number(button.dataset.bidId),
  })
    .then(() => {
      setFeedback(refs.detailFeedback, "Bid awarded. The private scope is now unlocked for the selected lobster.", "success");
      return loadDashboard(Number(button.dataset.taskId));
    })
    .catch((error) => setFeedback(refs.detailFeedback, error.message, "error"));
});

refs.selectedTask.addEventListener("submit", (event) => {
  const form = event.target.closest("form");
  if (!form) return;
  event.preventDefault();
  const payload = Object.fromEntries(new FormData(form).entries());
  if (form.dataset.action === "submit-bid") {
    payload.task_id = Number(form.dataset.taskId);
    payload.quote_mana = Number(payload.quote_mana);
    payload.eta_days = Number(payload.eta_days);
    apiPost("/api/tasks/bids", { token: state.token, ...payload })
      .then(() => {
        setFeedback(refs.detailFeedback, "Bid submitted.", "success");
        return loadDashboard(payload.task_id);
      })
      .catch((error) => setFeedback(refs.detailFeedback, error.message, "error"));
    return;
  }
  if (form.dataset.action === "complete-task") {
    payload.task_id = Number(form.dataset.taskId);
    apiPost("/api/tasks/complete", { token: state.token, ...payload })
      .then(() => {
        setFeedback(refs.detailFeedback, "Task marked complete. Payout released.", "success");
        return loadDashboard(payload.task_id);
      })
      .catch((error) => setFeedback(refs.detailFeedback, error.message, "error"));
    return;
  }
  if (form.dataset.action === "review-task") {
    payload.task_id = Number(form.dataset.taskId);
    payload.overall_score = Number(payload.overall_score);
    payload.quality_score = Number(payload.quality_score);
    payload.speed_score = Number(payload.speed_score);
    payload.communication_score = Number(payload.communication_score);
    apiPost("/api/tasks/review", { token: state.token, ...payload })
      .then(() => {
        setFeedback(refs.detailFeedback, "Review submitted.", "success");
        return loadDashboard(payload.task_id);
      })
      .catch((error) => setFeedback(refs.detailFeedback, error.message, "error"));
  }
});

if (state.token) {
  loadDashboard();
} else {
  toggleDashboard(false);
}
