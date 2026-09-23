"use strict";

const $ = (id) => document.getElementById(id);
const EXPECTED_MS = 4000;

let pollTimer = null;
let selectedDoc = null;

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
  const data = await res.json().catch(() => ({ detail: "invalid server response" }));
  if (!res.ok && res.status !== 422) throw new Error(data.detail || `HTTP ${res.status}`);
  return data;
}

/* ---------- asking ---------- */

async function ask() {
  const question = $("question").value.trim();
  if (!question) return;

  $("ask").disabled = true;
  $("answer").classList.add("hidden");

  const box = $("job-status");
  const started = Date.now();
  box.classList.remove("hidden");

  // Shell built once; only the clock updates on a timer. Rewriting innerHTML
  // every tick restarts the spinner's CSS animation so it never completes a
  // rotation, and re-creates every row underneath it.
  box.innerHTML = `
    <div class="job-head">
      <div class="spinner"></div>
      <div class="bar"><div id="job-bar"></div></div>
      <span class="hint" id="job-label"></span>
    </div>`;
  const bar = $("job-bar");
  const labelEl = $("job-label");

  const tick = () => {
    const elapsed = ((Date.now() - started) / 1000).toFixed(1);
    bar.style.width = `${Math.min(95, ((Date.now() - started) / EXPECTED_MS) * 100)}%`;
    labelEl.textContent = `searching documents · ${elapsed}s`;
  };
  tick();
  const ticker = setInterval(tick, 200);

  try {
    const result = await api("/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    let trace = [];
    if (result.trace_id) {
      trace = (await api(`/traces/${result.trace_id}`).catch(() => ({ trace: [] }))).trace || [];
    }
    showAnswer(result, trace);
    refreshMetrics();
  } catch (err) {
    $("answer").classList.remove("hidden");
    $("answer").innerHTML = `<div class="err">${esc(err.message)}</div>`;
  } finally {
    clearInterval(ticker);
    box.classList.add("hidden");
    $("ask").disabled = false;
  }
}

/* ---------- answer rendering ---------- */

function renderCitations(citations) {
  if (!citations || !citations.length) {
    return `<span class="hint">No citations — this answer cannot be traced to a source.</span>`;
  }
  return `<ul class="rules">${citations.map((c) => `
    <li>
      <code>[${c.marker}]</code>
      <span><b>${esc(c.filename || c.document_id)}</b>${c.heading ? " — " + esc(c.heading) : ""}
        <div class="tdetail">${esc(c.snippet)}</div>
      </span>
    </li>`).join("")}</ul>`;
}

function renderPassages(retrieval) {
  if (!retrieval || !retrieval.chunks || !retrieval.chunks.length) {
    const cov = retrieval ? Math.round((retrieval.best_coverage || 0) * 100) : 0;
    return `<span class="hint">No passage passed the relevance gate (best term coverage ${cov}%).</span>`;
  }
  return `<ul class="rules">${retrieval.chunks.map((c, i) => `
    <li>
      <code>[${i + 1}]</code>
      <span><b>${esc(c.filename || c.document_id)}</b>${c.heading ? " — " + esc(c.heading) : ""}
        ${(c.found_by || []).map((f) => badge(f, f === "vector" ? "ok" : "medium")).join("")}
        <span class="tsecs">score ${c.score}</span>
        <div class="tdetail">${esc((c.text || "").slice(0, 400))}</div>
      </span>
    </li>`).join("")}</ul>`;
}

// Turn [1] markers into clickable superscripts linked to the citation list.
function linkCitations(text) {
  return esc(text).replace(/\[(\d+(?:\s*,\s*\d+)*)\]/g,
    (m, nums) => `<sup class="cite">[${esc(nums)}]</sup>`);
}

function showAnswer(result, trace) {
  const box = $("answer");
  box.classList.remove("hidden");

  const status = result.refused
    ? badge("no answer found", "medium")
    : result.grounded
      ? badge("grounded", "ok")
      : badge("unverified", "bad");

  const warnings = (result.warnings || [])
    .map((w) => `<div class="warn">${esc(w)}</div>`)
    .join("");

  box.innerHTML = `
    <div class="result-head">
      ${status}
      <code>${(result.latency_ms / 1000).toFixed(1)}s</code>
      ${result.citations && result.citations.length
        ? `<code>${result.citations.length} citation(s)</code>` : ""}
    </div>
    ${warnings}
    <div class="draft answer-text">${linkCitations(result.answer)}</div>
    <h3 class="sub">Sources</h3>
    ${renderCitations(result.citations)}
    <h3 class="sub">Retrieved passages <span class="hint">what the model was shown</span></h3>
    ${renderPassages(result.retrieval)}
    ${traceBlock(trace)}`;
}

/* ---------- trace ---------- */

const PHASE_META = {
  parse:    { icon: "1", name: "Parsing" },
  chunk:    { icon: "2", name: "Chunking" },
  embed:    { icon: "3", name: "Embedding" },
  retrieve: { icon: "4", name: "Retrieval" },
  llm:      { icon: "AI", name: "Model call" },
  answer:   { icon: "5", name: "Answer" },
  store:    { icon: "6", name: "Stored" },
};

function renderTrace(events) {
  if (!events || !events.length) return "";
  return `<div class="trace">${events.map((e) => {
    const meta = PHASE_META[e.phase] || { icon: "•", name: e.phase };
    const secs = (e.elapsed_ms / 1000).toFixed(1);
    const exchange = (e.prompt || e.response) ? `
      <details class="exchange">
        <summary>${e.phase === "llm" ? "view prompt &amp; response" : "view detail"}</summary>
        ${e.prompt ? `<div class="xlabel">sent →</div><pre class="xbody">${esc(e.prompt)}</pre>` : ""}
        ${e.response ? `<div class="xlabel">${e.phase === "llm" ? "← received" : "content"}</div>
          <pre class="xbody resp">${esc(e.response)}</pre>` : ""}
      </details>` : "";
    return `
      <div class="tstep ${esc(e.status)} ${esc(e.phase)}">
        <span class="tphase" title="${esc(meta.name)}">${esc(meta.icon)}</span>
        <div class="tbody">
          <div class="tlabel">${esc(e.label)}<span class="tsecs">${secs}s</span></div>
          ${e.detail ? `<div class="tdetail">${esc(e.detail)}</div>` : ""}
          ${exchange}
        </div>
      </div>`;
  }).join("")}</div>`;
}

function traceBlock(events) {
  if (!events || !events.length) return "";
  return `<details class="trace-wrap">
    <summary>Execution trace <span class="hint">${events.length} steps</span></summary>
    ${renderTrace(events)}
  </details>`;
}

/* ---------- uploading ---------- */

async function uploadFiles(files) {
  const zone = $("dropzone");
  const original = zone.innerHTML;

  for (const file of files) {
    zone.innerHTML = `<div class="dz-main">Indexing ${esc(file.name)}…</div>`;
    const form = new FormData();
    form.append("file", file);
    try {
      const result = await api("/documents", { method: "POST", body: form });
      if (!result.ok) {
        zone.innerHTML = `<div class="dz-main err">${esc(file.name)}: ${esc(result.error || "failed")}</div>`;
        await new Promise((r) => setTimeout(r, 2200));
      }
    } catch (err) {
      zone.innerHTML = `<div class="dz-main err">${esc(err.message)}</div>`;
      await new Promise((r) => setTimeout(r, 2200));
    }
  }

  zone.innerHTML = original;
  wireDropzone();
  refreshDocuments();
  refreshMetrics();
}

function wireDropzone() {
  const zone = $("dropzone");
  const input = $("file-input");
  zone.onclick = () => input.click();
  input.onchange = (e) => e.target.files.length && uploadFiles([...e.target.files]);

  ["dragenter", "dragover"].forEach((evt) =>
    zone.addEventListener(evt, (e) => { e.preventDefault(); zone.classList.add("over"); })
  );
  ["dragleave", "drop"].forEach((evt) =>
    zone.addEventListener(evt, (e) => { e.preventDefault(); zone.classList.remove("over"); })
  );
  zone.addEventListener("drop", (e) => {
    if (e.dataTransfer.files.length) uploadFiles([...e.dataTransfer.files]);
  });
}

$("load-corpus").addEventListener("click", async () => {
  const button = $("load-corpus");
  button.disabled = true;
  button.textContent = "Loading…";
  try {
    const { files } = await api("/api/corpus");
    const loaded = [];
    for (const name of files) {
      const res = await fetch(`/api/corpus/${encodeURIComponent(name)}`);
      const blob = await res.blob();
      loaded.push(new File([blob], name, { type: "text/plain" }));
    }
    await uploadFiles(loaded);
  } catch (err) {
    console.error(err);
  } finally {
    button.disabled = false;
    button.textContent = "Load samples";
  }
});

/* ---------- documents ---------- */

async function refreshDocuments() {
  let data;
  try { data = await api("/documents"); } catch { return; }

  $("kb-summary").textContent =
    `${data.documents.length} document(s) · ${data.total_chunks} chunks`;

  const note = $("embedder-note");
  if (data.embedder) {
    note.innerHTML = data.embedder.semantic
      ? `Embeddings: <b>${esc(data.embedder.backend)}</b> (${data.embedder.dims}d, semantic).
         Retrieval fuses vector similarity with BM25 keyword scoring.`
      : `Embeddings: <b>${esc(data.embedder.backend)}</b> (${data.embedder.dims}d, <b>lexical only</b>)
         — the model backend does not expose an embeddings endpoint, so synonyms
         will not match. Retrieval leans on BM25 and a term-coverage gate.`;
  }

  const body = $("docs-body");
  if (!data.documents.length) {
    body.innerHTML = `<tr><td colspan="5" class="empty">No documents indexed yet.</td></tr>`;
    return;
  }

  body.innerHTML = data.documents.map((d) => `
    <tr data-id="${esc(d.id)}" class="${d.id === selectedDoc ? "selected" : ""}">
      <td class="issue" title="${esc(d.filename)}">${esc(d.filename || d.id)}</td>
      <td>${esc(d.doc_format || "—")}${d.ocr ? " " + badge("ocr", "medium") : ""}</td>
      <td>${d.chunk_count}</td>
      <td>${d.status === "indexed"
            ? badge("indexed", "ok")
            : badge(d.status, d.status === "failed" ? "bad" : "neutral")}</td>
      <td><button class="ghost small delete" data-id="${esc(d.id)}">remove</button></td>
    </tr>`).join("");

  body.querySelectorAll("tr[data-id]").forEach((tr) =>
    tr.addEventListener("click", (e) => {
      if (e.target.classList.contains("delete")) return;
      loadChunks(tr.dataset.id);
    })
  );
  body.querySelectorAll("button.delete").forEach((b) =>
    b.addEventListener("click", async (e) => {
      e.stopPropagation();
      await api(`/documents/${b.dataset.id}`, { method: "DELETE" }).catch(() => {});
      refreshDocuments();
      refreshMetrics();
    })
  );
}

async function loadChunks(documentId) {
  selectedDoc = documentId;
  document.querySelectorAll("#docs-body tr").forEach((tr) =>
    tr.classList.toggle("selected", tr.dataset.id === documentId)
  );

  try {
    const [doc, data] = await Promise.all([
      api(`/documents/${documentId}`),
      api(`/documents/${documentId}/chunks`),
    ]);
    $("detail").innerHTML = `
      <div class="result-head">
        <code>${esc(doc.id)}</code>
        <span class="hint">${esc(doc.filename)} · ${data.count} chunks</span>
      </div>
      ${doc.error ? `<div class="err">${esc(doc.error)}</div>` : ""}
      <h3 class="sub">Chunks <span class="hint">what retrieval searches over</span></h3>
      <ul class="rules">${data.chunks.map((c) => `
        <li>
          <code>#${c.chunk_index}</code>
          <span>${c.heading ? `<b>${esc(c.heading)}</b>` : "<i>no heading</i>"}
            <span class="tsecs">${c.token_count} tokens</span>
            <div class="tdetail">${esc(c.text.slice(0, 400))}</div>
          </span>
        </li>`).join("")}</ul>`;
  } catch (err) {
    $("detail").innerHTML = `<div class="err">${esc(err.message)}</div>`;
  }
}

/* ---------- metrics ---------- */

async function refreshMetrics() {
  let data;
  try { data = await api("/metrics"); } catch { return; }
  const m = data.metrics;
  $("model-info").textContent = `${data.model} · ${data.api_base}`;

  const cards = [
    ["documents", m.documents],
    ["chunks", m.chunks],
    ["questions", m.calls],
    ["avg latency", `${(m.avg_latency_ms / 1000).toFixed(1)}s`],
    ["tokens in", m.prompt_tokens],
    ["tokens out", m.completion_tokens],
  ];
  $("metrics").innerHTML = cards
    .map(([k, v]) =>
      `<div class="metric"><div class="label">${k}</div><div class="value">${esc(v)}</div></div>`)
    .join("");
}

/* ---------- wiring ---------- */

$("ask").addEventListener("click", ask);
$("question").addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") ask();
});
document.querySelectorAll(".chip").forEach((chip) =>
  chip.addEventListener("click", () => {
    $("question").value = chip.dataset.q;
    ask();
  })
);

wireDropzone();
refreshDocuments();
refreshMetrics();
