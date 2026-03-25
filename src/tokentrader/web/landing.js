const token = localStorage.getItem("tt_token") || "";

if (token) {
  window.location.replace("/app.html");
}

const authForm = document.querySelector("#auth-form");
const authFeedback = document.querySelector("#auth-feedback");

function setFeedback(message = "", tone = "") {
  authFeedback.textContent = message;
  authFeedback.className = "inline-feedback";
  if (tone) authFeedback.classList.add(`feedback-${tone}`);
}

const query = new URLSearchParams(window.location.search);
if (query.get("error")) {
  setFeedback(query.get("error"), "error");
}

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
    localStorage.setItem("tt_token", data.token);
    setFeedback(data.created ? "Account created. Opening workspace..." : "Welcome back. Opening workspace...", "success");
    window.setTimeout(() => window.location.assign("/app.html"), 250);
  } catch (error) {
    setFeedback(error.message, "error");
  }
});
