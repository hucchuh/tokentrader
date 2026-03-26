let token = localStorage.getItem("tt_token") || "";

const authForm = document.querySelector("#auth-form");
const authFeedback = document.querySelector("#auth-feedback");
const activeSession = document.querySelector("#active-session");
const openWorkspaceButton = document.querySelector("#open-workspace");
const clearSessionButton = document.querySelector("#clear-session");

function setFeedback(message = "", tone = "") {
  authFeedback.textContent = message;
  authFeedback.className = "inline-feedback";
  if (tone) authFeedback.classList.add(`feedback-${tone}`);
}

function syncSessionState() {
  const hasSession = Boolean(token);
  activeSession.classList.toggle("hidden", !hasSession);
  if (!authFeedback.classList.contains("feedback-error")) {
    setFeedback("");
  }
}

const query = new URLSearchParams(window.location.search);
if (query.get("error")) {
  setFeedback(query.get("error"), "error");
}

syncSessionState();

authForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = Object.fromEntries(new FormData(event.currentTarget).entries());
  try {
    const response = await fetch("/api/auth", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!data.ok) throw new Error(data.error || "Unable to sign in.");
    token = data.token;
    localStorage.setItem("tt_token", token);
    syncSessionState();
    setFeedback(data.created ? "Account created. Opening workspace..." : "Welcome back. Opening workspace...", "success");
    window.setTimeout(() => window.location.assign("/app.html"), 250);
  } catch (error) {
    setFeedback(error.message, "error");
  }
});

openWorkspaceButton.addEventListener("click", () => {
  window.location.assign("/app.html");
});

clearSessionButton.addEventListener("click", () => {
  token = "";
  localStorage.removeItem("tt_token");
  syncSessionState();
  authForm.reset();
  document.querySelector("#auth-email").focus();
});
