"use strict";

const $ = (id) => document.getElementById(id);
const EXPECTED_MS = 13000; // typical extraction latency on the local model

let pollTimer = null;
let selectedDoc = null;
let pendingFile = null;

/* ---------- utilities ---------- */

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

function badge(text, kind) {
  return `<span class="badge ${kind || "neutral"}">${esc(text)}</span>`;
}

const REVIEW_KIND = {
  auto_approved: "ok",
  needs_review: "medium",
  rejected: "bad",
};

function money(amount, currency) {
  if (amount === null || amount === undefined) return "—";
  const code = currency && currency !== "UNKNOWN" ? currency + " " : "";
  return code + Number(amount).toLocaleString(undefined, {
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  });
}

async function api(path, options) {
  const res = await fetch(path, options);
  const data = await res.json().catch(() => ({ detail: "invalid server response" }));
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  return data;
}

/* ---------- upload ---------- */

function selectFile(file) {
  pendingFile = file;
  $("file-name").textContent = file ? `${file.name} · ${(file.size / 1024).toFixed(0)} KB` : "";
  $("upload").disabled = !file;
}

const dropzone = $("dropzone");
dropzone.addEventListener("click", () => $("file-input").click());
$("file-input").addEventListener("change", (e) => selectFile(e.target.files[0]));

["dragenter", "dragover"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.add("over");
  })
);
["dragleave", "drop"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.remove("over");
  })
);
dropzone.addEventListener("drop", (e) => {
  if (e.dataTransfer.files.length) selectFile(e.dataTransfer.files[0]);
});

async function upload(file) {
  $("upload").disabled = true;
  $("result").classList.add("hidden");

  const form = new FormData();
  form.append("file", file);

  try {
    const data = await api("/documents", { method: "POST", body: form });
    trackDocument(data.document_id);
  } catch (err) {
    showError(err.message);
    $("upload").disabled = false;
  }
}

$("upload").addEventListener("click", () => pendingFile && upload(pendingFile));

// Sample buttons fetch a fixture from the server and upload it as a real file,
// so the demo path is identical to a genuine upload.
document.querySelectorAll(".chip").forEach((chip) =>
  chip.addEventListener("click", async () => {
    try {
      const res = await fetch(`/api/sample/${chip.dataset.sample}`);
      if (!res.ok) throw new Error("sample not available");
      const blob = await res.blob();
      const name = res.headers.get("X-Filename") || "sample.txt";
      const file = new File([blob], name, { type: blob.type || "application/octet-stream" });
      selectFile(file);
      upload(file);
    } catch (err) {
      showError(err.message);
    }
  })
);

/* ---------- polling ---------- */

function trackDocument(documentId) {
  const box = $("job-status");
  const started = Date.now();
  box.classList.remove("hidden");
  let events = [];
  let label = "uploading";

  // Build the shell ONCE. Rewriting box.innerHTML on a timer restarts the
  // spinner's CSS animation from zero every tick, so it never completes a
  // rotation, and it re-creates every trace row -- which reads as flicker and
  // collapses any <details> the user had opened. Only the parts that actually
  // change are updated below.
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

  // Cheap: two text/style writes, no DOM teardown.
  const tickClock = () => {
    const elapsed = ((Date.now() - started) / 1000).toFixed(1);
    bar.style.width = `${Math.min(95, ((Date.now() - started) / EXPECTED_MS) * 100)}%`;
    labelEl.textContent = `${label} · ${elapsed}s`;
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
    let doc, trace;
    try {
      [doc, trace] = await Promise.all([
        api(`/documents/${documentId}`),
        api(`/documents/${documentId}/trace`).catch(() => ({ trace: [] })),
      ]);
    } catch (err) {
      clearInterval(pollTimer); clearInterval(ticker);
      box.classList.add("hidden");
      showError(err.message);
      $("upload").disabled = false;
      return;
    }

    events = trace.trace || [];
    label = events.length ? events[events.length - 1].label : doc.status;
    renderSteps();

    if (doc.status === "pending" || doc.status === "processing") return;

    clearInterval(pollTimer); clearInterval(ticker);
    box.classList.add("hidden");
    $("upload").disabled = false;

    if (doc.status === "failed") {
      showError(doc.error || "extraction failed", events);
    } else {
      try {
        const extraction = await api(`/documents/${documentId}/extraction`);
        showResult(doc, extraction, events);
      } catch (err) {
        showError(err.message, events);
      }
    }
    refreshDocuments();
    refreshMetrics();
  }, 700);
}

/* ---------- execution trace (ported from the support platform) ---------- */

