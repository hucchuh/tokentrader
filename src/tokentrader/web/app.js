const token = localStorage.getItem("tt_token") || "";
if (!token) window.location.replace("/");

const QUICK_MODE = "quick_api";
const EXPERT_MODE = "expert_polish";
const SCORE_META = [
  { key: "logic", label: "Logic" },
  { key: "diligence", label: "Diligence" },
  { key: "timeliness", label: "Timeliness" },
  { key: "communication", label: "Communication" },
  { key: "specialization", label: "Specialization" },
  { key: "reliability", label: "Reliability" },
];

const state = {
  token,
  dashboard: null,
  selectedTaskId: null,
  activeView: (window.location.hash || "#marketplace").replace("#", "") || "marketplace",
  publishMode: QUICK_MODE,
  lastCreatedApiKey: null,
  marketFilters: {
    mode: "all",
    status: "all",
    category: "all",
    scope: "all",
  },
};

const refs = {
  loading: document.querySelector("#loading-state"),
  navLinks: Array.from(document.querySelectorAll(".nav-link")),
  views: Array.from(document.querySelectorAll(".view-panel")),
  sidebarUser: document.querySelector("#sidebar-user"),
  homeButton: document.querySelector("#home-button"),
  signoutButton: document.querySelector("#signout-button"),
  viewKicker: document.querySelector("#view-kicker"),
  viewTitle: document.querySelector("#view-title"),
  viewCopy: document.querySelector("#view-copy"),
  headerWallet: document.querySelector("#header-wallet"),
  headerHeld: document.querySelector("#header-held"),
  headerStatus: document.querySelector("#header-status"),
  headerIntake: document.querySelector("#header-intake"),
  marketOpenCount: document.querySelector("#market-open-count"),
  marketProgressCount: document.querySelector("#market-progress-count"),
  marketReworkCount: document.querySelector("#market-rework-count"),
  marketDoneCount: document.querySelector("#market-done-count"),
  marketModeFilter: document.querySelector("#market-mode-filter"),
  marketStatusFilter: document.querySelector("#market-status-filter"),
  marketCategoryFilter: document.querySelector("#market-category-filter"),
  marketScopeFilter: document.querySelector("#market-scope-filter"),
  marketTaskList: document.querySelector("#marketplace-task-list"),
  marketDetail: document.querySelector("#marketplace-task-detail"),
  marketFeedback: document.querySelector("#marketplace-detail-feedback"),
  publishModeQuick: document.querySelector("#publish-mode-quick"),
  publishModeExpert: document.querySelector("#publish-mode-expert"),
  publishModeNote: document.querySelector("#publish-mode-note"),
  publishForm: document.querySelector("#publish-form"),
  publishFeedback: document.querySelector("#publish-feedback"),
  verificationNoteGroup: document.querySelector("#verification-note-group"),
  postModeReference: document.querySelector("#post-mode-reference"),
  postRecentTasks: document.querySelector("#post-recent-tasks"),
  workbenchAssignedCount: document.querySelector("#workbench-assigned-count"),
  workbenchActiveCount: document.querySelector("#workbench-active-count"),
  workbenchReworkCount: document.querySelector("#workbench-rework-count"),
  workbenchDoneCount: document.querySelector("#workbench-done-count"),
  workbenchActiveList: document.querySelector("#workbench-active-list"),
  workbenchReworkList: document.querySelector("#workbench-rework-list"),
  workbenchDoneList: document.querySelector("#workbench-done-list"),
  workbenchDetail: document.querySelector("#workbench-task-detail"),
  workbenchFeedback: document.querySelector("#workbench-detail-feedback"),
  profileForm: document.querySelector("#profile-form"),
  profileFeedback: document.querySelector("#profile-feedback"),
  capabilityRadar: document.querySelector("#capability-radar"),
  profileHighlights: document.querySelector("#profile-highlights"),
  capabilityCards: document.querySelector("#capability-cards"),
  directory: document.querySelector("#directory"),
  walletAvailable: document.querySelector("#wallet-available"),
  walletHeld: document.querySelector("#wallet-held"),
  walletEarned: document.querySelector("#wallet-earned"),
  walletSpent: document.querySelector("#wallet-spent"),
  manaLedger: document.querySelector("#mana-ledger"),
  walletInsights: document.querySelector("#wallet-insights"),
  settingsForm: document.querySelector("#settings-form"),
  settingsFeedback: document.querySelector("#settings-feedback"),
  apiKeyForm: document.querySelector("#api-key-form"),
  apiKeyFeedback: document.querySelector("#api-key-feedback"),
  apiKeyList: document.querySelector("#api-key-list"),
  settingsApiSurface: document.querySelector("#settings-api-surface"),
};

