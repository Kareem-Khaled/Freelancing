"use strict";

const $ = (id) => document.getElementById(id);
const EXPECTED_MS = 45000; // local-model triage takes roughly this long

let selectedTicket = null;
let pollTimer = null;

/* ---------- utilities ---------- */

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

function badge(text, kind) {
  return `<span class="badge ${kind || "neutral"}">${esc(text)}</span>`;
}

async function api(path, options) {
  const res = await fetch(path, options);
  const data = await res.json().catch(() => ({ error: "invalid server response" }));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

/* ---------- identity (stands in for a login) ---------- */

async function loadIdentities() {
  const select = $("customer");
  let data;
  try {
    data = await api("/api/identities");
  } catch {
    select.innerHTML = `<option value="web">anonymous</option>`;
    return;
  }

  const saved = localStorage.getItem("sp_identity") || "";
  select.innerHTML =
    `<option value="web">Not signed in (anonymous)</option>` +
    data.identities
      .map((c) => `<option value="${esc(c.customer_id)}">
          ${esc(c.name)} — ${esc(c.customer_id)} · ${esc(c.plan)}
        </option>`)
      .join("");
  select.value = saved && [...select.options].some((o) => o.value === saved) ? saved : "web";

  const describe = () => {
    const anon = select.value === "web";
    localStorage.setItem("sp_identity", select.value);
    $("identity-note").textContent = anon
      ? "Account lookups will be refused — no verified identity."
      : `Lookups restricted to ${select.value}.`;
    $("identity-note").className = anon ? "hint warn-text" : "hint";
  };

  select.addEventListener("change", describe);
  describe();
}

/* ---------- submitting a ticket ---------- */

async function submitTicket() {
  const message = $("message").value;
  const customer = $("customer").value || "web";
  const ticketId = $("ticket-id").value.trim();

  $("submit").disabled = true;
  $("result").classList.add("hidden");

  try {
    const { job_id, queue_depth } = await api("/api/tickets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, customer, ticket_id: ticketId }),
    });
    trackJob(job_id, queue_depth);
  } catch (err) {
    showError(err.message);
    $("submit").disabled = false;
  }
}

function trackJob(jobId, queueDepth) {
  const box = $("job-status");
  const started = Date.now();
  box.classList.remove("hidden");
  let lastLabel = queueDepth > 1 ? `queued (${queueDepth} ahead)` : "starting";
  let events = [];

  // Build the shell ONCE. Rewriting box.innerHTML on a timer restarts the
  // spinner's CSS animation from zero every tick, so it never completes a
  // rotation, and it re-creates every trace row -- which reads as flicker and
  // collapses any <details> the user had opened to read a prompt. Only the
  // parts that actually change are updated below.
  box.innerHTML = `
    <div class="job-head">
      <div class="spinner"></div>
      <div class="bar"><div id="job-bar"></div></div>
      <span class="hint" id="job-label"></span>
    </div>
    <div id="job-trace"></div>`;

  const bar = $("job-bar");
  const labelEl = $("job-label");
  const traceEl = $("job-trace");
  let renderedCount = -1;

  // Cheap: two property writes, no DOM teardown.
  const tickClock = () => {
    const elapsed = ((Date.now() - started) / 1000).toFixed(1);
    bar.style.width = `${Math.min(95, ((Date.now() - started) / EXPECTED_MS) * 100)}%`;
    labelEl.textContent = `${lastLabel} · ${elapsed}s`;
  };

  // Expensive: only when a new step has actually arrived.
  const renderSteps = () => {
    if (events.length === renderedCount) return;
    renderedCount = events.length;
    traceEl.innerHTML = renderTrace(events, true);
  };

  tickClock();
  const ticker = setInterval(tickClock, 200);

  clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    let job;
    try {
      job = await api(`/api/jobs/${jobId}`);
    } catch (err) {
      clearInterval(pollTimer); clearInterval(ticker);
      box.classList.add("hidden");
      showError(err.message);
      $("submit").disabled = false;
      return;
    }

    events = job.trace || [];
    // Show the most recent step as the status line.
    if (events.length) lastLabel = events[events.length - 1].label;
    else if (job.status === "queued") lastLabel = `queued (${job.queue_depth} ahead)`;
    else lastLabel = "starting";
    renderSteps();

    if (job.status === "queued" || job.status === "running") return;

    clearInterval(pollTimer); clearInterval(ticker);
    box.classList.add("hidden");
    $("submit").disabled = false;

    if (job.status === "error") {
      showError(job.error || "processing failed");
    } else {
      showResult(job.result, events);
      $("ticket-id").value = job.result.ticket_id; // follow-ups continue the thread
      refreshQueue();
      refreshMetrics();
    }
  }, 700);
}

