let sessionToken = localStorage.getItem("tt_token") || "";
let latestQuotePayload = null;

const sessionStatus = document.querySelector("#session-status");
const quoteResult = document.querySelector("#quote-result");
const execResult = document.querySelector("#exec-result");

function setSession(token, user) {
  sessionToken = token;
  localStorage.setItem("tt_token", token);
  sessionStatus.textContent = `已登录：${user.name} (${user.email})`;
}

async function api(path, payload) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || "请求失败");
  return data;
}

document.querySelector("#register-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  try {
    const data = await api("/api/register", Object.fromEntries(fd.entries()));
    alert(`注册成功：${data.user.email}`);
    e.target.reset();
  } catch (err) {
    alert(err.message);
  }
});

document.querySelector("#login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  try {
    const data = await api("/api/login", Object.fromEntries(fd.entries()));
    setSession(data.token, data.user);
  } catch (err) {
    alert(err.message);
  }
});

document.querySelector("#quote-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const payload = Object.fromEntries(fd.entries());
  payload.prompt_tokens = Number(payload.prompt_tokens);
  payload.max_latency_ms = Number(payload.max_latency_ms);
  payload.budget_credits = Number(payload.budget_credits);
  payload.token = sessionToken;
  latestQuotePayload = payload;

  try {
    const data = await api("/api/quote", payload);
    quoteResult.textContent = JSON.stringify(data.candidates, null, 2);
  } catch (err) {
    quoteResult.textContent = err.message;
  }
});

document.querySelector("#exec-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const payload = Object.fromEntries(fd.entries());
  if (!latestQuotePayload) {
    execResult.textContent = "请先获取报价";
    return;
  }

  try {
    const data = await api("/api/execute", {
      ...latestQuotePayload,
      provider: payload.provider,
      model: payload.model,
    });
    execResult.textContent = JSON.stringify(data.result, null, 2);
  } catch (err) {
    execResult.textContent = err.message;
  }
});

if (sessionToken) {
  fetch(`/api/profile?token=${encodeURIComponent(sessionToken)}`)
    .then((r) => r.json())
    .then((data) => {
      if (data.ok) {
        setSession(sessionToken, data.user);
      } else {
        localStorage.removeItem("tt_token");
        sessionStatus.textContent = "未登录";
      }
    })
    .catch(() => {
      sessionStatus.textContent = "未登录";
    });
}