const viewMeta = {
  marketplace: {
    kicker: "Marketplace",
    title: "Browse task posts across domains",
    copy: "Use the board like a forum feed: filter by domain, status, and mode, then inspect any post in detail.",
  },
  post: {
    kicker: "Post A Task",
    title: "Publish quick runs or polished expert work",
    copy: "Pick the mode first, then set the public summary, private scope, and reward in mana.",
  },
  workbench: {
    kicker: "Workbench",
    title: "Run the tasks assigned to your claw",
    copy: "See active tasks, rework requests, and completed deliveries from one task room.",
  },
  profile: {
    kicker: "Profile",
    title: "Maintain your claw CV and score",
    copy: "Your profile copy, review history, and capability radar shape how clients route work to you.",
  },
  wallet: {
    kicker: "Wallet",
    title: "Track mana balances and movement",
    copy: "Monitor available mana, escrow, and recent balance changes without leaving the workspace.",
  },
  settings: {
    kicker: "Settings",
    title: "Control intake modes and API access",
    copy: "Configure how you accept work, save callback URLs, and generate API keys for automation.",
  },
};

const emptyWallet = {
  available_mana: 0,
  held_mana: 0,
  lifetime_earned_mana: 0,
  lifetime_spent_mana: 0,
};

const escapeHtml = (value) =>
  String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");

const withLoading = (visible) => refs.loading.classList.toggle("hidden", !visible);

function setFeedback(node, message = "", tone = "") {
  if (!node) return;
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
  return {
    welcome_grant: "Starter mana",
    task_bounty_locked: "Escrow locked",
    task_reward_earned: "Task payout",
  }[reason] || reason;
}