/* ---------- execution trace ---------- */

const PHASE_META = {
  validate: { icon: "1", name: "Input guards" },
  research: { icon: "2", name: "Research" },
  llm:      { icon: "AI", name: "Model call" },
  tool:     { icon: "→", name: "Tool call" },
  analyse:  { icon: "3", name: "Analysis" },
  rules:    { icon: "4", name: "Business rules" },
  store:    { icon: "5", name: "Stored" },
};

function renderTrace(events, live) {
  if (!events || !events.length) {
    return live ? `<div class="trace"><span class="hint">starting…</span></div>` : "";
  }
  const rows = events.map((e, i) => {
    const meta = PHASE_META[e.phase] || { icon: "•", name: e.phase };
    const secs = (e.elapsed_ms / 1000).toFixed(1);

    // Model calls carry the raw exchange; show it behind a disclosure so the
    // timeline stays readable but the full prompt/response is one click away.
    let exchange = "";
    if (e.prompt || e.response) {
      exchange = `
        <details class="exchange">
          <summary>view prompt &amp; response</summary>
          ${e.prompt ? `<div class="xlabel">sent →</div><pre class="xbody">${esc(e.prompt)}</pre>` : ""}
          ${e.response ? `<div class="xlabel">← received</div><pre class="xbody resp">${esc(e.response)}</pre>` : ""}
        </details>`;
    }

    return `
      <div class="tstep ${esc(e.status)} ${esc(e.phase)}">
        <span class="tphase" title="${esc(meta.name)}">${esc(meta.icon)}</span>
        <div class="tbody">
          <div class="tlabel">${esc(e.label)}<span class="tsecs">${secs}s</span></div>
          ${e.detail ? `<div class="tdetail">${esc(e.detail)}</div>` : ""}
          ${exchange}
        </div>
      </div>`;
  }).join("");
  return `<div class="trace">${rows}</div>`;
}

/* ---------- rendering a result ---------- */

function showError(message) {
  const box = $("result");
  box.classList.remove("hidden");
  box.innerHTML = `<div class="err"><b>Error:</b> ${esc(message)}</div>`;
}

function showResult(result, events) {
  const box = $("result");
  box.classList.remove("hidden");

  const a = result.analysis;
  const d = result.decision;
  const notices = [];
  if (result.truncated)
    notices.push(`<div class="warn">Message was truncated before analysis.</div>`);
  if (result.problem)
    notices.push(`<div class="warn">Input rejected: <b>${esc(result.problem)}</b> — ${esc(result.error || "")}</div>`);
  else if (result.error)
    notices.push(`<div class="err">${esc(result.error)}</div>`);

  if (!a) {
    box.innerHTML = notices.join("") || `<div class="err">No analysis returned.</div>`;
    return;
  }

  const entities = (a.entities || []).length
    ? `<div class="entities">${a.entities
        .map((e) => `<span class="entity"><b>${esc(e.type)}</b>=${esc(e.value)}</span>`)
        .join("")}</div>`
    : `<span class="hint">none extracted</span>`;

  const traceBlock = (events && events.length)
    ? `<details class="trace-wrap" open>
         <summary>Execution trace <span class="hint">${events.length} steps · ${(result.latency_ms / 1000).toFixed(1)}s</span></summary>
         ${renderTrace(events, false)}
       </details>`
    : renderTools(result.tools);

  box.innerHTML = `
    <div class="result-head">
      ${badge(result.ok ? "analysed" : "fallback", result.ok ? "ok" : "bad")}
      <code>${esc(result.ticket_id)}</code>
      <code>${result.attempts} attempt(s) · ${(result.latency_ms / 1000).toFixed(1)}s</code>
      ${result.attempts > 1 ? badge("repaired", "medium") : ""}
    </div>
    ${notices.join("")}
    ${traceBlock}
    ${renderDecision(d)}
    <h3 class="sub">Model classification</h3>
    <dl class="fields">
      <dt>language</dt><dd>${esc(a.language || "en")}</dd>
      <dt>category</dt><dd>${esc(a.category)}</dd>
      <dt>priority</dt><dd>${badge(a.priority, a.priority)}</dd>
      <dt>sentiment</dt><dd>${esc(a.sentiment)}</dd>
      <dt>issue</dt><dd>${esc(a.issue)}</dd>
      <dt>suggested action</dt><dd><code>${esc(a.suggested_action)}</code></dd>
      <dt>confidence</dt><dd>${Number(a.confidence).toFixed(2)}</dd>
      <dt>entities</dt><dd>${entities}</dd>
    </dl>
    <div class="draft">${esc(a.draft_response)}</div>`;
}