const PHASE_META = {
  parse:    { icon: "1", name: "Parsing" },
  llm:      { icon: "AI", name: "Model call" },
  extract:  { icon: "2", name: "Extraction" },
  validate: { icon: "3", name: "Validation" },
  store:    { icon: "4", name: "Stored" },
};

function renderTrace(events, live) {
  if (!events || !events.length) {
    return live ? `<div class="trace"><span class="hint">starting…</span></div>` : "";
  }
  const rows = events.map((e) => {
    const meta = PHASE_META[e.phase] || { icon: "•", name: e.phase };
    const secs = (e.elapsed_ms / 1000).toFixed(1);

    // Model calls carry the raw exchange; parsing carries the extracted text.
    let exchange = "";
    if (e.prompt || e.response) {
      const promptLabel = e.phase === "parse" ? "" : "sent →";
      const respLabel = e.phase === "parse" ? "extracted text" : "← received";
      exchange = `
        <details class="exchange">
          <summary>${e.phase === "parse" ? "view extracted text" : "view prompt &amp; response"}</summary>
          ${e.prompt ? `<div class="xlabel">${promptLabel}</div><pre class="xbody">${esc(e.prompt)}</pre>` : ""}
          ${e.response ? `<div class="xlabel">${respLabel}</div><pre class="xbody resp">${esc(e.response)}</pre>` : ""}
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

function traceBlock(events, seconds) {
  if (!events || !events.length) return "";
  return `<details class="trace-wrap" open>
    <summary>Execution trace
      <span class="hint">${events.length} steps${seconds ? ` · ${seconds}s` : ""}</span>
    </summary>
    ${renderTrace(events, false)}
  </details>`;
}

/* ---------- results ---------- */

function showError(message, events) {
  const box = $("result");
  box.classList.remove("hidden");
  box.innerHTML = `<div class="err"><b>Could not extract:</b> ${esc(message)}</div>`
    + traceBlock(events);
}

function renderFindings(findings) {
  if (!findings || !findings.length) {
    return `<span class="hint">No issues — the numbers add up.</span>`;
  }
  return `<ul class="findings">${findings
    .map((f) => `<li class="${esc(f.severity)}">
        <code>${esc(f.check)}</code><span>${esc(f.message)}</span>
      </li>`)
    .join("")}</ul>`;
}

function renderItems(items, currency) {
  if (!items || !items.length) {
    return `<span class="hint">No line items extracted.</span>`;
  }
  const sum = items.reduce((t, i) => t + (i.amount || 0), 0);
  return `
    <table class="items">
      <thead><tr>
        <th>Description</th><th class="num">Qty</th>
        <th class="num">Unit</th><th class="num">Amount</th>
      </tr></thead>
      <tbody>${items.map((i) => `
        <tr>
          <td>${esc(i.description || "—")}</td>
          <td class="num">${i.quantity ?? "—"}</td>
          <td class="num">${i.unit_price ?? "—"}</td>
          <td class="num">${money(i.amount, "")}</td>
        </tr>`).join("")}
      </tbody>
      <tfoot><tr>
        <td colspan="3">Sum of line items</td>
        <td class="num">${money(sum, "")}</td>
      </tr></tfoot>
    </table>`;
}

function showResult(doc, result, events) {
  const box = $("result");
  box.classList.remove("hidden");
  const e = result.extraction;
  const review = result.review_status;

  const fields = [
    ["vendor", e.vendor || "—", false],
    ["invoice #", e.invoice_number || "—", false],
    ["date", e.date || "—", false],
    ["due", e.due_date || "—", false],
    ["subtotal", money(e.subtotal, e.currency), false],
    ["tax", money(e.tax, e.currency), false],
    ["total", money(e.total, e.currency), true],
    ["confidence", Number(e.confidence).toFixed(2), false],
  ];

  box.innerHTML = `
    <div class="result-head">
      ${badge(review.replace("_", " "), REVIEW_KIND[review] || "neutral")}
      <code>${esc(doc.id)}</code>
      <code>${esc(doc.doc_format)}${doc.pages ? ` · ${doc.pages}p` : ""}</code>
      ${e.document_type !== "invoice" ? badge(e.document_type, "medium") : ""}
      ${doc.truncated ? badge("truncated", "medium") : ""}
    </div>
    ${traceBlock(events)}
    <h3 class="sub">Validation</h3>
    ${renderFindings(result.findings)}
    <h3 class="sub">Extracted</h3>
    <div class="inv-head">${fields.map(([k, v, big]) => `
      <div class="inv-field">
        <div class="k">${esc(k)}</div>
        <div class="v ${big ? "big" : ""}">${esc(v)}</div>
      </div>`).join("")}
    </div>
    <h3 class="sub">Line items</h3>
    ${renderItems(e.items, e.currency)}
    ${e.notes ? `<h3 class="sub">Notes</h3><div class="draft">${esc(e.notes)}</div>` : ""}`;
}

/* ---------- document list ---------- */

async function refreshDocuments() {
  let data;
  try { data = await api("/documents"); } catch { return; }

  const counts = data.review_counts || {};
  $("counts").innerHTML = Object.entries(counts)
    .map(([k, n]) => badge(`${k.replace("_", " ")} ${n}`, REVIEW_KIND[k] || "neutral"))
    .join("");

  const body = $("docs-body");
  if (!data.documents.length) {
    body.innerHTML = `<tr><td colspan="5" class="empty">No documents yet.</td></tr>`;
    return;
  }

  body.innerHTML = data.documents.map((d) => `
    <tr data-id="${esc(d.id)}" class="${d.id === selectedDoc ? "selected" : ""}">
      <td class="ticket">${esc(d.id)}</td>
      <td>${esc(d.doc_format || "—")}</td>
      <td class="issue" title="${esc(d.vendor || "")}">${esc(d.vendor || "—")}</td>
      <td>${d.total != null ? esc(money(d.total, d.currency)) : "—"}</td>
      <td>${d.review_status
            ? badge(d.review_status.replace("_", " "), REVIEW_KIND[d.review_status])
            : badge(d.status, d.status === "failed" ? "bad" : "neutral")}</td>
    </tr>`).join("");

  body.querySelectorAll("tr[data-id]").forEach((tr) =>
    tr.addEventListener("click", () => loadDetail(tr.dataset.id))
  );
}

/* ---------- metrics ---------- */

async function refreshMetrics() {
  let data;
  try { data = await api("/metrics"); } catch { return; }

  const m = data.metrics;
  $("model-info").textContent = `${data.model} · ${data.api_base}`;

  const cards = [
    ["calls", m.calls],
    ["success", `${(m.success_rate * 100).toFixed(0)}%`],
    ["retries", m.retries],
    ["avg latency", `${(m.avg_latency_ms / 1000).toFixed(1)}s`],
    ["tokens in", m.prompt_tokens],
    ["tokens out", m.completion_tokens],
  ];
  $("metrics").innerHTML = cards
    .map(([label, value]) =>
      `<div class="metric"><div class="label">${label}</div><div class="value">${esc(value)}</div></div>`)
    .join("");
}

/* ---------- detail ---------- */

async function loadDetail(documentId) {
  selectedDoc = documentId;
  document.querySelectorAll("#docs-body tr").forEach((tr) =>
    tr.classList.toggle("selected", tr.dataset.id === documentId)
  );

  const detail = $("detail");
  try {
    const [doc, trace] = await Promise.all([
      api(`/documents/${documentId}`),
      api(`/documents/${documentId}/trace`).catch(() => ({ trace: [] })),
    ]);

    let extraction = null;
    try { extraction = await api(`/documents/${documentId}/extraction`); } catch { /* not ready */ }

    const meta = `
      <div class="result-head">
        <code>${esc(doc.id)}</code>
        ${badge(doc.status, doc.status === "failed" ? "bad" : "ok")}
        <span class="hint">${esc(doc.filename || "—")} · ${esc(doc.doc_format)}
          · ${(doc.size_bytes / 1024).toFixed(0)} KB</span>
      </div>
      ${doc.error ? `<div class="err">${esc(doc.error)}</div>` : ""}`;

    if (!extraction) {
      detail.innerHTML = meta + traceBlock(trace.trace);
      return;
    }

    const e = extraction.extraction;
    detail.innerHTML = meta + `
      <h3 class="sub">Result</h3>
      <dl class="fields">
        <dt>review</dt><dd>${badge(extraction.review_status.replace("_", " "),
                                   REVIEW_KIND[extraction.review_status])}</dd>
        <dt>vendor</dt><dd>${esc(e.vendor || "—")}</dd>
        <dt>invoice #</dt><dd>${esc(e.invoice_number || "—")}</dd>
        <dt>date</dt><dd>${esc(e.date || "—")}</dd>
        <dt>total</dt><dd>${esc(money(e.total, e.currency))}</dd>
        <dt>items</dt><dd>${(e.items || []).length}</dd>
      </dl>
      <h3 class="sub">Validation</h3>
      ${renderFindings(extraction.findings)}
      ${traceBlock(trace.trace)}`;
  } catch (err) {
    detail.innerHTML = `<div class="err">${esc(err.message)}</div>`;
  }
}

/* ---------- wiring ---------- */

$("refresh").addEventListener("click", () => { refreshDocuments(); refreshMetrics(); });

refreshDocuments();
refreshMetrics();