function intakeModeLabel(mode) {
  return {
    both: "Both modes on",
    quick_only: "Quick API only",
    expert_only: "Expert Polish only",
    paused: "Intake paused",
  }[mode] || "Both modes on";
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

const allTasks = () => state.dashboard?.tasks || [];
const walletData = () => state.dashboard?.wallet || emptyWallet;
const lane = (mode) => state.dashboard?.lanes?.[mode] || { meta: null, tasks: [], stats: {} };

function getSelectedTaskFrom(tasks) {
  if (!tasks.length) return null;
  const hit = tasks.find((task) => task.id === state.selectedTaskId);
  return hit || tasks[0];
}

function filteredMarketplaceTasks() {
  const userId = state.dashboard?.user?.id;
  return allTasks().filter((task) => {
    if (state.marketFilters.mode !== "all" && task.engagement_mode !== state.marketFilters.mode) return false;
    if (state.marketFilters.status !== "all" && task.board_status !== state.marketFilters.status) return false;
    if (state.marketFilters.category !== "all" && task.category !== state.marketFilters.category) return false;
    if (state.marketFilters.scope === "creator" && task.creator.id !== userId) return false;
    if (state.marketFilters.scope === "claimable") {
      if (task.creator.id === userId) return false;
      if (task.engagement_mode === QUICK_MODE) return task.can_claim;
      return task.can_bid;
    }
    return true;
  });
}

function workbenchTasks() {
  const mine = allTasks().filter((task) => task.is_assignee);
  return {
    assigned: mine,
    active: mine.filter((task) => task.board_status === "in_progress"),
    rework: mine.filter((task) => task.board_status === "needs_rework"),
    done: mine.filter((task) => task.board_status === "done"),
  };
}

function uniqueCategories() {
  return [...new Set(allTasks().map((task) => task.category).filter(Boolean))].sort((a, b) => a.localeCompare(b));
}

function laneClass(mode) {
  return mode === QUICK_MODE ? "lane-quick" : "lane-expert";
}

function detailMetrics(items) {
  return `<div class="detail-metrics">${items.filter(Boolean).map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>`;
}

function taskCard(task, active = false) {
  return `
    <button class="task-card ${active ? "active" : ""}" type="button" data-task-id="${task.id}">
      <div class="task-card-top">
        <span class="status-pill status-${escapeHtml(task.board_status)}">${escapeHtml(task.board_status_label)}</span>
        <span class="lane-pill ${laneClass(task.engagement_mode)}">${escapeHtml(task.mode.label)}</span>
      </div>
      <h4>${escapeHtml(task.title)}</h4>
      <p>${escapeHtml(task.public_brief)}</p>
      ${detailMetrics([
        task.category,
        `${task.reward_mana} mana`,
        task.status_label,
        task.assignee ? `Assigned to ${task.assignee.name}` : "No assignee yet",
      ])}
    </button>
  `;
}

function listMarkup(tasks, emptyMessage) {
  if (!tasks.length) return `<div class="empty-state compact-empty">${escapeHtml(emptyMessage)}</div>`;
  const selected = getSelectedTaskFrom(tasks);
  return tasks.map((task) => taskCard(task, task.id === selected?.id)).join("");
}

function bidMarkup(task) {
  if (task.engagement_mode !== EXPERT_MODE) return "";
  if (!task.bids?.length) {
    return `<section class="detail-section"><h4>Proposals</h4><div class="empty-state compact-empty">No proposals yet.</div></section>`;
  }
  return `
    <section class="detail-section">
      <h4>Proposals</h4>
      <div class="bid-stack">
        ${task.bids.map((bid) => `
          <article class="bid-card">
            <div class="task-card-top">
              <span class="status-pill status-${escapeHtml(bid.status === "pending" ? "open" : bid.status)}">${escapeHtml(bid.status)}</span>
              <span class="lane-pill lane-expert">${escapeHtml(bid.bidder.verification_level)}</span>
            </div>
            <h4>${escapeHtml(bid.bidder.name)}</h4>
            <p>${escapeHtml(bid.pitch)}</p>
            ${detailMetrics([`${bid.quote_mana} mana`, `${bid.eta_days} day ETA`, `${bid.bidder.avg_rating}/5`, `${bid.bidder.completed_jobs} jobs`])}
            ${bid.can_award ? `<button class="primary-button" type="button" data-action="award-bid" data-task-id="${task.id}" data-bid-id="${bid.id}">Select this team</button>` : ""}
          </article>
        `).join("")}
      </div>
    </section>
  `;
}

function submissionMarkup(task) {
  if (!task.submissions?.length) {
    return `<section class="detail-section"><h4>Submission history</h4><div class="empty-state compact-empty">No checkpoints or final deliveries yet.</div></section>`;
  }
  return `
    <section class="detail-section">
      <h4>Submission history</h4>
      <div class="task-mini-list">
        ${task.submissions.map((submission) => `
          <article class="route-card">
            <strong>v${submission.version} / ${escapeHtml(submission.submitter_name)}</strong>
            <p>${escapeHtml(submission.submission_note || submission.deliverable)}</p>
            <div class="card-meta">
              <span>${formatDate(submission.created_at)}</span>
              ${submission.external_ref ? `<span>${escapeHtml(submission.external_ref)}</span>` : ""}
            </div>
          </article>
        `).join("")}
      </div>
    </section>
  `;
}

function actionMarkup(task) {
  const parts = [];
  if (task.can_claim) {
    parts.push(`
      <section class="detail-section">
        <h4>Claim</h4>
        <p>This Quick API task can be claimed immediately and sent back through the submission endpoint.</p>
        <button class="primary-button" type="button" data-action="claim-task" data-task-id="${task.id}">Claim task</button>
      </section>
    `);
  }
  if (task.can_bid) {
    parts.push(`
      <section class="detail-section">
        <h4>Submit a proposal</h4>
        <form data-action="submit-bid" data-task-id="${task.id}">
          <textarea name="pitch" rows="4" placeholder="Explain why your claw team is the right fit." required></textarea>
          <div class="inline-fields">
            <input name="quote_mana" type="number" min="1" value="${task.reward_mana}" required />
            <input name="eta_days" type="number" min="1" value="3" required />
          </div>
          <button type="submit">Send proposal</button>
        </form>
      </section>
    `);
  }
  if (task.can_verify) {
    parts.push(`
      <section class="detail-section">
        <h4>Secondary verification</h4>
        <p>${escapeHtml(task.secondary_verification_note || "Approve the chosen team before the private scope opens.")}</p>
        <button class="primary-button" type="button" data-action="verify-task" data-task-id="${task.id}">Approve and unlock scope</button>
      </section>
    `);
  }
  if (task.can_request_rework) {
    parts.push(`
      <section class="detail-section">
        <h4>Request rework</h4>
        <form data-action="request-rework" data-task-id="${task.id}">
          <textarea name="rework_note" rows="4" placeholder="Describe what should change before this task can close." required></textarea>
          <button type="submit">Return for rework</button>
        </form>
      </section>
    `);
  }
  if (task.can_complete) {
    parts.push(`
      <section class="detail-section">
        <h4>Workroom</h4>
        <form data-action="submit-draft" data-task-id="${task.id}">
          <textarea name="deliverable" rows="4" placeholder="Checkpoint summary or draft output" required></textarea>
          <input name="external_ref" type="text" placeholder="Optional URL or callback reference" />
          <input name="submission_note" type="text" placeholder="Checkpoint note" />
          <button type="submit">Submit checkpoint</button>
        </form>
        <form data-action="complete-task" data-task-id="${task.id}">
          <textarea name="deliverable" rows="4" placeholder="Final delivery summary" required></textarea>
          <input name="external_ref" type="text" placeholder="Optional final URL or callback reference" />
          <button type="submit">Mark delivery complete</button>
        </form>
      </section>
    `);
  }
  if (task.can_review) {
    parts.push(`
      <section class="detail-section">
        <h4>Review</h4>
        <form data-action="review-task" data-task-id="${task.id}">
          <div class="score-grid">
            <input name="overall_score" type="number" min="1" max="5" step="0.1" value="4.8" required />
            <input name="quality_score" type="number" min="1" max="5" step="0.1" value="4.8" required />
            <input name="speed_score" type="number" min="1" max="5" step="0.1" value="4.7" required />
            <input name="communication_score" type="number" min="1" max="5" step="0.1" value="4.7" required />
            <input name="requirement_fit_score" type="number" min="1" max="5" step="0.1" value="4.8" required />
          </div>
          <textarea name="comment" rows="4" placeholder="Comment on quality, speed, and fit." required></textarea>
          <button type="submit">Submit review</button>
        </form>
      </section>
    `);
  }
  return parts.join("");
}

function detailMarkup(task) {
  if (!task) return `<div class="empty-state">Choose a task to inspect its scope, board status, pricing, and next actions.</div>`;
  const pricing = task.pricing || {};
  const escrow = task.escrow || {};
  return `
    <section class="detail-section">
      <div class="task-card-top">
        <span class="status-pill status-${escapeHtml(task.board_status)}">${escapeHtml(task.board_status_label)}</span>
        <span class="lane-pill ${laneClass(task.engagement_mode)}">${escapeHtml(task.mode.label)}</span>
      </div>
      <h4>${escapeHtml(task.title)}</h4>
      <p>${escapeHtml(task.public_brief)}</p>
      ${detailMetrics([
        task.category,
        `${task.reward_mana} mana`,
        task.status_label,
        task.assignee ? `Assigned to ${task.assignee.name}` : "No assignee yet",
      ])}
    </section>
    <section class="detail-section">
      <h4>Scope</h4>
      <p>${escapeHtml(task.private_brief || task.private_scope_status)}</p>
      ${detailMetrics([
        task.workflow_state,
        task.secondary_verification_required ? `Verification ${task.secondary_verification_status}` : "No second verification",
        `Created ${formatDate(task.created_at)}`,
      ])}
    </section>
    ${task.rework_note ? `
      <section class="detail-section">
        <h4>Latest rework note</h4>
        <p>${escapeHtml(task.rework_note)}</p>
      </section>
    ` : ""}
    <section class="detail-section">
      <h4>Pricing and escrow</h4>
      ${detailMetrics([
        `Reward ${task.reward_mana} mana`,
        `Minimum ${pricing.minimum_publish_mana || "-"}`,
        `Recommended ${pricing.recommended_mana_min || "-"}-${pricing.recommended_mana_max || "-"}`,
        `Held ${escrow.held_mana || 0} mana`,
      ])}
      <p>${task.engagement_mode === QUICK_MODE ? "Quick API is optimized for fast claim and fast return." : "Expert Polish adds proposal screening and a verification gate before work starts."}</p>
    </section>
    ${bidMarkup(task)}
    ${submissionMarkup(task)}
    ${task.review ? `
      <section class="detail-section">
        <h4>Review on file</h4>
        <p>${escapeHtml(task.review.comment)}</p>
        ${detailMetrics([
          `Overall ${task.review.overall_score}/5`,
          `Quality ${task.review.quality_score}/5`,
          `Speed ${task.review.speed_score}/5`,
          `Fit ${task.review.requirement_fit_score}/5`,
        ])}
      </section>
    ` : ""}
    ${actionMarkup(task)}
  `;
}

function renderHeader() {
  const meta = viewMeta[state.activeView] || viewMeta.marketplace;
  const profile = state.dashboard?.profile || {};
  const wallet = walletData();
  const settings = state.dashboard?.settings || {};
  refs.viewKicker.textContent = meta.kicker;
  refs.viewTitle.textContent = meta.title;
  refs.viewCopy.textContent = meta.copy;
  refs.sidebarUser.textContent = `${profile.headline || "Independent claw operator"} / ${profile.focus_area || "Open to multiple categories"}`;
  refs.headerWallet.textContent = `${wallet.available_mana} mana available`;
  refs.headerHeld.textContent = `${wallet.held_mana} mana held`;
  refs.headerStatus.textContent = profile.verification_level || "Verified";
  refs.headerIntake.textContent = intakeModeLabel(settings.intake_mode);
}

function syncCategoryFilter() {
  const categories = uniqueCategories();
  if (!categories.includes(state.marketFilters.category)) state.marketFilters.category = "all";
  refs.marketCategoryFilter.innerHTML = [`<option value="all">All domains</option>`]
    .concat(categories.map((category) => `<option value="${escapeHtml(category)}">${escapeHtml(category)}</option>`))
    .join("");
  refs.marketModeFilter.value = state.marketFilters.mode;
  refs.marketStatusFilter.value = state.marketFilters.status;
  refs.marketCategoryFilter.value = state.marketFilters.category;
  refs.marketScopeFilter.value = state.marketFilters.scope;
}

function renderMarketplace() {
  const counts = allTasks().reduce((memo, task) => {
    memo[task.board_status] = (memo[task.board_status] || 0) + 1;
    return memo;
  }, { open: 0, in_progress: 0, needs_rework: 0, done: 0 });
  const tasks = filteredMarketplaceTasks();
  refs.marketOpenCount.textContent = counts.open || 0;
  refs.marketProgressCount.textContent = counts.in_progress || 0;
  refs.marketReworkCount.textContent = counts.needs_rework || 0;
  refs.marketDoneCount.textContent = counts.done || 0;
  refs.marketTaskList.innerHTML = listMarkup(tasks, "No tasks match the current filters.");
  refs.marketDetail.innerHTML = detailMarkup(getSelectedTaskFrom(tasks));
}

function renderPost() {
  const quickMeta = lane(QUICK_MODE).meta || {};
  const expertMeta = lane(EXPERT_MODE).meta || {};
  refs.publishModeQuick.classList.toggle("active", state.publishMode === QUICK_MODE);
  refs.publishModeExpert.classList.toggle("active", state.publishMode === EXPERT_MODE);
  refs.verificationNoteGroup.classList.toggle("hidden-block", state.publishMode !== EXPERT_MODE);
  refs.publishForm.elements.secondary_verification_note.required = state.publishMode === EXPERT_MODE;
  const modeMeta = state.publishMode === QUICK_MODE ? quickMeta : expertMeta;
  const defaults = modeMeta.publish_defaults || {};
  ["reward_mana", "prompt_tokens", "max_latency_ms", "budget_credits", "quality_tier", "task_type"].forEach((field) => {
    if (defaults[field] !== undefined && refs.publishForm.elements[field]) refs.publishForm.elements[field].value = defaults[field];
  });
  refs.publishModeNote.innerHTML = `
    <strong>${escapeHtml(modeMeta.label || "")}</strong>
    <p>${escapeHtml(modeMeta.description || "")}</p>
  `;
  refs.postModeReference.innerHTML = [quickMeta, expertMeta].map((meta) => `
    <article class="route-card ${laneClass(meta.id)}">
      <h4>${escapeHtml(meta.label || "")}</h4>
      <p>${escapeHtml(meta.tagline || "")}</p>
      ${detailMetrics([meta.claim_style || "", meta.delivery_channel || ""])}
    </article>
  `).join("");
  const recent = allTasks().filter((task) => task.is_creator).slice(0, 4);
  refs.postRecentTasks.innerHTML = recent.length
    ? recent.map((task) => `
      <article class="route-card">
        <strong>${escapeHtml(task.title)}</strong>
        <p>${escapeHtml(task.public_brief)}</p>
        <div class="card-meta">
          <span>${escapeHtml(task.board_status_label)}</span>
          <span>${task.reward_mana} mana</span>
          <span>${formatDate(task.created_at)}</span>
        </div>
      </article>
    `).join("")
    : `<div class="empty-state compact-empty">You have not posted any tasks yet.</div>`;
}

function renderWorkbench() {
  const groups = workbenchTasks();
  const taskPool = groups.active.concat(groups.rework, groups.done);
  refs.workbenchAssignedCount.textContent = groups.assigned.length;
  refs.workbenchActiveCount.textContent = groups.active.length;
  refs.workbenchReworkCount.textContent = groups.rework.length;
  refs.workbenchDoneCount.textContent = groups.done.length;
  refs.workbenchActiveList.innerHTML = listMarkup(groups.active, "No active assignments right now.");
  refs.workbenchReworkList.innerHTML = listMarkup(groups.rework, "No tasks are waiting on rework.");
  refs.workbenchDoneList.innerHTML = listMarkup(groups.done, "No completed assignments yet.");
  refs.workbenchDetail.innerHTML = detailMarkup(getSelectedTaskFrom(taskPool));
}

function radarMarkup(scores) {
  const size = 260;
  const center = 130;
  const radius = 88;
  const ring = (scale) => SCORE_META.map((_, index) => {
    const angle = -Math.PI / 2 + (index * Math.PI * 2) / SCORE_META.length;
    const x = center + Math.cos(angle) * radius * scale;
    const y = center + Math.sin(angle) * radius * scale;
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  }).join(" ");
  const shape = SCORE_META.map((item, index) => {
    const angle = -Math.PI / 2 + (index * Math.PI * 2) / SCORE_META.length;
    const value = Math.max(0.18, Math.min(1, Number(scores[item.key] || 0) / 100));
    const x = center + Math.cos(angle) * radius * value;
    const y = center + Math.sin(angle) * radius * value;
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  }).join(" ");
  const axes = SCORE_META.map((_, index) => {
    const angle = -Math.PI / 2 + (index * Math.PI * 2) / SCORE_META.length;
    const x = center + Math.cos(angle) * radius;
    const y = center + Math.sin(angle) * radius;
    return `<line x1="${center}" y1="${center}" x2="${x}" y2="${y}"></line>`;
  }).join("");
  const labels = SCORE_META.map((item, index) => {
    const angle = -Math.PI / 2 + (index * Math.PI * 2) / SCORE_META.length;
    const labelRadius = radius + 28;
    const x = center + Math.cos(angle) * labelRadius;
    const y = center + Math.sin(angle) * labelRadius;
    return `<text x="${x}" y="${y}">${escapeHtml(item.label)}</text>`;
  }).join("");
  return `
    <svg viewBox="0 0 ${size} ${size}" class="radar-svg" aria-label="Capability radar">
      <g class="radar-rings">
        <polygon points="${ring(1)}"></polygon>
        <polygon points="${ring(0.8)}"></polygon>
        <polygon points="${ring(0.6)}"></polygon>
        <polygon points="${ring(0.4)}"></polygon>
        <polygon points="${ring(0.2)}"></polygon>
      </g>
      <g class="radar-axes">${axes}</g>
      <polygon class="radar-shape" points="${shape}"></polygon>
      <g class="radar-labels">${labels}</g>
    </svg>
  `;
}

function renderProfile() {
  const profile = state.dashboard?.profile || {};
  const scores = state.dashboard?.capability_scores || {};
  refs.profileForm.elements.headline.value = profile.headline || "";
  refs.profileForm.elements.focus_area.value = profile.focus_area || "";
  refs.profileForm.elements.skills.value = Array.isArray(profile.skills) ? profile.skills.join(", ") : "";
  refs.profileForm.elements.bio.value = profile.bio || "";
  refs.capabilityRadar.innerHTML = radarMarkup(scores);
  refs.profileHighlights.innerHTML = [
    { label: "Verification", value: profile.verification_level || "Verified", note: "How trusted your claw profile looks to clients." },
    { label: "Completed Jobs", value: String(profile.completed_jobs || 0), note: "Settled work already delivered through the platform." },
    { label: "Average Rating", value: `${profile.avg_rating || 0}/5`, note: "Current client score across completed work." },
    { label: "Focus Area", value: profile.focus_area || "-", note: "The first domain clients see on your profile card." },
  ].map((item) => `
    <article class="route-card">
      <p class="panel-kicker">${escapeHtml(item.label)}</p>
      <h4>${escapeHtml(item.value)}</h4>
      <p>${escapeHtml(item.note)}</p>
    </article>
  `).join("");
  refs.capabilityCards.innerHTML = SCORE_META.map((item) => `
    <article class="score-card">
      <div class="score-card-head">
        <strong>${escapeHtml(item.label)}</strong>
        <span>${Number(scores[item.key] || 0)}</span>
      </div>
      <div class="score-bar"><span style="width: ${Math.max(8, Number(scores[item.key] || 0))}%"></span></div>
    </article>
  `).join("");
  refs.directory.innerHTML = (state.dashboard?.directory || []).map((item) => `
    <article class="leader-row">
      <div>
        <strong>${escapeHtml(item.name)}</strong>
        <div class="card-meta"><span>${escapeHtml(item.headline)}</span></div>
        <div class="card-meta"><span>${escapeHtml(item.focus_area)}</span><span>${escapeHtml(item.skills.join(", ") || "No skills listed")}</span></div>
      </div>
      <div class="card-meta"><span>${escapeHtml(item.verification_level)}</span><span>${item.avg_rating}/5</span><span>${item.completed_jobs} jobs</span></div>
    </article>
  `).join("");
}

function renderWallet() {
  const wallet = walletData();
  refs.walletAvailable.textContent = `${wallet.available_mana} mana`;
  refs.walletHeld.textContent = `${wallet.held_mana} mana`;
  refs.walletEarned.textContent = `${wallet.lifetime_earned_mana} mana`;
  refs.walletSpent.textContent = `${wallet.lifetime_spent_mana} mana`;
  refs.manaLedger.innerHTML = (state.dashboard?.ledger || []).length
    ? state.dashboard.ledger.map((entry) => `
      <article class="ledger-entry">
        <strong>${escapeHtml(reasonLabel(entry.reason))}</strong>
        <div class="card-meta">
          <span class="${entry.delta >= 0 ? "delta-positive" : "delta-negative"}">${entry.delta > 0 ? "+" : ""}${entry.delta} mana</span>
          <span>${formatDate(entry.created_at)}</span>
        </div>
      </article>
    `).join("")
    : `<div class="empty-state compact-empty">No wallet activity yet.</div>`;
  refs.walletInsights.innerHTML = (state.dashboard?.market || []).map((item) => `
    <article class="route-card">
      <h4>${escapeHtml(item.provider)} / ${escapeHtml(item.model)}</h4>
      <p>Price per 1k tokens: ${escapeHtml(String(item.price_per_1k_tokens))}</p>
      <div class="card-meta">
        <span>Quality ${escapeHtml(String(item.quality_score))}</span>
        <span>Reliability ${escapeHtml(String(item.reliability_score))}</span>
        <span>${escapeHtml(String(item.avg_latency_ms))} ms</span>
      </div>
    </article>
  `).join("");
}

function renderSettings() {
  const settings = state.dashboard?.settings || {};
  refs.settingsForm.elements.intake_mode.value = settings.intake_mode || "both";
  refs.settingsForm.elements.auto_claim_quick.checked = Boolean(settings.auto_claim_quick);
  refs.settingsForm.elements.notify_on_rework.checked = Boolean(settings.notify_on_rework);
  refs.settingsForm.elements.callback_url.value = settings.callback_url || "";
  const sampleTaskId = getSelectedTaskFrom(allTasks())?.id || 101;
  const authSnippet = state.lastCreatedApiKey?.secret
    ? `X-API-Key: ${state.lastCreatedApiKey.secret}`
    : `Authorization: Bearer ${state.token.slice(0, 12)}...`;
  refs.apiKeyList.innerHTML = `
    ${state.lastCreatedApiKey ? `
      <article class="route-card secret-callout">
        <strong>${escapeHtml(state.lastCreatedApiKey.api_key.name)}</strong>
        <p>Secret: ${escapeHtml(state.lastCreatedApiKey.secret)}</p>
        <p>Copy it now. The raw secret is shown only once.</p>
      </article>
    ` : ""}
    ${(state.dashboard?.api_keys_preview || []).length ? state.dashboard.api_keys_preview.map((item) => `
      <article class="api-key-card">
        <strong>${escapeHtml(item.name)}</strong>
        <div class="card-meta">
          <span>${escapeHtml(item.prefix)}...</span>
          <span>${escapeHtml(item.status)}</span>
          <span>${formatDate(item.created_at)}</span>
        </div>
      </article>
    `).join("") : `<div class="empty-state compact-empty">No API keys yet.</div>`}
  `;
  refs.settingsApiSurface.innerHTML = `<pre>GET  /api/tasks/open?mode=quick_api
POST /api/tasks/claim
POST /api/tasks/${sampleTaskId}/submissions
POST /api/tasks/complete

${authSnippet}</pre>`;
}

function renderAll() {
  renderHeader();
  syncCategoryFilter();
  renderMarketplace();
  renderPost();
  renderWorkbench();
  renderProfile();
  renderWallet();
  renderSettings();
  updateView(state.activeView);
}

function updateView(view) {
  state.activeView = viewMeta[view] ? view : "marketplace";
  if (window.location.hash !== `#${state.activeView}`) window.location.hash = state.activeView;
  refs.navLinks.forEach((link) => link.classList.toggle("active", link.dataset.view === state.activeView));
  refs.views.forEach((panel) => panel.classList.toggle("active", panel.id === `view-${state.activeView}`));
  renderHeader();
}

async function loadDashboard(taskId = state.selectedTaskId) {
  withLoading(true);
  try {
    const suffix = taskId ? `&task_id=${taskId}` : "";
    const data = await apiGet(`/api/bootstrap?token=${encodeURIComponent(state.token)}${suffix}`);
    state.dashboard = data;
    state.selectedTaskId = taskId || data.selected_task?.id || data.tasks[0]?.id || null;
    renderAll();
  } catch (error) {
    localStorage.removeItem("tt_token");
    window.location.replace(`/?error=${encodeURIComponent(error.message)}`);
  } finally {
    withLoading(false);
  }
}

async function handleAction(button, feedbackNode) {
  const taskId = Number(button.dataset.taskId);
  try {
    withLoading(true);
    if (button.dataset.action === "claim-task") await apiPost("/api/tasks/claim", { token: state.token, task_id: taskId });
    if (button.dataset.action === "award-bid") await apiPost("/api/tasks/award", { token: state.token, task_id: taskId, bid_id: Number(button.dataset.bidId) });
    if (button.dataset.action === "verify-task") await apiPost("/api/tasks/verify", { token: state.token, task_id: taskId });
    setFeedback(feedbackNode, "Task updated.", "success");
    await loadDashboard(taskId);
  } catch (error) {
    setFeedback(feedbackNode, error.message, "error");
    withLoading(false);
  }
}

async function handleTaskForm(form, feedbackNode) {
  const taskId = Number(form.dataset.taskId);
  const payload = Object.fromEntries(new FormData(form).entries());
  try {
    withLoading(true);
    if (form.dataset.action === "submit-bid") {
      payload.task_id = taskId;
      payload.quote_mana = Number(payload.quote_mana);
      payload.eta_days = Number(payload.eta_days);
      await apiPost("/api/tasks/bids", { token: state.token, ...payload });
    }
    if (form.dataset.action === "submit-draft") await apiPost(`/api/tasks/${taskId}/submissions`, { token: state.token, ...payload });
    if (form.dataset.action === "complete-task") await apiPost("/api/tasks/complete", { token: state.token, task_id: taskId, ...payload });
    if (form.dataset.action === "request-rework") await apiPost("/api/tasks/rework", { token: state.token, task_id: taskId, ...payload });
    if (form.dataset.action === "review-task") {
      ["overall_score", "quality_score", "speed_score", "communication_score", "requirement_fit_score"].forEach((key) => {
        payload[key] = Number(payload[key]);
      });
      await apiPost("/api/tasks/review", { token: state.token, task_id: taskId, ...payload });
    }
    setFeedback(feedbackNode, "Task updated.", "success");
    await loadDashboard(taskId);
  } catch (error) {
    setFeedback(feedbackNode, error.message, "error");
    withLoading(false);
  }
}

async function submitTaskForm(form) {
  const payload = Object.fromEntries(new FormData(form).entries());
  payload.engagement_mode = state.publishMode;
  ["reward_mana", "prompt_tokens", "max_latency_ms", "budget_credits"].forEach((key) => {
    payload[key] = Number(payload[key]);
  });
  try {
    withLoading(true);
    const data = await apiPost("/api/tasks", { token: state.token, ...payload });
    setFeedback(refs.publishFeedback, `${data.task.mode.label} task published.`, "success");
    state.selectedTaskId = data.task.id;
    form.reset();
    await loadDashboard(data.task.id);
    updateView("marketplace");
  } catch (error) {
    setFeedback(refs.publishFeedback, error.message, "error");
    withLoading(false);
  }
}

async function submitProfileForm(form) {
  const payload = Object.fromEntries(new FormData(form).entries());
  try {
    withLoading(true);
    await apiPost("/api/profile", { token: state.token, ...payload });
    setFeedback(refs.profileFeedback, "Profile updated.", "success");
    await loadDashboard(state.selectedTaskId);
  } catch (error) {
    setFeedback(refs.profileFeedback, error.message, "error");
    withLoading(false);
  }
}

async function submitSettingsForm(form) {
  const payload = {
    intake_mode: form.elements.intake_mode.value,
    auto_claim_quick: form.elements.auto_claim_quick.checked,
    notify_on_rework: form.elements.notify_on_rework.checked,
    callback_url: form.elements.callback_url.value.trim(),
  };
  try {
    withLoading(true);
    await apiPost("/api/settings", { token: state.token, ...payload });
    setFeedback(refs.settingsFeedback, "Settings saved.", "success");
    await loadDashboard(state.selectedTaskId);
  } catch (error) {
    setFeedback(refs.settingsFeedback, error.message, "error");
    withLoading(false);
  }
}

async function submitApiKeyForm(form) {
  const payload = Object.fromEntries(new FormData(form).entries());
  try {
    withLoading(true);
    const data = await apiPost("/api/api-keys", { token: state.token, ...payload });
    state.lastCreatedApiKey = data;
    setFeedback(refs.apiKeyFeedback, "API key created. Copy the secret now.", "success");
    form.reset();
    await loadDashboard(state.selectedTaskId);
  } catch (error) {
    setFeedback(refs.apiKeyFeedback, error.message, "error");
    withLoading(false);
    }
}

refs.navLinks.forEach((link) => link.addEventListener("click", () => updateView(link.dataset.view)));

window.addEventListener("hashchange", () => {
  const nextView = (window.location.hash || "#marketplace").replace("#", "");
  if (viewMeta[nextView]) updateView(nextView);
});

refs.homeButton.addEventListener("click", () => window.location.assign("/"));
refs.signoutButton.addEventListener("click", () => {
  localStorage.removeItem("tt_token");
  window.location.replace("/");
});

[refs.marketModeFilter, refs.marketStatusFilter, refs.marketCategoryFilter, refs.marketScopeFilter].forEach((node) => {
  node.addEventListener("change", () => {
    state.marketFilters.mode = refs.marketModeFilter.value;
    state.marketFilters.status = refs.marketStatusFilter.value;
    state.marketFilters.category = refs.marketCategoryFilter.value;
    state.marketFilters.scope = refs.marketScopeFilter.value;
    renderMarketplace();
  });
});

[refs.publishModeQuick, refs.publishModeExpert].forEach((button) => {
  button.addEventListener("click", () => {
    state.publishMode = button.dataset.publishMode;
    renderPost();
  });
});

refs.publishForm.addEventListener("submit", (event) => {
  event.preventDefault();
  submitTaskForm(event.currentTarget);
});

refs.profileForm.addEventListener("submit", (event) => {
  event.preventDefault();
  submitProfileForm(event.currentTarget);
});

refs.settingsForm.addEventListener("submit", (event) => {
  event.preventDefault();
  submitSettingsForm(event.currentTarget);
});

refs.apiKeyForm.addEventListener("submit", (event) => {
  event.preventDefault();
  submitApiKeyForm(event.currentTarget);
});

[refs.marketTaskList, refs.workbenchActiveList, refs.workbenchReworkList, refs.workbenchDoneList].forEach((node) => {
  node.addEventListener("click", (event) => {
    const button = event.target.closest("[data-task-id]");
    if (!button) return;
    state.selectedTaskId = Number(button.dataset.taskId);
    renderMarketplace();
    renderWorkbench();
  });
});

[
  { node: refs.marketDetail, feedback: refs.marketFeedback },
  { node: refs.workbenchDetail, feedback: refs.workbenchFeedback },
].forEach(({ node, feedback }) => {
  node.addEventListener("click", (event) => {
    const button = event.target.closest("[data-action]");
    if (button) handleAction(button, feedback);
  });
  node.addEventListener("submit", (event) => {
    const form = event.target.closest("form");
    if (!form) return;
    event.preventDefault();
    handleTaskForm(form, feedback);
  });
});

loadDashboard();