const ACTION_KIND = {
  auto_send: "ok",
  needs_info: "medium",
  human_review: "medium",
  escalate: "bad",
};

function renderTools(tools) {
  if (!tools || !tools.length) return "";
  const rows = tools
    .map((t) => {
      const args = Object.entries(t.arguments || {})
        .map(([k, v]) => `${esc(k)}=${esc(v)}`)
        .join(", ");
      const detail = t.ok ? t.result : t.error;
      return `<li>
        <code>${esc(t.name)}(${args})</code>
        <span>${t.ok ? "" : "⚠ "}${esc(detail || "")}</span>
      </li>`;
    })
    .join("");
  return `
    <h3 class="sub">Tools used <span class="hint">(verified account data)</span></h3>
    <ul class="rules">${rows}</ul>`;
}

function renderDecision(d) {
  if (!d) return "";

  const rules = d.fired_rules.length
    ? `<ul class="rules">${d.fired_rules
        .map((name, i) => `<li><code>${esc(name)}</code><span>${esc(d.reasons[i] || "")}</span></li>`)
        .join("")}</ul>`
    : `<span class="hint">No rules fired — the model's recommendation stands.</span>`;

  let override = "";
  if (d.overrode_model) {
    const parts = [];
    if (d.model_priority && d.model_priority !== d.priority)
      parts.push(`priority <b>${esc(d.model_priority)}</b> → <b>${esc(d.priority)}</b>`);
    if (d.model_requires_human !== null && d.model_requires_human !== d.requires_human)
      parts.push(`requires_human <b>${d.model_requires_human}</b> → <b>${d.requires_human}</b>`);
    override = `<div class="warn">Rules overrode the model: ${parts.join(", ")}</div>`;
  }

  return `
    <h3 class="sub">Final decision <span class="hint">(after business rules)</span></h3>
    ${override}
    <div class="decision">
      <div class="decision-head">
        ${badge(d.action.replace("_", " "), ACTION_KIND[d.action] || "neutral")}
        ${badge(d.priority, d.priority)}
        <span class="hint">SLA ${d.sla_hours}h</span>
        ${d.tags.map((t) => `<span class="entity">${esc(t)}</span>`).join("")}
      </div>
      ${rules}
    </div>`;
}

/* ---------- queue ---------- */

async function refreshQueue() {
  let data;
  try { data = await api("/api/tickets"); } catch { return; }

  const counts = data.counts || {};
  const actions = data.actions || {};
  $("counts").innerHTML =
    ["high", "medium", "low"].filter((p) => counts[p]).map((p) => badge(`${p} ${counts[p]}`, p)).join("") +
    Object.entries(actions)
      .map(([a, n]) => badge(`${a.replace("_", " ")} ${n}`, ACTION_KIND[a] || "neutral"))
      .join("");

  // Rule activity panel: how often each rule fires, for tuning.
  const rules = data.rules || {};
  const entries = Object.entries(rules);
  $("rule-activity").innerHTML = entries.length
    ? `<ul class="rules compact">${entries
        .map(([name, n]) => `<li><code>${esc(name)}</code><span>${n}×</span></li>`)
        .join("")}</ul>`
    : `<span class="hint">no rules fired yet</span>`;

  const body = $("queue-body");
  if (!data.tickets.length) {
    body.innerHTML = `<tr><td colspan="6" class="empty">No tickets yet.</td></tr>`;
    return;
  }

  body.innerHTML = data.tickets.map((t) => `
    <tr data-id="${esc(t.id)}" class="${t.id === selectedTicket ? "selected" : ""}">
      <td class="ticket">${esc(t.id)}</td>
      <td>${t.action ? badge(t.action.replace("_", " "), ACTION_KIND[t.action] || "neutral") : "—"}</td>
      <td>${t.priority ? badge(t.priority, t.priority) : "—"}</td>
      <td>${esc(t.category || "—")}</td>
      <td>${t.overrode_model ? badge("yes", "medium") : `<span class="hint">—</span>`}</td>
      <td class="issue" title="${esc(t.issue || "")}">${esc(t.issue || "—")}</td>
    </tr>`).join("");

  body.querySelectorAll("tr[data-id]").forEach((tr) =>
    tr.addEventListener("click", () => loadDetail(tr.dataset.id))
  );
}

/* ---------- metrics ---------- */

async function refreshMetrics() {
  let data;
  try { data = await api("/api/metrics"); } catch { return; }

  const m = data.metrics;
  $("model-info").textContent = `${data.model} · ${data.api_base}`;

  const cards = [
    ["calls", m.calls],
    ["success", `${(m.success_rate * 100).toFixed(0)}%`],
    ["retries", m.retries],
    ["avg latency", `${(m.avg_latency_ms / 1000).toFixed(1)}s`],
    ["tokens in", m.prompt_tokens],
    ["tokens out", m.completion_tokens],
    ["cost", `$${Number(m.cost_usd).toFixed(4)}`],
  ];
  $("metrics").innerHTML = cards
    .map(([label, value]) =>
      `<div class="metric"><div class="label">${label}</div><div class="value">${esc(value)}</div></div>`)
    .join("");

  // Surface the dominant cost driver rather than burying it in the numbers.
  if (m.calls > 0 && m.completion_tokens > 0) {
    const perCall = Math.round(m.completion_tokens / m.calls);
    $("think-note").textContent =
      `~${perCall} output tokens per call. Most of that is the model's <think> ` +
      `reasoning, which is stripped before validation — it is the main driver of latency.`;
  }
}

/* ---------- ticket detail ---------- */

async function loadDetail(ticketId) {
  selectedTicket = ticketId;
  document.querySelectorAll("#queue-body tr").forEach((tr) =>
    tr.classList.toggle("selected", tr.dataset.id === ticketId)
  );

  let data;
  try { data = await api(`/api/tickets/${encodeURIComponent(ticketId)}`); }
  catch (err) { $("detail").innerHTML = `<div class="err">${esc(err.message)}</div>`; return; }

  const thread = data.messages.map((m) => `
    <div class="msg ${esc(m.role)}">
      <div class="who">${esc(m.role.replace("_", " "))}</div>${esc(m.content)}
    </div>`).join("");

  const latest = data.analyses[data.analyses.length - 1];
  const latestDecision = latest && latest.action
    ? renderDecision({
        action: latest.action,
        priority: latest.priority,
        requires_human: latest.requires_human,
        sla_hours: latest.sla_hours,
        fired_rules: latest.fired_rules || [],
        reasons: latest.rule_reasons || [],
        tags: latest.tags || [],
        overrode_model: latest.overrode_model,
        model_priority: latest.model_priority,
        model_requires_human: latest.model_requires_human,
      })
    : "";
  const calls = data.calls.length ? `
    <h3 class="sub">LLM attempts</h3>
    <table>
      <thead><tr><th>#</th><th>op</th><th>latency</th><th>out tok</th><th>ok</th></tr></thead>
      <tbody>${data.calls.map((c) => `
        <tr>
          <td>${c.attempt}</td>
          <td>${esc(c.operation)}</td>
          <td>${(c.latency_ms / 1000).toFixed(1)}s</td>
          <td>${c.completion_tokens}</td>
          <td>${c.success ? badge("ok", "ok") : badge("fail", "bad")}</td>
        </tr>
        ${c.error ? `<tr><td colspan="5"><span class="hint">${esc(c.error)}</span></td></tr>` : ""}
      `).join("")}</tbody>
    </table>` : "";

  $("detail").innerHTML = `
    <div class="result-head">
      <code>${esc(data.ticket.id)}</code>
      ${latest ? badge(latest.priority, latest.priority) : ""}
      <span class="hint">${esc(data.ticket.customer)} · ${esc(data.ticket.status)}</span>
    </div>
    <h3 class="sub">Conversation</h3>
    <div class="thread">${thread || '<span class="hint">no messages</span>'}</div>
    ${latest && latest.tool_calls ? renderTools(latest.tool_calls) : ""}
    ${latestDecision}
    ${latest ? `<h3 class="sub">Latest analysis</h3>
      <dl class="fields">
        <dt>issue</dt><dd>${esc(latest.issue)}</dd>
        <dt>action</dt><dd><code>${esc(latest.suggested_action)}</code></dd>
        <dt>confidence</dt><dd>${Number(latest.confidence).toFixed(2)}</dd>
      </dl>` : ""}
    ${calls}
    <div class="row">
      <button class="ghost small" id="reply-btn">Reply in this thread</button>
    </div>`;

  const replyBtn = $("reply-btn");
  if (replyBtn) {
    replyBtn.addEventListener("click", () => {
      $("ticket-id").value = ticketId;
      $("message").focus();
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  }
}

/* ---------- wiring ---------- */

$("submit").addEventListener("click", submitTicket);
$("refresh").addEventListener("click", () => { refreshQueue(); refreshMetrics(); });
$("clear-form").addEventListener("click", () => {
  $("message").value = ""; $("ticket-id").value = "";
  $("result").classList.add("hidden");
});
document.querySelectorAll(".chip").forEach((chip) =>
  chip.addEventListener("click", () => {
    $("message").value = chip.dataset.sample;
    $("ticket-id").value = "";
    $("message").focus();
  })
);
// Cmd/Ctrl+Enter submits from the textarea.
$("message").addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") submitTicket();
});

loadIdentities();
refreshQueue();
refreshMetrics();
